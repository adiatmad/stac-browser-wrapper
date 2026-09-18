# OAM Preflight Validator — Feature Specification

## Job
Help a drone imagery contributor determine whether a local visual RGB/RGBA raster is suitable for OAM upload, without uploading the source raster to this application, and provide one safe local command to produce a new OAM-ready file when conversion is appropriate.

## In scope
- Visual RGB/RGBA drone orthomosaics.
- Local GDAL inspection via `gdalinfo -json`.
- User paste of GDAL metadata into the app.
- Validation of CRS, dimensions, band count/type, color interpretation, georeferenced extent, and COG-related state.
- Source formats such as ECW may be inspected and converted to GeoTIFF/COG.
- A single pasteable PowerShell or Bash command sequence that writes a new output file.
- Optional user-supplied EPSG when the source CRS is missing and the user knows the true CRS.

## Out of scope
- DEM, multispectral, SAR, or other non-visual product workflows.
- Automatic CRS guessing.
- Uploading source imagery to this app for validation.
- JOSM/QGIS export helpers in this feature.
- A claim that a local command can guarantee successful OAM ingestion under every server-side condition.

## Acceptance criteria
1. The app tells the user exactly what local GDAL command to run.
2. The user can paste the resulting JSON without uploading the raster.
3. The validator distinguishes hard prerequisites from informational COG state.
4. Missing CRS blocks automatic conversion until the user supplies the true EPSG.
5. Generated commands never overwrite the source path by default.
6. RGB and RGBA band selection is preserved; alpha is not silently discarded.
7. Conversion uses lossless compression by default.
8. The output command is a single pasteable shell sequence.
9. The UI does not claim that COG status alone determines OAM eligibility.
10. Real GDAL output from at least one representative source format is used to verify the workflow before release.

## Evidence sources
- HOTOSM/OpenAerialMap repository and current ingestion behavior.
- HOTOSM imagery documentation where applicable.
- GDAL's actual `gdalinfo` output for real test imagery.
