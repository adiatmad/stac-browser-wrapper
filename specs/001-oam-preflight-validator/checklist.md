# OAM Preflight Delivery Checklist

## Evidence
- [x] Current OAM validation behavior checked against upstream source.
- [x] Real plain `gdalinfo` output supplied by the user is represented in tests.
- [x] Unsupported assumptions are distinguished from verified OAM behavior.

## Safety
- [x] Source imagery is never overwritten by generated commands.
- [x] Missing CRS never triggers an automatic guess.
- [x] RGB/RGBA bands are preserved.
- [x] Lossy compression is not introduced silently.
- [x] Plain GDAL output is accepted without requiring a different command.
- [ ] Generated PowerShell command has been executed successfully against real imagery.

## Behavior
- [x] Valid 3/4-band Byte visual imagery gets a clear result.
- [x] Invalid band count gets a clear failure and reason.
- [x] Missing CRS requests user-supplied EPSG.
- [x] ECW can be inspected without uploading it.
- [x] COG state is treated according to verified OAM behavior.
- [x] OAM decoded-size limit is surfaced when estimable.
- [ ] Final generated output has been inspected with GDAL.

## UI / anti-slop
- [x] Every preflight UI element has a concrete job.
- [x] No invented success metrics or guarantees.
- [x] Error, empty, and recovery states are understandable.
- [x] No decorative preflight component was added solely for appearance.

## Convergence
- [ ] Focused tests/manual verification completed.
- [ ] Diff reviewed for accidental scope expansion.
- [ ] Known limitations documented.
- [ ] User-facing instructions match the actual implementation.
