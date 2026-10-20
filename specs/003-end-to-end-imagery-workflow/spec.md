# Feature Specification: Hosted End-to-End Imagery Workflow

**Status:** Proposed; implementation not yet authorized by passing acceptance checks.
**Parent application:** `stac-browser-wrapper`
**Upstream processing reference:** `adiatmad/dronetm-progress-mosaic`

## 1. Problem and user outcome

A user currently has separate workflows for discovering/reviewing imagery through the STAC/OAM browser and for retrieving completed DroneTM task orthophotos and building a mosaic. The user wants one hosted browser application that guides them through a single end-to-end imagery workflow.

The hosted application should provide a single entry point for:
1. discovering/reviewing supported STAC imagery using existing behavior;
2. configuring a DroneTM project and selecting eligible task orthophotos;
3. submitting a long-running processing job and observing its status;
4. reviewing generated mosaic metadata, validation results, preview, and report;
5. explicitly downloading or exporting outputs.

## 2. User and operating environment

- Primary interface: hosted browser application based on the existing Streamlit STAC wrapper.
- Long-running raster work: a separate server-side worker with GDAL/rasterio and durable job/output storage.
- The hosted service cannot directly read the user's Windows filesystem or invoke their installed OSGeo4W Shell.
- Source imagery may be large. The hosting target, storage capacity, job limits, retention, and representative-raster feasibility must be verified before real-project processing is enabled.

## 3. In scope

- Add a focused DroneTM workflow to the existing STAC wrapper rather than duplicating its current STAC/OAM functionality.
- Reuse the existing DroneTM repository's processing logic where it can be separated from UI and local filesystem assumptions without changing semantics.
- Define a small job lifecycle: queued, running, succeeded, failed, and cancelled (cancellation only if safe for the selected worker/runtime).
- Keep job status, progress, failure reasons, output metadata, validation results, and report accessible to the user.
- Use server-side configuration/secrets for DroneTM credentials; never expose bearer tokens to browser-delivered code, URLs, or logs.
- Store source downloads and generated outputs in an explicit job-scoped workspace with documented retention and cleanup behavior.
- Validate raster inputs and candidate outputs before marking a job successful or promoting an output as the job's final artifact.
- Provide a preview and downloadable output/report after validation.
- Preserve existing STAC browser and OAM preflight/handoff behavior.
- Keep any OAM remote-source handoff or publication a separate, explicit user action. No automatic OAM upload or publication is permitted.

## 4. Out of scope

- Automatically uploading, publishing, or replacing imagery on OAM.
- Moving, deleting, or rewriting the user's existing local orthophotos, caches, virtual environments, credentials, or mosaic outputs.
- Accessing a user's local drive from the hosted service.
- Replacing Streamlit or undertaking a broad UI rewrite.
- Rewriting mosaic algorithms, silently changing CRS/band/resampling/overlap semantics, or claiming alpha-aware blending where none exists.
- Supporting arbitrary archive extraction or new imagery sources without separate evidence and specification.
- Production deployment to an unverified host before storage, runtime, security, and processing limits are tested.

## 5. Functional requirements

**FR-001 — Single entry point.** The existing application exposes the new DroneTM workflow while preserving current STAC/OAM workflows.

**FR-002 — Explicit project configuration.** A user can configure a DroneTM project URL and provide any required token through a secure server-side mechanism. A project is not processed until the user explicitly starts a job.

**FR-003 — Task selection and provenance.** The application presents discovered task statuses and identifies which tasks are selected for download. It reports unavailable, failed, or invalid orthophotos rather than silently treating them as complete.

**FR-004 — Asynchronous processing.** Long-running downloads and raster operations run outside the interactive web request. Job status and failure details remain queryable after a browser refresh.

**FR-005 — Safe job storage.** Each job has an isolated workspace. Existing job outputs are not overwritten until a newly generated candidate has passed required validation. Source files are not modified by mosaic processing.

**FR-006 — Raster correctness.** The worker validates source raster readability and compatibility, records the chosen output CRS and relevant processing parameters, and validates the candidate output before marking success. It must not invent CRS information or silently discard bands.

**FR-007 — Reviewable artifacts.** Successful jobs expose output metadata, a preview, validation result, and a task/download report, with download links scoped to authorized job access.

**FR-008 — Credential safety.** Secrets are not embedded in client assets, query strings, exception messages, or normal logs. Error output is sanitized.

**FR-009 — Existing behavior.** Current STAC, remote-source handoff, OAM preflight, and DroneTM processing tests remain intact and pass, except for changes explicitly justified by this spec.

**FR-010 — No automatic publication.** Job execution, success, retries, and output download must never trigger an OAM upload or publication. Tests must assert this invariant.

**FR-011 — Resource limits.** The worker enforces documented file-size, runtime, concurrency, and available-storage limits and reports when a job exceeds them.

**FR-012 — Retention and cleanup.** Temporary downloads and outputs follow a documented retention policy. Cleanup must be scoped to the relevant expired job workspace and must never target user-local folders or unrelated jobs.

## 6. Acceptance criteria

- [ ] Existing STAC/OAM tests pass unchanged or have a documented, reviewed reason for any update.
- [ ] Existing DroneTM processing and launcher-contract tests are retained and run in CI.
- [ ] A synthetic small-raster job can be submitted, polled, completed, and downloaded in the target worker environment.
- [ ] A failed download or invalid raster produces a visible failed/partial result and does not silently count as successful imagery.
- [ ] A failed or invalid candidate does not replace an existing final artifact.
- [ ] Refreshing the browser does not lose the job's reported state.
- [ ] Secrets do not appear in browser code, URLs, logs, reports, or test failure output.
- [ ] Resource limits and cleanup are covered by tests.
- [ ] Tests verify that the workflow does not call an OAM upload/publish endpoint.
- [ ] A representative real DroneTM project is processed in a controlled acceptance test before production readiness is claimed.
- [ ] Deployment documentation states actual tested limits and known raster-processing limitations.

## 7. Safety and preservation invariants

1. Never upload to OAM automatically.
2. Never modify or delete source orthophotos as part of processing.
3. Never overwrite a validated final artifact until a candidate passes validation; preserve the previous artifact or backup according to the job storage contract.
4. Do not migrate, clean, or otherwise mutate the user's existing local data as a side effect of this feature.
5. Do not log credentials or expose them to the browser.
6. Do not claim a hosted workflow works on large production imagery until it has been tested against representative raster dimensions and measured resource use.

## 8. Open decisions that block production deployment

- Hosting provider and worker execution model (persistent worker/container versus managed job service).
- Durable object storage provider, access controls, and retention duration.
- Maximum job size, runtime, concurrency, and disk-space budget based on a representative project.
- Authentication and authorization model for job status and downloads.
- Whether users may provide per-job DroneTM tokens or only server-configured credentials.
- Supported cancellation semantics for the selected worker.
- Whether the first release supports only downloadable GeoTIFF/report artifacts or also an optional VRT.

Do not guess these decisions. Resolve them during planning and the deployment proof of concept.