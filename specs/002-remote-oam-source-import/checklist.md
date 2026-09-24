# Remote imagery to OAM v2 — Delivery Checklist

## Evidence
- [x] OAM uploader README checked.
- [x] OAM current ingestion/schema docs checked.
- [x] SpaceEye-T AWS Open Data registry checked.
- [x] S3 source is treated as public object storage, not an HTML scraping target.

## Safety
- [x] No imagery download is performed by the feature.
- [x] No source file is overwritten.
- [x] No acquisition date is guessed from LastModified.
- [x] Generic sources do not receive invented licenses.
- [x] OAM ingestion success is not guaranteed by the handoff.

## Behavior
- [x] S3 browser URL parses bucket, region, and prefix.
- [x] TIFF filtering works.
- [x] Object URLs encode spaces and punctuation correctly.
- [x] OAM prefill carries source_url and verified SpaceEye-T metadata.
- [x] STAC workflow can create the same kind of handoff.
- [ ] Live source listing verified against the public bucket.
- [ ] Returned TIFF URL publicly reachable.
- [ ] One generated OAM v2 prefill link manually inspected.
- [x] OAM acquisition-date requirement is reflected in the handoff UX.

## Anti-slop
- [x] No new abstraction duplicates the existing preflight validator.
- [x] No decorative UI without a job.
- [x] Copy states concrete source facts and limitations.
- [x] No invented metrics or upload guarantees.
- [x] Saved GDAL JSON is parsed in Python rather than relying on PowerShell object deserialization.
