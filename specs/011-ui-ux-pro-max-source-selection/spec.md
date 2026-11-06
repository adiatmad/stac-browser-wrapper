# Feature Specification: UI/UX Pro Max Source Selection

**Status:** Implemented; CI verified  
**Branch:** `feature/ui-ux-pro-max-source-selection`  
**Parent:** `feat/opengeo-stac-discovery-search`

## Problem

The Discover & map workflow presents a source-type selector, but the S3 mode still renders the STAC section heading and explanatory copy. The STAC URL control is disabled rather than removed. This leaves users looking at controls for a source they did not select and weakens the page's information hierarchy.

## User outcome

A mapper sees one clear source-entry panel at a time. Switching between STAC and public S3 changes the visible controls without changing either source workflow.

## Design guidance applied

Use the relevant guidance from [UI/UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill): progressive disclosure, data-first hierarchy, visible field labels, native keyboard-operable controls, clear interaction states, and responsive layouts without horizontal overflow.

The project already uses Streamlit and shadcn Components V2. Reuse native Streamlit bordered containers; do not add another UI framework, custom global CSS, remote fonts, decorative assets, or runtime dependencies. The upstream skill is design guidance only and is not vendored into the hosted application.

## Acceptance criteria

1. Public S3 mode displays its own labeled, bordered source-entry panel.
2. STAC mode displays its catalog directory and URL controls in its own labeled, bordered panel.
3. S3 mode does not render STAC-specific headings, catalog controls, or a disabled STAC URL input.
4. STAC mode does not render the S3 URL input or S3-specific controls.
5. Existing widget keys, STAC discovery/API search behavior, S3 listing behavior, result rendering, and handoff actions remain unchanged.
6. Existing local-first imagery handling and explicit user-controlled OAM publication remain unchanged.
7. No new runtime dependency, global stylesheet, or frontend framework is introduced.
8. Contract tests cover the mutually exclusive source-control branches.
9. Playwright browser smoke verifies source switching, confirms inactive controls are absent, and checks the selected source panels at 375px and 390px.
10. Existing unit, dependency-compatibility, and desktop/mobile browser-smoke CI jobs pass.

## Non-goals

- Full visual rebrand or replacement of the existing teal/slate theme.
- Rewriting Streamlit in React or introducing a second component library.
- Changing STAC/OAM requests, metadata interpretation, raster validation, or publication behavior.
- Changing the separate Local preparation workflow.


## Verification results

- Unit suite: **65 tests passed**.
- Streamlit/shadcn dependency compatibility: passed.
- Playwright desktop/mobile browser smoke: passed, including S3 ↔ STAC source switching and inactive-control assertions.
- Responsive checks: no horizontal page overflow at 390px and 375px for the STAC and S3 source panels.
- Desktop and mobile screenshots were generated and inspected from the CI artifact.
- No live external STAC/OAM behavior was changed or newly claimed.
