# Tasks: One-Path Local Raster-to-OAM Workflow

- [x] Inspect the current Local preparation UI, GDAL resolver, downstream OAM stages, README, and repository engineering constraints.
- [x] Remove the separate DroneTM tool promotion and workflow expander from this screen.
- [x] Remove the manual GDAL directory field and rely on automatic tool discovery.
- [x] Trigger local raster inspection automatically when a valid changed path is submitted.
- [x] Cache inspection by source path to avoid repeating GDAL work on unrelated reruns.
- [x] Preserve the downstream OAM validation, safe COG, metadata, and manual uploader stages.
- [x] Update the README to describe the one-path workflow.
- [x] Update contract tests for the new interaction contract.
- [ ] Run focused and full tests; inspect CI results.
- [ ] Verify the exact Windows path against the user's local GDAL/QGIS installation.
- [ ] Review the full diff for regressions and scope creep.
