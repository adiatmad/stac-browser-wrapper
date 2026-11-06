# Feature Specification: Complete and Safe OAM Duplicate Checks

**Status:** Implemented; CI verified (live HOTOSM pagination remains unverified)
**Branch:** `feature/oam-duplicate-pagination`

## Problem

The OAM duplicate check currently queries only the first 100 results and does not follow STAC pagination. It can therefore miss an existing image in later pages while reporting that the item was not found. It also treats a provider ID appearing anywhere inside an unrelated title as an exact identifier match.

## User outcome

Before preparing an OAM handoff, a mapper receives a reliable duplicate-check result: exact item-ID matches and spatial overlaps are checked across available result pages; a bounded search that cannot finish is clearly marked inconclusive rather than ready for submission.

## Scope and constraints

- Preserve the existing inline hosted-app architecture; do not add a project-specific import to `app.py`.
- Follow only advertised STAC `rel=next` links that use HTTPS GET and remain on the exact HOTOSM OAM items endpoint.
- Keep the request bounded to at most 10 pages of 100 items (up to 1,000 results).
- Match provider IDs only against exact STAC Item IDs; do not use title substring matching.
- Continue spatial-overlap checks on every fetched page.
- Do not change OAM publication or upload behavior.

## Acceptance criteria

1. The duplicate check follows valid advertised GET pagination links from the HOTOSM items endpoint.
2. Pagination requests stay on HTTPS and the exact trusted endpoint; cross-host, alternate-path, malformed, repeated, and non-GET next links are not followed.
3. The search is bounded to 10 pages and 100 items per page.
4. Exact provider-item-ID matching compares the complete STAC Item ID, not title substrings.
5. Spatial overlap checks are applied to items on later pages as well as the first page.
6. A complete search with no match reports that all returned pages were checked.
7. A search that reaches the page cap reports an inconclusive result and is never presented as ready for submission.
8. Missing or invalid bbox is reported as unable to check, not as no duplicate found.
9. Regression tests cover pagination, exact ID matching, spatial overlap on later pages, limits, unsafe next links, and missing bbox.
10. Existing local-first raster and explicit OAM publication safeguards remain unchanged.

## Verification

- Unit tests: pending CI.
- Live HOTOSM pagination behavior: not claimed until checked against the live API.


## Verification

- GitHub Actions run [42134690444](https://github.com/adiatmad/stac-browser-wrapper/actions/runs/42134690444) passed the unit, dependency-compatibility, and desktop/mobile browser-smoke jobs on commit `5930154006500d5ee4bebe3211ca63d8749fa533`.
- The regression suite covers exact ID matching, false-positive title matching, later-page exact/spatial matches, pagination caps, unsafe links, and missing bbox.
- Live HOTOSM pagination behavior remains unverified; mocked tests do not establish the live service's pagination contract.
