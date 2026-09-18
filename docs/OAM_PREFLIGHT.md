# OAM Drone Imagery Preflight

This feature is a local pre-upload helper for visual drone orthomosaics.

## Workflow

1. Keep the raster on the user's computer.
2. Run the displayed `gdalinfo -json` command locally.
3. Paste the JSON result into the Streamlit preflight page.
4. Review PASS / WARNING / FAIL checks.
5. If the metadata is sufficient, copy one generated PowerShell command.
6. The command creates a new lossless COG GeoTIFF and never overwrites the source.

## Scope

The first version targets visual orthomosaics:

- 3-band RGB or 4-band RGBA
- Byte / 8-bit data
- valid CRS
- non-zero raster extent
- GeoTIFF as the final output
- COG output for efficient downstream access

DEM, multispectral, SAR and other non-visual products are intentionally outside this workflow.

## CRS safety

The tool never guesses a missing CRS. If `gdalinfo` reports no CRS, the user must enter the EPSG code that represents the source imagery. The resulting command then reprojects/assigns that CRS before creating the final COG. The user is responsible for choosing the true source CRS.

## Compression

The generated visual COG uses DEFLATE rather than JPEG. This avoids introducing intentional lossy compression before upload. OAM may perform its own server-side processing after upload.

## Why COG is a warning rather than an upload blocker

Current OAM ingestion is designed to accept valid GeoTIFF input and handle conversion/transcoding as part of the ingestion pipeline. Therefore an already-existing COG is useful but is not treated as a prerequisite by this helper.
