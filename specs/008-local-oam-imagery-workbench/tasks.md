# Tasks: Local Geospatial Imagery Workbench

- [x] Inspect repository instructions, active Hallmark UI branch, current local-preparation UI, tests, and OAM upstream validation/conversion/schema/uploader contracts.
- [x] Confirm the approved execution model: local GDAL/QGIS subprocesses; official OAM uploader prefill handoff; no authenticated API or automatic upload.
- [x] Add local GDAL tool discovery and safe `gdalinfo -json` inspection helpers.
- [x] Add product-aware OAM validation for visual and non-visual rasters, including OAM's product-specific decoded-size budgets.
- [x] Add guarded lossless COG preparation, output verification, and downsampled PNG preview.
- [x] Generate local STAC/OAM metadata sidecar using GDAL WGS84 extent and user-confirmed metadata; place OAM-required fields and STAC providers under Item `properties`.
- [x] Generate OAM uploader fragment prefill without local paths, credentials, or source_url.
- [x] Replace manual report-paste UI with inspect → validate → prepare → metadata → user-controlled OAM handoff.
- [x] Add focused unit tests for GDAL invocation, product-aware checks, COG safety, STAC property placement, thumbnails, sidecar writing, and prefill privacy.
- [x] Update README with local execution and limitations.
- [x] Run full unittest suite and browser smoke against the final branch head; inspect the complete diff and CI results (59 unit tests, UI dependency compatibility, and desktop/mobile browser smoke passed in GitHub Actions run #226).
- [x] Record real-machine GDAL/QGIS execution and live OAM upload as unverified; these remain manual acceptance steps on the user's machine.
