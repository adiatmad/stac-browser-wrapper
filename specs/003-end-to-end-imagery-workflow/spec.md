# Feature Specification: Single-File Hosted End-to-End Imagery Workflow

**Status:** Proposed; implementation not yet authorized by passing acceptance checks.
**Parent application:** `stac-browser-wrapper`
**Upstream processing reference:** `adiatmad/dronetm-progress-mosaic`

## 1. Problem and user outcome

The user currently has separate workflows for discovering/reviewing imagery through the STAC/OAM browser and retrieving completed DroneTM task orthophotos and building a mosaic. The user wants one hosted Streamlit application and one Python source file to guide the end-to-end workflow.

The hosted application should provide a single entry point for:
1. discovering/reviewing supported STAC imagery using existing behavior;
2. configuring a DroneTM project and selecting eligible task orthophotos;
3. explicitly downloading selected orthophotos and building a mosaic;
4. reviewing output metadata, validation results, preview, and task report;
5. explicitly downloading/exporting outputs.

## 2. Hosting and source-file constraints

- Hosting target: Streamlit-hosted app.
- Python application source: exactly one deployed project Python file, `app.py`.
- Do not add project-specific Python helper modules, worker services, API services, or a separate Python package.
- Non-Python deployment files such as `requirements.txt`, README, tests, and Streamlit configuration are permitted.
- Existing STAC/OAM helper behavior currently imported from `validate_imagery.py` and `utils/oam_sources.py` must be preserved by inlining the required implementation into `app.py` or by a clearly justified equivalent that keeps the existing user-visible behavior. Do not silently drop existing features to satisfy the file count.
- DroneTM processing behavior currently in `mosaic_core.py` must be adapted into functions in `app.py`; do not import that project-specific Python module at runtime.
- This is a single-file Streamlit application, **not** a persistent asynchronous job service. Work runs in bounded user-triggered operations in the Streamlit app process. The UI must communicate this honestly.
- Streamlit-hosted local disk and session state must be treated as ephemeral unless the hosting product explicitly guarantees persistence. Do not promise jobs or files will survive app restarts, sleeping, redeployments, or session loss.
- Do not claim that Streamlit hosting can invoke the user's local Windows filesystem or OSGeo4W Shell.

## 3. In scope

- Add a focused DroneTM workflow to the existing STAC wrapper without duplicating or unintentionally regressing its STAC/OAM functionality.
- Preserve the existing DroneTM API behavior for project slug/UUID resolution, task discovery and normalization, selected task downloads, raster validation, mosaic generation, preview, and task report.
- Keep project URL validation strict and allow the user to review task statuses and selection before downloading.
- Use a temporary, project-scoped workspace and conservative limits for task count, input bytes, output dimensions/size, and runtime where these can be enforced.
- Validate downloaded rasters and candidate mosaic output before presenting success.
- Keep progress and error messages visible during bounded operations; report unavailable or invalid orthophotos rather than silently counting them as complete.
- Use Streamlit secrets for server-configured credentials where appropriate, or a password input for a per-session token. Never expose bearer tokens in URLs, rendered client code, logs, reports, or exception text.
- Preserve the current STAC browser, remote-source discovery, metadata preflight, and explicit OAM handoff behavior.
- Keep any OAM remote-source handoff or publication a separate, explicit user action. No automatic OAM upload or publication is permitted.
- Document ephemeral storage and realistic raster-size limits; require a controlled representative-project test before claiming production readiness.

## 4. Out of scope

- Separate worker/API service, queue, external database, or persistent job service.
- Guarantees of cross-session job status or durable artifact storage without an explicitly configured and tested external storage system.
- Automatically uploading, publishing, or replacing imagery on OAM.
- Accessing the user's local Windows drive or invoking their OSGeo4W installation from the hosted app.
- Moving, deleting, or rewriting the user's existing local orthophotos, caches, virtual environments, credentials, or mosaic outputs.
- Rewriting mosaic algorithms or silently changing CRS, band, resampling, or overlap semantics.
- Claiming alpha-aware blending where the existing implementation uses standard raster merge priority.
- Supporting arbitrary archive extraction or new imagery sources without separate evidence and specification.

## 5. Functional requirements

**FR-001 — Single entry point and file.** The hosted app is one Streamlit app with one project Python source file, `app.py`, and preserves existing STAC/OAM user-visible workflows.

