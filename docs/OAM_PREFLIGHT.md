# OAM local imagery preflight

This workflow prepares an existing local raster for manual submission through the current HOT OpenAerialMap uploader.

## User workflow

1. Paste the local raster path into Local preparation.
2. Open QGIS / OSGeo4W Shell on the Windows machine that contains the raster.
3. Run the generated GDAL version, JSON inspection, and file-size commands.
4. Paste the complete JSON report and file size in bytes into the app.
5. Review raster and OAM checks.
6. If necessary, run a generated non-overwriting COG conversion command. A CRS is assigned only when the user supplies a verified EPSG code.
7. Reinspect the converted output by pasting its path and repeating the report step.
8. Confirm the OAM metadata fields and open the official uploader. Select the local file and submit there.

The Streamlit app does not open the local path, inspect local files, or receive raster bytes. The user runs GDAL locally and supplies its text report.

## Current upstream OAM contract

Evidence was checked against the main branch of hotosm/openaerialmap, commit e20d1146059aab1408f1ae35755ff19982359048 (3 November 2026):

- backend/uploader-api/README.md: upload and prefill integration contract.
- backend/uploader-api/app/templates/upload.html: current upload fields and local file selection.
- backend/uploader-api/app/uploads/schemas.py: accepted TIFF content types and metadata keys.
- backend/uploader-api/app/config.py: 100 GiB upload ceiling.
- backend/uploader-api/pipeline/validate/validate.py: GeoTIFF driver, CRS, product-type and decoded-size validation.
- backend/uploader-api/pipeline/convert/convert.py: server-side COG conversion and verification.
- backend/uploader-api/pipeline/metadata/metadata.py: GSD, footprint, acquisition metadata and STAC generation.
- backend/stactools-hotosm/stac-extension/json-schema/v0.3.0/schema.json and docs/dev/ingest/schema.md: current OAM STAC metadata contract.

OAM accepts GeoTIFFs and creates its own COG during ingestion. Local COG creation is optional for an already-valid GeoTIFF. The uploader's upstream default maximum file size is 100 GiB; deployment configuration may override it. OAM's current supported product types are visual, multispectral, SAR, elevation, and pseudocolor. A CRS is required. Only a declared visual product is constrained to 3–4 8-bit bands; non-visual products retain native data.

The OAM pipeline derives GSD from pixel resolution and CRS and generates the Item geometry/footprint from the raster mask or extent. The user must confirm title, producer, platform, acquisition date, and license. The current OAM extension accepts CC-BY-4.0, CC-BY-SA-4.0, and CC-BY-NC-4.0.

## Generated OSGeo4W commands

The app provides commands to:

- verify the active GDAL version;
- run gdalinfo -json and copy the complete report to the clipboard;
- retrieve the exact local file size in bytes;
- create a separate COG GeoTIFF when the input is not already a GeoTIFF or needs a verified CRS assignment;
- inspect the generated output and repeat the same report workflow.

The conversion command uses the COG driver, tiled DEFLATE compression, and a BigTIFF-safe setting. It refuses to overwrite an existing output and never edits the source. When -a_srs is used, it assigns the verified CRS without reprojecting coordinates. The user must not run that option with an inferred or guessed EPSG code.

## Product-type interpretation

The app's product-type suggestion is based on GDAL metadata and is not a substitute for understanding the source. OAM performs its own detection from raster metadata and, for some four-band inputs, pixel sampling. In particular, an undefined fourth band is not assumed to be alpha. SAR cannot reliably be inferred from band count and data type alone.

## Size checks

- Upload size: upstream default ceiling of 100 GiB; confirm any deployment override with OAM operators.
- Decoded size: deployment-configurable. The current upstream defaults are 130 GB for lossless conversion and approximately 216.7 GB for eligible 8-bit RGB(A) visual conversion. The local result is a preflight estimate, not a guarantee that a particular deployment will accept the file.

## OAM upload handoff

The handoff uses the documented URL fragment fields only. For local files it does not include source_url, because a local Windows path is not publicly reachable by OAM. The user chooses Upload a file, selects the local GeoTIFF, reviews the prefilled metadata, signs in if required, and submits manually.

No raster bytes, credentials, or automatic publication are handled by this app.
