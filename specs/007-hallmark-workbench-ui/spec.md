# Feature Specification: Hallmark Workbench UI Refresh

**Status:** In progress  
**Branch:** `feat/hallmark-workbench-ui`  
**Baseline:** `main` at `37ab13664768704a6ea2f8a39678a27fb76f39a6`  
**Design method:** Hallmark v2.0.0, app-screen scope, full composition refresh

## Problem

The application currently presents local DroneTM preparation, OAM preflight, public S3 import, and STAC discovery as one long Streamlit page. The existing shadcn cards, badges, and metric cards improve individual elements, but users still need to scan a long sequence to find the workflow they need.

## User outcome

A GIS or humanitarian mapping user can immediately choose between:
- **Discover & map:** inspect STAC catalogs or public S3 sources, filter imagery, and prepare Tasking Manager/JOSM or OAM handoffs.
- **Local preparation:** follow the local DroneTM workflow and run the local-only GDAL/OAM preflight.

The interface should feel like a focused technical workbench, not a marketing landing page.

## Design direction

- Modern-minimal, restrained, high-contrast, and data-first.
- Keep Streamlit and the existing shadcn UI 1.x components.
- Introduce a small tokenized visual system in the app stylesheet; do not add fonts, icons, frontend frameworks, or runtime dependencies.
- Use a native Streamlit segmented control as the top-level navigation, and render only the selected workflow so local preparation does not trigger STAC discovery.
- Keep controls, maps, metrics, result details, and workflow copy close to their existing logic.
- Remove decorative emoji from UI labels; rely on clear text and existing semantic status components.

## Acceptance criteria

1. The app title and one-sentence description accurately describe STAC discovery, imagery inspection, and mapping/OAM handoffs.
2. The page has two clear top-level destinations: Discover & map, and Local preparation. Only the selected workflow executes; opening local preparation must not trigger a STAC crawl.
3. All existing workflows remain available: STAC URL resolution/crawl, public S3 listing, archive inspection, spatial filtering, Folium drawing, PRE/POST/all scene views, Tasking Manager/iD and JOSM TMS handoffs, OAM duplicate checks, explicit OAM prefill links, and CSV audit export.
4. Local DroneTM processing remains a separate local tool. The hosted app does not access local files, upload raster bytes, or automatically publish to OAM.
5. Existing widget keys, form fields, callback behavior, session-state contracts, external URLs, and workflow logic are preserved.
6. Existing shadcn card, badge, and metric-card integrations remain intact. No new runtime dependency or project-specific Python module is introduced.
7. UI styling uses declared tokens for colors and fonts, includes visible keyboard focus, supports reduced motion, and prevents horizontal overflow.
8. Controls and navigation remain usable at narrow viewport widths, including the top-level segmented control.
9. Contract tests verify the app parses, the new navigation and tokenized styling exist, and the local-only/no-automatic-publication safeguards remain.
10. CI unit tests pass. Browser rendering, keyboard navigation, and desktop/mobile visual inspection are recorded separately and are not inferred from unit-test success.

## Quality gates

### Floor — non-waivable
- Preserve all existing workflow wiring, widget keys, data requests, and user-facing actions.
- Preserve local-first imagery handling and explicit user-controlled OAM publication.
- Do not invent metadata, imagery facts, source capabilities, or success states.
- No horizontal page overflow; keyboard focus is visible; reduced-motion preferences are respected.
- No destructive change to imagery, user files, or publication state.

### Reflex — waiver requires evidence and a reason
- One consistent, tokenized visual language.
- Two top-level workflow destinations with task-oriented labels.
- One primary visual action per workflow region.
- Keep the interface data-first; do not add a marketing hero, decorative charts, or unsupported metrics.
- Prefer native Streamlit and existing shadcn components over custom widgets.

### Finish — report and answer, non-blocking
- Desktop and mobile spacing, label wrapping, control alignment, empty states, loading states, and error readability.
- Keyboard-only navigation and visible focus.
- Consistent heading hierarchy and concise instructions.

### Ledger
Record any repeated Reflex waiver or recurring UI exception for later review; do not silently normalize repeated exceptions.

## Non-goals

- Rewriting the application in React or introducing another frontend.
- Changing STAC/OAM network behavior, metadata interpretation, raster validation, GDAL commands, or archive-proxy behavior.
- Adding imagery previews, new data sources, new metrics, or new publication actions.
- Changing the existing single-file hosted-app contract.
- Merging the pull request without explicit user approval.

## Verification

- Run the existing Python unit suite and repository CI.
- Review the full diff for lost controls, keys, links, handlers, or changed data behavior.
- Perform a live Streamlit/browser check at desktop and mobile widths, including keyboard focus and empty/error/loading states.
- If live browser access is unavailable, mark visual acceptance as blocked/unverified and provide the exact manual checks still needed.
