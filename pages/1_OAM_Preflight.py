"""Detailed local-only OAM drone preflight page.

Workflow:
1. Select a local imagery path.
2. Run the generated gdalinfo command locally.
3. Paste the complete report.
4. Inspect raster readiness without uploading the raster.
5. Check the separate OAM v0.3.0 publication metadata contract.
6. Get one local preparation command when conversion is appropriate.
"""

import json
import os
import re

import streamlit as st

from validate_imagery import build_oam_recommendation, parse_gdalinfo_text, validate_info
from utils.gdal_report import parse_detailed_gdalinfo, visual_assessment
from utils.oam_v030_preflight import check_oam_item, OAM_LICENSES, OAM_SCHEMA_URL


def _visual_conversion_command(path: str, detailed: dict) -> str | None:
    bands = detailed.get("bands") or []
    if len(bands) not in (3, 4):
        return None
    source = path.strip()
    root, _ = os.path.splitext(source)
    output = f"{root}_OAM.tif"
    selected = "-b 1 -b 2 -b 3"
    return (
        f'$out="{output}"; if (Test-Path $out) {{ Remove-Item $out -Force }}; '
        f'gdal_translate -of COG -ot Byte {selected} -colorinterp red,green,blue -scale -a_nodata 0 '
        f'-co COMPRESS=DEFLATE "{source}" "$out"; '
        f'if ($LASTEXITCODE -eq 0) {{ gdalinfo "$out" }}'
    )


def _extract_pixel_size(text: str) -> float | None:
    match = re.search(r"Pixel Size = \(([-+0-9.eE]+),\s*([-+0-9.eE]+)\)", text)
    if not match:
        return None
    try:
        return abs(float(match.group(1)))
    except ValueError:
        return None


def _build_oam_item_from_form(*, detailed: dict, title: str, producer: str, platform: str,
                              gsd: float | None, acquisition_datetime: str, license_value: str,
                              source_url: str, geometry_json: str, bbox_text: str) -> dict:
    try:
        geometry = json.loads(geometry_json) if geometry_json.strip() else None
    except json.JSONDecodeError:
        geometry = None
    try:
        bbox = [float(x.strip()) for x in bbox_text.split(",")] if bbox_text.strip() else None
    except ValueError:
        bbox = None

    properties = {
        "title": title.strip(),
        "datetime": acquisition_datetime.strip() or None,
        "license": license_value,
        "oam:platform_type": platform,
        "oam:producer_name": producer.strip(),
        "oam:product_type": "visual",
    }
    return {
        "type": "Feature",
        "stac_extensions": [OAM_SCHEMA_URL],
        "geometry": geometry,
        "bbox": bbox,
        "gsd": gsd,
        "providers": [{"name": producer.strip(), "roles": ["producer", "licensor"]}] if producer.strip() else [],
        "properties": properties,
        "assets": {"visual": {"href": source_url.strip(), "roles": ["visual"]}} if source_url.strip() else {},
    }


st.set_page_config(page_title="OAM Preflight", layout="wide")
st.title("🛩️ OAM Drone Preflight")
st.caption("Local-only: inspect the GDAL report first, then check whether the imagery and its OAM publication metadata are actually ready.")

path = st.text_input(
    "1 · Select imagery on your computer",
    placeholder=r"C:\drone\orthomosaic.tif",
    help="Only the path is used to generate a command. The raster is never uploaded to this app.",
    key="detailed_preflight_path",
)

if path.strip():
    st.markdown("**2 · Run this locally**")
    st.code(f'gdalinfo "{path.strip()}"', language="powershell")
    st.caption("Run the command in PowerShell/QGIS OSGeo4W, then paste the complete output below. Nothing is uploaded.")

report_text = st.text_area(
    "3 · Paste the complete GDAL output",
    height=260,
    placeholder="Driver: GTiff/GeoTIFF\nSize is ...\nCoordinate System is: ...\nBand 1 ...",
    key="detailed_preflight_report",
)

