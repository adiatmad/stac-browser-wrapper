import streamlit as st

st.set_page_config(page_title="OAM Preflight", layout="wide")
st.title("OAM preflight")
st.caption(
    "The guided OSGeo4W report workflow now lives in the main application's "
    "Local preparation tab so raster inspection, OAM checks, and uploader handoff "
    "share one source of truth."
)
st.page_link("app.py", label="Open Local preparation", icon="🛰️")
st.info(
    "Paste your local raster path in that tab, run the generated commands in "
    "QGIS / OSGeo4W Shell, paste the GDAL JSON report, and follow the OAM guidance."
)
