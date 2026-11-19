# Feature Specification: Discovery Results Hierarchy

**Status:** Implemented; CI and screenshot review verified  
**Branch:** `feature/streamlit-workbench-design`

## Problem

The discovery screen reports only usable GeoTIFF, PRE-event, and POST-event counts. Users cannot immediately distinguish the number of STAC items inspected from the subset that exposes usable imagery. This makes the result summary less informative before users move into mapping or OAM handoff.

## User outcome

After discovery and optional area filtering, users can quickly understand:
- how many STAC items were inspected;
- how many yielded usable GeoTIFF imagery;
- how the usable scenes split into PRE-event and POST-event groups;
- which downstream workflow to choose.

## Acceptance criteria

1. The result summary distinguishes total discovered STAC item count from usable GeoTIFF scenes.
2. PRE-event and POST-event counts remain visible and retain their existing classification logic.
3. All four metrics use the same filtered selection when an area filter is active.
4. Existing handoff tabs, widget keys, session-state contracts, discovery limits, network behavior, and OAM publication safeguards remain unchanged.
5. No custom CSS, JavaScript, new dependencies, or new data requests are introduced.
6. Existing unit tests and desktop/mobile Playwright smoke checks pass.
7. The layout remains readable at the existing mobile smoke widths.

## Non-goals

- Changing STAC crawling, item classification, filtering, or pagination.
- Changing map drawing or spatial-filter behavior.
- Reworking Tasking Manager/JOSM, OAM, or advanced-data handoffs.
- Adding features or changing publication behavior.

## Verification evidence

- CI run [44481082311](https://github.com/adiatmad/stac-browser-wrapper/actions/runs/44481082311): unit, desktop/mobile browser smoke, and dependency compatibility all passed.
- Desktop and mobile screenshots inspected from artifact [14508557450](https://github.com/adiatmad/stac-browser-wrapper/actions/runs/44481082311/artifacts/14508557450).
- Screenshot inspection confirmed existing Streamlit styling remains in place; no app-wide theme inversion was introduced.