if report_text.strip():
    try:
        raw = report_text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            if raw.endswith("```"):
                raw = raw[:-3].strip()

        if raw.lstrip().startswith("{"):
            info = json.loads(raw)
        else:
            info = parse_gdalinfo_text(raw)

        result = validate_info(info)
        detailed = parse_detailed_gdalinfo(raw)
        visual = visual_assessment(detailed)

        st.markdown("### 4 · Raster evidence")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Driver", detailed["driver"] or "Unknown")
        size = detailed["size"]
        col2.metric("Raster size", f"{size[0]:,} × {size[1]:,}" if size else "Unknown")
        col3.metric("Bands", len(detailed["bands"]))
        col4.metric("CRS", f"EPSG:{detailed['epsg']}" if detailed["epsg"] else "Not identified")

        if visual["status"] == "PASS":
            st.success(f"✅ **{visual['label']}** — {visual['detail']}")
        else:
            st.warning(f"⚠️ **{visual['label']}** — {visual['detail']}")

        if detailed["decodedBytes"] is not None:
            st.caption(f"Estimated decoded raster size: {detailed['decodedBytes'] / 1_000_000_000:.2f} GB")

        st.markdown("### Band details")
        for band in detailed["bands"]:
            overview_text = ", ".join(band["overviews"]) if band["overviews"] else "none reported"
            st.markdown(
                f"**Band {band['band']}** · {band['type']} · {band['colorInterpretation']} · "
                f"block {band['block'][0]}×{band['block'][1]} · overviews: {overview_text}"
            )
            if band.get("nodata") is not None:
                st.caption(f"NoData: {band['nodata']}")
            if band.get("description"):
                st.caption(f"Description: {band['description']}")

        with st.expander("Show georeferencing and raster metadata"):
            if detailed["origin"]:
                st.write(f"**Origin:** {detailed['origin'][0]}, {detailed['origin'][1]}")
            if detailed["pixelSize"]:
                st.write(f"**Pixel size:** {detailed['pixelSize'][0]}, {detailed['pixelSize'][1]}")
            if detailed["corners"]:
                st.write("**Corner coordinates:**")
                for name, value in detailed["corners"].items():
                    st.write(f"- {name}: {value}")
            if detailed["imageStructure"]:
                st.write("**Image structure:**")
                for key, value in detailed["imageStructure"].items():
                    st.write(f"- {key}: {value}")
            if detailed["metadata"]:
                st.write("**Metadata:**")
                for key, value in detailed["metadata"].items():
                    st.write(f"- {key}: {value}")

        st.markdown("### 5 · Raster readiness")
        for check in result["checks"]:
            icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[check["status"]]
            st.markdown(f"{icon} **{check['name']}** — {check['detail']}")

        hard_fails = [c for c in result["checks"] if c["status"] == "FAIL"]
        if hard_fails:
            st.error("❌ Raster has a hard failure for the current visual workflow. Do not call it OAM-ready yet.")
        elif visual["status"] != "PASS":
            st.warning("⚠️ This is not proven to be a visual RGB/RGBA orthomosaic. OAM also supports multispectral, SAR, elevation and pseudocolor products; choose the product type based on the actual data rather than forcing a conversion.")
        elif result["status"] == "WARN":
            st.warning("⚠️ Raster structure is usable but needs review before publication.")
        else:
            st.success("✅ Raster passes the local visual checks.")

        st.markdown("### 6 · OAM v0.3.0 publication readiness")
        st.caption("Current OAM requires more than a valid COG: GSD, platform, producer, geometry/bbox, capture time, title, accepted license, producer provider, a public assets.visual URL, and the current OAM schema declaration.")

        inferred_gsd = None
        if detailed.get("pixelSize") and detailed.get("epsg") == 4326:
            inferred_gsd = None
        gsd_default = inferred_gsd
        title = st.text_input("Title", value=os.path.splitext(os.path.basename(path.strip()))[0] if path.strip() else "", key="oam30_title")
        producer = st.text_input("Imagery producer", placeholder="Person or organisation that produced the imagery", key="oam30_producer")
        platform = st.selectbox("Platform", ["uav", "kite", "balloon", "aircraft", "satellite"], key="oam30_platform")
        gsd_text = st.text_input("GSD (metres/pixel)", value=str(gsd_default or ""), placeholder="Example: 0.05", key="oam30_gsd")
        acquisition_datetime = st.text_input("Acquisition datetime (ISO 8601)", placeholder="Example: 2026-09-09T02:03:10Z", key="oam30_datetime")
        license_value = st.selectbox("OAM license", sorted(OAM_LICENSES), key="oam30_license")
        source_url = st.text_input("Public assets.visual URL", placeholder="https://.../orthomosaic.tif", key="oam30_visual_url")
        bbox_text = st.text_input("BBox [west, south, east, north]", placeholder="120.123, -8.42, 120.133, -8.41", key="oam30_bbox")
        geometry_json = st.text_area("Geometry GeoJSON", placeholder='{"type":"Polygon","coordinates":[[[...]]]}', height=100, key="oam30_geometry")

        try:
            gsd_value = float(gsd_text) if gsd_text.strip() else None
        except ValueError:
            gsd_value = None
            st.error("GSD must be a positive number in metres per pixel.")

        item = _build_oam_item_from_form(
            detailed=detailed,
            title=title,
            producer=producer,
            platform=platform,
            gsd=gsd_value,
            acquisition_datetime=acquisition_datetime,
            license_value=license_value,
            source_url=source_url,
            geometry_json=geometry_json,
            bbox_text=bbox_text,
        )
        oam_result = check_oam_item(item)

        for check in oam_result["checks"]:
            icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌", "INFO": "ℹ️"}[check["status"]]
            st.markdown(f"{icon} **{check['name']}** — {check['detail']}")

        if oam_result["status"] == "PASS" and not hard_fails:
            st.success("✅ **Publication metadata is complete based on the information provided.** The raster and the public asset still need to remain accessible to OAM.")
        elif not hard_fails:
            st.warning("⚠️ **Metadata needs attention before publication.** Nothing has been uploaded by this tool.")
        else:
            st.error("❌ **Not publication-ready yet.** The failed OAM fields above are the exact missing requirements.")

        st.markdown("### 7 · Local conversion, only when needed")
        needs_local_conversion = (
            detailed["driver"].upper().startswith("GTIFF") is False
            or result["summary"].get("cogLayout", "").upper() != "COG"
            or not result["summary"].get("isTiled", False)
            or not result["summary"].get("hasOverviews", False)
        )

        if visual["status"] == "PASS" and needs_local_conversion:
            rec = build_oam_recommendation(info, path.strip(), source_epsg=None)
            if rec["ready"] and rec["command"]:
                st.caption("The command below creates a new local COG and verifies it. It never overwrites the source.")
                output = rec["output"]
                combined = f'$out="{output}"; if (Test-Path $out) {{ Remove-Item $out -Force }}; {rec["command"]}; if ($LASTEXITCODE -eq 0) {{ gdalinfo "$out" }}'
                st.code(combined, language="powershell")
        elif visual["status"] != "PASS":
            candidate = _visual_conversion_command(path.strip(), detailed) if path.strip() else None
            if candidate and len(detailed["bands"]) in (3, 4):
                st.warning("Only run this candidate if you know the source bands are the intended visible RGB channels. Converting Float32/other values to Byte with -scale changes the raster values.")
                st.code(candidate, language="powershell")
        else:
            st.info("No local COG conversion is required by the raster checks.")

    except Exception as exc:
        st.error(f"Could not process the GDAL report: {exc}")
