# Tasks

## Specify / clarify / plan
- [x] Define remote-source handoff outcome and non-goals.
- [x] Verify current OAM uploader remote-source behavior.
- [x] Verify SpaceEye-T license and public S3 source.
- [x] Choose direct S3 object URLs over browser-page scraping.
- [x] Record acquisition-date non-inference rule.

## Implementation
- [x] Add reusable public S3 source helpers.
- [x] Add S3 browser-prefix parsing.
- [x] Add TIFF filtering with MASKS/LINEAGE exclusion.
- [x] Add OAM v2 fragment prefill generation.
- [x] Add SpaceEye-T verified metadata profile.
- [x] Add remote source UI to existing app.
- [x] Prevent OAM handoff for arbitrary archive-only sources.
- [x] Add focused tests.
- [x] Add saved `gdalinfo -json` validation so users do not need PowerShell JSON parsing.

## Convergence
- [x] Run focused tests in the repository environment — 12/12 passing.
- [ ] Exercise the supplied live SpaceEye-T prefix and confirm it is currently archive-only.
- [ ] Confirm a direct TIFF URL is publicly reachable (if the source publishes one).
- [ ] Inspect one generated OAM prefill link manually.
- [x] Review diff for scope expansion and unsupported claims.
