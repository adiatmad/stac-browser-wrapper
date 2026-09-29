# OAM v0.3.0 Visual Preflight

## Job
Help a user determine, locally and before upload, whether a raster is suitable for OAM's visual workflow and whether the metadata needed to publish an OAM STAC Item is complete.

## Non-goals
- Never upload imagery for validation.
- Never infer an unknown CRS.
- Never claim that a technically valid COG guarantees successful OAM publication.
- Never force elevation or multispectral data into a visual RGB product.

## Evidence
- Current OAM extension: `https://docs.imagery.hotosm.org/oam/v0.3.0/schema.json`
- Current schema documentation: `https://docs.imagery.hotosm.org/dev/ingest/schema/`
- Current OAM extension source: `backend/stactools-hotosm/stac-extension/README.md`

## Acceptance criteria
1. Local raster inspection remains GDAL-report based; no raster bytes leave the user's machine.
2. Raster readiness and OAM publication readiness are shown as separate gates.
3. Raster evidence includes driver, dimensions, CRS, bands, types, color interpretation, tiling, overviews, COG state, extent and relevant metadata.
4. OAM publication readiness checks current required fields: `gsd`, `oam:platform_type`, `oam:producer_name`, geometry, bbox, acquisition time, title, accepted license, producer/provider alignment, `assets.visual`, and the current OAM schema URL.
5. Missing metadata is reported as a concrete field-level action, not a generic warning.
6. OAM product types are not collapsed into visual-only validity; elevation, multispectral, SAR and pseudocolor remain legitimate product types.
7. Conversion commands create a new local file and never overwrite the source.
8. A conversion from non-Byte or undefined bands to visual RGB is explicitly presented as a user-confirmed candidate, not an automatic truth-preserving conversion.

## Verification
- Unit tests cover complete and incomplete OAM v0.3.0 metadata.
- Existing GDAL/OAM preflight tests remain green.
- Real GDAL reports remain the primary manual acceptance test.
