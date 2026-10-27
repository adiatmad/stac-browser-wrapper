# Tasks: Shadcn UI Modernization

- [x] Inspect repository instructions, current PR #8 head, dependencies, app structure, and existing single-file contract tests.
- [x] Verify upstream `streamlit-shadcn-ui` Components V2 API and compatibility floor.
- [x] Record acceptance criteria and explicit non-goals in the feature specification.
- [x] Add the shadcn dependency and required Streamlit version floor.
- [x] Modernize the local DroneTM information panel with a shadcn card while preserving the explicit local-tool link and safety guidance.
- [x] Render preflight PASS/WARN/FAIL states as badges while retaining existing descriptions and overall alerts.
- [x] Replace the three native imagery metrics with shadcn metric cards.
- [x] Add contract tests for dependency compatibility, component integration, preserved workflow affordances, and the no-automatic-upload boundary.
- [x] Re-read the committed diff and run the full repository unit-test workflow in GitHub Actions (32 tests passed) and install/import the complete app requirements (Streamlit 1.66.1 and shadcn UI 1.4.0); run: https://github.com/adiatmad/stac-browser-wrapper/actions/runs/39873116541.
- [ ] Verify the hosted Streamlit app starts with the new dependency and manually inspect desktop/mobile layout, keyboard focus, empty states, and preflight results.
- [ ] Update acceptance evidence and known limitations; keep PR draft/unmerged until user approves.
