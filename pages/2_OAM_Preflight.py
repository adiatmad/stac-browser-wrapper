import json

import streamlit as st

from utils.validate_imagery import (
    build_gdal_report_command,
    build_oam_ready_command,
    parse_report,
    validate_report,
)

st.set_page_config(page_title="OAM Preflight Validator", layout="wide")
st.title("🔎 OAM Preflight Validator")
st.caption("Local-only preflight for visual drone imagery. Your raster is never uploaded to this app.")

st.info(
    "Workflow: copy the gdalinfo result from your own computer → paste it here → "
    "get one PowerShell command that creates a new, lossless OAM-ready COG."
)

st.subheader("1. Run GDAL locally")
path = st.text_input(
    "Local imagery path",
    placeholder=r"C:\data\orthomosaic.tif or C:\data\source.ecw",
    help="Only the path is used to generate the local command. The raster itself stays on your computer.",
)
shell = st.selectbox("Shell", ["PowerShell (Windows)", "Bash / Zsh"], index=0)
shell_key = "powershell" if shell.startswith("PowerShell") else "bash"

if path.strip():
    command = build_gdal_report_command(path, shell_key)
    st.markdown("Run this command **on your own computer**:")
    st.code(command, language="powershell" if shell_key == "powershell" else "bash")
    st.caption("Copy the complete JSON output from gdalinfo and paste it below. No imagery is sent to the app.")

st.subheader("2. Paste the gdalinfo result")
report_text = st.text_area(
    "gdalinfo -json output",
    height=240,
    placeholder='Paste the complete output from: gdalinfo -json "your-image.tif"',
)

if st.button("Validate imagery", type="primary"):
    if not report_text.strip():
        st.warning("Paste the gdalinfo JSON first.")
    else:
        try:
            report = parse_report(report_text)
            st.session_state["preflight_report"] = validate_report(report)
            st.session_state["preflight_raw"] = report
        except ValueError as exc:
            st.error(str(exc))

result = st.session_state.get("preflight_report")
raw_report = st.session_state.get("preflight_raw")
if result:
    st.subheader("3. Preflight result")
    fail_count = sum(c.status == "FAIL" for c in result.checks)
    warn_count = sum(c.status == "WARNING" for c in result.checks)
    pass_count = sum(c.status == "PASS" for c in result.checks)
    m1, m2, m3 = st.columns(3)
    m1.metric("PASS", pass_count)
    m2.metric("WARNING", warn_count)
    m3.metric("FAIL", fail_count)

    if fail_count:
        st.error("❌ Not ready yet. Resolve the failed prerequisite(s) before upload.")
    elif warn_count:
        st.warning("⚠️ No hard preflight failure, but review the warnings before upload.")
    else:
        st.success("✅ Preflight passed for visual RGB/RGBA imagery.")

    for check in result.checks:
        icon = {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌", "INFO": "ℹ️"}.get(check.status, "•")
        with st.container(border=True):
            st.markdown(f"**{icon} {check.name} — {check.status}**")
            st.write(check.detail)
            if check.fix:
                st.caption(f"Suggested action: {check.fix}")

    st.subheader("4. Generate ONE combined command")
    source_name = str((raw_report or {}).get("filename") or path or "input.tif")
    default_out = source_name.rsplit(".", 1)[0] + "_oam_ready.tif" if "." in source_name else source_name + "_oam_ready.tif"
    output_path = st.text_input("New output filename", value=default_out, key="oam_output")

    crs_check = next((c for c in result.checks if c.name == "Coordinate reference system"), None)
    needs_epsg = crs_check is not None and crs_check.status == "FAIL"
    target_epsg = None
    if needs_epsg:
        st.warning("No CRS was found. Do not guess it. Enter the CRS that the source imagery actually uses.")
        target_epsg = st.text_input("Source EPSG", placeholder="e.g. 32751", key="source_epsg")

    try:
        command = build_oam_ready_command(raw_report or {}, source_name, output_path, target_epsg or None, shell_key)
        st.success("Copy this ONE command and run it locally. The original imagery is never overwritten.")
        st.code(command, language="powershell" if shell_key == "powershell" else "bash")
        st.caption("The conversion uses lossless DEFLATE compression. It does not intentionally reduce the source imagery's pixel values.")
    except ValueError as exc:
        st.info(str(exc))

    with st.expander("Raw gdalinfo JSON"):
        st.code(json.dumps(raw_report, indent=2), language="json")

st.divider()
st.caption(
    "Scope: visual RGB/RGBA drone orthomosaics. ECW and other source formats can be inspected, "
    "then converted to a new GeoTIFF/COG. DEM, multispectral and SAR workflows are intentionally out of scope."
)
