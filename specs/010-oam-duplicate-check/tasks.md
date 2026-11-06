# Tasks: Complete and Safe OAM Duplicate Checks

- [x] Inspect repository instructions, duplicate-check implementation, UI result rendering, and CI test workflow.
- [x] Define bounded pagination, exact-ID matching, and inconclusive-result acceptance criteria.
- [x] Follow advertised same-endpoint HTTPS GET pagination links with a ten-page cap.
- [x] Replace title substring matching with exact STAC Item ID equality.
- [x] Keep spatial-overlap checks active across all fetched pages.
- [x] Distinguish complete no-match, inconclusive page-cap, missing bbox, and request failure states in the UI.
- [x] Add focused regression tests for later-page ID/spatial matches, false-positive title matches, pagination limits, unsafe links, and missing bbox.
- [ ] Run focused and full unit tests; inspect failures.
- [ ] Verify GitHub Actions unit, dependency compatibility, and browser smoke jobs.
- [ ] Inspect the complete diff and confirm OAM/local-raster safeguards are unchanged.
- [ ] Verify the live HOTOSM API pagination shape separately; do not infer live-service behavior from mocks.
