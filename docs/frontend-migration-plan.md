# Frontend Migration Plan

## Strategy
Migrate by user workflow, not by line-by-line Python translation. Keep the current Streamlit app, Python utilities, and optional archive proxy operational during frontend migration. The frontend is additive until the MVP is verified.

## Workstreams and milestones

### M0 — Repository and browser feasibility
- Review current Python features, existing tests, and data flow.
- Identify representative STAC catalogs/API endpoints and OAM endpoints.
- Test catalog discovery, GET search, thumbnails, geometry, and OAM requests from browser context for CORS.
- Document sources that fail browser access and identify manual URL fallback.
**Exit:** feasibility matrix and risks are documented; no full frontend implementation begins before critical CORS uncertainty is addressed.

### M1 — Frontend foundation
- Add Vite/TypeScript project in a separate frontend directory.
- Configure GitHub Pages base path for project-site URL.
- Establish design tokens, responsive shell, panels, buttons, cards, empty/loading/error states.
- Add typed STAC model and service boundary.
- Set up Vitest and mocked fixtures.
- Add CI build/test.
**Exit:** clean build, shell responsive, test runner works, CI passes.

### M2 — Discovery vertical slice
- Catalog picker and manual URL.
- URL resolver for documented/verified patterns.
- Search form: bbox, datetime, collection.
- STAC GET Item Search client, pagination, safety caps.
- Results cards and thumbnails.
- Leaflet map with footprints and synchronized selection.
- Item inspector: key properties, assets, geometry, raw JSON.
- Clear API error states.
**Exit:** complete search → result → map → inspect workflow passes with fixtures and browser tests.

### M3 — Real-source compatibility
- Integrate only CORS-compatible sources identified in M0.
- Catalog discovery behavior and fallback.
- Test representative real APIs manually in browser.
- Document unsupported APIs and restrictions.
**Exit:** source compatibility matrix updated and real-browser smoke test completed.

### M4 — OAM workflow
- Implement OAM lookup adapter and duplicate-candidate comparison.
- Exact provider/item ID match separate from spatial overlap.
- Display candidate footprint and source details.
- Metadata checks and OAM prefill URL.
- Handoff opens official uploader; no upload automation.
**Exit:** duplicate and handoff tests; safeguards reviewed.

### M5 — Advanced workflows (optional post-MVP)
- Public S3 GeoTIFF discovery.
- Remote-source handoff.
- Archive exploration; preserve security restrictions and optional proxy architecture.
- Local raster preparation: parse user-pasted GDAL report in browser, consistency checks, conversion command generation, no raster bytes upload.
**Exit:** each workflow has its own acceptance criteria and test coverage; not a prerequisite for Phase 1.

## Suggested implementation order
1. M0 browser feasibility spike (smallest high-risk experiment).
2. M1 foundation.
3. M2 discovery/inspection.
4. M3 real source integration.
5. Deploy public MVP.
6. M4 OAM.
7. M5 advanced features as justified.

## Test strategy
- Unit: URL parsing/resolution; STAC response normalization; bbox/date/collection filters; pagination and caps; asset/thumbnail selection; metadata validation; OAM prefill construction; duplicate candidate classification.
- Component/browser: search form validation; loading/error/empty states; result-map selection synchronization; metadata inspector; responsive navigation.
- End-to-end: mocked catalog → search → results → select footprint → inspect item → open asset/handoff action.
- Live smoke: manually test a small representative set of real endpoints; keep live network out of deterministic CI.

## CORS feasibility matrix
Record each source with: source/catalog name, endpoint, operation, browser result, CORS headers/error, authentication needs, fallback, tested date.
Required operations to test: catalog listing, search, item response, thumbnail/asset, OAM lookup. A failure for an optional source must not block MVP.

## Scope discipline
Do not add framework/state-management libraries, backend, database, auth, proxy, user accounts, or automated publication without an explicit requirement and evidence that static architecture cannot satisfy it.
