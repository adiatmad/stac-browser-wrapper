# Implementation Plan

## Architecture
- Keep raster processing entirely on the contributor's machine.
- Use Streamlit only for instructions, metadata parsing, validation display, and command generation.
- Keep validation logic in `validate_imagery.py` so it can be tested independently of Streamlit.
- Keep the user-facing preflight workflow in the existing `app.py`.

## Decision rules
- Target product is OAM `visual`: 3 or 4 Byte/uint8 bands.
- Current OAM validation requires a CRS and applies a decoded-size limit; these are hard checks.
- Source format may need local conversion to GeoTIFF before OAM validation. ECW is therefore a valid inspection source but not treated as an OAM upload target.
- Existing COG structure, internal tiling, and overviews are diagnostics/recommendations, not automatic OAM hard blockers.
- Color interpretation is evidence: undefined interpretation must remain a warning requiring band-order confirmation, not be silently promoted to RGB/RGBA.
- Missing CRS requires explicit user input for the true source EPSG; never guess.
- Generated output uses a new filename and lossless DEFLATE compression.
- Plain `gdalinfo` and JSON are both accepted because the user's normal local workflow naturally produces the plain report.

## Verification strategy
1. Update the living spec before implementation changes.
2. Run focused parser/validation tests using the supplied ECW report.
3. Inspect the generated command for band preservation, lossless compression, and CRS semantics.
4. Run the command locally against the real ECW.
5. Inspect the generated output with `gdalinfo`.
6. Paste the final output back into the validator and confirm the result.
7. Compare the final behavior against current OAM source before merge.
8. Run the anti-slop delivery gate: no unsupported claims, no unnecessary UI, no duplicate logic, and clear error/recovery states.
