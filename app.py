import streamlit as st
import requests
from urllib.parse import urlparse, unquote, urljoin
import re
import io
import csv
from datetime import datetime


st.title("STAC-to-OAM Tool")

root_url_input = st.text_input("Enter STAC Browser URL")
st.caption(
    "Example — Vantor (STAC Browser link): "
    "https://browser.moregeo.it/external/vantor-opendata.s3.amazonaws.com/events/Bordeaux-France-Wildfire-July-2026/B160001101B07110.json"
)
st.caption(
    "Example — Planet (direct STAC URL): "
    "https://data.source.coop/planet/disasterdata/nepal-flash-flood-2026-08-26/post-event/catalog.json"
)

all_links = []
tiff_links = []  # list of dicts: {"item_url": str, "tiff_url": str, "guessed": bool}
oam_items = []  # list of dicts from extract_oam_metadata()
collection_license_cache = {}  # collection URL -> license string ("" if none), avoids refetching per item

OAM_DEFAULT_LICENSE = "CC-BY 4.0"  # OAM's default license option; not auto-matched to the STAC item's own license
OAM_UPLOADER_ISSUE_URL = "https://github.com/hotosm/openaerialmap/issues/296"
OAM_FIELDNAMES = [
    "item_url", "title", "platform", "sensor", "date_start", "date_end",
    "image_source_url", "provider", "tags", "license_oam_default", "stac_license_reference",
    "longitude_risk", "reprojection_command",
]


def extract_real_stac_url(browser_url: str) -> str:
    """Extract and normalize the real STAC JSON URL from a STAC Browser URL,
    or pass through a direct STAC catalog/item URL unchanged.

    Supports three input shapes:
    - the older hash-based browser format (.../#/external/<url>)
    - the newer path-based browser format used by Vantor's browser
      (.../external/<url>)
    - a direct STAC catalog/item URL with no browser wrapper at all
      (e.g. https://data.source.coop/.../catalog.json) — treated as
      already being the real STAC URL.
    """
    if "#/external/" in browser_url:
        raw_url = browser_url.split("#/external/")[-1].strip()
    elif "/external/" in browser_url:
        raw_url = browser_url.split("/external/")[-1].strip()
    else:
        # No browser wrapper detected — assume this is already a direct
        # STAC URL. Invalid input still fails gracefully later, when
        # fetch_json() can't reach it.
        raw_url = browser_url.strip()

    real_url = unquote(raw_url)

    if "?" in real_url:
        real_url = real_url.split("?")[0]

    parsed = urlparse(real_url)
    if not parsed.scheme:
        real_url = "https://" + real_url

    if not real_url.endswith(".json"):
        st.warning("Extracted URL does not end with .json — may not be a valid STAC JSON")

    return real_url


def resolve_relative_url(base_url: str, relative_url: str) -> str:
    """Convert a relative URL to an absolute URL."""
    if relative_url.startswith(('http://', 'https://')):
        return relative_url
    elif relative_url.startswith('./'):
        relative_url = relative_url[2:]

    return urljoin(base_url, relative_url)


def format_datetime_display(iso_str: str) -> str:
    """Format an ISO 8601 datetime string to match OAM's own date display
    exactly, e.g. "Aug 5, 2026 12:00 AM" (no leading zero on day or hour).
    The value is kept in UTC as recorded in the STAC item — no timezone
    conversion is applied.
    Falls back to the raw string rather than dropping it if parsing fails.
    """
    if not iso_str:
        return ""
    try:
        s = iso_str.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        # Some providers use more than 6 digits of fractional seconds,
        # which fromisoformat can choke on — trim to microsecond precision.
        s = re.sub(r"(\.\d{6})\d+", r"\1", s)
        dt = datetime.fromisoformat(s)

        month = dt.strftime("%b")
        day = str(dt.day)
        year = dt.year
        hour12 = dt.strftime("%I").lstrip("0") or "12"
        minute = dt.strftime("%M")
        ampm = dt.strftime("%p")

        return f"{month} {day}, {year} {hour12}:{minute} {ampm}"
    except Exception:
        return iso_str


