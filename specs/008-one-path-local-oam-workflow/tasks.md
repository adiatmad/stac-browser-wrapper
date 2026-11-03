# Tasks: OSGeo4W Report-Guided Local OAM Workflow

- [x] Inspect current wrapper implementation, tests, repository rules, and current HOTOSM/OpenAerialMap uploader and ingestion code.
- [x] Confirm current upstream OAM upload size, accepted input, product-type, metadata, COG, and prefill contracts.
- [x] Replace local Streamlit file inspection with path-driven OSGeo4W Shell commands and pasted GDAL JSON.
- [x] Add exact local file-size command and enforce the upstream default 100 GiB uploader ceiling.
- [x] Add report parser and OAM-aligned product-type suggestions.
- [x] Align raster validation: GeoTIFF, CRS, product-aware bands, decoded-size guidance, and non-mandatory local COG.
- [x] Generate guarded COG conversion command only when required or explicitly requested; require verified EPSG before CRS assignment.
- [x] Add report reinspection instructions for converted output.
- [x] Replace the clipboard pipe with a saved raw JSON report, explicit clipboard-copy command, and Notepad fallback.
- [x] Replace the Streamlit metadata form and prefill URL with a direct link to the official OAM uploader.
- [x] Route the legacy OAM preflight page to the unified workflow.
- [x] Update README, OAM preflight docs, specification, acceptance tasks, and focused regression tests.
- [x] Add focused OSGeo4W/report/OAM contract tests and update upload-size regression coverage.
- [ ] Run focused and full unit tests; inspect and fix failures.
- [ ] Verify GitHub Actions unit, dependency compatibility, and browser smoke jobs.
- [ ] Inspect complete PR diff for regressions, unsafe commands, and mismatch with upstream OAM.
- [ ] Manual Windows acceptance: run generated commands in the user's QGIS / OSGeo4W Shell and paste the actual GDAL report.
- [ ] Manual OAM acceptance: select and submit a valid local GeoTIFF in the official uploader; report result separately from CI.

- [x] Verify pasted GDAL report path against the path entered in the app; warn when GDAL omits an absolute path.
- [x] Require a usable affine geotransform for reliable OAM GSD/footprint metadata; warn on the identity transform.
- [x] Display per-band NoData and align decoded-size estimation with the upstream validator.
