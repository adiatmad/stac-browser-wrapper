# Feature Specification: Single-File Hosted End-to-End Imagery Workflow

**Status:** Proposed; implementation not yet authorized by passing acceptance checks.
**Parent application:** `stac-browser-wrapper`
**Upstream processing reference:** `adiatmad/dronetm-progress-mosaic`

## 1. Problem and user outcome

The user currently has separate workflows for discovering/reviewing imagery through the STAC/OAM browser and retrieving completed DroneTM task orthophotos and building a mosaic. The user wants one hosted Streamlit application and one Python source file to guide the end-to-end workflow.

The hosted application should provide a single entry point for discovering/reviewing supported STAC imagery and guiding users to the separate, user-run DroneTM processing workflow for task downloads and mosaic creation.

DroneTM orthophoto downloads and mosaic generation are deliberately run on the user's own computer using the maintained `adiatmad/dronetm-progress-mosaic` project. The hosted app must not download or process DroneTM orthophotos, accept DroneTM tokens, or pretend it can access the user's local files. This keeps large raster processing on the user's machine and preserves the tested local cache and OSGeo4W/COG workflow.

## 2. Hosting and source-file constraints

- Hosting target: Streamlit-hosted app.
- Python application source: exactly one deployed project Python file, `app.py`.
- Do not add project-specific Python helper modules, worker services, API services, or a separate Python package.
- Non-Python deployment files such as `requirements.txt`, README, tests, and Streamlit configuration are permitted.
- Existing STAC/OAM helper behavior currently imported from `validate_imagery.py` and `utils/oam_sources.py` must be preserved by inlining the required implementation into `app.py` or by a clearly justified equivalent that keeps the existing user-visible behavior. Do not silently drop existing features to satisfy the file count.
- DroneTM processing remains in the separate `adiatmad/dronetm-progress-mosaic` local-first project; do not copy its processing stack into the hosted app.
- The hosted app is a single-file Streamlit interface for STAC/OAM plus clear links and instructions for the user-run DroneTM workflow. The local DroneTM app is separately run by the user and may retain its own source files and local cache.
- STAC/OAM network requests remain user-triggered in the hosted app. The app must not claim that it can invoke the user's local Windows filesystem or OSGeo4W Shell.
- The local DroneTM app must keep its established behavior: user-triggered task discovery/download, validated local caching, mosaic/report generation, explicit local outputs, and no automatic OAM upload.

## 3. In scope

- Add a clear, concise DroneTM local-processing section to the hosted STAC wrapper, linking to the existing local-first repository and explaining the supported local launch/rebuild paths.
- Preserve the existing DroneTM API, caching, raster validation, mosaic, preview/report and OSGeo4W/COG behaviors in `adiatmad/dronetm-progress-mosaic`; avoid rewriting this working processing stack in the hosted app.
- Make it clear that task download and mosaic generation happen on the user's computer, not on Streamlit hosting.
- Preserve the current STAC browser, remote-source discovery, metadata preflight, and explicit OAM handoff behavior.
- Keep any OAM remote-source handoff or publication a separate, explicit user action. No automatic OAM upload or publication is permitted.
- Document ephemeral storage and realistic raster-size limits; require a controlled representative-project test before claiming production readiness.

## 4. Out of scope

- Running DroneTM task downloads or raster mosaicking on the hosted Streamlit server.
- Copying the local DroneTM processing stack into the hosted app.
- Guarantees of cross-session job status or durable artifact storage.
- Automatically uploading, publishing, or replacing imagery on OAM.
- Accessing the user's local Windows drive or invoking their OSGeo4W installation from the hosted app.
- Moving, deleting, or rewriting the user's existing local orthophotos, caches, virtual environments, credentials, or mosaic outputs.
- Rewriting mosaic algorithms or silently changing CRS, band, resampling, or overlap semantics.
- Claiming alpha-aware blending where the existing implementation uses standard raster merge priority.
- Supporting arbitrary archive extraction or new imagery sources without separate evidence and specification.

## 5. Functional requirements

**FR-001 — Single entry point and file.** The hosted app is one Streamlit app with one project Python source file, `app.py`, and preserves existing STAC/OAM user-visible workflows.

**FR-002 — DroneTM local handoff.** The hosted app links to the maintained local DroneTM repository and explains that the user must run it on their own computer. It does not collect DroneTM tokens or call DroneTM processing APIs.

**FR-003 — Local workflow clarity.** Instructions distinguish launching/updating the local app from rebuilding the COG using existing local orthophotos. They mention local cache/output locations only where supported by the upstream README and make no claim that hosted Streamlit can access those files.

**FR-004 — Processing provenance and safety.** The local DroneTM tool remains responsible for task statuses, selected downloads, validated caching, failure reporting, mosaic metadata, preview, and report. Preserve source files and do not automatically upload to OAM.

**FR-005 — Existing behavior.** Existing STAC/OAM and DroneTM processing tests remain intact and pass, except for changes explicitly justified by this spec. Existing project-specific helper modules may be inlined, but their tested behavior must be retained.

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
