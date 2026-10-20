# Implementation Plan: Hosted End-to-End Imagery Workflow

## Strategy

Keep `stac-browser-wrapper` as the user-facing application. Treat `dronetm-progress-mosaic` as the source of existing processing behavior, not as a directory to copy wholesale into the web app. Run long-running raster operations in a separate worker and communicate through a small job interface.

Do not implement production hosting until the proof of concept establishes that the chosen environment can process representative rasters within its storage, runtime, and memory limits.

## Evidence inspected

- `stac-browser-wrapper/AGENTS.md`: evidence-first changes, feature branches, focused scope, tests and real-workflow verification, no overwriting imagery, Spec Kit sequence.
- `stac-browser-wrapper/.specify/memory/constitution.md`: evidence, preservation of local data, verifiable delivery, anti-slop, explicit uncertainty.
- `stac-browser-wrapper/app.py`: current Streamlit interface, existing STAC/OAM flows, optional GDAL import.
- `stac-browser-wrapper/requirements.txt`: Streamlit, requests, Folium, streamlit-folium, Shapely; no existing worker/queue/object-storage dependency.
- `stac-browser-wrapper/specs/002-remote-oam-source-import/spec.md`: current remote-source handoff is explicit and must not become an automatic upload.
- `dronetm-progress-mosaic/README.md`: task discovery/download/cache, raster validation, mosaic and report behavior; Windows-first local app.
- `dronetm-progress-mosaic/requirements.txt`: Streamlit, requests, pandas, rasterio, numpy, Pillow.
- `dronetm-progress-mosaic/specs/local-one-click-workflow.md`: source-data preservation, candidate COG validation before replacement, no OAM upload, and retained tests.

## Architecture

1. **Web/UI layer:** existing Streamlit app. Add only project configuration, task/job initiation, job status, and validated-artifact review needed for the end-to-end user journey.
2. **Processing boundary:** extract or wrap processing functions behind a UI-independent interface. Avoid importing the legacy GUI/Streamlit entry point into the worker.
3. **Worker/job layer:** isolated process for long-running network and raster operations; persistent job state; controlled retries; sanitized errors; documented resource limits.
4. **Storage layer:** job-scoped persistent storage for downloaded orthophotos and output artifacts. Keep this distinct from repository files and any user's local Windows data.
5. **Validation layer:** reuse proven raster checks and validate candidate output before success. Record CRS, dimensions, bands, data type, and COG validation when a COG is produced.
6. **Publication boundary:** no OAM upload code is added to job execution. Existing explicit OAM handoff behavior remains separate.

## Minimal implementation phases

### Phase A — Baseline and processing contract
- Record existing test commands and results for both repositories.
- Inspect the complete processing call graph and identify UI, cache, path, and configuration coupling.
- Define typed inputs/results for project, selected tasks, job status, output artifacts, validation, and sanitized errors.
- Do not change processing semantics during extraction.

### Phase B — Worker proof of concept
- Select a target host only after documenting runtime, storage, network, and disk constraints.
- Run one synthetic raster job end to end in the worker environment.
- Verify persistence across worker/job polling and failure handling.
- Measure resource usage; do not use production imagery until the synthetic test passes.

### Phase C — Hosted integration
- Add the minimal UI and job API integration to the existing app.
- Preserve current STAC/OAM screens and their behavior.
- Add secure access controls for job status and artifact downloads.
- Keep job work out of the web request lifecycle.

### Phase D — Safety and acceptance
- Add tests for failed downloads, invalid rasters, candidate-output replacement, job persistence, resource limits, secret redaction, cleanup scope, and no automatic OAM publication.
- Run both existing test suites and all new tests.
- Conduct a controlled real-project acceptance test only after the hosting and security decisions are resolved.
- Document verified limits, manual deployment steps, and known limitations.

## Main risks and mitigations

- **Large rasters exceed hosted quotas:** benchmark with representative dimensions and enforce preflight storage/runtime limits.
- **Web process timeout or memory exhaustion:** use a separate worker and bounded concurrency.
- **Local/hosted storage confusion:** use explicit job-scoped paths/object keys; never reference user-local Windows paths from hosted code.
- **Credential leakage:** server-side secret handling, redaction tests, no tokens in URLs or client state.
- **Behavior changes during extraction:** preserve processing semantics and require regression tests before integration.
- **Accidental OAM publication:** keep upload out of worker flow and assert no upload calls in tests.

## Exit gate

Proceed to full integration only when baseline tests are recorded, the processing boundary is understood, and the synthetic worker job passes in the proposed hosting environment. Production readiness requires representative-raster evidence and a controlled real-project acceptance test.