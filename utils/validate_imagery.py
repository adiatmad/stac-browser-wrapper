"""Local GDAL report parsing and OAM imagery preflight checks.

This module deliberately does not import osgeo.gdal. The Streamlit app runs on a
server, while the user's imagery should remain local. Users run GDAL locally,
paste the compact JSON report here, and the app evaluates it.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    name: str
    status: str  # PASS, WARNING, FAIL, INFO
    detail: str
    fix: str = ""


@dataclass
class ValidationReport:
    source: dict[str, Any]
    checks: list[CheckResult] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return any(c.status == "FAIL" for c in self.checks)

    @property
    def warnings(self) -> bool:
        return any(c.status == "WARNING" for c in self.checks)


def _first_band(report: dict[str, Any]) -> dict[str, Any]:
    bands = report.get("bands") or []
    return bands[0] if bands else {}


def _band_types(report: dict[str, Any]) -> list[str]:
    return [str(b.get("type", "")).upper() for b in report.get("bands") or []]


def _metadata_layout(report: dict[str, Any]) -> str:
    metadata = report.get("metadata") or {}
    image_structure = metadata.get("IMAGE_STRUCTURE") or {}
    return str(image_structure.get("LAYOUT", "")).upper()


def _is_tiled(report: dict[str, Any]) -> bool | None:
    band = _first_band(report)
    block = band.get("block")
    size = report.get("size") or []
    if not isinstance(block, list) or len(block) != 2:
        return None
    if not isinstance(size, list) or len(size) != 2:
        return None
    return block[0] < size[0] or block[1] < size[1]


def _has_overviews(report: dict[str, Any]) -> bool:
    return any(bool(band.get("overviews")) for band in report.get("bands") or [])


def _bounds(report: dict[str, Any]) -> list[float] | None:
    extent = report.get("wgs84Extent") or {}
    geometry = extent.get("coordinates") if isinstance(extent, dict) else None
    if geometry:
        try:
            rings = geometry[0] if geometry and isinstance(geometry[0], list) else geometry
            points = [point for point in rings if isinstance(point, (list, tuple)) and len(point) >= 2]
            xs = [float(point[0]) for point in points]
            ys = [float(point[1]) for point in points]
            if points:
                return [min(xs), min(ys), max(xs), max(ys)]
        except (TypeError, ValueError, IndexError):
            pass

    corners = report.get("cornerCoordinates") or {}
    try:
        points = [corners[k] for k in ("upperLeft", "upperRight", "lowerRight", "lowerLeft") if k in corners]
        xs = [float(p[0]) for p in points]
        ys = [float(p[1]) for p in points]
        return [min(xs), min(ys), max(xs), max(ys)]
    except (TypeError, ValueError, IndexError):
        return None


def parse_report(text: str) -> dict[str, Any]:
    try:
        value = json.loads(text.strip())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON: {exc}") from exc
    if not isinstance(value, dict):
        raise ValueError("The GDAL report must be a JSON object.")
    return value


def validate_report(report: dict[str, Any]) -> ValidationReport:
    """Evaluate a GDAL JSON report for an OAM visual RGB/RGBA upload."""
    checks: list[CheckResult] = []
    driver = str(report.get("driverShortName") or report.get("driver", "")).upper()
    filename = str(report.get("filename", ""))
    bands = report.get("bands") or []
    types = _band_types(report)
    crs = report.get("coordinateSystem")
    size = report.get("size") or []
    layout = _metadata_layout(report)
    tiled = _is_tiled(report)
    overviews = _has_overviews(report)
    bounds = _bounds(report)

    checks.append(CheckResult(
        "GeoTIFF input",
        "PASS" if driver in {"GTIFF", "COG"} else "WARNING",
        f"Driver: {driver or 'unknown'}; file: {filename or 'not reported'}.",
        "The final command will convert the source to GeoTIFF/COG." if driver not in {"GTIFF", "COG"} else "",
    ))

    has_crs = bool(crs and (crs.get("wkt") or crs.get("projjson") or crs.get("authority"))) if isinstance(crs, dict) else bool(crs)
    checks.append(CheckResult(
        "Coordinate reference system",
        "PASS" if has_crs else "FAIL",
        "A CRS is present." if has_crs else "No CRS was reported.",
        "Select the true source CRS (EPSG code) before generating the final command." if not has_crs else "",
    ))

    valid_size = len(size) == 2 and all(isinstance(v, (int, float)) and v > 0 for v in size)
    checks.append(CheckResult(
        "Raster dimensions",
        "PASS" if valid_size else "FAIL",
        f"Size: {size[0]} x {size[1]}." if valid_size else "Raster dimensions are missing or invalid.",
    ))

    visual_shape = len(bands) in (3, 4)
    byte_bands = all(t == "BYTE" for t in types) if types else False
    rgb_interpretations = [str(b.get("colorInterpretation", "")).upper() for b in bands]
    rgb_like = rgb_interpretations[:3] == ["RED", "GREEN", "BLUE"] or not any(rgb_interpretations)
    visual_ok = visual_shape and byte_bands and rgb_like
    if visual_ok:
        detail = f"{len(bands)} bands; Byte data type; RGB/RGBA-compatible interpretation."
        status = "PASS"
        fix = ""
    elif len(bands) not in (3, 4):
        detail = f"Found {len(bands)} bands; this preflight targets 3 RGB or 4 RGBA visual bands."
        status = "FAIL"
        fix = "Inspect the source and select/export the visual RGB(A) bands."
    elif types and not byte_bands:
        detail = f"Band types: {', '.join(types)}. Visual OAM imagery should be Byte/8-bit."
        status = "FAIL"
        fix = "Convert the visual imagery deliberately to Byte RGB(A); do not silently change non-visual products."
    else:
        detail = "Band layout needs manual review for visual RGB(A) use."
        status = "WARNING"
        fix = "Confirm the first three bands are Red, Green, Blue."
    checks.append(CheckResult("Visual RGB/RGBA bands", status, detail, fix))

    if layout == "COG":
        cog_status = "PASS"
        cog_detail = "GDAL reports IMAGE_STRUCTURE LAYOUT=COG."
    else:
        cog_status = "WARNING"
        cog_detail = "The report does not identify the file as a COG. This is informational: current OAM ingestion can convert valid GeoTIFF input to COG."
    checks.append(CheckResult("COG layout", cog_status, cog_detail, ""))

    if tiled is True:
        tile_status = "PASS"
        tile_detail = f"Internal block size reported as {_first_band(report).get('block')}."
    elif tiled is False:
        tile_status = "WARNING"
        tile_detail = "The first band appears to use a full-width/full-height block rather than tiled blocks."
    else:
        tile_status = "WARNING"
        tile_detail = "Block layout was not reported; tiling cannot be confirmed."
    checks.append(CheckResult("Internal tiling", tile_status, tile_detail))

    checks.append(CheckResult(
        "Overviews",
        "PASS" if overviews else "WARNING",
        "Overviews are reported by GDAL." if overviews else "No overviews are reported.",
        "The final COG conversion will build the required internal pyramid." if not overviews else "",
    ))

    if bounds is None:
        checks.append(CheckResult("Georeferenced bounds", "FAIL", "No usable corner/extent coordinates were reported."))
    else:
        finite = all(abs(v) != float("inf") and v == v for v in bounds)
        nonzero_extent = bounds[0] != bounds[2] and bounds[1] != bounds[3]
        checks.append(CheckResult(
            "Georeferenced bounds",
            "PASS" if finite and nonzero_extent else "FAIL",
            f"Bounds: {bounds}." if finite and nonzero_extent else f"Invalid or zero-area bounds: {bounds}.",
            "Reproject/georeference the raster with a known CRS before upload." if not (finite and nonzero_extent) else "",
        ))

    return ValidationReport(source=report, checks=checks)


def build_gdal_report_command(path: str, shell: str = "powershell") -> str:
    """Build a compact local GDAL inspection command."""
    if not path.strip():
        raise ValueError("A local raster path is required.")
    escaped = path.replace("'", "''")
    if shell.lower() == "powershell":
        return (
            "$i = gdalinfo -json '" + escaped + "' | ConvertFrom-Json; "
            "$o = [ordered]@{driverShortName=$i.driverShortName;filename=$i.filename;size=$i.size;"
            "coordinateSystem=$i.coordinateSystem;cornerCoordinates=$i.cornerCoordinates;wgs84Extent=$i.wgs84Extent;"
            "metadata=$i.metadata;bands=@($i.bands | ForEach-Object {[ordered]@{band=$_.band;type=$_.type;"
            "colorInterpretation=$_.colorInterpretation;block=$_.block;overviews=$_.overviews}})}; "
            "$o | ConvertTo-Json -Depth 12 -Compress"
        )
    if shell.lower() in {"bash", "sh", "zsh"}:
        return f"gdalinfo -json '{escaped}'"
    raise ValueError("shell must be 'powershell' or 'bash'.")


def build_rgb_cog_command(input_path: str, output_path: str, band_count: int = 3, shell: str = "powershell") -> str:
    """Build a lossless visual COG conversion; never overwrite the input."""
    if band_count == 4:
        bands = " -b 1 -b 2 -b 3 -b 4"
    else:
        bands = " -b 1 -b 2 -b 3"
    compression = "DEFLATE"
    if shell.lower() == "powershell":
        return f'gdal_translate -of COG -co COMPRESS={compression}{bands} "{input_path}" "{output_path}"'
    return f"gdal_translate -of COG -co COMPRESS={compression}{bands} '{input_path}' '{output_path}'"


def build_reproject_command(input_path: str, output_path: str, epsg: str, shell: str = "powershell") -> str:
    epsg_clean = str(epsg).strip().upper().replace("EPSG:", "")
    if not epsg_clean.isdigit():
        raise ValueError("EPSG must be numeric, e.g. 32751.")
    if shell.lower() == "powershell":
        return f'gdalwarp -t_srs EPSG:{epsg_clean} -of COG -co COMPRESS=DEFLATE "{input_path}" "{output_path}"'
    return f"gdalwarp -t_srs EPSG:{epsg_clean} -of COG -co COMPRESS=DEFLATE '{input_path}' '{output_path}'"


def build_oam_ready_command(
    report: dict[str, Any],
    input_path: str,
    output_path: str,
    target_epsg: str | None = None,
    shell: str = "powershell",
) -> str:
    """Return one pasteable command sequence that creates a lossless OAM-ready COG.

    A missing CRS requires an explicit target/source EPSG from the user. If a CRS
    is already present, no reprojection is performed unless target_epsg is supplied.
    The original file is never overwritten.
    """
    bands = report.get("bands") or []
    types = _band_types(report)
    if len(bands) not in (3, 4):
        raise ValueError("Automatic OAM visual conversion requires 3 RGB or 4 RGBA bands.")
    if not types or any(t != "BYTE" for t in types):
        raise ValueError("Automatic visual conversion requires Byte/8-bit bands.")

    crs = report.get("coordinateSystem")
    has_crs = bool(crs and (crs.get("wkt") or crs.get("projjson") or crs.get("authority"))) if isinstance(crs, dict) else bool(crs)
    if not has_crs and not target_epsg:
        raise ValueError("No CRS was reported. Select the true source EPSG before generating a command.")

    epsg = str(target_epsg).strip().upper().replace("EPSG:", "") if target_epsg else ""
    if epsg and not epsg.isdigit():
        raise ValueError("EPSG must be numeric, e.g. 32751.")

    if shell.lower() == "powershell":
        src = f'"{input_path}"'
        dst = f'"{output_path}"'
        if epsg:
            tmp = f'"{output_path.rsplit(".", 1)[0]}_reprojected.tif"'
            return (
                f'gdalwarp -t_srs EPSG:{epsg} -of GTiff {src} {tmp}; '
                f'if ($LASTEXITCODE -eq 0) {{ gdal_translate -of COG -co COMPRESS=DEFLATE'
                f' -b 1 -b 2 -b 3{(" -b 4" if len(bands) == 4 else "")} {tmp} {dst} }}'
            )
        return build_rgb_cog_command(input_path, output_path, len(bands), shell)

    src = f"'{input_path}'"
    dst = f"'{output_path}'"
    if epsg:
        tmp = f"'{output_path.rsplit('.', 1)[0]}_reprojected.tif'"
        return (
            f"gdalwarp -t_srs EPSG:{epsg} -of GTiff {src} {tmp} && "
            f"gdal_translate -of COG -co COMPRESS=DEFLATE -b 1 -b 2 -b 3"
            f"{(' -b 4' if len(bands) == 4 else '')} {tmp} {dst}"
        )
    return build_rgb_cog_command(input_path, output_path, len(bands), shell)
