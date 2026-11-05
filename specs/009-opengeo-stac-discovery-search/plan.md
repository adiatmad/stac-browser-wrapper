# Plan: Public STAC Discovery and API Search

1. Keep the existing single-file hosted application and dependency set.
2. Add pure helpers for registry validation/filtering, advertised GET search-link resolution, core STAC search URL construction, and explicit thumbnail asset selection.
3. Load the OpenGeo registry only after user action; cache successful data and retain manual URL entry as a fallback.
4. Add an optional API-search form immediately beside the existing STAC URL input. Preserve recursive catalog browsing as the default.
5. Add thumbnail rendering to existing item detail expanders; do not create a second result-card system.
6. Add focused AST-extracted unit tests and update the README/specification.
7. Run the full unit suite and CI, then inspect the complete diff and browser smoke evidence.

## Bounded execution contract

- **Goal/input:** deliver catalog discovery, bounded GET Item Search, and explicit thumbnail previews on a feature branch from the inspected `main` revision.
- **Permitted actions:** read repository sources, edit the app/tests/spec, create commits on the feature branch, open a PR, and inspect CI. Do not merge or publish.
- **Feedback:** use syntax/unit failures, dependency checks, browser smoke results, and diff review as evidence; repair only a concrete failure.
- **Bounds:** API search follows at most 10 pages and processes at most 1,000 items. The implementation loop stops after three repair iterations per concrete failure; exhausted or ambiguous changes escalate.
- **Acceptance:** unit tests, dependency compatibility, desktop/mobile smoke, and a clean reviewed diff.
- **Human boundary:** PR merge and live provider-specific acceptance remain with the repository owner.
- **Stop condition:** all automated checks pass and the PR is mergeable; do not claim live endpoint compatibility without testing it.
