# Feature Specification: Single-File Hosted STAC/OAM App with Local DroneTM Handoff

**Status:** Implementation in progress on PR #8. CI is green on the latest checked commit; hosted Streamlit deployment has not yet been verified.

## 1. User outcome

Keep the hosted STAC browser as the single entry point for STAC/OAM discovery and preflight, while giving users a clear route to the separate local DroneTM processing tool. The hosted app must use one project-specific Python runtime file (`app.py`).

DroneTM task orthophoto downloads, local cache, mosaic generation, reports, and OSGeo4W/COG rebuilding run on the user's own computer through `adiatmad/dronetm-progress-mosaic`. This is intentional: large raster processing should not be moved into the Streamlit host, and the hosted app cannot access a user's Windows files or OSGeo4W shell.

## 2. Hosting and source-file constraints

- The hosted interface runs as a Streamlit app with `app.py` as its only project-specific Python runtime file.
- Required STAC/OAM behavior previously imported from `validate_imagery.py` and `utils/oam_sources.py` is inlined into `app.py`; the hosted entry point must not import project-specific Python modules.
- Existing helper modules, CLI scripts, tests, and non-Python deployment files may remain in the repository for testing or local use. The constraint is the hosted app's runtime entry point, not deletion of useful local tooling.
- DroneTM processing remains in the separate local-first repository. Do not import or port `mosaic_core.py` into the hosted app.
- The hosted app must not ask for DroneTM API tokens, call DroneTM processing APIs, or imply that local processing is happening on Streamlit.
- Third-party packages are allowed when declared in `requirements.txt`; do not add rasterio/numpy/Pillow to the hosted app solely for local DroneTM work.

## 3. In scope

- Preserve existing STAC crawling, item/asset parsing, public S3 source discovery, source classification, archive-source helpers, metadata preflight, OAM duplicate checking, CSV audit export, and explicit OAM prefill handoff.
- Add a concise hosted UI section linking to the local DroneTM repository.
- Explain the two local DroneTM workflows distinctly:
  - Launch/update the local app to discover tasks, review statuses, download selected orthophotos, validate/cache files, build a mosaic, and review the report/preview.
  - Run `rebuild_cog.bat` with OSGeo4W/QGIS on Windows to rebuild `mosaic.vrt` and a physical COG from already-downloaded local `task_*.tif` files.
- Keep the local DroneTM repository's existing processing and launcher tests intact.
- Fix the GDAL diagnostic casing mismatch by retaining original pixel-type spelling for human-readable details while normalizing values separately for comparisons.
- Add tests for the single-file runtime contract, syntax, and local DroneTM handoff.

## 4. Out of scope

- Running DroneTM task downloads or raster mosaicking on the hosted Streamlit server.
- Copying the local DroneTM processing stack into the hosted app.
- Accessing the user's local Windows drive or invoking their OSGeo4W installation from the hosted app.
- Automatically uploading, publishing, or replacing imagery on OpenAerialMap.
- Modifying or deleting local source orthophotos, caches, credentials, virtual environments, or existing mosaic outputs.
- Changing mosaic CRS, band, resampling, or overlap semantics in the local DroneTM tool.
- Claiming the hosted app or local processing is production-ready without the relevant test/acceptance evidence.

## 5. Functional requirements

**FR-001 — Single hosted entry point.** The hosted Streamlit application uses `app.py` as its only project-specific Python runtime file and preserves the existing STAC/OAM user-visible workflow.

**FR-002 — No project-specific runtime imports.** `app.py` must not import `validate_imagery`, `utils.oam_sources`, `mosaic_core`, or another project-owned Python module. Required STAC/OAM helper behavior must be inlined rather than silently removed.

**FR-003 — Local DroneTM handoff.** The app links to `https://github.com/adiatmad/dronetm-progress-mosaic` and explicitly says DroneTM downloads and raster processing run on the user's computer, not in hosted Streamlit.

**FR-004 — Correct local workflow instructions.** The UI distinguishes task download/mosaic generation in the local DroneTM app from rebuilding a COG from existing orthophotos with `rebuild_cog.bat` and OSGeo4W/QGIS.

**FR-005 — Preserve data and processing.** The hosted feature does not modify local data. The local DroneTM tool retains its current validated cache, task failure reporting, mosaic/report generation, and COG candidate validation behavior.

**FR-006 — Explicit OAM handoff.** The hosted app may prepare a prefilled OAM handoff link for user review, but no upload or publication occurs automatically.

**FR-007 — Test honesty.** Report actual CI results separately from hosted deployment and real-project acceptance. A passing unit-test workflow does not prove Streamlit deployment or real DroneTM connectivity.

## 6. Acceptance criteria

- [ ] Hosted `app.py` parses as valid Python.
- [ ] Static tests verify no project-specific Python imports in the hosted entry point.
- [ ] CI runs the existing STAC/OAM test suite plus the new contract tests and passes.
- [ ] STAC/OAM helper behavior remains consistent with existing tested behavior after inlining.
- [ ] The DroneTM handoff link and local-vs-hosted distinction are present and accurate.
- [ ] The local DroneTM test workflow remains green on its current source revision; do not imply this validates the hosted app.
- [ ] Diff review confirms no automatic OAM upload/publication and no changes to local imagery/cache/output data.
- [ ] Hosted Streamlit startup is manually verified before claiming deployment readiness.

## 7. Safety invariants

1. Never upload to OAM automatically.
2. Never imply the hosted app can access local Windows files or OSGeo4W.
3. Never collect or forward a DroneTM token in the hosted app.
4. Never delete, overwrite, or migrate the user's local orthophotos, cache, credentials, or mosaic outputs as a side effect.
5. Never claim tests, deployment, or real-project behavior succeeded without evidence.

## 8. Known trade-off

The hosted app provides a guided entry point, not a single remote raster-processing service. Users run DroneTM processing locally. This preserves the local-first workflow and avoids unreliable large-raster processing or misleading file-access promises in the Streamlit runtime.