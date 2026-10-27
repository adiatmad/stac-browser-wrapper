# Feature Specification: Shadcn UI Modernization

**Status:** Implementation in progress  
**Branch:** `feat/shadcn-ui-modernization`  
**Parent:** PR #8, `feat/end-to-end-imagery-workflow-spec`

## Problem

The hosted humanitarian imagery app uses mostly native Streamlit headings, metrics, and plain-text status rows. Users need a clearer visual hierarchy without changing the existing imagery discovery, local drone processing, spatial filtering, or OAM handoff behavior.

## Outcome

Adopt `streamlit-shadcn-ui` Components V2 for a small set of high-value display components while keeping the app's project-specific runtime logic in the single `app.py` file.

## Acceptance criteria

1. The dependency declarations require Python 3.10+ compatible library release `streamlit-shadcn-ui>=1.4.0,<2.0.0` and Streamlit `>=1.60.0`, matching the upstream Components V2 compatibility requirements.
2. The DroneTM local-processing section is presented as a clear card that states processing remains local and no automatic OAM upload occurs.
3. OAM drone preflight checks use visible status badges for PASS, WARN, and FAIL while retaining each check's name and explanatory detail and the existing overall status messages.
4. Imagery totals use three responsive shadcn metric cards for total, PRE-event, and POST-event scenes.
5. Existing workflows remain available: public S3 listing, STAC discovery, spatial filtering, Tasking Manager/JOSM handoff, OAM duplicate checking, explicit OAM prefill links, and CSV audit export.
6. No raster/image bytes are uploaded by the UI refresh, no automatic OAM publication is added, and local DroneTM processing remains a separate local tool.
7. No new project-specific Python module is introduced; application runtime behavior remains in `app.py`.
8. Contract tests verify dependency declarations, component integration, preserved workflow affordances, and the no-automatic-upload boundary.
9. CI unit tests pass on the proposed PR. A live Streamlit startup/browser check is recorded separately; passing unit tests alone is not treated as visual acceptance.

## Non-goals

- Rewriting the application with React or introducing a separate frontend.
- Replacing existing Streamlit inputs, tabs, Folium map, or OAM interaction logic.
- Changing STAC/OAM requests, metadata interpretation, raster validation, local file handling, or publication behavior.
- Uploading, processing, or modifying user imagery.
- Merging the PR without explicit user approval.

## Design decision

Use the upstream Components V2 API's stateless `card`, `badge`, and `metric_card` helpers only where they improve hierarchy. Keep native Streamlit controls and status alerts where they already provide the interaction semantics. Pin the dependency to the 1.x API line and raise the Streamlit minimum to its documented `1.60.0` floor rather than attempting a partial compatibility fallback to older Streamlit releases.
