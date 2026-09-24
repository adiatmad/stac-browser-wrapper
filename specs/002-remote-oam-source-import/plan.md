# Remote imagery source to OAM v2 — Implementation Plan

## Smallest architecture

1. Add `utils/oam_sources.py` for source discovery, S3 URL handling, and OAM prefill construction.
2. Add a source-mode branch to the existing Streamlit app.
3. Reuse the existing STAC metadata pipeline; add an OAM prefill handoff instead of another uploader implementation.
4. Add focused unit tests with no live network dependency.
5. Classify archive-only prefixes explicitly and verify that they cannot generate a misleading OAM handoff.

## Decisions

- Use public S3 ListObjectsV2 rather than scraping the HTML bucket browser.
- Treat S3 LastModified as object metadata only, not acquisition time.
- Use the AWS Open Data registry as the license authority for SpaceEye-T.
- Use OAM's documented fragment handoff only when the source exposes a direct TIFF URL.
- Do not add raster downloads, ZIP extraction, local transcoding, or a second OAM validation engine.
