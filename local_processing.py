"""Local, lossless GeoTIFF compression helpers using the GDAL CLI."""
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
        if value:
            root = Path(value)
            candidates.extend([root / "bin", root / "apps" / "gdal" / "bin"])
            if env_name == "QGIS_PREFIX_PATH":
                candidates.extend([root.parent / "bin", root.parent / "apps" / "gdal" / "bin"])
    for root in (Path(r"C:\\OSGeo4W"), Path(r"C:\\OSGeo4W64")):
        candidates.extend([root / "bin", root / "apps" / "gdal" / "bin"])
    for base in (Path(r"C:\\Program Files"), Path(r"C:\\Program Files (x86)")):
        try:
            for qgis in base.glob("QGIS*"):
                candidates.extend([qgis / "bin", qgis / "apps" / "gdal" / "bin"])
        except OSError:
            pass
    return candidates

def find_gdal_tools() -> tuple[str | None, str | None]:
    """Find GDAL CLI tools via PATH or common Windows QGIS/OSGeo4W install paths."""
    info = shutil.which("gdalinfo") or shutil.which("gdalinfo.exe")
    translate = shutil.which("gdal_translate") or shutil.which("gdal_translate.exe")
    if info and translate:
        return info, translate
    for directory in _candidate_gdal_dirs():
        info_candidate = directory / "gdalinfo.exe"
        translate_candidate = directory / "gdal_translate.exe"
        if info_candidate.is_file() and translate_candidate.is_file():
            return str(info_candidate), str(translate_candidate)
    return info, translate

def _run(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(args, check=True, capture_output=True, text=True, encoding="utf-8", errors="replace")

def read_raster_info(gdalinfo_path: str, raster_path: str, checksums: bool = False) -> dict[str, Any]:
    args = [gdalinfo_path, "-json"]
    if checksums:
        args.append("-checksum")
    args.append(raster_path)
    result = _run(args)
    info = json.loads(result.stdout)
    if not isinstance(info, dict) or not info.get("size") or not info.get("bands"):
        raise ValueError("GDAL did not return raster dimensions and bands for this file.")
    return info

def _image_structure(info: dict[str, Any]) -> dict[str, Any]:
    return ((info.get("metadata") or {}).get("IMAGE_STRUCTURE") or {})

def compression_command(gdal_translate_path: str, source: str, output: str) -> list[str]:
    """Build a lossless COG command. Output path must not exist before running."""
    return [
        gdal_translate_path, "-of", "COG",
        "-co", "COMPRESS=ZSTD", "-co", "LEVEL=12",
        "-co", "PREDICTOR=YES", "-co", "BLOCKSIZE=512",
        "-co", "OVERVIEW_RESAMPLING=AVERAGE", "-co", "BIGTIFF=YES",
        "-co", "NUM_THREADS=ALL_CPUS", source, output,
    ]

def _compare_raster_structure(source_info: dict[str, Any], output_info: dict[str, Any]) -> list[str]:
    issues: list[str] = []
    for key, label in (("size", "dimensions"), ("geoTransform", "geotransform")):
        if source_info.get(key) != output_info.get(key):
            issues.append(f"Full-resolution {label} changed.")
    source_bands, output_bands = source_info.get("bands") or [], output_info.get("bands") or []
    if len(source_bands) != len(output_bands):
        issues.append("Band count changed.")
    else:
        for index, (src, out) in enumerate(zip(source_bands, output_bands), 1):
            for key, label in (("type", "data type"), ("colorInterpretation", "color interpretation"), ("noDataValue", "NoData value")):
                if src.get(key) != out.get(key):
                    issues.append(f"Band {index} {label} changed.")
    source_crs, output_crs = source_info.get("coordinateSystem") or {}, output_info.get("coordinateSystem") or {}
    if source_crs.get("id") != output_crs.get("id") and source_crs.get("wkt") != output_crs.get("wkt"):
        issues.append("Coordinate reference system changed or could not be matched.")
    layout = str(_image_structure(output_info).get("LAYOUT", "")).upper()
    if layout != "COG":
        issues.append("GDAL did not report the output as COG (LAYOUT=COG).")
    compression = str(_image_structure(output_info).get("COMPRESSION", "")).upper()
    if compression != "ZSTD":
        issues.append(f"Output compression is {compression or 'unknown'}, not ZSTD.")
    return issues

def process_lossless_cog(gdalinfo_path: str, gdal_translate_path: str, source_path: str, output_path: str, verify_checksums: bool = True) -> dict[str, Any]:
    source, output = Path(source_path), Path(output_path)
    if not source.is_file():
        raise ValueError("The source file does not exist or is not a file.")
    if source.resolve() == output.resolve():
        raise ValueError("Choose a different output path; the original must never be overwritten.")
    if output.exists():
        raise ValueError("Output already exists. Choose a new output filename; nothing was overwritten.")
    if source.suffix.lower() not in {".tif", ".tiff"}:
        raise ValueError("Choose a stitched orthomosaic GeoTIFF (.tif or .tiff).")
    source_info = read_raster_info(gdalinfo_path, str(source), checksums=verify_checksums)
    if not (source_info.get("coordinateSystem") or source_info.get("geoTransform")):
        raise ValueError("Source has no reported georeferencing. Stop; compression cannot fix this.")
    command = compression_command(gdal_translate_path, str(source), str(output))
    _run(command)
    output_info = read_raster_info(gdalinfo_path, str(output), checksums=verify_checksums)
    issues = _compare_raster_structure(source_info, output_info)
    if verify_checksums:
        src_bands, out_bands = source_info.get("bands") or [], output_info.get("bands") or []
        if len(src_bands) != len(out_bands) or any(a.get("checksum") != b.get("checksum") for a, b in zip(src_bands, out_bands)):
            issues.append("Full-resolution band checksums differ; pixel values were not verified as identical.")
    source_size, output_size = source.stat().st_size, output.stat().st_size
    reduction = (1 - output_size / source_size) * 100 if source_size else 0.0
    return {
        "source_path": str(source), "output_path": str(output),
        "source_size_bytes": source_size, "output_size_bytes": output_size,
        "reduction_percent": reduction, "under_upload_limit": output_size <= OAM_UPLOAD_LIMIT_BYTES,
        "source_info": source_info, "output_info": output_info,
        "verification_issues": issues,
        "checksums_verified": verify_checksums and not any("checksum" in issue.lower() for issue in issues),
        "command": command,
    }