def guess_provider_name(item_url: str) -> str:
    """Best-effort provider display name from the item's URL — checks the
    domain (Vantor, Maxar) and, for providers hosted on shared platforms
    like source.coop, the URL path (Planet)."""
    parsed = urlparse(item_url)
    domain = parsed.netloc.lower()
    path = parsed.path.lower()
    if "vantor" in domain:
        return "Vantor"
    if "maxar" in domain:
        return "Maxar"
    if "planet" in path:
        return "Planet"
    return domain


def compute_utm_epsg(lon: float, lat: float) -> int:
    """Compute the UTM EPSG code (WGS84 datum) for a given lon/lat."""
    zone = int((lon + 180) // 6) + 1
    zone = max(1, min(60, zone))
    return (32600 if lat >= 0 else 32700) + zone


def build_reprojection_command(item_id: str, epsg: int) -> str:
    """gdalwarp command to reproject imagery into the given UTM zone, per
    the workaround documented in OAM issue #296.
    Kept as a single line (no backslash line-continuation) so it works
    unmodified in cmd.exe, PowerShell, and bash/zsh alike — backslash
    continuation is bash-only and breaks silently in cmd.exe.
    """
    src_name = f"{item_id}.tif"
    dst_name = f"{item_id}_utm.tif"
    return (
        f"gdalwarp -multi -wo NUM_THREADS=ALL_CPUS -t_srs EPSG:{epsg} -r cubic -of COG "
        f"-co COMPRESS=JPEG -co QUALITY=85 -co OVERVIEWS=IGNORE_EXISTING "
        f"-co BLOCKSIZE=512 -co BIGTIFF=YES -co NUM_THREADS=ALL_CPUS "
        f"{src_name} {dst_name}"
    )


def check_oam_longitude_risk(item_data: dict) -> dict:
    """Best-effort heuristic flag for a known OAM uploader bug
    (see OAM_UPLOADER_ISSUE_URL): the old transcoder silently fails on
    geographic-CRS (e.g. EPSG:4326) imagery whose longitude exceeds +/-90.

    This STAC item doesn't tell us the raster's true CRS (no proj:epsg
    extension present), so this checks the item's WGS84 bbox as a
    heuristic trigger only — not a confirmed diagnosis.
    """
    bbox = item_data.get("bbox")
    if not bbox or len(bbox) < 4:
        return {"at_risk": False, "epsg": None, "command": ""}

    west, south, east, north = bbox[0], bbox[1], bbox[2], bbox[3]
    at_risk = abs(west) > 90 or abs(east) > 90

    if not at_risk:
        return {"at_risk": False, "epsg": None, "command": ""}

    center_lon = (west + east) / 2
    center_lat = (south + north) / 2
    epsg = compute_utm_epsg(center_lon, center_lat)
    item_id = item_data.get("id", "item")

    return {"at_risk": True, "epsg": epsg, "command": build_reprojection_command(item_id, epsg)}


def get_collection_license(item_url: str, item_data: dict) -> str:
    """Fallback for providers (e.g. Planet) that don't declare a license on
    the Item itself, only on its parent Collection. Fetches and caches the
    Collection's license per unique collection URL, so it's fetched once
    total per collection rather than once per item in it."""
    links = item_data.get("links", [])

    collection_href = None
    for link in links:
        if link.get("rel") == "collection":
            collection_href = link.get("href")
            break
    if not collection_href:
        for link in links:
            if link.get("rel") == "parent":
                collection_href = link.get("href")
                break
    if not collection_href:
        return ""

    collection_url = resolve_relative_url(item_url, collection_href)

    if collection_url in collection_license_cache:
        return collection_license_cache[collection_url]

    collection_data = fetch_json(collection_url)
    license_value = (collection_data or {}).get("license", "") or ""
    collection_license_cache[collection_url] = license_value
    return license_value


def extract_oam_metadata(item_url: str, item_data: dict, tiff_url: str) -> dict:
    """Map available STAC fields to OpenAerialMap upload-form fields.

    Platform, Provider, and the OAM License default are fixed best-effort
    values (per-provider) meant to be reviewed/edited, not auto-submitted
    blindly. Tags are intentionally left blank — STAC has no equivalent
    field, so anything auto-generated here would be a guess, not metadata.
    """
    properties = item_data.get("properties", {})

    title = properties.get("title") or item_data.get("id", "")

    instruments = properties.get("instruments") or []
    constellation = properties.get("constellation", "") or ""
    vehicle_name = properties.get("vehicle_name", "") or ""
    if instruments:
        sensor = ", ".join(instruments)
    elif constellation and vehicle_name:
        sensor = f"{constellation.title()} {vehicle_name}"
    else:
        sensor = constellation.title() or vehicle_name

    # STAC items commonly carry a single acquisition "datetime" rather than
    # a start/end range — both OAM date fields use that same instant.
    dt_display = format_datetime_display(properties.get("datetime", ""))
    date_start = dt_display
    date_end = dt_display

    longitude_risk = check_oam_longitude_risk(item_data)

    # Some providers only declare a license on the parent Collection, not
    # on the Item itself — fall back to that when the Item has none.
    stac_license = item_data.get("license", "") or ""
    if not stac_license:
        stac_license = get_collection_license(item_url, item_data)

    return {
        "item_url": item_url,
        "title": title,
        "platform": "Satellite",
        "sensor": sensor,
        "date_start": date_start,
        "date_end": date_end,
        "provider": guess_provider_name(item_url),
        "tags": "",
        "license_oam_default": OAM_DEFAULT_LICENSE,
        "stac_license_reference": stac_license,
        "image_source_url": tiff_url or "",
        "longitude_risk": longitude_risk["at_risk"],
        "reprojection_command": longitude_risk["command"],
    }


def guess_tiff_url(stac_item_url: str, item_data: dict) -> str:
    """
    Best-effort fallback for when a STAC item has no usable TIFF asset href.

    This is a GUESS based on known provider URL conventions (Maxar, Vantor),
    not a verified asset — callers must treat the result accordingly and the
    UI must flag it as unconfirmed. Returns None if nothing can be
    confidently guessed for the detected provider.
    """
    domain = urlparse(stac_item_url).netloc.lower()
    properties = item_data.get("properties", {})
    item_id = item_data.get("id", "")
    parsed_url = urlparse(stac_item_url)
    path_parts = parsed_url.path.split('/')

    # --- Maxar-style layout: events/{event}/ard/{grid}/{tile}/{date}/{image_id}-visual.tif
    if "maxar" in domain:
        event_name = grid = tile = date = None

        for i, part in enumerate(path_parts):
            if "events" in part and i + 1 < len(path_parts):
                event_name = path_parts[i + 1]
            if part.isdigit() and len(part) == 2:  # Grid like "44"
                grid = part
            if part.isdigit() and len(part) == 12:  # Tile like "033313123002"
                tile = part
            if re.match(r"\d{4}-\d{2}-\d{2}", part):  # Date pattern
                date = part

        if "event" in properties:
            event_name = properties.get("event", event_name)
        if "grid" in properties:
            grid = properties.get("grid", grid)
        if "tile" in properties:
            tile = properties.get("tile", tile)
        if properties.get("datetime"):
            date = properties["datetime"].split("T")[0]

        if event_name and grid and tile and date:
            if item_id and len(item_id) >= 16 and any(c.isalpha() for c in item_id):
                base_image_id = item_id[:16]
            else:
                base_image_id = "10400100AFC26500"  # Maxar default
            return f"https://{domain}/events/{event_name}/ard/{grid}/{tile}/{date}/{base_image_id}-visual.tif"

        return None

    # --- Vantor-style layout: events/{event}/{item_id}.json -> events/{event}/{item_id}-visual.tif
    if "vantor" in domain:
        event_name = None

        for i, part in enumerate(path_parts):
            if "events" in part and i + 1 < len(path_parts):
                event_name = path_parts[i + 1]

        if "event" in properties:
            event_name = properties.get("event", event_name)

        if event_name and item_id:
            return f"https://{domain}/events/{event_name}/{item_id}-visual.tif"

        return None

    # Unknown provider — no safe guess available
    return None


def fetch_json(url: str):
    """Fetch and parse JSON from a URL. Returns None (with a UI warning) on failure."""
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Failed to fetch {url}: {e}")
        return None


def generate_tiff_url(stac_item_url: str, item_data: dict):
    """
    Returns (tiff_url, is_guessed).
    Real asset hrefs found in the STAC item are always preferred over
    guessed URLs. Returns (None, False) if nothing could be found.
    """
    try:
        if item_data.get("type") == "Feature" and item_data.get("stac_version"):
            assets = item_data.get("assets", {})

            visual_assets = []
            for asset_name, asset_info in assets.items():
                href = asset_info.get("href", "")

                if href and href.endswith((".tif", ".tiff")):
                    absolute_href = resolve_relative_url(stac_item_url, href)

                    if any(keyword in asset_name.lower() for keyword in ["visual", "rgb", "natural"]):
                        visual_assets.insert(0, absolute_href)
                    else:
                        visual_assets.append(absolute_href)

            if visual_assets:
                return visual_assets[0], False

            # No usable asset href in the item itself — fall back to a guess
            guessed = guess_tiff_url(stac_item_url, item_data)
            if guessed:
                return guessed, True

        return None, False

    except Exception as e:
        st.warning(f"Could not generate TIFF URL for {stac_item_url}: {e}")
        return None, False


def process_item_data(item_url: str, item_data: dict):
    """Given an already-fetched STAC item, derive both its TIFF URL and its
    OAM-ready metadata in one pass (avoids fetching the item twice)."""
    tiff_url, is_guessed = generate_tiff_url(item_url, item_data)
    if tiff_url:
        tiff_links.append({"item_url": item_url, "tiff_url": tiff_url, "guessed": is_guessed})

    oam_items.append(extract_oam_metadata(item_url, item_data, tiff_url))


def process_item(item_url: str):
    """Fetch a STAC item by URL, then process it."""
    item_data = fetch_json(item_url)
    if item_data is None:
        return
    process_item_data(item_url, item_data)


def crawl_stac(url, visited=None):
    """Recursive STAC crawler for links with rel=item or rel=collection."""
    if visited is None:
        visited = set()

    if url in visited:
        return

    visited.add(url)

    data = fetch_json(url)
    if data is None:
        return

    links = data.get("links", [])

    for link in links:
        href = link.get("href")
        rel = link.get("rel")

        if not href:
            continue

        abs_href = urljoin(url, href)

        if rel == "item":
            if abs_href not in all_links:
                all_links.append(abs_href)
                process_item(abs_href)

        elif rel in ["collection", "child"]:
            if abs_href not in all_links:
                all_links.append(abs_href)
            crawl_stac(abs_href, visited)


# MAIN EXECUTION
if root_url_input:
    real_url = extract_real_stac_url(root_url_input)

    if real_url:
        with st.spinner("Crawling STAC links and generating TIFF URLs..."):
            root_data = fetch_json(real_url)

            if root_data is not None and root_data.get("type") == "Feature":
                # The root URL is itself a single STAC Item (common for Vantor
                # links), not a Catalog/Collection to crawl.
                all_links.append(real_url)
                process_item_data(real_url, root_data)
            elif root_data is not None:
                crawl_stac(real_url)

        if all_links:
            st.success(f"Found {len(all_links)} STAC links and generated {len(tiff_links)} TIFF URLs")

            tab1, tab2, tab3 = st.tabs(["STAC Links", "TIFF URLs", "OAM Metadata"])

            with tab1:
                st.subheader("Original STAC Links")
                for idx, link in enumerate(all_links, 1):
                    st.markdown(f"{idx}. [{link}]({link})")

            with tab2:
                st.subheader("Complete TIFF URLs")
                if tiff_links:
                    for idx, entry in enumerate(tiff_links, 1):
                        tiff_url = entry["tiff_url"]
                        if entry["guessed"]:
                            st.warning(f"#{idx}: this URL is a guess based on naming conventions — it is not confirmed to exist. Verify before relying on it.")
                        st.code(tiff_url, language=None)
                        st.markdown(f"{idx}. [{tiff_url}]({tiff_url})")

                    tiff_text = "\n".join(entry["tiff_url"] for entry in tiff_links)
                    st.download_button(
                        label="Download Complete TIFF URLs",
                        data=tiff_text,
                        file_name="complete_tiff_urls.txt",
                        mime="text/plain"
                    )
                else:
                    st.info("No TIFF URLs could be generated.")

            with tab3:
                st.subheader("OpenAerialMap Ready-to-Fill Metadata")
                st.caption(
                    "Title, Sensor, and Dates come from STAC metadata. Platform, Provider, and the "
                    "License below are fixed defaults meant to be reviewed before submitting — they "
                    "are not verified against OAM's actual requirements for this dataset. Tags are "
                    "left blank since STAC has no equivalent field."
                )

                st.caption(
                    f"Note: OAM's uploader has a known bug ([issue #296]({OAM_UPLOADER_ISSUE_URL})) where "
                    "geographic-CRS imagery beyond ±90° longitude can fail transcoding silently. Items below "
                    "flag this automatically when it may apply."
                )
                st.link_button("Open OAM Upload Page", "https://map.openaerialmap.org/#/upload")

                if oam_items:
                    for idx, meta in enumerate(oam_items, 1):
                        with st.expander(f"{idx}. {meta['title'] or meta['item_url']}"):
                            fields = [
                                ("Title", meta["title"]),
                                ("Platform", meta["platform"]),
                                ("Sensor", meta["sensor"]),
                                ("Date start", meta["date_start"]),
                                ("Date end", meta["date_end"]),
                                ("Image source (Url)", meta["image_source_url"]),
                                ("Provider", meta["provider"]),
                                ("Tags", meta["tags"]),
                                ("License", meta["license_oam_default"]),
                            ]
                            for label, value in fields:
                                col_label, col_value = st.columns([1, 3])
                                with col_label:
                                    st.markdown(f"**{label}**")
                                with col_value:
                                    st.code(value, language=None)

                            if meta["longitude_risk"]:
                                st.warning(
                                    "This item's bounding box crosses ±90° longitude. If the source imagery "
                                    f"is in a geographic CRS (e.g. EPSG:4326), OAM's uploader may fail silently "
                                    f"(see [issue #296]({OAM_UPLOADER_ISSUE_URL})). Workaround — reproject to "
                                    "the local UTM zone before uploading (replace the input filename with your "
                                    "actual downloaded file):"
                                )
                                st.code(meta["reprojection_command"], language="bash")

                                with st.expander("How to run this command on Windows (first time using GDAL)"):
                                    st.markdown(
                                        "1. **Download the image** — click the *Image source (Url)* link above "
                                        "(or right-click it → Save link as) and save the `.tif` file somewhere "
                                        "easy to find, e.g. your Downloads folder.\n"
                                        "2. **Install GDAL** — download and run the "
                                        "[OSGeo4W installer](https://trac.osgeo.org/osgeo4w/) "
                                        "(\"Express Web Install\"). Tick **GDAL** in the package list and finish "
                                        "the install.\n"
                                        "3. **Open the OSGeo4W Shell** from the Start Menu — it comes with "
                                        "`gdalwarp` already set up, no extra configuration needed.\n"
                                        "4. **Go to the folder with your file.** In that shell, type `cd ` "
                                        "followed by the folder path and press Enter, e.g.:\n"
                                        "   ```\n   cd C:\\Users\\YourName\\Downloads\n   ```\n"
                                        "5. **Paste the command above** into the shell as a single line and "
                                        "press Enter. Large images can take a minute or two.\n"
                                        "6. **Find the result** — a new file ending in `_utm.tif` will appear "
                                        "in that same folder. Upload **that** file to OAM instead of the "
                                        "original."
                                    )

                            if meta["stac_license_reference"]:
                                st.caption(
                                    f"STAC item's own license field: **{meta['stac_license_reference']}** — "
                                    f"the OAM License above defaults to {OAM_DEFAULT_LICENSE} regardless; "
                                    f"double-check this if the source license isn't CC-BY."
                                )

                            st.caption(f"Source item: {meta['item_url']}")

                    csv_buffer = io.StringIO()
                    writer = csv.DictWriter(csv_buffer, fieldnames=OAM_FIELDNAMES)
                    writer.writeheader()
                    for meta in oam_items:
                        writer.writerow(meta)

                    st.download_button(
                        label="Download OAM Metadata CSV",
                        data=csv_buffer.getvalue(),
                        file_name="oam_metadata.csv",
                        mime="text/csv"
                    )
                else:
                    st.info("No OAM metadata could be generated.")

        else:
            st.info("No item or collection links found.")
