# Tasks: Hosted End-to-End Imagery Workflow

Tasks are intentionally gated. Do not start production deployment or migrate imagery until the relevant acceptance gate passes.

## 1. Baseline and discovery
- [ ] 1.1 Identify and document the exact existing test commands and CI workflows in both repositories.
- [ ] 1.2 Run both baseline test suites and record pass/fail results and environment versions.
- [ ] 1.3 Trace DroneTM task discovery, download/cache, raster validation, mosaic, report, and output replacement call paths.
- [ ] 1.4 Identify code that depends on Streamlit/Tkinter, Windows paths, OSGeo4W, local environment files, or persistent local directories.
- [ ] 1.5 Decide the target hosting/worker/storage/authentication approach from evidence; document quotas and estimated costs before implementation.

## 2. Define and verify the processing boundary
- [ ] 2.1 Define a UI-independent request/result contract for a processing job.
- [ ] 2.2 Keep task selection, CRS decisions, band handling, resampling, overlap behavior, and output naming explicit.
- [ ] 2.3 Add unit tests around the extracted interface before changing its callers.
- [ ] 2.4 Verify existing local app and launcher workflows remain usable.
- [ ] 2.5 Confirm source imagery, local caches, credentials, and existing outputs are untouched by tests and refactoring.

## 3. Worker proof of concept
- [ ] 3.1 Build the smallest worker that accepts a validated synthetic-raster job.
- [ ] 3.2 Implement persistent job status and authorized artifact retrieval.
- [ ] 3.3 Implement scoped workspace creation and safe cleanup for a disposable test job.
- [ ] 3.4 Enforce runtime, disk, file-size, and concurrency limits.
- [ ] 3.5 Add sanitized error reporting and verify secrets never enter client responses/logs.
- [ ] 3.6 Run the synthetic job in the actual candidate hosting environment and record measured resource use.
- [ ] 3.7 **Gate:** stop if the host cannot support representative raster size or safe persistent storage.

## 4. Integrate the hosted UI
- [ ] 4.1 Add a DroneTM workflow entry to the existing Streamlit application without duplicating STAC/OAM behavior.
- [ ] 4.2 Add project/task review and explicit user confirmation before a job starts.
- [ ] 4.3 Add queued/running/succeeded/failed state handling and refresh-safe progress.
- [ ] 4.4 Add output metadata, validation summary, preview, and report downloads.
- [ ] 4.5 Keep OAM remote-source handoff separate and never invoke upload/publish automatically.
- [ ] 4.6 Add UI tests for empty, loading, success, failure, expired-job, and access-denied states.

## 5. Regression and safety verification
- [ ] 5.1 Run all existing STAC/OAM tests.
- [ ] 5.2 Run all existing DroneTM processing and launcher-contract tests.
- [ ] 5.3 Test download failure, corrupt input, incompatible CRS/bands, and invalid output.
- [ ] 5.4 Test that invalid candidates never replace a previous validated artifact.
- [ ] 5.5 Test job persistence, authorization, expiry, and cleanup isolation.
- [ ] 5.6 Test file-size/runtime/disk limits and concurrent job behavior.
- [ ] 5.7 Test secret redaction in logs, exceptions, reports, and browser responses.
- [ ] 5.8 Assert the processing workflow makes no OAM upload/publish calls.
- [ ] 5.9 Inspect diffs for accidental changes to source imagery, caches, credentials, local outputs, or unrelated features.

## 6. Acceptance and delivery
- [ ] 6.1 Deploy to a non-production environment and run smoke tests.
- [ ] 6.2 Process a controlled real DroneTM project only after synthetic and resource gates pass.
- [ ] 6.3 Record actual test commands/results, runtime, peak disk/memory use, and tested raster dimensions.
- [ ] 6.4 Document setup, secrets configuration, retention, limits, failure recovery, and rollback.
- [ ] 6.5 Open a reviewed pull request; do not merge or claim production readiness until required checks pass.
