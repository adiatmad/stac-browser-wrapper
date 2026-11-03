# Tasks: One-Path Local Raster-to-OAM Workflow

- [x] Inspect the current Local preparation UI, GDAL resolver, downstream OAM stages, README, and repository engineering constraints.
- [x] Remove the separate DroneTM tool promotion and workflow expander from this screen.
- [x] Remove the manual GDAL directory field and rely on automatic tool discovery.
- [x] Trigger local raster inspection only after an explicit form submission.
- [x] Cache inspection by source path to avoid repeating GDAL work on unrelated reruns.
- [x] Replace silent invalid-path waiting text with actionable missing-path, non-file, hosted-app, and missing-GDAL feedback.
- [x] Preserve the downstream OAM validation, safe COG, metadata, and manual uploader stages.
- [x] Update the README to describe the one-path workflow.
- [x] Update contract tests for the new interaction contract.
- [x] Run unit tests: GitHub Actions unit job passed (58 tests).
- [x] Verify shadcn dependency compatibility: passed.
- [x] Complete desktop/mobile browser smoke; GitHub Actions run 238 passed.
- [ ] Verify the exact Windows path against the user's local GDAL/QGIS installation (requires the user's machine).
- [x] Review the full diff for regressions and scope creep.
