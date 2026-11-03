# Tasks: Local Geospatial Imagery Workbench

- [x] Inspect repository instructions, active Hallmark UI branch, current local-preparation UI, tests, and OAM upstream validation/conversion/schema/uploader contracts.
- [x] Confirm the approved execution model: local GDAL/QGIS subprocesses; official OAM uploader prefill handoff; no authenticated API or automatic upload.
- [ ] Add local GDAL tool discovery and safe `gdalinfo -json` inspection helpers.
- [ ] Add product-aware OAM validation for visual and non-visual rasters.
- [ ] Add guarded lossless COG preparation, output verification, and downsampled PNG preview.
- [ ] Generate local STAC/OAM metadata sidecar using GDAL WGS84 geometry and user-confirmed metadata.
- [ ] Generate OAM uploader fragment prefill without local paths, credentials, or source_url.
- [ ] Replace manual report-paste UI with inspect → validate → prepare → metadata → user-controlled OAM handoff.
- [ ] Add focused unit tests for helper behavior and safety invariants.
- [ ] Update README with local execution and limitations.
- [ ] Run full unittest suite and browser smoke; inspect complete diff and CI results.
- [ ] Record unverified real-machine GDAL/QGIS and live OAM upload checks; do not claim them as passed.
