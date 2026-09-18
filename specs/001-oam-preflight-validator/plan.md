# Implementation Plan

## Architecture
- Keep raster processing on the contributor's machine.
- Use Streamlit only for instructions, metadata parsing, validation display, and command generation.
- Keep validation logic in `utils/validate_imagery.py` so it can be tested independently of Streamlit.
- Keep the user-facing workflow in `pages/2_OAM_Preflight.py`.

## Decision rules
- OAM visual imagery is the target: RGB/RGBA, Byte/8-bit, georeferenced, valid CRS.
- Existing COG structure, internal tiling, and overviews are useful diagnostics but are not automatically treated as OAM upload blockers unless upstream evidence establishes that requirement.
- Missing CRS requires explicit user input for the true source EPSG.
- Generated output uses a new filename and lossless compression by default.

## Verification strategy
1. Unit-test metadata parsing and validation with small synthetic GDAL JSON fixtures.
2. Run the CLI/report workflow against a real ECW or GeoTIFF supplied by the user.
3. Inspect the generated command for band preservation and correct CRS semantics.
4. Run the generated command locally and inspect the resulting file with `gdalinfo -json`.
5. Re-run the validator on the resulting file.
6. Record any mismatch between expected and observed OAM behavior before changing rules.