**FR-002 — Explicit project configuration.** A user can configure a valid DroneTM project URL, API base URL, route templates, timeout, and any required token. No processing begins until the user explicitly requests it.

**FR-003 — Task selection and provenance.** The app presents discovered task IDs and statuses, allows task selection, identifies cached/downloaded items within the current runtime, and reports unavailable, failed, or invalid orthophotos.

**FR-004 — Bounded processing.** Downloads and raster operations run only after explicit user action and within documented limits. The app must not imply durable asynchronous processing. If a job exceeds limits or the host cannot safely handle it, stop with an actionable error before exhausting resources.

**FR-005 — Safe temporary workspace.** Processing uses a temporary isolated workspace. It never mutates or deletes user-local files. It does not replace an existing validated final artifact with an invalid candidate. Since hosted disk may be ephemeral, the app warns that files may be lost when the process/session restarts.

**FR-006 — Raster correctness.** Validate source readability and required CRS, record output CRS, dimensions, bands, data type, source count and relevant processing parameters, and validate the candidate output before marking success. Do not invent CRS information or silently discard bands.

**FR-007 — Reviewable artifacts.** Successful processing exposes output metadata, a preview, validation summary and task report, with explicit downloads. Avoid unnecessary full-file in-memory copies where possible and enforce output-size limits.

**FR-008 — Credential safety.** Secrets are not embedded in client assets, query strings, exception messages, reports, or normal logs. Error output is sanitized.

**FR-009 — Existing behavior.** Existing STAC/OAM and DroneTM processing tests remain intact and pass, except for changes explicitly justified by this spec. Existing project-specific helper modules may be inlined, but their tested behavior must be retained.

**FR-010 — No automatic publication.** Processing, retries, success, and artifact download must never trigger an OAM upload or publication. Tests must assert this invariant.

**FR-011 — Resource limits.** Enforce and document realistic task-count, total download size, per-file size, runtime, raster dimension, output size, and concurrency limits to the extent supported by the selected Streamlit hosting environment. Do not imply one concurrent operation per user is globally guaranteed unless verified.

**FR-012 — Ephemeral-state honesty.** The UI and documentation state that session state and local temporary files are not durable storage. A browser refresh or app restart may interrupt processing or remove artifacts. Users must download outputs promptly.

**FR-013 — Single-file deployment check.** A repository check verifies that the deployed application entry point does not import project-specific Python files. Standard third-party dependencies remain declared in `requirements.txt`.

## 6. Acceptance criteria

- [ ] Existing STAC/OAM tests pass unchanged or have a documented, reviewed reason for updates.
- [ ] Existing DroneTM processing and launcher-contract tests are retained and run.
- [ ] Required STAC/OAM helper behavior is preserved after moving required functions into `app.py`.
- [ ] A repository check confirms there are no runtime imports of project-specific Python helper modules.
- [ ] Synthetic small GeoTIFFs can be validated and mosaicked by the app's processing functions.
- [ ] Failed downloads and invalid rasters are visible and do not silently count as successful inputs.
- [ ] An invalid candidate never replaces a validated output in the current workspace.
- [ ] Secrets do not appear in rendered output, URLs, logs, reports, or test failure output.
- [ ] Resource-limit handling and temporary-workspace cleanup are covered by tests.
- [ ] Tests verify that processing makes no OAM upload/publish calls.
- [ ] App messaging accurately describes ephemeral storage and the absence of durable background jobs.
- [ ] A controlled real DroneTM project is tested before production readiness is claimed.
- [ ] Deployment documentation records actual tested raster dimensions, runtime, peak memory/disk use, and known limitations.

## 7. Safety and preservation invariants

1. Never upload to OAM automatically.
2. Never modify or delete source orthophotos as part of processing.
3. Never present an invalid output as successful.
4. Do not migrate, clean, or otherwise mutate the user's existing local data as a side effect.
5. Do not log credentials or expose them to browser-visible output.
6. Do not claim large production imagery works until representative dimensions and resource use have been measured in the actual hosted environment.
7. Do not imply that Streamlit session state or local disk is durable storage.

## 8. Known trade-offs

A single-file Streamlit app avoids extra application modules and services, but it cannot provide reliable durable background jobs by itself. Large multi-task mosaics may exceed hosted resource quotas or interactive request limits. If the actual project exceeds the verified limits, the safe outcome is a clear limit/error message and a documented local OSGeo4W workflow—not an untested hidden worker or automatic upload.
