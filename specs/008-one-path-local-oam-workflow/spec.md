# Feature Specification: OSGeo4W Report-Guided Local OAM Workflow

**Status:** Implemented on feature branch; automated verification pending  
**Branch:** feat/osgeo4w-report-guided-oam-preflight

## Problem

The previous Local preparation flow tried to inspect a Windows path from the machine running Streamlit. That fails when the app is hosted, and it does not match the user's preferred workflow of running GDAL directly in QGIS / OSGeo4W Shell.

The old preflight guidance also treated local COG creation and a local STAC draft as required steps, although the current OAM uploader already validates GeoTIFF input, creates its own COG, derives GSD and footprint metadata, and registers the STAC Item.

## User outcome

The user pastes one local raster path and receives copy-ready OSGeo4W Shell commands. The user runs GDAL on the Windows machine that contains the raster, pastes the JSON report and file size back into Streamlit, receives evidence-based OAM checks and any required safe conversion command, then gets a metadata-prefilled link to the official uploader.

Path → OSGeo4W commands → pasted GDAL report → OAM diagnosis → optional/required local conversion → report verification → confirmed metadata → manual OAM upload.

## Upstream evidence and decisions

Checked hotosm/openaerialmap main at commit e20d1146059aab1408f1ae35755ff19982359048 (3 November 2026):

- Uploader integration and prefill fields: backend/uploader-api/README.md.
- Upload form and its metadata fields: backend/uploader-api/app/templates/upload.html.
- Upload API metadata keys/content types: backend/uploader-api/app/uploads/schemas.py.
- Upload ceiling: backend/uploader-api/app/config.py (MAX_UPLOAD_BYTES = 100 * 1024**3).
- Raster validation: backend/uploader-api/pipeline/validate/validate.py.
- Server-side COG conversion: backend/uploader-api/pipeline/convert/convert.py.
- GSD, footprint and STAC generation: backend/uploader-api/pipeline/metadata/metadata.py.
- OAM extension v0.3.0: backend/stactools-hotosm/stac-extension/json-schema/v0.3.0/schema.json and docs/dev/ingest/schema.md.

Decisions:
- The app never opens the pasted path or claims it can access the user's local filesystem. It only generates shell commands and parses the report pasted by the user.
- The report command uses gdalinfo -json "path" | clip; a separate PowerShell command returns the exact local file size in bytes.
- OAM requires GeoTIFF input with a declared CRS; the current upstream default upload ceiling is 100 GiB and may be overridden by deployment configuration.
- OAM itself creates the published COG. A local COG is optional for an already-valid GeoTIFF; a separate COG GeoTIFF is generated when the source is not GeoTIFF or needs a verified CRS assignment.
- The app never guesses CRS, product type semantics, acquisition date, producer, platform, or license.
- OAM derives GSD and footprint from the raster; the app does not ask the user to invent either.
- The uploader prefill uses only documented URL-fragment fields. A local filesystem path is never passed as source_url.
- The user selects the local file and confirms upload in the official OAM uploader. No credentials or automatic upload are added.
- Preserve the native Streamlit appearance and the Discover & map workflow.

## Acceptance criteria

1. One pasted local path generates OSGeo4W Shell commands without requiring local Streamlit or GDAL access by the app.
2. The generated commands report GDAL version, copy complete gdalinfo -json output to the clipboard, and report file size in bytes.
3. The app parses a complete pasted GDAL JSON report and rejects incomplete or unrelated JSON with actionable feedback.
4. The app reports driver, dimensions, CRS, bands/types/color interpretation, compression/COG layout, decoded-size estimate, and current OAM checks.
5. Exceeding the upstream default 100 GiB upload ceiling is a preflight failure unless an OAM deployment override is confirmed; an unknown file size blocks the handoff until checked.
6. The checks align with current OAM ingestion: GeoTIFF driver, CRS, supported product types, 3–4 8-bit bands only for declared visual imagery, and deployment-configurable decoded-size guidance.
7. Non-GeoTIFF input gets a separate non-overwriting COG GeoTIFF command. A missing CRS gets no command until the user supplies a verified EPSG code; -a_srs assigns and does not reproject.
8. The output can be reinspected by repeating the path/report workflow.
9. A prebuilt COG is informational, not a prerequisite, when the input is already a valid GeoTIFF with CRS.
10. Metadata handoff confirms title, producer, platform, acquisition date, and accepted CC license. Product type override, sensor and contact are optional.
11. The handoff uses only documented uploader fields, contains no local path or source_url, and requires manual file selection and submission.
12. The app explains that OAM computes GSD and footprint and performs server-side COG conversion.
13. Native Streamlit styling, navigation and Discover & map behavior remain unchanged.
14. Focused tests and repository CI pass; real OSGeo4W execution and a live OAM upload remain manual acceptance checks.

## Non-goals

- Opening or uploading local raster bytes from Streamlit.
- Requiring Streamlit to run on the same computer as the raster.
- Automatic OAM upload, publication, credentials, or status tracking.
- Requiring a local COG or generating a duplicate local STAC Item.
- Reprojecting, rescaling, changing band meaning, or assigning an inferred CRS.
- Changing the UI theme or the Discover & map workflow.

## Verification

Automated tests cover report parsing, OSGeo4W command generation, non-overwrite behavior, product suggestions, OAM upload-size checks, and metadata-prefill privacy. GitHub Actions must pass before merge. Real Windows GDAL output and a live OAM upload cannot be verified from hosted CI and must be reported separately.
