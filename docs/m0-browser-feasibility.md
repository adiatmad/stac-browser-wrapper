# M0 Browser Feasibility Spike

## Purpose
Determine whether the browser-only frontend can reach the external services that the current Streamlit app uses. This is a browser-origin test: server-side HTTP success is not evidence that JavaScript running on GitHub Pages can read the response.

## Source inventory grounded in the current app
| Operation | Endpoint / source | Why it matters |
|---|---|---|
| Catalog discovery | `https://raw.githubusercontent.com/opengeos/geospatial-data-catalogs/master/stac_catalogs.json` | Current app's public catalog registry |
| Sample catalog read | `https://browser.moregeo.it/external/vantor-opendata.s3.amazonaws.com/events/Indonesia-Earthquakes-Aug-2026/collection.json` | Current app's default sample collection URL |
| OAM STAC search | `https://api.imagery.hotosm.org/stac/collections/openaerialmap/items?limit=1` | Current app's OAM duplicate lookup service |
| Item/asset URLs | Discovered dynamically from returned STAC Item | Need to test metadata JSON separately from thumbnail/image rendering |

The current app defines a 1,000-item / 10-page search cap. This spike deliberately requests only one OAM item and does not crawl or download imagery.

## Running the probe
1. Serve `cors-probe.html` from an HTTP(S) origin. Do not use `file://`.
2. For the final decision, run it from the actual GitHub Pages project origin: `https://adiatmad.github.io/stac-browser-wrapper/`. A localhost result is useful but does not prove that a provider's origin allowlist accepts GitHub Pages.
3. Select **Run all tests**.
4. Save **Download results JSON** and retain the browser DevTools Console + Network evidence for failures.
5. Repeat after a meaningful provider/configuration change.

The probe tests:
- Fetch of the catalog registry.
- Fetch of the current sample collection.
- Fetch of one OAM STAC Item.
- Image loading for thumbnail/overview/visual assets advertised by the OAM item, when present.
- Optional manually supplied endpoints.

It does not test every item asset, every pagination link, authentication, POST-only search, large responses, or production reliability.

## Interpreting results
- `PASS`: browser JavaScript received a successful response and parsed JSON where applicable.
- `HTTP_OR_PARSE_FAILURE`: browser received an HTTP response but it was not successful or JSON was malformed.
- `BROWSER_FETCH_FAILED`: browser fetch rejected. CORS is possible, but so are DNS, TLS, offline/network, mixed-content, and browser-extension failures. Inspect DevTools; do not label every rejection as CORS without evidence.
- `IMAGE_LOAD_PASS`: browser loaded the image for display. This does not mean JavaScript can read image bytes.
- `IMAGE_LOAD_FAILED`: image did not load; inspect URL, status, and console.

## M0 exit decision
- **Proceed with direct browser integration** only for required sources whose JSON endpoints pass from the actual Pages origin.
- **Manual STAC URL fallback** is acceptable for optional catalog-registry failure, provided users can paste a working STAC API URL.
- If OAM API access fails from Pages, keep OAM duplicate checking out of Phase 1; do not introduce a proxy or server just to preserve a Phase 2 feature.
- If a required imagery API fails, stop before M1/M2 integration and decide whether the product scope should be narrowed or a separately reviewed backend is justified.
- Keep deterministic CI tests mocked; never make live external API availability a CI gate.

## Current status
**Not yet executed in a real browser.** The GitHub connector can inspect and modify repository files, but it does not provide a browser session with the actual GitHub Pages origin. A result must not be fabricated from server-side checks or assumed CORS headers.
