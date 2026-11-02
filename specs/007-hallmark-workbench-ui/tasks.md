# Tasks: Hallmark Workbench UI Refresh

- [x] Inspect repository instructions, constitution, current UI, existing UI modernization spec, dependencies, and tests.
- [x] Inspect Hallmark v2.0.0 app-screen, redesign, quality-gate, and interaction-state guidance.
- [x] Evaluate Streamlit UI improver candidates; reuse the existing shadcn Components V2 dependency and reject the archived Microsoft template and NeonUI 0.1.0 as unsuitable.
- [x] Record user outcome, scope, non-goals, and Floor/Reflex/Finish/Ledger gates in the feature specification.
- [x] Add a tokenized, restrained Streamlit visual layer with keyboard focus, responsive spacing, and reduced-motion support.
- [x] Introduce Discover & map / Local preparation navigation with the existing shadcn Tabs V2 component and conditional rendering, without changing workflow logic or widget keys.
- [x] Add STAC crawl loading and empty states, plus an empty state for missing OAM-compatible items.
- [x] Tighten UI labels and remove decorative emoji while preserving factual copy and user actions.
- [x] Extend contract tests for navigation, styling safeguards, preserved workflows, and WCAG AA text/focus contrast for the selected theme tokens.
- [x] Add Playwright smoke coverage for actual Streamlit startup, shadcn tab switching, keyboard navigation, mobile overflow, and screenshot artifacts.
- [ ] Run the full unit suite and repository CI; investigate any failures without weakening assertions.
  - Evidence: the shadcn dependency-compatibility job passed. The unit job currently fails in the pre-existing `spaceeye_oam_prefill` parity test because `app.py` uses `CC-BY-4.0` while `utils/oam_sources.py` still uses `CC-BY 4.0`; the separate open PR #17 fixes that mismatch. This UI PR does not change license or OAM helper behavior.
- [ ] Review the full diff for lost controls, links, fields, handlers, state keys, or changed data behavior.
- [ ] Verify the live app in a browser at desktop and mobile widths, including keyboard focus and loading/empty/error states.\n  - Browser smoke test now runs under Playwright and uploads desktop/mobile screenshots plus the Streamlit server log as a CI artifact.
- [ ] Update this checklist with actual evidence and known limitations; keep the PR unmerged pending user approval.
