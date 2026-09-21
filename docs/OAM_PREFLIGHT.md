# OAM Drone Imagery Preflight

This feature is a local pre-upload helper for visual drone orthomosaics.

## Workflow

1. Keep the raster on the user's computer.
2. Run `gdalinfo` locally; plain text or `gdalinfo -json` output is accepted.
3. Paste the complete output into the Streamlit preflight page.
4. Review PASS / WARNING / FAIL checks.
5. If the metadata is sufficient, copy one generated PowerShell command.
6. The command creates a new lossless COG GeoTIFF and never overwrites the source.

The app does not receive the raster bytes.

## Scope

The first version targets visual orthomosaics:

- 3-band RGB or 4-band RGBA
- Byte / 8-bit data
- valid CRS
- non-zero raster extent
- GeoTIFF as the final output
- COG output for efficient downstream access when local preparation is requested

DEM, multispectral, SAR and other non-visual products are intentionally outside this workflow.

## CRS safety

The tool never guesses a missing CRS. If `gdalinfo` reports no CRS, the user must enter the EPSG code that represents the source imagery. The resulting command then uses that supplied CRS for local preparation. The user is responsible for choosing the true source CRS.

## Compression

The generated visual COG uses DEFLATE rather than JPEG. This avoids introducing intentional lossy compression before upload. OAM may perform its own server-side processing after upload.

## Why COG is a warning rather than an upload blocker

Current OAM ingestion is designed to accept valid GeoTIFF input and handle conversion/transcoding as part of the ingestion pipeline. Therefore an already-existing COG is useful but is not treated as a prerequisite by this helper.

## Windows / QGIS GDAL setup

If QGIS is installed but `gdalinfo --formats` does not list ECW, configure the current PowerShell session to use QGIS's GDAL plugin and data directories:

```powershell
$qgis="C:\Program Files\QGIS 4.2.0"; $env:PATH="$qgis\bin;$qgis\apps\gdal\bin;"+$env:PATH; $env:GDAL_DRIVER_PATH="$qgis\apps\gdal\lib\gdalplugins"; $env:GDAL_DATA="$qgis\apps\gdal\share\gdal"
```

Then verify:

```powershell
gdalinfo --formats | Select-String "ECW|JP2ECW"
```

This is a shell-environment fix, not an application upload or raster-processing dependency. Do not copy individual GDAL/ECW DLLs from unrelated installations.

## Verified representative ECW

The representative test file supplied for this feature is readable through QGIS 4.2.0's GDAL 3.13.1 after the environment above is configured. GDAL reports:

- ECW driver, SDK 5.5
- 26482 × 25891 pixels
- EPSG:4326
- 4 Byte bands
- 256 × 256 blocks
- 7 overview levels per band
- WGS84 geographic extent
- `ColorInterp=Undefined` for all four bands

The last point is intentionally surfaced as a warning: GDAL's metadata does not prove that the four bands are RGB + alpha. The preflight therefore does not claim RGBA semantics automatically. The same warning remains after COG conversion unless the source already carries explicit RGB/RGBA color interpretation.

The decoded-size estimate is about 2.7 GB, comfortably below the current 130 GB OAM validation limit. This is an estimate from dimensions, band count and Byte storage, not the compressed ECW file size.

## Verification status

Automated regression tests cover the representative ECW metadata and command generation.

Manual verification has confirmed that the real ECW can be opened with GDAL after the QGIS environment is configured. The real ECW has now been converted locally to a GeoTIFF/COG. The generated output reports GTiff, 26482 × 25891, four Byte bands, 512 × 512 blocks, and seven overview levels per band. GDAL still reports `ColorInterp=Undefined`, so the preflight must keep this as a verification warning rather than asserting RGBA semantics. The final convergence step is to feed the complete output `gdalinfo` back through the preflight and review the final diff.
