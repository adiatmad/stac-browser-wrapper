"""Detailed local-only OAM drone preflight page.

The page never opens or uploads the raster. It only uses the GDAL text report
pasted by the user to explain what the source contains and what to do next.
"""

import json
from pathlib import Path

import streamlit as st

from validate_imagery import build_oam_recommendation, parse_gdalinfo_text, validate_info
from utils.gdal_report import parse_detailed_gdalinfo, visual_assessment


st.set_page_config(page_title="OAM Preflight", layout="wide")
st.title("🛩️ OAM Drone Preflight")
st.caption("Local-only: inspect the GDAL report, understand the raster, then get one local preparation command if needed.")

path = st.text_input(
    "1 · Select imagery on your computer",
    placeholder=r"C:\drone\orthomosaic.tif",
    help="Only the path is used to generate a command. The raster is never uploaded to this app.",
    key="detailed_preflight_path",
)

if path.strip():
    st.markdown("**2 · Run this locally**")
    st.code(f'gdalinfo "{path.strip()}"', language="powershell")
    st.caption("Run the command in PowerShell/QGIS OSGeo4W, then paste the complete output below.")

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

        st.markdown("### 4 · What your file contains")
        col1, col2, col3, col4 = st.columns(4)
        col1.metric("Driver", detailed["driver"] or "Unknown")
        size = detailed["size"]
        col2.metric("Raster size", f"{size[0]:,} × {size[1]:,}" if size else "Unknown")
        col3.metric("Bands", len(detailed["bands"]))
        col4.metric("CRS", f"EPSG:{detailed['epsg']}" if detailed["epsg"] else "Not identified")

        if visual["status"] == "PASS":
            st.success(f"✅ **{visual['label']}** — {visual['detail']}")
        else:
            st.error(f"❌ **{visual['label']}** — {visual['detail']}")

        if detailed["decodedBytes"] is not None:
            gb = detailed["decodedBytes"] / 1_000_000_000
            st.caption(f"Estimated decoded raster size: {gb:.2f} GB")

        st.markdown("### Band details")
        for band in detailed["bands"]:
            overview_text = ", ".join(band["overviews"]) if band["overviews"] else "none reported"
            st.markdown(
                f"**Band {band['band']}** · {band['type']} · {band['colorInterpretation']} · "
                f"block {band['block'][0]}×{band['block'][1]} · "
                f"overviews: {overview_text}"
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

        st.markdown("### OAM preflight")
        for check in result["checks"]:
            icon = {"PASS": "✅", "WARN": "⚠️", "FAIL": "❌"}[check["status"]]
            st.markdown(f"{icon} **{check['name']}** — {check['detail']}")

        hard_fails = [c for c in result["checks"] if c["status"] == "FAIL"]
        if hard_fails:
            st.error("❌ **Do not treat this as ready for the visual orthomosaic workflow.** Fix the failed checks or identify the data as a different OAM product type.")
        elif visual["status"] == "FAIL":
            st.error("❌ **Not ready for the visual RGB/RGBA workflow.** The detailed report suggests this may be elevation, multispectral, or another non-visual product.")
        elif result["status"] == "WARN":
            st.warning("⚠️ **Review before upload.** No hard structural failure was detected, but the warnings should be understood first.")
        else:
            st.success("✅ **Ready based on the supplied report.**")

        if visual["status"] == "PASS":
            st.markdown("### 5 · One combined local preparation command")
            if detailed["epsg"]:
                rec = build_oam_recommendation(info, path.strip(), source_epsg=None)
            else:
                rec = build_oam_recommendation(info, path.strip(), source_epsg=None)
            if rec["ready"] and rec["command"]:
                output = rec["output"]
                combined = (
                    f'$out="{output}"; if (Test-Path $out) {{ Remove-Item $out -Force }}; '
                    f'{rec["command"]}; if ($LASTEXITCODE -eq 0) {{ gdalinfo "$out" }}'
                )
                st.code(combined, language="powershell")
                st.caption("This creates a new local COG and verifies it with gdalinfo. The source file is not overwritten.")
            else:
                st.info("No conversion command is required from the current evidence.")

    except Exception as exc:
        st.error(f"Could not process the GDAL report: {exc}")
