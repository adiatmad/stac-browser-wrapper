"""Local lossless GeoTIFF compression helpers using the GDAL CLI."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any

OAM_UPLOAD_LIMIT_BYTES = 100 * 1024**3


def _candidate_gdal_dirs() -> list[Path]:
    candidates: list[Path] = []
    for env_name in ("OSGEO4W_ROOT", "QGIS_PREFIX_PATH"):
        value = os.environ.get(env_name)
        if not value:
            continue
        root = Path(value)
        candidates.extend([root / "bin", root / "apps" / "gdal" / "bin"])
        if env_name == "QGIS_PREFIX_PATH":
            candidates.extend([root.parent / "bin", root.parent / "apps" / "gdal" / "bin"])
    for root in (Path("C:/OSGeo4W"), Path("C:/OSGeo4W64")):
        candidates.extend([root / "bin", root / "apps" / "gdal" / "bin"])
    for base in (Path("C:/Program Files"), Path("C:/Program Files (x86)")):
        try:
            for qgis in base.glob("QGIS*"):
                candidates.extend([qgis / "bin", qgis / "apps" / "gdal" / "bin"])
        except OSError:
            pass
    return candidates


def find_gdal_tools() -> tuple[str | None, str | None]:
    """Find GDAL CLI tools on PATH or in common Windows QGIS/OSGeo4W locations."""
    info = shutil.which("gdalinfo") or shutil.which("gdalinfo.exe")
    translate = shutil.which("gdal_translate") or shutil.which("gdal_translate.exe")
    if info and translate:
        return info, translate
    for directory in _candidate_gdal_dirs():
        info_path, translate_path = directory / "gdalinfo.exe", directory / "gdal_translate.exe"
        if info_path.is_file() and translate_path.is_file():
            return str(info_path), str(translate_path)
    return info, translate


def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace"
        )
    except subprocess.CalledProcessError as exc:
        diagnostic = (exc.stderr or exc.stdout or "").strip()
        raise RuntimeError(diagnostic or f"GDAL command failed (exit code {exc.returncode}).") from exc


def read_raster_info(gdalinfo_path: str, raster_path: str, checksums: bool = False) -> dict[str, Any]:
    args = [gdalinfo_path, "-json"]
    if checksums:
        args.append("-checksum")
    args.append(raster_path)
    info = json.loads(_run(args).stdout)
    if not isinstance(info, dict) or not info.get("size") or not info.get("bands"):
        raise ValueError("GDAL did not return raster dimensions and bands for this file.")
    return info


def _image_structure(info: dict[str, Any]) -> dict[str, Any]:
    return ((info.get("metadata") or {}).get("IMAGE_STRUCTURE") or {})


def compression_command(
    gdal_translate_path: str, source: str, output: str, predictor: int = 2
) -> list[str]:
    """Create a tiled, lossless ZSTD GeoTIFF; OAM creates the serving COG."""
    return [
        gdal_translate_path, "-of", "GTiff",
        "-co", "TILED=YES", "-co", "BLOCKXSIZE=512", "-co", "BLOCKYSIZE=512",
        "-co", "COMPRESS=ZSTD", "-co", "ZSTD_LEVEL=12", "-co", f"PREDICTOR={predictor}",
        "-co", "BIGTIFF=YES", "-co", "NUM_THREADS=ALL_CPUS", source, output,
    ]



def _has_valid_georeferencing(info: dict[str, Any]) -> bool:
    """Check GeoTIFF driver, positive raster dimensions, CRS, and a nonsingular affine transform."""
    if info.get("driverShortName") != "GTiff":
        return False
    size = info.get("size") or []
    if len(size) != 2 or any(int(value) <= 0 for value in size):
        return False
    crs = info.get("coordinateSystem") or {}
    if not (crs.get("id") or crs.get("wkt") or crs.get("projjson")):
        return False
    transform = info.get("geoTransform") or []
    if len(transform) != 6:
        return False
    try:
        determinant = float(transform[1]) * float(transform[5]) - float(transform[2]) * float(transform[4])
    except (TypeError, ValueError):
        return False
    return determinant != 0


def _compare_raster_structure(source: dict[str, Any], output: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, label in (("size", "dimensions"), ("geoTransform", "geotransform")):
        if source.get(key) != output.get(key):
            issues.append(f"Full-resolution {label} changed.")

    source_bands, output_bands = source.get("bands") or [], output.get("bands") or []
    if len(source_bands) != len(output_bands):
        issues.append("Band count changed.")
    else:
        for index, (src, out) in enumerate(zip(source_bands, output_bands), 1):
            for key, label in (
                ("type", "data type"), ("colorInterpretation", "color interpretation"),
                ("noDataValue", "NoData value"),
            ):
                if src.get(key) != out.get(key):
                    issues.append(f"Band {index} {label} changed.")

    source_crs, output_crs = source.get("coordinateSystem") or {}, output.get("coordinateSystem") or {}
    if source_crs.get("id") != output_crs.get("id") and source_crs.get("wkt") != output_crs.get("wkt"):
        issues.append("Coordinate reference system changed or could not be matched.")
    if output.get("driverShortName") != "GTiff":
        issues.append("Output is not a GeoTIFF.")
    if str(_image_structure(output).get("COMPRESSION", "")).upper() != "ZSTD":
        issues.append("Output compression is not ZSTD.")
    if not output_bands or not all(
        len(band.get("block", [])) >= 2 and min(band["block"][:2]) >= 16
        for band in output_bands
    ):
        issues.append("Output tiling could not be verified.")
    return issues



def inspect_geotiff(
    gdalinfo_path: str,
    gdal_translate_path: str,
    source_path: str,
    output_path: str,
) -> dict[str, Any]:
    """Inspect a local GeoTIFF and prepare (but do not run) its lossless command."""
    source, output = Path(source_path), Path(output_path)
    if not source.is_file():
        raise ValueError("The source file does not exist or is not a file.")
    if source.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("Choose a GeoTIFF (.tif or .tiff).")
    if source.resolve() == output.resolve():
        raise ValueError("Choose a different output path; the original must never be overwritten.")
    if output.exists():
        raise ValueError("Output already exists. Choose a new filename; nothing was overwritten.")
    if output.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("The output must use a .tif or .tiff filename.")
    if not output.parent.is_dir():
        raise ValueError("The output folder does not exist. Choose an existing folder.")

    info = read_raster_info(gdalinfo_path, str(source))
    ready = _has_valid_georeferencing(info)
    bands = info.get("bands") or []
    dtype = str(bands[0].get("type", "")).lower() if bands else ""
    predictor = 3 if dtype.startswith(("float", "complex")) else 2
    return {
        "source_path": str(source),
        "output_path": str(output),
        "source_size_bytes": source.stat().st_size,
        "under_upload_limit": source.stat().st_size <= OAM_UPLOAD_LIMIT_BYTES,
        "info": info,
        "ready": ready,
        "reason": "" if ready else (
            "Basic preflight failed: source must be a readable GeoTIFF with positive dimensions, "
            "a CRS and a valid affine geotransform. Correct it in QGIS before processing."
        ),
        "inspect_command": f'"{gdalinfo_path}" -json "{source}"',
        "compression_command": compression_command(
            gdal_translate_path, str(source), str(output), predictor
        ),
    }


def process_lossless_geotiff(
    gdalinfo_path: str,
    gdal_translate_path: str,
    source_path: str,
    output_path: str,
    verify_checksums: bool = False,
) -> dict[str, Any]:
    source, output = Path(source_path), Path(output_path)
    if not source.is_file():
        raise ValueError("The source file does not exist or is not a file.")
    if source.resolve() == output.resolve():
        raise ValueError("Choose a different output path; the original must never be overwritten.")
    if output.exists():
        raise ValueError("Output already exists. Choose a new output filename; nothing was overwritten.")
    if source.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("Choose a stitched orthomosaic GeoTIFF (.tif or .tiff).")
    if output.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("The compressed output must use a .tif or .tiff filename.")
    if not output.parent.is_dir():
        raise ValueError("The output folder does not exist. Choose an existing folder.")

    source_info = read_raster_info(gdalinfo_path, str(source), checksums=verify_checksums)
    if not _has_valid_georeferencing(source_info):
        raise ValueError("Source must be a GeoTIFF with positive dimensions, a CRS, and a valid affine transform. Correct it in QGIS first.")

    bands = source_info.get("bands") or []
    dtype = str(bands[0].get("type", "")).lower()
    predictor = 3 if dtype.startswith(("float", "complex")) else 2
    command = compression_command(gdal_translate_path, str(source), str(output), predictor)

    try:
        _run(command)
        output_info = read_raster_info(gdalinfo_path, str(output), checksums=verify_checksums)
        issues = _compare_raster_structure(source_info, output_info)
        if verify_checksums:
            source_bands, compressed_bands = source_info.get("bands") or [], output_info.get("bands") or []
            if len(source_bands) != len(compressed_bands) or any(
                src.get("checksum") != out.get("checksum")
                for src, out in zip(source_bands, compressed_bands)
            ):
                issues.append("Band checksums differ; pixel equality was not confirmed.")
    except Exception:
        if output.exists():
            output.unlink()
        raise

    source_size, output_size = source.stat().st_size, output.stat().st_size
    return {
        "source_path": str(source), "output_path": str(output),
        "source_size_bytes": source_size, "output_size_bytes": output_size,
        "reduction_percent": (1 - output_size / source_size) * 100 if source_size else 0,
        "under_upload_limit": output_size <= OAM_UPLOAD_LIMIT_BYTES,
        "source_info": source_info, "output_info": output_info,
        "verification_issues": issues,
        "checksums_verified": verify_checksums and not any("checksum" in issue.lower() for issue in issues),
        "command": command,
    }



def _powershell_quote(value: str) -> str:
    """Quote one argument for a PowerShell command line."""
    return "'" + str(value).replace("'", "''") + "'"


def build_gdal_commands(
    gdal_translate_path: str,
    source_path: str,
    output_path: str,
    gdalinfo_json: str,
) -> dict[str, str]:
    """Validate pasted gdalinfo JSON and return a copy/paste PowerShell command."""
    source, output = Path(source_path), Path(output_path)
    if source.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("Source path must end in .tif or .tiff.")
    if output.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("Output path must end in .tif or .tiff.")
    if str(source).casefold() == str(output).casefold():
        raise ValueError("Output path must be different from the source; the original must never be overwritten.")
    try:
        info = json.loads(gdalinfo_json)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Paste the complete, valid JSON output from gdalinfo -json (line {exc.lineno}, column {exc.colno}).") from exc
    if not isinstance(info, dict):
        raise ValueError("The pasted gdalinfo JSON must be a JSON object.")
    if not _has_valid_georeferencing(info):
        raise ValueError(
            "Basic preflight failed. Expected a GTiff with positive dimensions, a CRS, "
            "and a valid affine geotransform. Check the source in QGIS."
        )
    bands = info.get("bands") or []
    dtype = str(bands[0].get("type", "")).lower()
    predictor = 3 if dtype.startswith(("float", "complex")) else 2
    args = compression_command(gdal_translate_path, str(source), str(output), predictor)
    command = (
        f"if (Test-Path -LiteralPath {_powershell_quote(str(output))}) "
        "{ throw 'Output already exists; choose a new output filename.' }; "
        + "& " + " ".join(_powershell_quote(arg) for arg in args)
    )
    return {
        "source_path": str(source),
        "output_path": str(output),
        "predictor": str(predictor),
        "translate_command": command,
    }
