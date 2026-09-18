"""Local GDAL report parsing and OAM imagery preflight checks.

The Streamlit app never receives the raster. Users run gdalinfo locally, paste
its JSON output, and receive a single conservative command to create a new
lossless OAM-ready COG.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CheckResult:
    name: str
    status: str
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
    if not isinstance(block, list) or len(block) != 2 or not isinstance(size, list) or len(size) != 2:
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
            points = [p for p in rings if isinstance(p, (list, tuple)) and len(p) >= 2]
            if points:
                xs = [float(p[0]) for p in points]
                ys = [float(p[1]) for p in points]
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
    checks.append(CheckResult("Raster dimensions", "PASS" if valid_size else "FAIL", f"Size: {size[0]} x {size[1]}." if valid_size else "Raster dimensions are missing or invalid."))

    visual_shape = len(bands) in (3, 4)
    byte_bands = all(t == "BYTE" for t in types) if types else False
    rgb_interpretations = [str(b.get("colorInterpretation", "")).upper() for b in bands]
    rgb_like = rgb_interpretations[:3] == ["RED", "GREEN", "BLUE"] or not any(rgb_interpretations)
    visual_ok = visual_shape and byte_bands and rgb_like
    if visual_ok:
        status, detail, fix = "PASS", f"{len(bands)} bands; Byte data type; RGB/RGBA-compatible interpretation.", ""
    elif len(bands) not in (3, 4):
        status, detail, fix = "FAIL", f"Found {len(bands)} bands; this preflight targets 3 RGB or 4 RGBA visual bands.", "Inspect the source and select/export the visual RGB(A) bands."
    elif types and not byte_bands:
        status, detail, fix = "FAIL", f"Band types: {', '.join(types)}. Visual OAM imagery should be Byte/8-bit.", "Convert the visual imagery deliberately to Byte RGB(A); do not silently change non-visual products."
    else:
        status, detail, fix = "WARNING", "Band layout needs manual review for visual RGB(A) use.", "Confirm the first three bands are Red, Green, Blue."
    checks.append(CheckResult("Visual RGB/RGBA bands", status, detail, fix))

    checks.append(CheckResult(
        "COG layout",
        "PASS" if layout == "COG" else "WARNING",
        "GDAL reports IMAGE_STRUCTURE LAYOUT=COG." if layout == "COG" else "The report does not identify the file as a COG. This is informational: current OAM ingestion can convert valid GeoTIFF input to COG.",
    ))
    checks.append(CheckResult(
        "Internal tiling",
        "PASS" if tiled is True else "WARNING",
        f"Internal block size reported as {_first_band(report).get('block')}." if tiled is True else "Internal tiling was not confirmed.",
    ))
    checks.append(CheckResult(
        "Overviews",
        "PASS" if overviews else "WARNING",
        "Overviews are reported by GDAL." if overviews else "No overviews are reported; the final COG conversion can build them.",
    ))

    if bounds is None:
        checks.append(CheckResult("Georeferenced bounds", "FAIL", "No usable corner/extent coordinates were reported."))
    else:
        finite = all(abs(v) != float("inf") and v == v for v in bounds)
        nonzero_extent = bounds[0] != bounds[2] and bounds[1] != bounds[3]
        checks.append(CheckResult("Georeferenced bounds", "PASS" if finite and nonzero_extent else "FAIL", f"Bounds: {bounds}." if finite and nonzero_extent else f"Invalid or zero-area bounds: {bounds}."))
    return ValidationReport(source=report, checks=checks)


def build_gdal_report_command(path: str, shell: str = "powershell") -> str:
    if not path.strip():
        raise ValueError("A local raster path is required.")
    if shell.lower() == "powershell":
        escaped = path.replace('"', '""')
        return f'gdalinfo -json "{escaped}"'
    if shell.lower() in {"bash", "sh", "zsh"}:
        escaped = path.replace("'", "'\\''")
        return f"gdalinfo -json '{escaped}'"
    raise ValueError("shell must be 'powershell' or 'bash'.")


def build_rgb_cog_command(input_path: str, output_path: str, band_count: int = 3, shell: str = "powershell") -> str:
    bands = " -b 1 -b 2 -b 3" + (" -b 4" if band_count == 4 else "")
    compression = "DEFLATE"  # lossless; do not degrade drone imagery before OAM upload.
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


def build_oam_ready_command(report: dict[str, Any], input_path: str, output_path: str, target_epsg: str | None = None, shell: str = "powershell") -> str:
    """Return one pasteable command sequence that creates a lossless visual COG."""
    bands = report.get("bands") or []
    types = _band_types(report)
    if len(bands) not in (3, 4):
        raise ValueError("Automatic OAM visual conversion requires 3 RGB or 4 RGBA bands.")
    if not types or any(t != "BYTE" for t in types):
        raise ValueError("Automatic visual conversion requires Byte/8-bit bands.")

    crs = report.get("coordinateSystem")
    has_crs = bool(crs and (crs.get("wkt") or crs.get("projjson") or crs.get("authority"))) if isinstance(crs, dict) else bool(crs)
    epsg = str(target_epsg).strip().upper().replace("EPSG:", "") if target_epsg else ""
    if not has_crs and not epsg:
        raise ValueError("No CRS was reported. Select the true source EPSG before generating a command.")
    if epsg and not epsg.isdigit():
        raise ValueError("EPSG must be numeric, e.g. 32751.")

    if shell.lower() == "powershell":
        src, dst = f'"{input_path}"', f'"{output_path}"'
        if epsg:
            stem = output_path.rsplit(".", 1)[0]
            tmp = f'"{stem}_reprojected.tif"'
            band_args = " -b 1 -b 2 -b 3" + (" -b 4" if len(bands) == 4 else "")
            return (
                f'gdalwarp -t_srs EPSG:{epsg} -of GTiff {src} {tmp}; '
                f'if ($LASTEXITCODE -eq 0) {{ gdal_translate -of COG -co COMPRESS=DEFLATE{band_args} {tmp} {dst} }}'
            )
        return build_rgb_cog_command(input_path, output_path, len(bands), shell)

    src, dst = f"'{input_path}'", f"'{output_path}'"
    if epsg:
        stem = output_path.rsplit(".", 1)[0]
        tmp = f"'{stem}_reprojected.tif'"
        band_args = " -b 1 -b 2 -b 3" + (" -b 4" if len(bands) == 4 else "")
        return f"gdalwarp -t_srs EPSG:{epsg} -of GTiff {src} {tmp} && gdal_translate -of COG -co COMPRESS=DEFLATE{band_args} {tmp} {dst}"
    return build_rgb_cog_command(input_path, output_path, len(bands), shell)
