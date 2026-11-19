# Feature Specification: Native Streamlit Theme

**Status:** Superseded (2026-11-19)  
**Branch:** `feature/streamlit-workbench-design`

## Decision

Fresh review found that a forced global theme is unnecessary for this UI-only iteration. Remove the theme override and keep Streamlit's existing/default appearance; avoid global palette changes or CSS overrides.

## Scope

- No app-wide light/dark inversion or forced color palette.
- UI hierarchy improvements remain limited to the discovery summary and its labels.
- No workflow logic, dependencies, CSS, or deployment changes.

## Acceptance criteria

1. No repository-level theme override is added.
2. Existing app appearance remains controlled by Streamlit defaults/user settings.
3. No custom CSS/JS or dependencies.
4. UI-only changes do not alter discovery, filtering, handoff, or publication safeguards.
5. Review and test the focused discovery layout separately.
