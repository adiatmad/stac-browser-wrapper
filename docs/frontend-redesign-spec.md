# Frontend Redesign Specification

## Status
Superseded on 2026-11-19. The project will retain Streamlit and improve its existing interface; see `specs/012-streamlit-native-workbench-theme/spec.md`.

The static GitHub Pages frontend proposal is paused. Its CORS findings remain useful evidence, not a requirement to continue the migration.

## Goal
Redesign STAC Browser Wrapper into a polished static, browser-based imagery discovery and inspection workbench, deployable at GitHub Pages, while preserving the value and safeguards of the current Streamlit tool.

Target URL: `https://adiatmad.github.io/stac-browser-wrapper/`

## Product concept
Workflow: **Discover → Inspect → Prepare → Handoff**

- Discover catalogs, STAC APIs, collections, and imagery.
- Inspect footprints, preview assets, metadata, and links.
- Prepare metadata and review possible OpenAerialMap duplicates.
- Handoff to official OAM workflows; the MVP does not upload or publish.

## Current capability inventory
The current Python application includes:
- Resolve external STAC Browser URLs to underlying STAC URLs.
- Discover public STAC catalogs/APIs through OpenGeo geospatial-data-catalogs.
- STAC GET Item Search with bbox, datetime, collections, and pagination.
- Safety cap of 1,000 items or 10 pages per search.
- Thumbnail display when advertised by an item.
- Metadata extraction (title, provider, sensor, dates, license, bbox/geometry).
- OpenAerialMap duplicate checking via provider IDs and spatial overlap.
- Spatial filtering and Folium map.
- OAM metadata preparation and uploader prefill.
- Public S3 GeoTIFF discovery.
- Remote-source OAM handoff preparation.
- Local raster preflight using GDAL report and copy-ready QGIS/OSGeo4W commands.
- Optional ZIP-contained TIFF/archive proxy workflow and local GDAL conversion guidance.

## Target user experience
Desktop-first, responsive, map-centered workspace. Main screen has:
1. Header and workflow navigation.
2. Search/filter panel (catalog/API, collection, date, bbox/AOI).
3. Result cards with preview and key metadata.
4. Interactive map with selected result footprint.
5. Item inspector for metadata, assets, geometry, and raw STAC JSON.

Avoid decorative dashboard KPIs, excessive animation, and data not grounded in actual API results. Prioritize scannability and task completion.

## MVP scope (Phase 1)
- Static frontend hosted on GitHub Pages.
- Catalog selection and manual STAC URL entry.
- Supported STAC Browser URL resolution.
- GET Item Search and supported bbox/date/collection filters.
- Pagination and safety limits.
- Result cards, thumbnails, footprints, selection synchronization.
- Item metadata and asset inspector.
- Map fit-to-results / selected item.
- Clear error and empty states for CORS, timeout, malformed data, unsupported capability, and no results.
- Responsive layout.
- Mock-based unit and browser tests.

## Phase 2 — OAM workflow
- OAM lookup for possible duplicates.
- Exact ID match and spatial overlap match presented distinctly.
- Candidate duplicate footprints and metadata for review.
- Metadata preparation and required-field checks.
- License compatibility warnings and missing-value indicators.
- Official uploader prefill/handoff.
- No automatic upload or publication.

## Deferred
- Public S3 object browsing and remote source workflows (Phase 3).
- ZIP archive exploration and optional proxy workflow (Phase 3).
- Local GDAL report / GeoTIFF preparation wizard and conversion-command generator (Phase 4).
- Authentication, server-side proxy, user accounts, database, and persistent backend.
- Broad API feature support beyond tested STAC GET Item Search.

## Proposed technology
- Vite for build and static deployment.
- TypeScript for typed STAC objects and services.
- Vanilla TypeScript and DOM components initially; avoid framework/state library unless complexity demonstrates a need.
- CSS variables and modular CSS.
- Leaflet for map and footprint/AOI interaction.
- Turf only for geometry operations that need it.
- Vitest for unit tests; Playwright for browser tests.
- GitHub Actions for CI and Pages deployment.

## Proposed frontend structure
```
frontend/
  index.html
  package.json
  vite.config.ts
  tsconfig.json
  src/
    main.ts
    styles/
    components/
    services/
      stac-client.ts
      catalog-discovery.ts
      oam-client.ts
      s3-discovery.ts
      url-resolver.ts
    models/
    utils/
  tests/
    unit/
    browser/
```
Keep modules consolidated when splitting creates overhead. This is a boundary proposal, not a requirement to create every file.

## Architectural constraints
- GitHub Pages is static hosting; it does not run the current Python/Streamlit code.
- Browser fetches are subject to CORS; every critical external endpoint must be tested from browser context.
- No secret credentials, API keys, or private tokens in public client code.
- No direct filesystem access. Local raster inspection remains user-run via GDAL/QGIS.
- Parse GDAL report text/JSON in-browser only; don't upload raster bytes.
- Don't silently ignore unsupported API features; explain limitations.
- External APIs may fail, be rate-limited, change schema, or disallow browser requests.

## Safeguards (must not regress)
1. Never infer or guess a license.
2. Never infer acquisition date from modification time unless source explicitly defines it as acquisition time.
3. Never guess CRS.
4. Footprint overlap alone is not proof of a duplicate; label possible matches and allow review.
5. No automatic upload or publication.
6. Never upload local raster bytes in this static frontend.
7. Do not bypass authentication or access restrictions.
8. Local paths must not be sent to OAM as remote source URLs.
9. Do not claim catalog discovery's public-access flag proves every linked asset is public.
10. Preserve pagination and request safety limits.

## Acceptance criteria

### Search
- User can select a catalog or enter a supported STAC API URL.
- Supported STAC Browser URL patterns resolve without losing required query parameters.
- Bbox, datetime, and collection filters are sent only when supported.
- GET Item Search is used; unsupported POST-only search is clearly identified.
- Pagination works and existing 1,000-item / 10-page safety caps remain.
- Errors distinguish CORS, timeout/network, malformed response, unsupported endpoint/capability, and empty results.

### Results and map
- Cards display available title, date, provider, sensor, license, and preview.
- Missing metadata remains explicitly unknown/absent; no fabricated values.
- Selecting a card highlights its footprint and updates inspector.
- Map selection can select corresponding result.
- GeoJSON geometry is rendered; malformed geometry doesn't crash the result set.
- Map can fit result extent and selected item.

### Inspection
- Key metadata, geometry, assets, asset roles/links, and raw STAC JSON are inspectable.
- Thumbnail failure is isolated from other results.

### OAM (Phase 2)
- Candidate duplicates distinguish exact ID from spatial similarity.
- Spatial match is presented as candidate, not definitive duplicate.
- Metadata fields are validated; unknown values flagged.
- Prefill handoff uses supported OAM fields.
- No automatic publishing.

### Hosting and quality
- Production build succeeds and GitHub Actions deploys Pages.
- Site works under repository subpath, including asset URLs.
- No backend or secret required for deployment.
- Desktop and mobile layout usable.
- No critical browser-console errors.
- Unit tests cover URL resolver, STAC parsing, filtering, pagination/caps, metadata validation, and duplicate logic.
- Browser tests use mocks/fixtures, not live external network dependencies.

## Release gates
Phase 1 is releasable only after:
- CORS feasibility tests pass for required target catalog/API sources or a documented manual-source fallback exists.
- All Phase 1 acceptance criteria pass.
- Mock-driven tests pass.
- Pages deployment is verified at the actual project URL.
- The existing Streamlit app remains available as fallback during migration.
