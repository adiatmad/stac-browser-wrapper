# Tasks: Single-File Hosted STAC/OAM App with Local DroneTM Handoff

Tasks are gated. Do not claim tests passed without actual CI results. Do not merge or publish automatically.

## 1. Baseline and discovery
- [ ] 1.1 Identify the exact existing test commands and CI workflows in both repositories.
- [ ] 1.2 Record actual pass/fail results and the specific failing tests.
- [ ] 1.3 Trace the STAC/OAM imports and map project-specific helper functions required by the hosted UI.
- [ ] 1.4 Confirm the DroneTM local app already owns project URL resolution, task discovery/download, validated caching, mosaic/report generation, and OSGeo4W/COG rebuild behavior.
- [ ] 1.5 Confirm the hosted app does not need DroneTM API credentials or raster-processing dependencies.

## 2. Single-file hosted app
- [ ] 2.1 Inline required `validate_imagery.py` and `utils/oam_sources.py` implementations into hosted `app.py` without dropping STAC/OAM behavior.
- [ ] 2.2 Remove project-specific runtime imports from `app.py`; retain third-party imports and optional GDAL support as appropriate.
- [ ] 2.3 Add a concise DroneTM local-processing section linking to `adiatmad/dronetm-progress-mosaic`.
- [ ] 2.4 Explain the local app launch/update path separately from the OSGeo4W COG rebuild path.
- [ ] 2.5 Keep all OAM actions explicit; do not add automatic upload/publication.
- [ ] 2.6 Add/maintain static tests for the single-file runtime and local-handoff wording/links.

## 3. Regression and safety verification
- [ ] 3.1 Run all existing STAC/OAM tests and document results.
- [ ] 3.2 Run the DroneTM processing and launcher-contract tests and document results.
- [ ] 3.3 Resolve any CI failures with minimal, evidence-backed fixes; do not change tests just to hide implementation mismatches.
- [ ] 3.4 Inspect the app diff for regressions to STAC crawling, S3 source discovery, metadata preflight, duplicate checking, and explicit OAM handoff.
- [ ] 3.5 Verify no DroneTM token handling or DroneTM processing calls were added to the hosted app.
- [ ] 3.6 Verify no OAM upload/publish calls were added and local source/cache/output files remain untouched.

## 4. Hosted acceptance and delivery
- [ ] 4.1 Deploy the branch to a non-production Streamlit app and verify startup/dependency installation.
- [ ] 4.2 Manually verify the DroneTM repository link and local workflow instructions.
- [ ] 4.3 Record actual test/CI outcomes, remaining blockers, and the exact PR state.
- [ ] 4.4 Keep the PR unmerged until required checks pass; do not claim production readiness without hosted acceptance.
