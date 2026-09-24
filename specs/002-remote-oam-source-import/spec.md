# Remote imagery source to OAM v2 — Feature Specification

## Job

Let a contributor take imagery already published at a public STAC asset URL or public S3 object URL and hand it to the current OAM v2 uploader without downloading and re-uploading the raster locally.

## User outcome

For each selected source image, the app should:
- identify the direct public GeoTIFF URL;
- show only metadata that is supported by source evidence;
- provide one OAM v2 prefilled handoff link;
- preserve the source URL so OAM fetches the imagery server-side;
- make review explicit before submission.

## In scope

- Existing STAC item/asset workflow.
- Public S3 bucket-browser URLs containing an encoded `#prefix=` fragment.
- Public S3 ListObjectsV2 discovery.
- Explicit source capability classification: `DIRECT_RASTER`, `ARCHIVE_ONLY`, or `EMPTY`.
- GeoTIFF filtering.
- Optional exclusion of `MASKS/` and `LINEAGE/` paths.
- OAM uploader fragment prefill using the documented `source_url` handoff only for direct raster objects.
- SpaceEye-T VVHR Open Data as a verified source profile:
  - provider: SI Imaging Services;
  - platform: satellite;
  - sensor: SpaceEye-T;
  - license: CC-BY 4.0.
- External/source ID derived from the stable S3 object key.
- No acquisition date inferred from S3 LastModified.

## Source capability rules

- `DIRECT_RASTER`: a public `.tif`/`.tiff` object is exposed; it may receive an OAM remote-source handoff.
- `ARCHIVE_ONLY`: the prefix exposes an archive such as ZIP but no direct raster object; no OAM handoff is generated.
- `EMPTY`: no supported raster/archive object is exposed.
- Arbitrary imagery ZIP extraction is deliberately not implemented here because current OAM does not accept arbitrary ZIP source URLs.

## Out of scope

- Downloading imagery into this app.
- Uploading imagery directly from this app.
- Automatic raster inspection of remote files.
- Automatic CRS/GSD inference from a remote object without running GDAL/OAM validation.
- Guessing acquisition timestamps.
- Guessing licenses for generic STAC/S3 sources.
- Building a new OAM API client when the documented uploader handoff already exists.

## Evidence

- Current OAM uploader supports public HTTPS `source_url` imports and documented fragment prefill fields.
- Current OAM uploader fetches remote GeoTIFFs server-side and runs its normal validation/conversion pipeline.
- SpaceEye-T AWS Open Data registry documents CC BY 4.0, the S3 bucket, and the dataset manager.
- Current OAM documentation says openly licensed imagery can be contributed through the uploader.

## Acceptance criteria

1. The user can paste the supplied SpaceEye-T S3 browser URL and classify the objects exposed under its prefix.
2. A direct-raster prefix produces HTTPS public object URLs with correct key encoding; an archive-only prefix produces no OAM handoff.
3. MASKS/LINEAGE artifacts can be excluded without hiding normal TIFFs.
4. Each selected direct SpaceEye-T TIFF object gets a prefilled OAM v2 link using its direct object URL.
5. The prefill includes only verified provider/platform/sensor/license values.
6. The UI makes clear that OAM requires a valid acquisition date; SpaceEye-T does not receive one unless source evidence provides it.
7. Acquisition start/end are absent unless the source supplies an acquisition timestamp.
8. The app never downloads or extracts an archive merely to prepare the OAM handoff.
9. STAC uploads continue to work and can use the same OAM prefill mechanism.
10. Unit tests cover URL parsing, object filtering, URL encoding, and metadata handoff.
11. The feature does not claim that a preflight or prefill guarantees OAM ingestion.

## Verification

- Run the focused Python tests.
- Exercise the supplied S3 browser URL against the live public bucket.
- Confirm at least one returned TIFF URL is reachable as a public HTTPS object.
- Open a generated OAM prefill link and inspect the populated fields before submitting.
- Keep raster validation in the existing local preflight or OAM server pipeline rather than inventing a second validator.
