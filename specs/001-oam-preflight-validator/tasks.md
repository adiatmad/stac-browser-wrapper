# Tasks

## Specify / clarify / plan
- [x] Define OAM visual preflight scope and explicit non-goals.
- [x] Record local-only imagery constraint.
- [x] Record hard-vs-recommended OAM semantics.
- [x] Record plain-text and JSON GDAL evidence as accepted inputs.
- [x] Record real ECW workflow as representative test case.

## Implementation
- [x] Add local-only GDAL metadata workflow.
- [x] Add validation helper.
- [x] Add plain `gdalinfo` parser.
- [x] Add Streamlit preflight UI.
- [x] Ensure missing CRS never triggers a guess.
- [x] Preserve 3/4 visual bands during conversion.
- [x] Use lossless DEFLATE for generated visual output.
- [x] Add current OAM decoded-size check.
- [x] Add focused automated tests for the supplied ECW report.

## Convergence
- [ ] Run the automated test suite.
- [ ] Run the generated command against the user's real ECW locally.
- [ ] Inspect the generated output with GDAL.
- [ ] Re-run the validator on the generated output.
- [ ] Compare final behavior against current OAM behavior.
- [ ] Review the diff for accidental scope expansion.
- [ ] Document any remaining limitations before merge.
