# Implementation Plan: Single-File Hosted STAC/OAM App with Local DroneTM Handoff

## Strategy

Keep `stac-browser-wrapper` as the hosted Streamlit interface, with exactly one project-specific Python runtime file: `app.py`. Inline the required STAC/OAM helpers into that file so existing discovery, preflight, duplicate-checking, and explicit OAM handoff behavior is preserved.

DroneTM task discovery/download and raster processing stay in `adiatmad/dronetm-progress-mosaic`, run by the user on their own computer. Do not port `mosaic_core.py` into the hosted app. This keeps large raster processing, validated local caching, Windows launchers, and OSGeo4W/COG operations local, and avoids implying the hosted runtime can access a user's filesystem.

## Evidence inspected

- `AGENTS.md` and `.specify/memory/constitution.md`: evidence-first changes, small scope, local imagery safety, test actual behavior, and no unsupported success claims.
- `app.py`: existing hosted STAC/OAM workflow imports project-specific functions from `validate_imagery.py` and `utils/oam_sources.py`; these have now been inlined into `app.py` on the feature branch.
- `utils/oam_sources.py`: public S3 listing/classification, archive path helpers, evidence-backed SpaceEye metadata, and explicit OAM prefill links.
- `validate_imagery.py`: gdalinfo text parsing, visual preflight, and local conversion recommendation helpers used by the app.
- `tests/test_gdal_report.py`: diagnostic text is expected to preserve source pixel-type casing (`Float32`); implementation now keeps original casing for display while normalizing separately for comparisons.
- `dronetm-progress-mosaic/README.md`: local app handles task discovery/download/cache/mosaic/report; `rebuild_cog.bat` builds VRT and COG from existing local task rasters; no automatic OAM upload.
- `dronetm-progress-mosaic/tests/test_core.py`, `test_gui_contract.py`, and `test_local_launch_scripts.py`: local processor and launcher contracts remain the responsibility of that repository.

## Architecture and invariants

1. Hosted project-specific Python runtime logic stays in `app.py`; no runtime imports from `validate_imagery`, `utils.oam_sources`, or `mosaic_core`.
2. Third-party dependencies remain ordinary package imports. Do not add rasterio/numpy/Pillow to the hosted app solely for local DroneTM processing.
3. Preserve current STAC/OAM crawling, public S3 source discovery, metadata preflight, duplicate check, CSV export, and explicit OAM prefill behavior.
4. The hosted UI links to the maintained DroneTM repository and distinguishes the local app launch/update path from the local OSGeo4W COG rebuild path.
5. Do not ask for a DroneTM token, call DroneTM APIs, or claim the hosted app can read local Windows paths or invoke OSGeo4W.
6. No automatic OAM upload/publication. Any handoff to the OAM uploader remains a separate explicit user action.
7. Preserve local DroneTM source orthophotos, caches, credentials, and existing outputs; do not change its processing algorithm as part of this hosted-app feature.

## Implementation phases

### Phase A — Baseline and call graph
- Identify both repositories' exact test commands and CI workflows.
- Record actual CI outcomes and failures; do not infer success from a code write.
- Trace the helper functions used by the hosted STAC/OAM UI and the local DroneTM entry points.

### Phase B — Single-file hosted app and local handoff
- Inline the required STAC/OAM helpers into `app.py` without dropping existing UI behavior.
- Add a concise local DroneTM handoff section with the repository link and correct workflow distinction.
- Keep hosted dependencies scoped to the hosted STAC/OAM app.
- Add a static contract test that rejects project-specific runtime imports and checks the local handoff.
- Fix existing diagnostic casing mismatch without changing the test expectation.

### Phase C — Regression verification
- Run the existing STAC/OAM unit tests, including the new single-file contract test.
- Inspect the app diff for changes to source discovery, metadata preflight, duplicate checks, and explicit OAM handoff.
- Verify the hosted app does not process DroneTM imagery or handle DroneTM tokens.
- Check the local DroneTM repository's existing test workflow; do not claim local processing passed unless its CI result is available.

### Phase D — Hosted acceptance and delivery
- Verify the feature branch CI result and inspect any new failures.
- Verify the hosted app starts with the declared requirements in a non-production Streamlit deployment.
- Manually check that the local DroneTM repository link and launch/COG instructions are accurate.
- Keep the PR unmerged until required checks pass; do not claim hosted acceptance without actual deployment evidence.

## Main risks and mitigations

- **User confusion about execution location:** clearly label DroneTM processing as local and state that hosted Streamlit cannot access local Windows files or OSGeo4W.
- **Single-file constraint regresses existing features:** inline the helper implementations, retain tests, and inspect the diff against existing UI call paths.
- **False completion claims:** report CI and hosted-deployment results separately; do not treat repository edits as execution evidence.
- **Accidental publication:** keep OAM handoff explicit and do not add upload/publish calls to DroneTM processing.

## Exit gate

Do not claim implementation complete until STAC/OAM tests pass in CI, the static single-file contract passes, the hosted app starts successfully, the local DroneTM handoff is accurate, and the PR checks are green. Report the local DroneTM CI result separately from hosted-app checks.