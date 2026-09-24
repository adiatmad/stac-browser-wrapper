# Remote imagery source to OAM v2 — Implementation Plan

## Smallest architecture

1. Add `utils/oam_sources.py` for source discovery, S3 URL handling, and OAM prefill construction.
2. Add a source-mode branch to the existing Streamlit app.
3. Reuse the existing STAC metadata pipeline; add an OAM prefill handoff instead of another uploader implementation.
4. Add focused unit tests with no live network dependency.
5. Classify archive-only prefixes explicitly and verify that they cannot generate a misleading OAM handoff.
6. For archive-backed sources, add a standalone HTTP translation proxy that exposes a verified TIFF member as a real HTTPS resource without materializing the source ZIP.
7. Keep visualization/tile serving and permanent raster mirroring out of this feature; they are separate capabilities.

## Decisions

- Use public S3 ListObjectsV2 rather than scraping the HTML bucket browser.
- Treat S3 LastModified as object metadata only, not acquisition time.
- Use the AWS Open Data registry as the license authority for SpaceEye-T.
- Use OAM's documented fragment handoff only when the source exposes a direct TIFF URL.
- Do not download or extract source archives into the Streamlit app.
- Do not invent a `.TIF` URL from a ZIP member path.
- Do not pass GDAL `/vsizip//vsicurl/` paths to OAM.
- For ZIP STORE members, translate TIFF byte ranges directly to S3 ZIP byte ranges.
- For compressed ZIP members, stream the decompressed TIFF only where the HTTP contract remains honest; never claim linear Range support when it does not exist.
- Keep TiTiler and permanent extract-to-COG publishing outside this feature.
