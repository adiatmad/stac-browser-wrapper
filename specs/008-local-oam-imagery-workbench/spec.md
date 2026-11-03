# Feature Specification: Local Geospatial Imagery Preparation and OAM Handoff

**Status:** Approved for implementation on `feat/local-oam-imagery-workbench`.

## User outcome

Turn the existing Local preparation workflow into a local-first geospatial imagery preparation and publication workbench. A user running Streamlit on the same computer as their imagery can inspect a raster with installed GDAL/QGIS, validate it against current OAM ingestion behavior, create a separate lossless COG and preview thumbnail, generate a local STAC/OAM metadata draft, and open the official OAM uploader with supported metadata prefilled.

## Evidence and decisions

- Repository guidance: `AGENTS.md`, `.specify/memory/constitution.md`, and the existing single-file hosted-app contract.
- OAM validation: `backend/uploader-api/pipeline/validate/validate.py`. A CRS is required; only declared `visual` products require 8-bit 3–4 band data. Other supported product types retain native values.
- OAM conversion: `backend/uploader-api/pipeline/convert/convert.py`. OAM performs its own server-side COG conversion; visual RGB(A) uses lossy JPEG q90, while other products use lossless native-dtype ZSTD.
- OAM item fields: `docs/dev/ingest/schema.md`. Required metadata includes GSD, platform type, producer, geometry/bbox, acquisition time, title, accepted CC license, producer-first providers, `assets.visual`, and the OAM v0.3.0 extension.
- OAM uploader integration: `backend/uploader-api/README.md#integrating-an-external-system`. A fragment prefill link can carry supported metadata without exchanging API credentials. Local files must still be selected by the user in the uploader.
- The existing app is a single-file hosted Streamlit entry point. Keep project-specific runtime logic in `app.py`; no new runtime package is required.

## Functional requirements

1. Detect `gdalinfo` and `gdal_translate` from PATH, an explicit GDAL bin directory, or common OSGeo4W/QGIS locations.
2. Run `gdalinfo -json` locally against a user-supplied path. Never upload or transmit raster bytes.
3. Display driver, dimensions, CRS, bands/types/color interpretation, bounds, block layout, overviews, compression/COG layout, file size, and estimated decoded size when computable.
4. Validate by declared OAM product type:
   - All supported types require a readable GeoTIFF and CRS.
   - `visual` requires 3–4 8-bit bands.
   - `multispectral`, `sar`, `elevation`, and `pseudocolor` retain native band count and data type.
   - Report uncertain color interpretation, missing WGS84 extent, unusually large decoded size, and non-COG layout as warnings rather than inventing facts.
5. Prepare a separate lossless COG using local GDAL, preserving source dimensions, band count, georeferencing, and data type. Refuse to overwrite source or existing output. Do not coerce arbitrary data to Byte or silently drop bands.
6. Generate a downsampled local PNG preview where GDAL can do so without changing the source raster.
7. Generate a local STAC/OAM metadata draft from GDAL's WGS84 extent plus user-confirmed metadata. Explicitly label the generated extent rectangle as a bbox-derived footprint and require user acknowledgement. Never infer acquisition time, producer, license, platform, or GSD.
8. Open the official OAM uploader using documented URL-fragment prefill fields. Do not include a local path as `source_url`, store credentials, call authenticated OAM APIs, or upload automatically. The user selects the local raster and confirms submission in OAM.
9. Keep the existing Discover & map workflow, UI navigation, hosted single-file app contract, and publication safeguards intact.

## Non-goals

- Replacing OAM's server-side COG conversion or claiming a locally generated COG is the final published OAM asset.
- Automatic upload, authenticated API calls, credential storage, or publication status tracking that requires an authenticated OAM integration.
- Reprojection, band remapping, rescaling, nodata edits, CRS assignment, or any other destructive/semantic raster transformation.
- Processing imagery in Streamlit Cloud or loading raster pixels into Streamlit memory.
- Building a full desktop GIS or replacing QGIS.

## Acceptance criteria

- [ ] The app detects local GDAL tools or explains how to launch it from OSGeo4W/QGIS shell or provide the GDAL bin directory.
- [ ] Inspect runs `gdalinfo -json` through argument-list subprocess calls (no shell interpolation) and reports actionable failures/timeouts.
- [ ] Product-aware validation accepts non-visual native data types and rejects invalid declared visual inputs.
- [ ] A prepared COG is a new file; source and existing outputs are never overwritten.
- [ ] Prepared output retains dimensions, band count, geotransform, CRS, and data type; GDAL reports COG layout.
- [ ] Thumbnail and STAC metadata sidecar are generated locally without uploading imagery.
- [ ] STAC metadata uses GDAL-derived EPSG:4326 extent and user-entered metadata only; it records `oam:footprint_source=bbox` and requires acknowledgement that this is not a traced valid-pixel footprint. OAM-required `gsd`, `oam:platform_type`, and `oam:producer_name`, plus the STAC `providers` array, are placed under Item `properties`. Missing required values remain missing and block the handoff.
- [ ] OAM prefill contains supported metadata fields but no local filesystem path or `source_url`; the user manually selects and submits the file.
- [ ] Existing hosted app single-file contract and Discover & map workflows remain intact.
- [ ] Focused tests and full unit tests pass; browser/CI evidence is reported separately from real local GDAL and real OAM upload acceptance.

## Safety invariants

1. Source imagery is read-only.
2. No overwrite, implicit deletion, or destructive raster transformation.
3. No CRS or capture metadata is guessed.
4. Raster bytes never leave the local GDAL process as part of inspection/preparation.
5. No OAM upload occurs without the user explicitly selecting the file and confirming in the official uploader.
6. Cloud-hosted Streamlit is never represented as having access to the user's local machine.

## Implementation plan

1. Add pure, bounded local GDAL helpers inline in `app.py`.
2. Replace the paste-a-report workflow with inspect → validate → prepare → metadata → official OAM handoff.
3. Add AST-isolated unit tests for GDAL discovery, subprocess safety, product-aware checks, output preservation, STAC geometry, and prefill URL privacy.
4. Update user documentation and the feature checklist.
5. Run unit tests and UI smoke/CI; inspect the complete diff. Mark local GDAL execution and real OAM upload as unverified unless actually performed on the user's machine.
