# Tasks: Public STAC Discovery and API Search

- [x] Inspect current app, project constitution, AGENTS.md, STAC crawler, UI workflow, tests, and CI.
- [x] Inspect OpenGeo's public STAC registry structure and Leafmap STAC search/preview patterns.
- [x] Define scope, constraints, acceptance criteria, and non-goals.
- [x] Add on-demand public catalog registry loading, validation, filtering, and URL selection.
- [x] Add advertised HTTPS GET STAC Item Search endpoint discovery.
- [x] Add validated core bbox, datetime, collection, and page-limit query construction.
- [x] Bound API pagination to 1,000 items / 10 pages and stop on POST-only next links.
- [x] Add explicit HTTPS thumbnail asset selection and display.
- [x] Add visible loading states for catalog-registry and STAC API-root requests.
- [x] Preserve default catalog crawling and all OAM/local-preparation safeguards.
- [x] Add focused tests and README documentation.
- [x] Run focused and full unit tests for bounded pagination changes; all 64 tests passed.
- [x] Verify GitHub Actions unit, dependency compatibility, and desktop/mobile browser smoke jobs for final code commit `d9dcb18`.
- [x] Review complete diff for regressions, unsupported assumptions, and security/safety issues, including bounded pagination and HTTPS URL handling.
- [x] Apply the Anti-Slop purpose and responsiveness review while preserving the existing design direction.
- [ ] Confirm live catalog/API behavior separately from automated CI; provider-specific availability remains an external-service check.
