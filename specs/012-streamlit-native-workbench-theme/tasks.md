# Tasks: Native Streamlit Workbench Theme

- [x] Inspect repository instructions, constitution, current app UI, prior UI specifications, dependencies, and browser smoke coverage.
- [x] Confirm the prior global stylesheet was rolled back after readability feedback.
- [x] Record the Streamlit-only direction, acceptance criteria, and non-goals.
- [x] Add a native high-contrast light theme using Streamlit configuration only.
- [x] Add and run a focused automated test for theme configuration and contrast (included in the passing unit job).
- [x] Run the full unit suite (GitHub Actions unit job passed).
- [x] Complete desktop/mobile Playwright smoke checks (GitHub Actions run 44471158793 passed all three jobs).
- [x] Inspect desktop/mobile screenshots from artifact `streamlit-ui-smoke-evidence`: text and controls remain readable, tab keyboard focus is visible, and layouts reflow at 390px/375px without horizontal page overflow.
- [x] Review the complete diff; only native theme config, contract test, and decision/checklist documentation changed. `app.py`, dependencies, workflow logic, and widget keys are untouched.
- [x] Keep the change in a draft PR, unmerged pending user review.
