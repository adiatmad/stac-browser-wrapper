# Feature Specification: Public STAC Discovery and API Search

**Status:** Implemented on feature branch; CI verification pending
**Branch:** `feat/opengeo-stac-discovery-search`

## Problem

The workbench currently requires users to know a STAC URL. It can recursively browse static catalogs and extract assets, but it does not expose a catalog directory or a first-class STAC API Item Search flow. API users therefore have to discover endpoints and construct search URLs themselves.

## User outcome

A mapper can find a public catalog, load its URL into the existing discovery workflow, and—when the root advertises an HTTPS GET Item Search link—narrow results by WGS84 bounding box, date interval, collection IDs, and page limit. Results can show an explicitly advertised thumbnail when available.

## Evidence and design decisions

- Catalog directory source: [OpenGeo geospatial-data-catalogs](https://github.com/opengeos/geospatial-data-catalogs), `stac_catalogs.json`. The app loads it on demand and caches it for one hour.
- Public discovery is filtered to registry records with `access == "public"`, `isPrivate == false`, and HTTPS URLs. The registry's access classification does not guarantee that every linked asset is openly downloadable or has a permissive license.
- API search endpoint is discovered only from a root link with `rel == "search"`, GET method (or no declared method), and HTTPS target. No guessed `/search` path, POST body, authentication bypass, or vendor-specific query extension is added.
- Search uses STAC core GET parameters: `bbox`, `datetime`, `collections`, and `limit`. BBox is validated as four WGS84 coordinates. Provider-specific cloud-cover and sorting extensions are out of scope until a catalog advertises and supports them.
- Thumbnail display requires an explicit thumbnail role/key, image media type or supported image extension, and HTTPS URL. No thumbnail is invented from a data asset.
- Existing catalog crawling, map filtering, OAM duplicate checks, handoffs, and local-only GDAL/OAM preparation remain intact. No new runtime dependency is introduced.

## Acceptance criteria

1. A user can explicitly load and search the public OpenGeo catalog directory; ordinary app startup does not fetch the directory.
2. Only public, non-private HTTPS catalog records are selectable; title, summary, API/static classification, and registry record date are shown.
3. Selecting a catalog fills the existing STAC URL field and reuses the current crawler.
4. API search is optional and requires an advertised HTTPS GET search link.
5. Search supports optional WGS84 bbox, datetime, comma-separated collection IDs, and a 1–1000 result-page limit.
6. Invalid bbox/limit input and unsupported POST-only search are reported clearly without silently falling back to a guessed endpoint.
7. Existing browse-by-catalog behavior remains the default and unchanged when API search is off.
8. Item thumbnails are displayed only when the STAC Item explicitly advertises a suitable HTTPS thumbnail image.
9. No new dependency, external upload, credential handling, OAM publication action, or local raster access is introduced.
10. Focused tests, full unit tests, dependency compatibility, and browser smoke CI pass. Live catalog availability and per-provider API behavior remain external-service checks.

## Non-goals

- Replacing Streamlit/Folium with Leafmap or AnyMap.
- Assuming every STAC API supports POST search, cloud-cover query extensions, sorting extensions, or identical pagination behavior.
- Treating registry public access as an asset license grant.
- Adding TiTiler infrastructure or manufacturing thumbnails from arbitrary COG URLs.
- Changing OAM metadata, duplicate detection, publication, or local GDAL workflows.
