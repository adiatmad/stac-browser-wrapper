# OAM Preflight Validator — Feature Specification

## Job
Help a drone imagery contributor determine whether a local visual RGB/RGBA raster is suitable for OAM upload, without uploading the source raster to this application, and provide one safe local command to prepare a new file when conversion is appropriate.

## In scope
- Visual RGB/RGBA drone orthomosaics.
- Local GDAL inspection using either plain `gdalinfo` output or `gdalinfo -json` output.
- User paste of GDAL metadata into the app; the raster itself is never uploaded.
- Diagnosis against current OAM visual validation behavior.
- Clear separation between hard OAM requirements, warnings/recommendations, and facts GDAL cannot prove.
- Source formats such as ECW may be inspected and converted locally to GeoTIFF/COG.
- One pasteable PowerShell command that creates a new output file without overwriting the source.
- Optional user-supplied EPSG only when the source CRS is missing and the user knows the true CRS.

## Out of scope
- DEM, multispectral, SAR, or other non-visual product workflows.
- Automatic CRS guessing.
- Uploading source imagery to this app for validation.
- JOSM/QGIS export helpers.
- Claiming that local preflight guarantees successful server-side OAM ingestion under every condition.

## Acceptance criteria
1. The app tells the user exactly what local GDAL command to run.
2. The user can paste either standard `gdalinfo` text or `gdalinfo -json` without uploading the raster.
3. The validator distinguishes current OAM hard validation requirements from informational/recommended checks.
4. Missing CRS blocks automatic conversion until the user supplies the true EPSG.
5. Generated commands never overwrite the source path by default.
6. RGB and RGBA band selection is preserved; alpha is not silently discarded.
7. Conversion uses lossless compression by default.
8. The output command is a single pasteable PowerShell command.
9. The UI does not claim that COG status alone determines OAM eligibility.
10. The current OAM decoded-size validation limit is surfaced when it can be estimated from GDAL metadata.
11. A representative real GDAL report from the user's ECW workflow is covered by an automated parser/validation test.
12. Before merge, the generated command is run locally against the real source and the output is inspected with GDAL.

## Evidence sources
- HOTOSM/OpenAerialMap current uploader validation code.
- HOTOSM imagery documentation where applicable.
- Real GDAL output supplied by the user.
