# Tasks: UI/UX Pro Max Source Selection

- [x] Read repository instructions and inspect the active PR #25 branch, app source, existing UI tests, and browser smoke workflow.
- [x] Read the upstream UI/UX Pro Max skill guidance and applicable UX rules for progressive disclosure, labels, keyboard operation, and responsive layouts.
- [x] Define scope, non-goals, and acceptance criteria.
- [x] Keep the existing Streamlit/shadcn stack; reject global CSS, new dependencies, and a custom frontend.
- [x] Group S3 source controls in a bordered, labeled panel.
- [x] Group STAC catalog and URL controls in a bordered, labeled panel.
- [x] Render only the selected source's controls; remove inactive STAC controls from S3 mode.
- [x] Add source-selection contract coverage.
- [x] Extend Playwright smoke coverage for S3/STAC switching, inactive-control visibility, and 375px source-panel overflow.
- [x] Run full unit tests and all GitHub Actions checks (65 unit tests, dependency compatibility, and browser smoke passed).
- [x] Inspect desktop/mobile screenshots and browser logs; source switching and 375px/390px overflow checks passed.
- [x] Review the full diff; widget keys, data requests, source behavior, and OAM/local-raster safeguards remain unchanged.

CI evidence: GitHub Actions run [42126662788](https://github.com/adiatmad/stac-browser-wrapper/actions/runs/42126662788) on code commit `a1b387a2aebbab4d792483270c63584d9b6545d7` passed all three jobs.
