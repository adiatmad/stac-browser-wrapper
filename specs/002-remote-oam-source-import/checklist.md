# Remote imagery to OAM v2 — Delivery Checklist

## Evidence
- [x] OAM uploader README checked.
- [x] OAM current ingestion/schema docs checked.
- [x] SpaceEye-T AWS Open Data registry checked.
- [x] S3 source is treated as public object storage, not an HTML scraping target.
- [x] Supplied Nepal prefix independently checked with recursive AWS CLI listing on 2026-09-24: ZIP products/previews exposed, no direct TIFF object.

## Safety
- [x] No imagery download or archive extraction is performed by the feature.
- [x] No source file is overwritten.
- [x] No acquisition date is guessed from LastModified.
- [x] Generic sources do not receive invented licenses.
- [x] OAM ingestion success is not guaranteed by the handoff.

## Behavior
- [x] S3 browser URL parses bucket, region, and prefix.
- [x] TIFF filtering works.
- [x] Archive-only sources are identified without extracting or downloading the archive.
- [x] Archive-only wording does not imply that the archive contains no raster; it means no direct raster object was exposed by S3 listing.
- [x] A read-only GDAL `/vsizip//vsicurl/` path is offered for local streaming of public archive members.
- [x] Supplied SpaceEye-T ZIP member path verified with GDAL: primary GeoTIFF, 29,560 × 36,720, WGS 84 / EPSG:4326.
- [x] Embedded TIFF timestamp `2026-08-30 04:37:53` recorded as source evidence without inventing a timezone or OAM acquisition timestamp.
- [x] Object URLs encode spaces and punctuation correctly.
- [x] OAM prefill carries source_url and verified SpaceEye-T metadata for direct TIFF objects only.
- [x] STAC workflow can create the same kind of handoff.
- [x] Supplied Nepal prefix is verified archive-only; no OAM handoff is generated for it.
- [x] Exploratory `aws s3 sync` was cancelled after preview files began downloading; bulk synchronization is not part of the feature.
- [x] Current OAM behavior checked: arbitrary imagery ZIP URLs are not accepted.
- [ ] Returned direct-TIFF URL publicly reachable under the OAM remote-source contract (no direct TIFF was exposed by the supplied prefix).
- [ ] One generated OAM v2 prefill link manually inspected in the browser.
- [x] OAM acquisition-date requirement is reflected in the handoff UX.

## Anti-slop
- [x] No new abstraction duplicates the existing preflight validator.
- [x] No decorative UI without a job.
- [x] Copy states concrete source facts and limitations.
- [x] No invented metrics or upload guarantees.
- [x] Saved GDAL JSON is parsed in Python rather than relying on PowerShell object deserialization.
