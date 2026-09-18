# OAM Preflight Delivery Checklist

## Evidence
- [ ] Current OAM behavior checked against upstream source/docs.
- [ ] At least one real `gdalinfo -json` report has been tested.
- [ ] Any unsupported assumptions are documented.

## Safety
- [ ] Source imagery is never overwritten by generated commands.
- [ ] Missing CRS never triggers an automatic guess.
- [ ] RGB/RGBA bands are preserved.
- [ ] Lossy compression is not introduced silently.
- [ ] Generated shell syntax is valid for the selected shell.

## Behavior
- [ ] Valid RGB/RGBA Byte imagery gets a clear result.
- [ ] Invalid band count/type gets a clear failure and reason.
- [ ] Missing CRS requests user-supplied EPSG.
- [ ] ECW or another non-GTiff source can be inspected without uploading it.
- [ ] COG is treated according to verified OAM behavior rather than as an invented hard prerequisite.

## UI / anti-slop
- [ ] Every UI element has a concrete job.
- [ ] No invented success metrics or guarantees.
- [ ] Error, empty, and recovery states are understandable.
- [ ] No decorative component was added solely to make the interface look more sophisticated.

## Convergence
- [ ] Focused tests/manual verification completed.
- [ ] Diff reviewed for accidental scope expansion.
- [ ] Known limitations are documented.
- [ ] User-facing instructions match the actual implementation.
