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
- [x] Expose a read-only GDAL `/vsizip//vsicurl/` path for public imagery ZIPs without extracting them in the app.
- [x] Add focused tests — 16/16 passing locally.
- [x] Add saved `gdalinfo -json` validation so users do not need PowerShell JSON parsing.

## Convergence
- [x] Run focused tests in the repository environment — 16/16 passing.
- [x] Exercise the supplied live SpaceEye-T prefix via ListObjectsV2/AWS CLI — recursive listing exposes ZIP products and no direct TIFF object; classified as archive-only.
- [ ] Confirm a direct TIFF URL is publicly reachable (not applicable to the supplied archive-only prefix; required before claiming a live direct-raster handoff).
- [ ] Inspect one generated OAM prefill link manually in the browser.
- [x] Review diff for scope expansion and unsupported claims.
- [x] Distinguish archive contents from direct OAM-compatible object discovery.
- [x] Verify the supplied SpaceEye-T ZIP contains a primary GeoTIFF member via remote GDAL `/vsizip//vsicurl/` access.
- [x] Record the verified member path and embedded TIFF timestamp without treating the timestamp as timezone-qualified OAM acquisition metadata.
- [x] Cross-check the public prefix with AWS CLI recursive listing; do not introduce a bulk `aws s3 sync` dependency.
