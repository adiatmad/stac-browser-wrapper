# Feature Specification: One-Path Local Raster-to-OAM Workflow

**Status:** Implemented on feature branch; verification pending  
**Branch:** `fix/one-path-local-oam-flow`

## Problem

The Local preparation screen regressed into a multi-control setup flow: users had to configure a GDAL directory, enter a raster path, and click a separate inspection button. It also promoted a separate DroneTM task-download/mosaic application in the same workflow, splitting attention instead of helping users finish the job they came to do.

## User outcome

A user running the app locally pastes one existing raster path and clicks **Inspect raster**. The app confirms that the file is accessible to the Streamlit process, inspects it with local GDAL, and then presents one continuous workflow:

**source raster → inspect → validate for OAM → prepare a safe COG → confirm metadata → open the official OAM uploader.**

The previous native Streamlit appearance remains unchanged.

## Decisions

- Keep this feature focused on an existing local raster. The source may be a DroneTM-produced orthomosaic, but this workflow does not own DroneTM task discovery or orthophoto downloads.
- Remove the separate DroneTM tool promotion and the "Separate DroneTM task-download and mosaic workflow" expander from this screen. Do not present a second application as a required step in the raster-to-OAM flow.
- Discover GDAL automatically from the environment, common QGIS/OSGeo4W locations, and PATH. Do not ask users to provide a GDAL bin directory in the normal workflow.
- Inspect only after an explicit **Inspect raster** form submission. Show actionable errors when the path is blank, missing, a directory, inaccessible to the Streamlit process, or GDAL is unavailable. Cache successful results in Streamlit session state so unrelated reruns do not repeatedly inspect a large raster.
- Keep the existing OAM product validation, safe COG generation, metadata confirmation, and official uploader handoff.
- Preserve explicit user review and submission in OAM. No credentials, source raster bytes, or automatic publication are added.

## Acceptance criteria

1. The user needs only the existing raster path and one explicit **Inspect raster** action; there is no GDAL directory field.
2. Submitting a valid path with **Inspect raster** runs local GDAL inspection and shows raster metadata.
3. A changed path triggers a new inspection; unrelated Streamlit reruns do not repeat the same inspection.
4. Blank, missing, directory, and inaccessible paths plus unavailable GDAL tools produce clear, actionable feedback; stale inspection results are never shown as belonging to a new path.
5. The separate DroneTM download/mosaic promotion and expander are absent from Local preparation.
6. The downstream OAM validation, lossless non-overwriting COG preparation, explicit metadata confirmation, and manual OAM uploader handoff remain available.
7. Source rasters are never overwritten, uploaded by this app, or automatically published.
8. Native Streamlit styling is preserved.
9. Focused contract tests and the repository CI pass.

## Non-goals

- Adding DroneTM API task discovery or orthophoto downloads to this existing-raster workflow.
- Automatically uploading or publishing to OAM.
- Changing OAM metadata semantics, GDAL conversion behavior, or the STAC discovery workflow.
- Introducing new runtime dependencies or changing the established visual theme.

## Verification

- Static/contract tests for one-path auto-inspection and absence of the separate DroneTM promotion.
- Full repository unit tests and CI.
- Real Windows verification with `D:\\orthobekasigeotiff.tif` and the user's installed GDAL/QGIS remains a deployment acceptance check; it cannot be claimed from GitHub CI alone.
