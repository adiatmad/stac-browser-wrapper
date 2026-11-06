# Implementation Plan: UI/UX Pro Max Source Selection

## Decision

Keep the existing top-level workflow tabs, source-type radio, Streamlit runtime, and shadcn components. Make the S3 and STAC source-entry regions mutually exclusive and group each region in a native `st.container(border=True)`.

## Alternatives

- **Keep both source regions in the page and disable the inactive input:** rejected because it leaves irrelevant headings and controls visible and increases scanning effort.
- **Replace the source selector with a new tab component or custom frontend:** rejected because the current native radio is keyboard-operable and already wired; a new component would add interaction and responsive risk without improving the underlying job.
- **Add a global CSS theme or another UI framework:** rejected because the previous global stylesheet reduced readability and the repository already has a supported component system.

## Implementation

1. Add a bordered, labeled S3 source-entry panel around its existing URL, artifact filter, validation, and list action.
2. Keep the STAC catalog directory and URL field inside the existing STAC-only branch and group them in a matching bordered panel.
3. Remove the disabled STAC field from S3 mode and remove the STAC-only heading/copy from that mode.
4. Add a contract test for the source-mode branch structure.
5. Extend the existing Playwright smoke test to switch S3 → STAC and verify inactive controls are absent.
6. Run the full repository CI and inspect desktop/mobile screenshots and logs.

## Risk controls

- Preserve existing widget keys and all source/result processing code.
- Do not change network calls, STAC crawl parameters, S3 object filtering, or OAM handoff generation.
- Do not touch local raster/GDAL logic or publication behavior.
- Treat browser smoke and unit tests as separate evidence; CI does not prove live external catalog availability.
