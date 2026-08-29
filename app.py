import streamlit as st
import requests
from urllib.parse import urlparse, unquote, urljoin
import re
import io
import csv
from datetime import datetime
import time
import json
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium

# ---------- Constants ----------
OAM_DEFAULT_LICENSE = "CC-BY 4.0"
OAM_UPLOADER_ISSUE_URL = "https://github.com/hotosm/openaerialmap/issues/296"
OAM_MAP_URL = "https://map.openaerialmap.org/"
OAM_META_API = "https://api.openaerialmap.org/meta"

OAM_FIELDNAMES = [
    "item_url", "title", "platform", "sensor", "date_start", "date_end",
    "image_source_url", "provider", "tags", "license_oam_default", "stac_license_reference",
    "longitude_risk", "reprojection_command", "provider_item_id",
]

# ---------- Session State Initialization ----------
if "oam_duplicates" not in st.session_state:
    st.session_state["oam_duplicates"] = {}

if "location_filter_bbox" not in st.session_state:
    st.session_state["location_filter_bbox"] = None

if "pending_drawing" not in st.session_state:
    st.session_state["pending_drawing"] = None

if "last_processed_url" not in st.session_state:
    st.session_state["last_processed_url"] = ""

# ---------- Spatial & Geometry Helpers ----------
def parse_bbox_2d(bbox: list):
    """Safely extract 2D bbox [west, south, east, north] from 2D or 3D STAC bounding boxes."""
    if not bbox or len(bbox) < 4:
        return None
    if len(bbox) >= 6:
        return [bbox[0], bbox[1], bbox[3], bbox[4]]
    return [bbox[0], bbox[1], bbox[2], bbox[3]]

def calculate_iou(bbox1: list, bbox2: list) -> float:
    """Calculates Intersection over Union (IoU) overlap ratio between two 2D bboxes."""
    w1, s1, e1, n1 = bbox1
    w2, s2, e2, n2 = bbox2

    inter_w = max(0, min(e1, e2) - max(w1, w2))
    inter_h = max(0, min(n1, n2) - max(s1, s2))
    inter_area = inter_w * inter_h

    if inter_area <= 0:
        return 0.0

    area1 = (e1 - w1) * (n1 - s1)
    area2 = (e2 - w2) * (n2 - s2)
    union_area = area1 + area2 - inter_area
    return inter_area / union_area if union_area > 0 else 0.0

