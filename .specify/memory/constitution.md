# Project Constitution

## Principle 1 — Evidence before implementation
Repository behavior, authoritative OAM behavior, and real GDAL output take precedence over assumptions.

## Principle 2 — User outcome over feature volume
Build the smallest change that solves the stated job. Explicitly record non-goals.

## Principle 3 — Safety over convenience
Never invent CRS information, silently discard imagery bands, overwrite source imagery, or claim upload compatibility that has not been verified.

## Principle 4 — Local data stays local
Imagery validation should not require uploading source raster data to this project. Use local GDAL commands and exchange only the metadata/report needed for analysis.

## Principle 5 — Verifiable delivery
Every implementation must have focused acceptance checks. A successful commit is not evidence that the feature works.

## Principle 6 — Anti-slop
Avoid invented claims, decorative UI, unnecessary abstractions, generic copy, and scope creep. Every user-facing element must have a concrete job.

## Principle 7 — Explicit uncertainty
If upstream behavior, raster semantics, or a source CRS cannot be verified, say so and ask for the missing evidence rather than guessing.

## Governance
For each non-trivial feature, use the Spec Kit sequence where useful: specify → clarify → plan → checklist → tasks → analyze → implement → converge. For small changes, retain the principles without adding unnecessary ceremony.
