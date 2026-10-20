# Implementation Plan: Single-File Hosted End-to-End Imagery Workflow

## Strategy

Keep `stac-browser-wrapper` as the user-facing Streamlit application with exactly one hosted project Python source file, `app.py`. Preserve its STAC/OAM features by inlining the required project-specific helper implementations. DroneTM raster processing stays in `adiatmad/dronetm-progress-mosaic` and is run by the user on their own computer. The hosted app provides a local-workflow handoff section; it does not download DroneTM imagery, process rasters, or ask for DroneTM credentials.

This split is intentional: large raster work stays local, where the existing cache, Windows launcher and OSGeo4W/COG workflow already live. The hosted app does not promise access to local files or persistent processing.

## Evidence inspected

- `stac-browser-wrapper/AGENTS.md`: evidence-first changes, feature branches, focused scope, tests and real-workflow verification, no overwriting imagery, Spec Kit sequence.
- `stac-browser-wrapper/.specify/memory/constitution.md`: evidence, preservation of local data, verifiable delivery, anti-slop, explicit uncertainty.
- `stac-browser-wrapper/app.py`: current Streamlit STAC/OAM interface; currently imports project-specific functions from `validate_imagery.py` and `utils/oam_sources.py`.
- `stac-browser-wrapper/requirements.txt`: Streamlit, requests, Folium, streamlit-folium, Shapely; third-party dependencies can remain external.
- `stac-browser-wrapper/validate_imagery.py`: existing imagery validation/recommendation implementation; required app behavior must be preserved if the module is no longer imported.
- `stac-browser-wrapper/utils/oam_sources.py`: existing public S3 source discovery, archive/source URL, metadata and explicit OAM handoff helpers; preserve applicable behavior.
- `stac-browser-wrapper/specs/002-remote-oam-source-import/spec.md`: current remote-source handoff is explicit and must not become an automatic upload.
- `dronetm-progress-mosaic/app.py`: existing Streamlit user flow for project config, task selection, download, mosaic, preview, and report.
- `dronetm-progress-mosaic/mosaic_core.py`: project URL/UUID handling, task normalization, retries, raster validation, download, mosaic, preview, and report functions to adapt into `app.py`.
- `dronetm-progress-mosaic/requirements.txt`: Streamlit, requests, pandas, rasterio, numpy, Pillow. Reconcile third-party dependencies without blindly copying incompatible version pins.
- `dronetm-progress-mosaic/specs/local-one-click-workflow.md`: source-data preservation, candidate COG validation before replacement, no OAM upload, and retained tests.

## Architecture

1. **One application file:** all project-specific runtime Python code lives in `app.py`. Standard installed packages are allowed. Do not import `validate_imagery`, `utils.oam_sources`, `mosaic_core`, or any other project-specific Python module at runtime.
2. **Existing STAC/OAM behavior:** inline the smallest necessary existing helper implementations into `app.py), preserving user-visible behavior and existing tests. Keep explicit OAM handoff separate from processing.
3. **DroneTM functions:** adapt functions from `mosaic_core.py` into clearly separated sections in `app.py`; preserve API routes, retry policy, task normalization, raster checks, CRS behavior, band behavior, overlap semantics, report columns, and safe candidate validation unless tests justify a change.
4. **Streamlit UI:** add the DroneTM workflow without removing or breaking current STAC/OAM features. Keep credentials in password inputs or Streamlit secrets, not URLs or logs.
5. **Temporary workspace:** use a per-run temporary directory and cleanup only that directory. Do not assume Streamlit's local disk persists between restarts or that session state is durable.
6. **Bounded processing:** preflight selection count, expected download size where discoverable, available temporary disk, raster dimensions and output estimates where feasible. Enforce conservative caps; avoid unbounded concurrency and avoid holding full raster arrays or GeoTIFF byte strings in memory.
7. **Validation:** test helper functions using synthetic rasters before integrating them with UI. Validate every downloaded raster and candidate mosaic; only present success after output validation.
8. **Publication boundary:** no OAM upload/publish code is added to the DroneTM processing path. Existing explicit OAM handoff behavior remains separate.

## Implementation phases

### Phase A — Baseline and call graph
- Identify exact test commands and CI workflows in both repositories.
- Run both baseline test suites and record actual results and environment versions.
- Inspect all imports and call paths used by the STAC/OAM UI and DroneTM processing.
- Identify which functions must be inlined and any naming collisions.
- Do not change application behavior until baseline results and compatibility requirements are recorded.

### Phase B — Single-file hosted app and local handoff
- Inline the STAC/OAM helper implementations required by `app.py`, preserving existing feature behavior and tests.
- Add the DroneTM local-workflow section with links and concise launch/COG instructions.
- Keep hosted requirements limited to dependencies used by the STAC/OAM app; do not add rasterio/numpy/Pillow solely for local DroneTM processing.
- Add a static check that `app.py` has no project-specific Python imports.

### Phase C — Local workflow handoff and documentation
- Make it explicit that DroneTM downloads and raster processing run on the user's computer.
- Explain the distinction between launching/updating the local DroneTM app and rebuilding a COG from existing local orthophotos.
- Preserve all existing STAC/OAM screens and explicit handoff behavior.
- Do not imply that the hosted app can access local Windows files, local cache, or OSGeo4W.

### Phase D — Regression and hosted acceptance
- Run existing STAC/OAM tests and existing DroneTM processing/launcher-contract tests.
- Add failure, resource-limit, credential-redaction, cleanup-isolation, single-file, and no-OAM-upload tests.
- Run synthetic-raster smoke tests in CI.
- Deploy to the selected Streamlit host and verify imports and app startup.
- Conduct a controlled real-project test only after synthetic and resource gates pass.
- Document verified limits, manual deployment steps, and known limitations.

## Main risks and mitigations

- **Large rasters exceed Streamlit limits:** keep DroneTM raster processing local; do not move it into Streamlit hosting.
- **Confusion about where work runs:** label the local DroneTM handoff clearly and link to the maintained repository.
- **Single file becomes hard to maintain:** use clear sections, small functions, explicit contracts, and tests; do not add unrelated features.
- **Inlining changes behavior:** baseline tests first and regression tests for existing STAC/OAM and DroneTM behaviors.
- **Credential leakage:** password inputs/server-side secrets, URL validation, sanitized exceptions, and redaction tests.
- **Accidental OAM publication:** keep upload outside the processing path and assert no upload calls in tests.

## Exit gate

Do not claim implementation complete until existing STAC/OAM tests and local DroneTM tests have actual recorded results, the hosted `app.py` has no project-specific Python imports, the UI handoff is accurate, and the hosted app starts successfully. Keep the local DroneTM project's own acceptance requirements visible; do not claim its real-project behavior was tested by the hosted app.