# ---------- OAM Duplicate Check Endpoint ----------
def check_oam_duplicate(meta: dict) -> dict:
    """
    Checks OAM for existing uploads.
    Combines direct Title/ID search with Spatial (Bbox IoU > 70%) footprint overlap detection.
    """
    provider_item_id = meta.get("provider_item_id", "").strip()
    stac_bbox = parse_bbox_2d(meta.get("bbox"))
    headers = {"User-Agent": "STAC-to-OAM-Tool/1.0"}

    # Method 1: Title query using provider item ID
    if provider_item_id:
        try:
            params = {"title": provider_item_id, "limit": 50}
            resp = requests.get(OAM_META_API, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                for item in results:
                    title = item.get("title", "")
                    if provider_item_id.lower() in title.lower():
                        return {
                            "exists": True,
                            "oam_id": item.get("_id"),
                            "oam_title": title,
                            "match_type": "Exact ID in Title",
                            "error": None
                        }
        except Exception:
            pass

    # Method 2: Fallback to Spatial Bbox Overlap match (IoU Threshold: 70%)
    if stac_bbox:
        bbox_str = ",".join(str(v) for v in stac_bbox)
        params = {"bbox": bbox_str, "limit": 100}
        try:
            resp = requests.get(OAM_META_API, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                for item in results:
                    oam_bbox = parse_bbox_2d(item.get("bbox"))
                    if oam_bbox:
                        iou = calculate_iou(stac_bbox, oam_bbox)
                        if iou > 0.70:
                            return {
                                "exists": True,
                                "oam_id": item.get("_id"),
                                "oam_title": item.get("title", "Untitled"),
                                "match_type": f"Spatial Overlap ({int(iou * 100)}%)",
                                "error": None
                            }
        except Exception as e:
            return {"exists": False, "oam_id": None, "oam_title": None, "match_type": None, "error": f"Bbox error: {e}"}

    return {"exists": False, "oam_id": None, "oam_title": None, "match_type": None, "error": None}

# ---------- STAC & GDAL Helpers ----------
def extract_real_stac_url(browser_url: str) -> str:
    if "#/external/" in browser_url:
        raw_url = browser_url.split("#/external/")[-1].strip()
    elif "/external/" in browser_url:
        raw_url = browser_url.split("/external/")[-1].strip()
    else:
        raw_url = browser_url.strip()
    real_url = unquote(raw_url)
    if "?" in real_url:
        real_url = real_url.split("?")[0]
    parsed = urlparse(real_url)
    if not parsed.scheme:
        real_url = "https://" + real_url
    if not real_url.endswith(".json"):
        st.warning("Extracted URL does not end with .json — verify if this is a valid STAC endpoint.")
    return real_url

def resolve_relative_url(base_url: str, relative_url: str) -> str:
    if relative_url.startswith(('http://', 'https://')):
        return relative_url
    elif relative_url.startswith('./'):
        relative_url = relative_url[2:]
    return urljoin(base_url, relative_url)

def format_datetime_display(iso_str: str) -> str:
    if not iso_str:
        return ""
    try:
        s = iso_str.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
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
    zone = int((lon + 180) // 6) + 1
    zone = max(1, min(60, zone))
    return (32600 if lat >= 0 else 32700) + zone

def build_reprojection_command(item_id: str, epsg: int) -> str:
    src_name = f"{item_id}.tif"
    dst_name = f"{item_id}_utm.tif"
    return (
        f"gdalwarp -multi -wo NUM_THREADS=ALL_CPUS -t_srs EPSG:{epsg} -r cubic -of COG "
        f"-co COMPRESS=JPEG -co QUALITY=85 -co OVERVIEWS=IGNORE_EXISTING "
        f"-co BLOCKSIZE=512 -co BIGTIFF=YES -co NUM_THREADS=ALL_CPUS "
        f"{src_name} {dst_name}"
    )

def check_oam_longitude_risk(item_data: dict) -> dict:
    bbox = parse_bbox_2d(item_data.get("bbox"))
    if not bbox:
        return {"at_risk": False, "epsg": None, "command": ""}
    west, south, east, north = bbox
    at_risk = abs(west) > 90 or abs(east) > 90
    if not at_risk:
        return {"at_risk": False, "epsg": None, "command": ""}

    # Anti-meridian wrap-around adjustment
    if west > east:
        center_lon = (west + east + 360) / 2
        if center_lon > 180:
            center_lon -= 360
    else:
        center_lon = (west + east) / 2

    center_lat = (south + north) / 2
    epsg = compute_utm_epsg(center_lon, center_lat)
    item_id = item_data.get("id", "item")
    return {"at_risk": True, "epsg": epsg, "command": build_reprojection_command(item_id, epsg)}

def get_collection_license(item_url: str, item_data: dict, collection_cache: dict) -> str:
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
    if collection_url in collection_cache:
        return collection_cache[collection_url]
    collection_data = fetch_json(collection_url)
    license_value = (collection_data or {}).get("license", "") or ""
    collection_cache[collection_url] = license_value
    return license_value

def extract_oam_metadata(item_url: str, item_data: dict, tiff_url: str, collection_cache: dict) -> dict:
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
    dt_display = format_datetime_display(properties.get("datetime", ""))
    date_start = dt_display
    date_end = dt_display
    longitude_risk = check_oam_longitude_risk(item_data)
    stac_license = item_data.get("license", "") or ""
    if not stac_license:
        stac_license = get_collection_license(item_url, item_data, collection_cache)
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
        "bbox": item_data.get("bbox"),
        "provider_item_id": item_data.get("id", ""),
    }

def bbox_intersects(item_bbox, filter_bbox) -> bool:
    parsed_item = parse_bbox_2d(item_bbox)
    if not parsed_item or not filter_bbox:
        return True
    iw, is_, ie, in_ = parsed_item
    fw, fs, fe, fn = filter_bbox
    return not (ie < fw or iw > fe or in_ < fs or is_ > fn)

def guess_tiff_url(stac_item_url: str, item_data: dict) -> str:
    domain = urlparse(stac_item_url).netloc.lower()
    properties = item_data.get("properties", {})
    item_id = item_data.get("id", "")
    parsed_url = urlparse(stac_item_url)
    path_parts = parsed_url.path.split('/')
    if "maxar" in domain:
        event_name = grid = tile = date = None
        for i, part in enumerate(path_parts):
            if "events" in part and i + 1 < len(path_parts):
                event_name = path_parts[i + 1]
            if part.isdigit() and len(part) == 2:
                grid = part
            if part.isdigit() and len(part) == 12:
                tile = part
            if re.match(r"\d{4}-\d{2}-\d{2}", part):
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
                base_image_id = "10400100AFC26500"
            return f"https://{domain}/events/{event_name}/ard/{grid}/{tile}/{date}/{base_image_id}-visual.tif"
        return None
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
    return None

def fetch_json(url: str):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Failed to fetch {url}: {e}")
        return None

def generate_tiff_url(stac_item_url: str, item_data: dict):
    try:
        if item_data.get("type") == "Feature" or "assets" in item_data:
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
            guessed = guess_tiff_url(stac_item_url, item_data)
            if guessed:
                return guessed, True
        return None, False
    except Exception as e:
        st.warning(f"Could not generate TIFF URL for {stac_item_url}: {e}")
        return None, False

def process_item_data(item_url: str, item_data: dict, tiff_links: list, oam_items: list, collection_cache: dict):
    tiff_url, is_guessed = generate_tiff_url(item_url, item_data)
    if tiff_url:
        tiff_links.append({"item_url": item_url, "tiff_url": tiff_url, "guessed": is_guessed})
    oam_items.append(extract_oam_metadata(item_url, item_data, tiff_url, collection_cache))

def process_item(item_url: str, tiff_links: list, oam_items: list, collection_cache: dict):
    item_data = fetch_json(item_url)
    if item_data is None:
        return
    process_item_data(item_url, item_data, tiff_links, oam_items, collection_cache)

def crawl_stac(url, all_links: list, tiff_links: list, oam_items: list, collection_cache: dict, visited=None, data=None):
    if visited is None:
        visited = set()
    if url in visited:
        return
    visited.add(url)
    if data is None:
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
                process_item(abs_href, tiff_links, oam_items, collection_cache)
        elif rel in ["collection", "child"]:
            if abs_href not in all_links:
                all_links.append(abs_href)
            crawl_stac(abs_href, all_links, tiff_links, oam_items, collection_cache, visited)

@st.cache_data(show_spinner="Crawling STAC links and generating TIFF URLs...", ttl=600)
def run_crawl(real_url: str):
    all_links = []
    tiff_links = []
    oam_items = []
    collection_cache = {}
    root_data = fetch_json(real_url)
    if root_data is not None and root_data.get("type") == "Feature":
        all_links.append(real_url)
        process_item_data(real_url, root_data, tiff_links, oam_items, collection_cache)
    elif root_data is not None:
        crawl_stac(real_url, all_links, tiff_links, oam_items, collection_cache, data=root_data)
    return all_links, tiff_links, oam_items

# ---------- Main Application Interface ----------
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

if root_url_input:
    real_url = extract_real_stac_url(root_url_input)

    # Reset duplicates state if input URL changes
    if real_url != st.session_state["last_processed_url"]:
        st.session_state["oam_duplicates"] = {}
        st.session_state["location_filter_bbox"] = None
        st.session_state["pending_drawing"] = None
        st.session_state["last_processed_url"] = real_url

    if real_url:
        col_recrawl, _ = st.columns([1, 3])
        with col_recrawl:
            if st.button("🔄 Re-crawl (ignore cache)"):
                run_crawl.clear()
                st.session_state["oam_duplicates"] = {}
                st.session_state["location_filter_bbox"] = None
                st.session_state["pending_drawing"] = None

        all_links, tiff_links, oam_items = run_crawl(real_url)

        if all_links:
            st.success(f"Found {len(all_links)} STAC links and generated {len(tiff_links)} TIFF URLs")

            group_by_location = st.toggle("📍 Group by location (draw a box on the map)")

            if group_by_location:
                items_with_bbox = [m for m in oam_items if parse_bbox_2d(m.get("bbox"))]
                if items_with_bbox:
                    st.caption(
                        "Item footprints are shown as blue boxes. Draw a rectangle over the area you "
                        "want, then click Apply filter."
                    )
                    
                    parsed_bboxes = [parse_bbox_2d(m["bbox"]) for m in items_with_bbox]
                    all_lons = [b[0] for b in parsed_bboxes] + [b[2] for b in parsed_bboxes]
                    all_lats = [b[1] for b in parsed_bboxes] + [b[3] for b in parsed_bboxes]
                    center_lat = sum(all_lats) / len(all_lats)
                    center_lon = sum(all_lons) / len(all_lons)

                    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=5)
                    for m in items_with_bbox:
                        b = parse_bbox_2d(m["bbox"])
                        folium.Rectangle(
                            bounds=[[b[1], b[0]], [b[3], b[2]]],
                            color="blue", weight=1, fill=True, fill_opacity=0.1,
                            tooltip=m["title"],
                        ).add_to(fmap)

                    Draw(
                        export=False,
                        draw_options={
                            "rectangle": True, "polygon": False, "circle": False,
                            "marker": False, "circlemarker": False, "polyline": False,
                        },
                        edit_options={"edit": False},
                    ).add_to(fmap)

                    map_data = st_folium(fmap, height=420, width=700, key="location_filter_map")
                    
                    # Store active drawing safely into session_state before rerun triggers
                    if map_data and map_data.get("last_active_drawing"):
                        st.session_state["pending_drawing"] = map_data["last_active_drawing"]

                    col_apply, col_clear = st.columns([1, 1])
                    with col_apply:
                        if st.button("Apply filter"):
                            drawn = st.session_state.get("pending_drawing")
                            if drawn and drawn.get("geometry", {}).get("type") == "Polygon":
                                coords = drawn["geometry"]["coordinates"][0]
                                lons = [c[0] for c in coords]
                                lats = [c[1] for c in coords]
                                st.session_state["location_filter_bbox"] = (min(lons), min(lats), max(lons), max(lats))
                            else:
                                st.warning("Draw a rectangle on the map first, then click Apply filter.")
                    with col_clear:
                        if st.button("Clear filter"):
                            st.session_state["location_filter_bbox"] = None
                            st.session_state["pending_drawing"] = None

                    active_filter = st.session_state["location_filter_bbox"]
                    if active_filter:
                        w, s, e, n = active_filter
                        st.caption(f"Active filter box: {w:.3f}, {s:.3f} to {e:.3f}, {n:.3f}")
                else:
                    st.info("No item footprints available to plot (items are missing bbox data).")

            active_filter = st.session_state["location_filter_bbox"] if group_by_location else None
            if active_filter:
                filtered_item_urls = {
                    m["item_url"] for m in oam_items if bbox_intersects(m.get("bbox"), active_filter)
                }
                display_tiff_links = [e for e in tiff_links if e["item_url"] in filtered_item_urls]
                display_oam_items = [m for m in oam_items if m["item_url"] in filtered_item_urls]
                st.caption(f"Showing {len(display_oam_items)} of {len(oam_items)} items within the drawn box.")
            else:
                display_tiff_links = tiff_links
                display_oam_items = oam_items

            tab1, tab2, tab3 = st.tabs(["STAC Links", "TIFF URLs", "OAM Metadata"])

            with tab1:
                st.subheader("Original STAC Links")
                for idx, link in enumerate(all_links, 1):
                    st.markdown(f"{idx}. [{link}]({link})")

            with tab2:
                st.subheader("Complete TIFF URLs")
                if display_tiff_links:
                    for idx, entry in enumerate(display_tiff_links, 1):
                        tiff_url = entry["tiff_url"]
                        if entry["guessed"]:
                            st.warning(f"#{idx}: this URL is a guess based on naming conventions — it is not confirmed to exist. Verify before relying on it.")
                        st.code(tiff_url, language=None)
                        st.markdown(f"{idx}. [{tiff_url}]({tiff_url})")

                    tiff_text = "\n".join(entry["tiff_url"] for entry in display_tiff_links)
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

                if display_oam_items:
                    col_check, _ = st.columns([1, 4])
                    with col_check:
                        if st.button("🔍 Check duplicates on OAM"):
                            st.session_state["oam_duplicates"] = {}
                            progress_bar = st.progress(0, text="Checking OAM metadata...")
                            total = len(display_oam_items)
                            for i, meta in enumerate(display_oam_items):
                                result = check_oam_duplicate(meta)
                                st.session_state["oam_duplicates"][meta["item_url"]] = result
                                if i % 5 == 0 or i == total - 1:
                                    progress_bar.progress((i + 1) / total, text=f"Checked {i+1}/{total}")
                                time.sleep(0.15)
                            progress_bar.empty()
                            st.success("Duplicate check complete!")

                if display_oam_items:
                    for idx, meta in enumerate(display_oam_items, 1):
                        with st.expander(f"{idx}. {meta['title'] or meta['item_url']}"):
                            dup_info = st.session_state.get("oam_duplicates", {}).get(meta["item_url"])
                            if dup_info is not None:
                                if dup_info.get("error"):
                                    st.warning(f"⚠️ Duplicate check failed: {dup_info['error']}")
                                elif dup_info.get("exists"):
                                    oam_id = dup_info.get("oam_id", "unknown")
                                    oam_title = dup_info.get("oam_title", "")
                                    match_type = dup_info.get("match_type", "Matched")
                                    st.success(f"✅ Already uploaded to OAM (ID: {oam_id})\n\n_Title:_ {oam_title}\n\n_Match Method:_ {match_type}")
                                else:
                                    st.info("❌ Not found on OAM – ready to upload.")
                            else:
                                st.caption("Click 'Check duplicates on OAM' above to see if this item already exists.")

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

                            st.markdown("**Check for duplicates on OAM**")
                            st.caption(
                                "OAM titles often embed the provider's original ID. Copy the ID below "
                                "if you wish to manually query OAM search."
                            )
                            st.code(meta["provider_item_id"], language=None)
                            st.link_button("Open OAM to search manually", OAM_MAP_URL)

                            if meta["longitude_risk"]:
                                st.warning(
                                    "This item's bounding box crosses ±90° longitude. If the source imagery "
                                    f"is in a geographic CRS (e.g. EPSG:4326), OAM's uploader may fail silently "
                                    f"(see [issue #296]({OAM_UPLOADER_ISSUE_URL})). Workaround — reproject to "
                                    "the local UTM zone before uploading:"
                                )
                                st.code(meta["reprojection_command"], language="bash")

                                with st.expander("How to run this command on Windows (first time using GDAL)"):
                                    st.markdown(
                                        "1. **Download the image** — click the *Image source (Url)* link above "
                                        "and save the `.tif` file.\n"
                                        "2. **Install GDAL** via the "
                                        "[OSGeo4W installer](https://trac.osgeo.org/osgeo4w/).\n"
                                        "3. **Open OSGeo4W Shell** from Start Menu.\n"
                                        "4. **Navigate to directory**: `cd C:\\Users\\YourName\\Downloads`\n"
                                        "5. **Paste command** above and press Enter.\n"
                                        "6. Upload generated `_utm.tif` file to OAM."
                                    )

                            if meta["stac_license_reference"]:
                                st.caption(
                                    f"STAC item license field: **{meta['stac_license_reference']}** — "
                                    f"the OAM License defaults to {OAM_DEFAULT_LICENSE}; double-check if source license differs."
                                )

                            st.caption(f"Source item: {meta['item_url']}")

                    csv_buffer = io.StringIO()
                    writer = csv.DictWriter(csv_buffer, fieldnames=OAM_FIELDNAMES, extrasaction="ignore")
                    writer.writeheader()
                    for meta in display_oam_items:
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
