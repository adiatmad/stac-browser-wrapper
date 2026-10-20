# Tasks: Single-File Hosted End-to-End Imagery Workflow

Tasks are gated. Do not claim production readiness, process large production imagery, or migrate any user data before the relevant acceptance gate passes.

## 1. Baseline and discovery
- [ ] 1.1 Identify and document exact existing test commands and CI workflows in both repositories.
- [ ] 1.2 Run both baseline test suites and record actual pass/fail results and environment versions.
- [ ] 1.3 Trace the STAC/OAM UI imports and the DroneTM task discovery, download/cache, raster validation, mosaic, report, and output validation call paths.
- [ ] 1.4 List all project-specific Python imports required by the existing app and map each to the implementation that must be inlined or preserved.
- [ ] 1.5 Identify current behavior that relies on persistent local files, Windows paths, OSGeo4W, Tkinter, or external services.
- [ ] 1.6 Record realistic Streamlit hosting constraints and define provisional caps; do not invent persistence guarantees.

## 2. Single-file processing functions
- [ ] 2.1 Adapt DroneTM functions from `mosaic_core.py` into `app.py` without changing API, retry, normalization, CRS, band, resampling, overlap, or report semantics without evidence.
- [ ] 2.2 Inline the required functions from `validate_imagery.py` and `utils/oam_sources.py` while preserving current STAC/OAM behavior.
- [ ] 2.3 Reconcile third-party dependencies in `requirements.txt` and verify compatible versions for Streamlit hosting.
- [ ] 2.4 Add synthetic GeoTIFF tests for valid/invalid inputs, output metadata, mosaic correctness, and candidate validation.
- [ ] 2.5 Add a static test that deployed `app.py` does not import project-specific Python modules.
- [ ] 2.6 Verify no code path calls an OAM upload or publish endpoint.

## 3. Bounded Streamlit workflow
- [ ] 3.1 Add project configuration and secure token entry without exposing credentials.
- [ ] 3.2 Add task discovery, task-status review, explicit selection, and explicit user confirmation before downloads.
- [ ] 3.3 Add bounded downloads with visible progress and accurate partial-failure reporting.
- [ ] 3.4 Add safe temporary workspace creation and cleanup scoped only to the current run.
- [ ] 3.5 Add candidate mosaic generation and validate the output before success.
- [ ] 3.6 Add metadata, preview, validation summary, and task-report downloads without unnecessary full-file memory copies.
- [ ] 3.7 Display honest warnings about ephemeral files/session state, interrupted operations, and tested limits.
- [ ] 3.8 Verify existing STAC/OAM screens, source discovery, metadata preflight, and explicit handoff still work.

## 4. Regression and safety verification
- [ ] 4.1 Run all existing STAC/OAM tests and document results.
- [ ] 4.2 Run all existing DroneTM processing and launcher-contract tests and document results.
- [ ] 4.3 Test failed downloads, corrupt inputs, missing CRS, incompatible raster dimensions/bands, and invalid outputs.
- [ ] 4.4 Test that invalid candidates never replace a previously validated artifact.
- [ ] 4.5 Test task-count, file-size, runtime, raster-dimension, and available-disk limits.
- [ ] 4.6 Test credential redaction in UI errors, logs, reports, and failure paths.
- [ ] 4.7 Test temporary cleanup cannot target unrelated folders or source imagery.
- [ ] 4.8 Assert the workflow makes no OAM upload/publish calls.
- [ ] 4.9 Inspect diffs for accidental changes to existing STAC/OAM behavior, local data assumptions, and unrelated features.

## 5. Hosted acceptance and delivery
- [ ] 5.1 Deploy the branch to a non-production Streamlit app and verify startup and dependency installation.
- [ ] 5.2 Run synthetic raster tests in the actual hosted runtime and record observed resource use.
- [ ] 5.3 Process a controlled real DroneTM project only if the synthetic tests and provisional limits pass.
- [ ] 5.4 Record actual tested raster dimensions, duration, peak memory/disk use, and known failure limits.
- [ ] 5.5 Document secrets configuration, temporary-file behavior, user download steps, failure recovery, and the local OSGeo4W fallback.
- [ ] 5.6 Open a reviewed pull request; do not merge or claim production readiness until required checks pass.
