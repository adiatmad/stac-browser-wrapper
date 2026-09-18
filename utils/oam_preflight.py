"""Local OAM visual-imagery preflight helpers.

The browser never needs the raster itself. Users paste GDAL metadata generated
locally; this module parses the relevant fields and creates a conservative,
PowerShell-friendly conversion command without overwriting the source.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any


@dataclass
class Check:
    name: str
    status: str
    detail: str


@dataclass
class PreflightResult:
    checks: list[Check]
    suggested_command: str
    notes: list[str]

    @property
    def status(self) -> str:
        if any(c.status == "FAIL" for c in self.checks):
            return "FAIL"
        if any(c.status == "WARN" for c in self.checks):
            return "WARNING"
        return "PASS"

    def as_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "checks": [asdict(c) for c in self.checks],
            "suggested_command": self.suggested_command,
            "notes": self.notes,
        }


def _loads_gdal(text: str) -> dict[str, Any] | None:
    try:
        obj = json.loads(text.strip())
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _text_value(text: str, pattern: str) -> str | None:
    m = re.search(pattern, text, re.IGNORECASE | re.MULTILINE)
    return m.group(1).strip() if m else None


def parse_gdalinfo(text: str) -> dict[str, Any]:
    """Parse either `gdalinfo -json` or ordinary `gdalinfo` output."""
    data = _loads_gdal(text)
    if data:
        driver = data.get("driverShortName") or data.get("driver")
        size = data.get("size") or []
        bands = data.get("bands") or []
        srs = data.get("coordinateSystem")
        epsg = None
        if isinstance(srs, dict):
            blob = json.dumps(srs)
            m = re.search(r'"EPSG"[^0-9]*(\d+)', blob, re.I)
            if m:
                epsg = m.group(1)
        metadata = data.get("metadata") or {}
        image_structure = metadata.get("IMAGE_STRUCTURE", {}) if isinstance(metadata, dict) else {}
        overview_count = 0
        for band in bands:
            if isinstance(band, dict):
                overview_count = max(overview_count, len(band.get("overviews") or []))
        return {
            "driver": driver,
            "width": size[0] if len(size) > 0 else None,
            "height": size[1] if len(size) > 1 else None,
            "band_count": len(bands),
            "data_types": [b.get("type") for b in bands if isinstance(b, dict)],
            "color_interpretations": [b.get("colorInterpretation") for b in bands if isinstance(b, dict)],
            "crs": srs,
            "epsg": epsg,
            "image_structure": image_structure,
            "overview_count": overview_count,
            "raw_json": data,
        }

    driver = _text_value(text, r"^Driver:\s*([^,\n]+)")
    size_match = re.search(r"^Size is\s*(\d+)\s*,\s*(\d+)", text, re.I | re.M)
    band_nums = re.findall(r"^Band\s+(\d+)", text, re.I | re.M)
    types = re.findall(r"Type=([A-Za-z0-9]+)", text, re.I)
    epsg_match = re.search(r"(?:AUTHORITY\[\"EPSG\"\s*,\s*\"|EPSG[:\s])(\d+)", text, re.I)
    layout = _text_value(text, r"LAYOUT[=:]\s*([^\s,]+)")
    tiled = _text_value(text, r"TILED[=:]\s*([^\s,]+)")
    return {
        "driver": driver,
        "width": int(size_match.group(1)) if size_match else None,
        "height": int(size_match.group(2)) if size_match else None,
        "band_count": len(band_nums),
        "data_types": types,
        "color_interpretations": [],
        "crs": epsg_match.group(1) if epsg_match else None,
        "epsg": epsg_match.group(1) if epsg_match else None,
        "image_structure": {"LAYOUT": layout, "TILED": tiled},
        "overview_count": len(re.findall(r"Overviews:\s", text, re.I)),
        "raw_text": text,
    }


def _quote_ps(value: str) -> str:
    return '"' + value.replace('"', '""') + '"'


def build_command(input_path: str, output_path: str, meta: dict[str, Any], target_epsg: str | None = None) -> str:
    """Build one pasteable PowerShell command sequence; never overwrite input."""
    src = _quote_ps(input_path)
    dst = _quote_ps(output_path)
    bands = int(meta.get("band_count") or 0)
    dtypes = {str(x).lower() for x in (meta.get("data_types") or []) if x}
    if bands not in (3, 4) or dtypes != {"byte"}:
        return ""

    compression = "JPEG" if bands == 3 else "DEFLATE"
    options = f'-of COG -co COMPRESS={compression} -co BIGTIFF=IF_SAFER'
    if target_epsg:
        code = str(target_epsg).upper().replace("EPSG:", "")
        tmp = _quote_ps(str(Path(output_path).with_name(Path(output_path).stem + "_reprojected.tif")))
        return (
            f'gdalwarp -t_srs EPSG:{code} -of GTiff {src} {tmp}; '
            f'if ($LASTEXITCODE -eq 0) {{ gdal_translate {options} {tmp} {dst} }}'
        )
    return f'gdal_translate {options} {src} {dst}'


def validate_gdalinfo(text: str, input_path: str = "input.tif", output_path: str | None = None, target_epsg: str | None = None) -> PreflightResult:
    meta = parse_gdalinfo(text)
    checks: list[Check] = []
    notes: list[str] = []

    driver = str(meta.get("driver") or "").lower()
    if driver in {"gtiff", "geotiff"}:
        checks.append(Check("GeoTIFF driver", "PASS", "GDAL reports GTiff."))
    elif driver:
        checks.append(Check("GeoTIFF driver", "WARN", f"GDAL reports '{meta['driver']}'. The source will be converted to GeoTIFF."))
    else:
        checks.append(Check("GeoTIFF driver", "WARN", "Driver could not be identified from the pasted output."))

    ext = Path(input_path).suffix.lower()
    if ext in {".tif", ".tiff"}:
        checks.append(Check("File extension", "PASS", "The source is a TIFF/GeoTIFF."))
    else:
        checks.append(Check("File extension", "WARN", "The source is not a .tif/.tiff; the generated command will create one."))

    if meta.get("crs") or meta.get("epsg"):
        crs_detail = "A CRS is present."
        if meta.get("epsg"):
            crs_detail = f"A CRS is present (EPSG:{meta['epsg']})."
        checks.append(Check("CRS", "PASS", crs_detail))
    elif target_epsg:
        checks.append(Check("CRS", "WARN", f"No CRS was detected; the command will assign the user-selected EPSG:{target_epsg}. Verify this is the true source CRS."))
    else:
        checks.append(Check("CRS", "FAIL", "No CRS could be identified. Select the correct EPSG before conversion."))

    bands = int(meta.get("band_count") or 0)
    if bands in (3, 4):
        checks.append(Check("Bands", "PASS", f"{bands}-band RGB/RGBA visual imagery."))
    elif bands:
        checks.append(Check("Bands", "FAIL", f"{bands} bands detected. This preflight targets OAM visual RGB/RGBA imagery (3 or 4 bands)."))
    else:
        checks.append(Check("Bands", "FAIL", "Band count could not be determined."))

    dtypes = {str(x).lower() for x in (meta.get("data_types") or []) if x}
    if dtypes == {"byte"}:
        checks.append(Check("Pixel type", "PASS", "All detected bands are Byte/8-bit."))
    elif dtypes:
        checks.append(Check("Pixel type", "FAIL", f"Detected pixel type(s): {', '.join(sorted(dtypes))}. Visual OAM imagery should be Byte/8-bit."))
    else:
        checks.append(Check("Pixel type", "WARN", "Pixel type could not be determined from the pasted output."))

    structure = {str(k).upper(): str(v).upper() for k, v in (meta.get("image_structure") or {}).items()}
    layout = structure.get("LAYOUT", "")
    if layout == "COG":
        checks.append(Check("COG layout", "PASS", "GDAL reports LAYOUT=COG."))
    else:
        checks.append(Check("COG layout", "WARN", "Source is not reported as COG. This is not itself an OAM upload blocker; OAM converts imagery during processing."))
        notes.append("COG is treated as informational rather than a hard upload prerequisite.")
    if structure.get("TILED", "") in {"YES", "TRUE"} or layout == "COG":
        checks.append(Check("Internal tiling", "PASS", "Tiled storage is indicated."))
    else:
        checks.append(Check("Internal tiling", "WARN", "Internal tiling was not confirmed; OAM conversion can create tiled output."))

    ov = int(meta.get("overview_count") or 0)
    if ov > 0 or layout == "COG":
        checks.append(Check("Overviews", "PASS", "Overview/resolution-pyramid information is present or implied by COG layout."))
    else:
        checks.append(Check("Overviews", "WARN", "No overviews were confirmed; OAM conversion can create the COG pyramid."))

    output = output_path or str(Path(input_path).with_name(Path(input_path).stem + "_oam_ready.tif"))
    command = build_command(input_path, output, meta, target_epsg=target_epsg)
    if not command:
        if bands not in (3, 4):
            notes.append("No automatic conversion command was generated because this tool targets 3/4-band visual imagery.")
        elif dtypes != {"byte"}:
            notes.append("No automatic conversion command was generated because the imagery is not Byte/8-bit. Convert the data type deliberately rather than silently changing values.")

    if not (meta.get("crs") or meta.get("epsg")) and not target_epsg:
        command = ""

    return PreflightResult(checks=checks, suggested_command=command, notes=notes)
