"""Detailed parsing of plain-text GDAL reports for the local OAM preflight UI.

This module only parses text supplied by the user. It never opens, uploads, or
transmits the raster itself.
"""

from __future__ import annotations

import re
from typing import Any


def _match(pattern: str, text: str, flags: int = re.MULTILINE) -> re.Match[str] | None:
    return re.search(pattern, text, flags)


def _number_pair(pattern: str, text: str) -> list[float] | None:
    m = _match(pattern, text)
    if not m:
        return None
    return [float(m.group(1)), float(m.group(2))]


def parse_detailed_gdalinfo(text: str) -> dict[str, Any]:
    """Extract the useful raster facts from normal ``gdalinfo`` text output."""
    raw = text.strip()
    if not raw:
        raise ValueError("No GDAL report was provided.")

    driver = ""
    m = _match(r"^Driver:\s*(.+)$", raw)
    if m:
        driver = m.group(1).strip()

    size = None
    m = _match(r"^Size is\s+(\d+)\s*,\s*(\d+)", raw)
    if m:
        size = [int(m.group(1)), int(m.group(2))]

    epsg = None
    m = _match(r'ID\["EPSG",\s*(\d+)\]', raw)
    if m:
        epsg = int(m.group(1))

    origin = _number_pair(r"^Origin = \(\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*\)", raw)
    pixel_size = _number_pair(r"^Pixel Size = \(\s*([-+0-9.eE]+)\s*,\s*([-+0-9.eE]+)\s*\)", raw)

    corners: dict[str, str] = {}
    for name in ("Upper Left", "Lower Left", "Upper Right", "Lower Right", "Center"):
        m = _match(rf"^{re.escape(name)}\s+(.*)$", raw)
        if m:
            corners[name] = m.group(1).strip()

    metadata: dict[str, str] = {}
    metadata_start = _match(r"^Metadata:\s*$", raw)
    if metadata_start:
        tail = raw[metadata_start.end():]
        for line in tail.splitlines():
            if line.startswith("  ") and not line.startswith("    ") and ":" not in line:
                key, sep, value = line.strip().partition("=")
                if sep:
                    metadata[key] = value
            elif line and not line.startswith(" "):
                break

    image_structure: dict[str, str] = {}
    m = _match(r"^Image Structure Metadata:\s*$", raw)
    if m:
        tail = raw[m.end():]
        for line in tail.splitlines():
            if line.startswith("  "):
                key, sep, value = line.strip().partition("=")
                if sep:
                    image_structure[key] = value
            elif line and not line.startswith(" "):
                break

    bands: list[dict[str, Any]] = []
    sections = re.split(r"(?=^Band\s+\d+\s+)", raw, flags=re.MULTILINE)[1:]
    for section in sections:
        header = _match(
            r"^Band\s+(\d+)\s+Block=(\d+)x(\d+)\s+Type=([^,\r\n]+),\s*ColorInterp=([^\r\n]+)",
            section,
        )
        if not header:
            continue
        band: dict[str, Any] = {
            "band": int(header.group(1)),
            "block": [int(header.group(2)), int(header.group(3))],
            "type": header.group(4).strip(),
            "colorInterpretation": header.group(5).strip(),
        }
        nodata = _match(r"^\s*NoData Value=([^\r\n]+)", section)
        if nodata:
            band["nodata"] = nodata.group(1).strip()
        description = _match(r"^\s*Description = (.+)$", section)
        if description:
            band["description"] = description.group(1).strip()
        overviews = _match(r"^\s*Overviews:\s*(.+)$", section)
        band["overviews"] = [x.strip() for x in overviews.group(1).split(",") if x.strip()] if overviews else []
        bands.append(band)

    width, height = size if size else (None, None)
    decoded_bytes = None
    if width and height and bands:
        byte_sizes = {
            "BYTE": 1, "UINT8": 1, "INT8": 1, "UINT16": 2, "INT16": 2,
            "UINT32": 4, "INT32": 4, "FLOAT32": 4, "FLOAT64": 8,
        }
        if all(b.get("type", "").upper() in byte_sizes for b in bands):
            decoded_bytes = width * height * sum(byte_sizes[b["type"].upper()] for b in bands)

    return {
        "driver": driver,
        "size": size,
        "epsg": epsg,
        "origin": origin,
        "pixelSize": pixel_size,
        "corners": corners,
        "metadata": metadata,
        "imageStructure": image_structure,
        "bands": bands,
        "decodedBytes": decoded_bytes,
    }


def visual_assessment(report: dict[str, Any]) -> dict[str, Any]:
    """Classify whether the report looks like the tool's visual RGB/RGBA target."""
    bands = report.get("bands") or []
    types = [str(b.get("type", "")).upper() for b in bands]
    colors = [str(b.get("colorInterpretation", "")).lower() for b in bands]
    rgb = colors[:3] == ["red", "green", "blue"]
    byte_pixels = bool(types) and all(t in {"BYTE", "UINT8"} for t in types)
    count_ok = len(bands) in (3, 4)

    if count_ok and byte_pixels and rgb:
        return {
            "status": "PASS",
            "label": "Visual RGB/RGBA candidate",
            "detail": "The supplied report describes 3/4 8-bit bands with RGB color interpretation.",
        }

    reasons = []
    if not count_ok:
        reasons.append(f"{len(bands)} bands")
    if not byte_pixels:
        reasons.append(f"pixel types {types or ['unknown']}")
    if not rgb:
        reasons.append(f"color interpretation {colors or ['unknown']}")
    return {
        "status": "FAIL",
        "label": "Not a visual RGB/RGBA candidate",
        "detail": "The report does not match this tool's visual orthomosaic target: " + "; ".join(reasons) + ". It may instead be elevation, multispectral, or another product type.",
    }
