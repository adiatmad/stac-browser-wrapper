import json

import streamlit as st

from utils.validate_imagery import (
    build_gdal_report_command,
    build_reproject_command,
    build_rgb_cog_command,
    parse_report,
    validate_report,
)

st.set_page_config(page_title="OAM Preflight Validator", layout="wide")
st.title("🔎 OAM Preflight Validator")
st.caption("Local-only preflight for GeoTIFF imagery. Your raster is never uploaded to this app.")

st.info(
    "Current OAM ingestion accepts valid GeoTIFF input and can convert it to COG. "
    "So COG status below is a quality check, not a hard OAM prerequisite."
)

st.subheader("1. Inspect the local raster")
path = st.text_input(
    "Local raster path",
    placeholder=r"C:\data\orthomosaic.tif or C:\data\source.ecw",
)
shell = st.selectbox("Your shell", ["PowerShell (Windows)", "Bash / Zsh"], index=0)
shell_key = "powershell" if shell.startswith("PowerShell") else "bash"

if path.strip():
    command = build_gdal_report_command(path, shell_key)
    st.markdown("Run this **on your own computer** where GDAL is installed:")
    st.code(command, language="powershell" if shell_key == "powershell" else "bash")
    st.caption("The command reads the local raster and returns only a compact JSON diagnostic.")

st.subheader("2. Paste the diagnostic result")
report_text = st.text_area(
    "GDAL diagnostic JSON",
    height=180,
    placeholder='{"driverShortName":"GTiff", ...}',
)

if st.button("Validate imagery", type="primary"):
    if not report_text.strip():
        st.warning("Paste the GDAL diagnostic JSON first.")
    else:
        try:
            report = parse_report(report_text)
            result = validate_report(report)
            st.session_state["preflight_result"] = result
        except ValueError as exc:
            st.error(str(exc))

result = st.session_state.get("preflight_result")
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
        st.error("❌ Not ready as a visual RGB/RGBA GeoTIFF. Fix the failed checks before OAM upload.")
    elif warn_count:
        st.warning("⚠️ No hard preflight failure, but review the warnings before upload.")
    else:
        st.success("✅ Preflight passed for a visual RGB/RGBA GeoTIFF.")

    for check in result.checks:
        icon = {"PASS": "✅", "WARNING": "⚠️", "FAIL": "❌", "INFO": "ℹ️"}.get(check.status, "•")
        with st.container(border=True):
            st.markdown(f"**{icon} {check.name} — {check.status}**")
            st.write(check.detail)
            if check.fix:
                st.caption(f"Suggested action: {check.fix}")

    st.subheader("4. Fix commands")
    source = result.source
    source_name = str(source.get("filename", path or "input.tif"))
    default_out = source_name.rsplit(".", 1)[0] + "_cog.tif" if "." in source_name else source_name + "_cog.tif"
    output_path = st.text_input("Output GeoTIFF path", value=default_out)
    bands = len(source.get("bands") or [])
    band_count = 4 if bands == 4 else 3

    if bands in (3, 4):
        st.markdown("**RGB/RGBA → COG**")
        st.code(build_rgb_cog_command(source_name, output_path, band_count, shell_key), language="powershell" if shell_key == "powershell" else "bash")
        if bands == 4:
            st.caption("This keeps band 4 (alpha); it does not silently drop transparency.")

    st.markdown("**Reproject → COG**")
    epsg = st.text_input("Target EPSG (optional)", placeholder="e.g. 32751")
    if epsg.strip():
        try:
            reproj_out = output_path.rsplit(".", 1)[0] + "_projected.tif"
            st.code(
                build_reproject_command(source_name, reproj_out, epsg, shell_key),
                language="powershell" if shell_key == "powershell" else "bash",
            )
        except ValueError as exc:
            st.warning(str(exc))

    with st.expander("Raw parsed report"):
        st.code(json.dumps(source, indent=2), language="json")

st.divider()
st.caption(
    "Scope: visual RGB/RGBA imagery. ECW and other source formats can be inspected here, "
    "but they are treated as source material that should be converted to GeoTIFF before the OAM preflight."
)
