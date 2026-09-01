import streamlit as st
import requests
from urllib.parse import urlparse, unquote, urljoin
import re
import io
import csv
from datetime import datetime
import time
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from shapely.geometry import box, shape

# Try importing GDAL for server-side VRT generation; fallback gracefully if unavailable
try:
    from osgeo import gdal
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False

# ---------- Constants ----------
OAM_DEFAULT_LICENSE = "CC-BY 4.0"
OAM_MAP_URL = "https://map.openaerialmap.org/"
OAM_META_API = "https://api.openaerialmap.org/meta"

DEFAULT_SAMPLE_URL = (
    "https://browser.moregeo.it/external/vantor-opendata.s3.amazonaws.com/"
    "events/Indonesia-Earthquakes-Aug-2026/collection.json"
)

OAM_FIELDNAMES = [
    "item_url", "title", "platform", "sensor", "date_start", "date_end",
    "image_source_url", "provider", "tags", "license_oam_default", 
    "stac_license_reference", "longitude_risk", "reprojection_command", 
    "provider_item_id", "oam_duplicate_status", "oam_existing_link"
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
    if not bbox or len(bbox) < 4:
        return None
    if len(bbox) >= 6:
        return [bbox[0], bbox[1], bbox[3], bbox[4]]
    return [bbox[0], bbox[1], bbox[2], bbox[3]]

def calculate_exact_iou(stac_geom: dict, oam_bbox: list) -> float:
    if not oam_bbox:
        return 0.0
    try:
        oam_2d = parse_bbox_2d(oam_bbox)
        if not oam_2d:
            return 0.0
        poly_oam = box(*oam_2d)
        
        if stac_geom:
            poly_stac = shape(stac_geom)
        else:
            poly_stac = poly_oam
            
        if not poly_stac.is_valid:
            poly_stac = poly_stac.buffer(0)
        if not poly_oam.is_valid:
            poly_oam = poly_oam.buffer(0)

        intersection = poly_stac.intersection(poly_oam).area
        union = poly_stac.union(poly_oam).area
        return (intersection / union) if union > 0 else 0.0
    except Exception:
        return 0.0

def extract_event_name_from_url(url: str) -> str:
    match = re.search(r'/events/([^/]+)', url)
    if match:
        return match.group(1)
    
    parsed = urlparse(url)
    path_parts = [p for p in parsed.path.split('/') if p]
    if path_parts:
        last_part = path_parts[-1].replace('.json', '')
        if last_part in ['catalog', 'collection', 'item'] and len(path_parts) > 1:
            return path_parts[-2]
        return last_part
    return "stac_event"

def get_item_phase(entry: dict) -> str:
    phase = str(entry.get("phase", "")).strip().lower()
    if phase == "pre":
        return "PRE"
    elif phase == "post":
        return "POST"

    title = str(entry.get("title", "")).upper()
    if "[PRE]" in title or " PRE " in title or title.startswith("PRE"):
        return "PRE"
    elif "[POST]" in title or " POST " in title or title.startswith("POST"):
        return "POST"

    return "OTHER"

# ---------- OAM Duplicate Check Helpers ----------
def generate_oam_map_link(oam_id: str) -> str:
    if not oam_id:
        return ""
    return f"https://api.imagery.hotosm.org/map/?href=https://api.imagery.hotosm.org/stac/collections/openaerialmap/items/{oam_id}"

def check_oam_duplicate(meta: dict) -> dict:
    provider_item_id = meta.get("provider_item_id", "").strip()
    stac_bbox = parse_bbox_2d(meta.get("bbox"))
    stac_geom = meta.get("geometry")
    headers = {"User-Agent": "STAC-to-OAM-Tool/7.1"}

    if provider_item_id:
        try:
            params = {"title": provider_item_id, "limit": 50}
            resp = requests.get(OAM_META_API, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                for item in results:
                    title = item.get("title", "")
                    if provider_item_id.lower() in title.lower():
                        oam_id = item.get("_id")
                        return {
                            "exists": True,
                            "oam_id": oam_id,
                            "status_str": "Already exists (Exact ID match)",
                            "link": generate_oam_map_link(oam_id),
                            "error": None
                        }
        except Exception:
            pass

    if stac_bbox:
        bbox_str = ",".join(str(v) for v in stac_bbox)
        params = {"bbox": bbox_str, "limit": 100}
        try:
            resp = requests.get(OAM_META_API, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                for item in results:
                    oam_bbox = item.get("bbox")
                    if oam_bbox:
                        iou = calculate_exact_iou(stac_geom, oam_bbox)
                        if iou > 0.70:
                            oam_id = item.get("_id")
                            return {
                                "exists": True,
                                "oam_id": oam_id,
                                "status_str": f"Already exists (Spatial Overlap {int(iou * 100)}%)",
                                "link": generate_oam_map_link(oam_id),
                                "error": None
                            }
        except Exception as e:
            return {"exists": False, "oam_id": None, "status_str": f"Check Failed: {e}", "link": "", "error": str(e)}

    return {"exists": False, "oam_id": None, "status_str": "Not found on OAM", "link": "", "error": None}

# ---------- STAC Crawling & Metadata Parsing ----------
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
        return dt.strftime("%b %d, %Y %I:%M %p")
    except Exception:
        return iso_str

def guess_provider_name(item_data: dict, item_url: str) -> str:
    providers = item_data.get("properties", {}).get("providers", []) or item_data.get("providers", [])
    if providers and isinstance(providers, list):
        p_name = providers[0].get("name")
        if p_name:
            return p_name
    parsed = urlparse(item_url)
    domain = parsed.netloc.lower()
    if "vantor" in domain:
        return "Vantor"
    if "maxar" in domain:
        return "Maxar"
    return domain or "Unknown"

def extract_oam_metadata(item_url: str, item_data: dict, tiff_url: str) -> dict:
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
        sensor = constellation.title() or vehicle_name or "Satellite Sensor"

    raw_dt = properties.get("datetime", "")
    dt_display = format_datetime_display(raw_dt)
    stac_license = item_data.get("license") or properties.get("license", "")

    return {
        "item_url": item_url,
        "title": title,
        "platform": "Satellite",
        "sensor": sensor,
        "date_start": dt_display,
        "date_end": dt_display,
        "raw_datetime": raw_dt,
        "phase": properties.get("phase") or properties.get("odp:phase") or "",
        "provider": guess_provider_name(item_data, item_url),
        "tags": "",
        "license_oam_default": OAM_DEFAULT_LICENSE,
        "stac_license_reference": stac_license,
        "image_source_url": tiff_url or "",
        "longitude_risk": False,
        "reprojection_command": "",
        "bbox": item_data.get("bbox"),
        "geometry": item_data.get("geometry"),
        "provider_item_id": item_data.get("id", ""),
        "oam_duplicate_status": "Not checked",
        "oam_existing_link": ""
    }

def bbox_intersects(item_bbox, filter_bbox) -> bool:
    parsed_item = parse_bbox_2d(item_bbox)
    if not parsed_item or not filter_bbox:
        return True
    iw, is_, ie, in_ = parsed_item
    fw, fs, fe, fn = filter_bbox
    return not (ie < fw or iw > fe or in_ < fs or is_ > fn)

def fetch_json(url: str):
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        st.warning(f"Failed to fetch {url}: {e}")
        return None

def generate_tiff_url_from_stac(stac_item_url: str, item_data: dict) -> tuple[str | None, bool]:
    assets = item_data.get("assets", {})
    if not assets:
        return None, False

    for key, asset in assets.items():
        href = asset.get("href", "")
        roles = asset.get("roles", [])
        if href and ("visual" in roles or "rgb" in key.lower() or "overview" in key.lower()):
            if href.endswith((".tif", ".tiff")):
                return resolve_relative_url(stac_item_url, href), False

    for asset in assets.values():
        href = asset.get("href", "")
        asset_type = asset.get("type", "").lower()
        if href and ("geotiff" in asset_type or href.endswith((".tif", ".tiff"))):
            return resolve_relative_url(stac_item_url, href), False

    return None, False

def process_item_data(item_url: str, item_data: dict, tiff_links: list, oam_items: list):
    tiff_url, is_guessed = generate_tiff_url_from_stac(item_url, item_data)
    meta = extract_oam_metadata(item_url, item_data, tiff_url)
    if tiff_url:
        tiff_links.append({
            "item_url": item_url,
            "tiff_url": tiff_url,
            "provider_item_id": meta["provider_item_id"],
            "guessed": is_guessed,
            "title": meta["title"],
            "phase": meta["phase"],
            "raw_datetime": meta["raw_datetime"]
        })
    oam_items.append(meta)

def crawl_stac(url: str, all_links: list, tiff_links: list, oam_items: list, visited=None, data=None):
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
                item_data = fetch_json(abs_href)
                if item_data:
                    process_item_data(abs_href, item_data, tiff_links, oam_items)
        elif rel in ["collection", "child"]:
            if abs_href not in all_links:
                all_links.append(abs_href)
                crawl_stac(abs_href, all_links, tiff_links, oam_items, visited)

@st.cache_data(show_spinner="Searching for imagery...", ttl=600)
def run_crawl(real_url: str):
    all_links = []
    tiff_links = []
    oam_items = []
    root_data = fetch_json(real_url)
    
    if root_data is not None and root_data.get("type") == "Feature":
        all_links.append(real_url)
        process_item_data(real_url, root_data, tiff_links, oam_items)
    elif root_data is not None:
        crawl_stac(real_url, all_links, tiff_links, oam_items, data=root_data)
        
    return all_links, tiff_links, oam_items

# ---------- Streamlit Main Application UI ----------
st.set_page_config(page_title="Humanitarian Imagery Wizard", layout="wide", initial_sidebar_state="collapsed")
st.title("🌍 Humanitarian Imagery Wizard")
st.markdown("Transform raw satellite data into ready-to-use maps for disaster response.")

st.header("Step 1: Fetch Event Imagery")
st.info("💡 Paste the URL of the data catalog you found. We will automatically find all the usable map images inside it.")

root_url_input = st.text_input("Data Catalog URL:", value=DEFAULT_SAMPLE_URL)

if root_url_input:
    real_url = extract_real_stac_url(root_url_input)
    event_prefix = extract_event_name_from_url(real_url)

    if real_url != st.session_state["last_processed_url"]:
        st.session_state["oam_duplicates"] = {}
        st.session_state["location_filter_bbox"] = None
        st.session_state["pending_drawing"] = None
        st.session_state["last_processed_url"] = real_url

    all_links, tiff_links, oam_items = run_crawl(real_url)

    if all_links:
        st.divider()
        st.header("Step 2: Isolate Target Area (Optional)")
        
        group_by_location = st.toggle("📍 Draw a box on the map to filter images")
        
        if group_by_location:
            st.info("🗺️ **Pro Tip:** Disaster imagery often covers huge regions. Draw a box over your specific activation area so you don't overwhelm the mapping software with unnecessary map data.")
            items_with_bbox = [m for m in oam_items if parse_bbox_2d(m.get("bbox"))]
            if items_with_bbox:
                parsed_bboxes = [parse_bbox_2d(m["bbox"]) for m in items_with_bbox]
                all_lons = [b[0] for b in parsed_bboxes] + [b[2] for b in parsed_bboxes]
                all_lats = [b[1] for b in parsed_bboxes] + [b[3] for b in parsed_bboxes]
                center_lat = sum(all_lats) / len(all_lats)
                center_lon = sum(all_lons) / len(all_lons)

                fmap = folium.Map(location=[center_lat, center_lon], zoom_start=6)
                for m in items_with_bbox:
                    b = parse_bbox_2d(m["bbox"])
                    folium.Rectangle(
                        bounds=[[b[1], b[0]], [b[3], b[2]]],
                        color="blue", weight=1, fill=True, fill_opacity=0.1,
                        tooltip=m["title"],
                    ).add_to(fmap)

                Draw(
                    export=False,
                    draw_options={"rectangle": True, "polygon": False, "circle": False, "marker": False},
                    edit_options={"edit": False},
                ).add_to(fmap)

                map_data = st_folium(fmap, height=380, width=700, key="location_filter_map")
                
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
                with col_clear:
                    if st.button("Clear filter"):
                        st.session_state["location_filter_bbox"] = None
                        st.session_state["pending_drawing"] = None

        active_filter = st.session_state["location_filter_bbox"] if group_by_location else None
        if active_filter:
            filtered_item_urls = {
                m["item_url"] for m in oam_items if bbox_intersects(m.get("bbox"), active_filter)
            }
            display_tiff_links = [e for e in tiff_links if e["item_url"] in filtered_item_urls]
            display_oam_items = [m for m in oam_items if m["item_url"] in filtered_item_urls]
        else:
            display_tiff_links = tiff_links
            display_oam_items = oam_items

        # Dashboard Metrics
        pre_items = [e for e in display_tiff_links if get_item_phase(e) == "PRE"]
        post_items = [e for e in display_tiff_links if get_item_phase(e) == "POST"]
        all_items = [e for e in display_tiff_links]
        
        st.subheader("📊 Imagery Found")
        m1, m2, m3 = st.columns(3)
        m1.metric("Total Usable Images", len(display_tiff_links))
        m2.metric("PRE-Event (Before Disaster)", len(pre_items))
        m3.metric("POST-Event (After Disaster)", len(post_items))

        st.divider()
        st.header("Step 3: Choose Your Goal")

        tab_tm, tab_oam, tab_adv = st.tabs([
            "🎯 Goal A: Setup a Mapping Project", 
            "🌍 Goal B: Publish to OpenAerialMap", 
            "⚙️ Advanced Data"
        ])

        with tab_tm:
            st.info("🗺️ **What is this?** These links allow mapping software (like the HOT Tasking Manager, iD Editor, or JOSM) to instantly stream the satellite imagery in the background so volunteers can trace buildings and roads.")
            
            mosaic_tab_pre, mosaic_tab_post, mosaic_tab_all = st.tabs([
                f"PRE-Event Baseline ({len(pre_items)} scenes)", 
                f"POST-Event Damage ({len(post_items)} scenes)", 
                f"ALL Scenes ({len(all_items)} scenes)"
            ])

            def render_instant_tms_workflow(items: list[dict], category_name: str):
                if not items:
                    st.info(f"No {category_name} images found in this selection.")
                    return
                
                ids = [item["provider_item_id"] for item in items if item.get("provider_item_id")]
                if not ids:
                    st.warning("Could not extract STAC Item IDs for the selected scenes.")
                    return
                    
                ids_str = ",".join(ids)

                tm_url = f"https://api.imagery.hotosm.org/raster/collections/vantor-opendata/tiles/WebMercatorQuad/{{z}}/{{x}}/{{y}}?ids={ids_str}&assets=visual&nodata=0"
                st.markdown("**1. For Tasking Manager & iD Editor:**")
                st.caption("Copy this URL and paste it directly into the 'Custom Imagery' field.")
                st.code(tm_url, language="text")

                josm_url = f"tms:https://api.imagery.hotosm.org/raster/collections/vantor-opendata/tiles/WebMercatorQuad/{{zoom}}/{{x}}/{{y}}?ids={ids_str}&assets=visual&nodata=0"
                st.markdown("**2. For JOSM Desktop Software:**")
                st.caption("Go to Imagery > Imagery Preferences > + TMS, and paste this URL.")
                st.code(josm_url, language="text")
                
                with st.expander("🛠️ Advanced: View the exact Image IDs in this layer"):
                    st.markdown("The images will render in this exact order (top ID renders in front).")
                    for idx, img_id in enumerate(ids, 1):
                        st.markdown(f"`{idx}. {img_id}`")

            with mosaic_tab_pre:
                render_instant_tms_workflow(pre_items, "PRE")
            with mosaic_tab_post:
                render_instant_tms_workflow(post_items, "POST")
            with mosaic_tab_all:
                render_instant_tms_workflow(all_items, "ALL")

        with tab_oam:
            st.info("🛑 **Why check for duplicates?** Uploading the exact same footprint twice clutters the global map. Use the button below to check if someone from the community has already uploaded these images before you download the final CSV.")
            
            if display_oam_items:
                if st.button("🔍 Check for Existing Map Duplicates"):
                    st.session_state["oam_duplicates"] = {}
                    progress_bar = st.progress(0, text="Checking global database...")
                    total = len(display_oam_items)
                    for i, meta in enumerate(display_oam_items):
                        result = check_oam_duplicate(meta)
                        st.session_state["oam_duplicates"][meta["item_url"]] = result
                        if result.get("exists") and result.get("link"):
                            meta["oam_existing_link"] = result["link"]
                        progress_bar.progress((i + 1) / total)
                        time.sleep(0.10)
                    progress_bar.empty()
                    st.success("Verification complete! Check the results below.")

                for meta in display_oam_items:
                    dup_info = st.session_state.get("oam_duplicates", {}).get(meta["item_url"])
                    if dup_info:
                        meta["oam_duplicate_status"] = dup_info.get("status_str", "Not checked")
                        if dup_info.get("link"):
                            meta["oam_existing_link"] = dup_info["link"]
                    else:
                        meta["oam_duplicate_status"] = "Not checked"

                for idx, meta in enumerate(display_oam_items, 1):
                    status_label = meta["oam_duplicate_status"]
                    with st.expander(f"{idx}. {meta['title']} | Status: [{status_label}]"):
                        if "Already exists" in status_label:
                            st.warning(f"⚠️ {status_label}")
                            if meta.get("oam_existing_link"):
                                if "Exact ID" in status_label:
                                    st.link_button("👀 View Exact Image (HOTOSM Viewer)", meta["oam_existing_link"])
                                else:
                                    st.link_button("⚠️ View Overlapping Image (HOTOSM Viewer)", meta["oam_existing_link"])
                        elif "Not found" in status_label:
                            st.success(f"✅ {status_label} – Ready for submission.")
                        
                        fields = [
                            ("Image Date", meta["date_start"]),
                            ("Satellite Provider", meta["provider"]),
                            ("Duplicate Status", meta["oam_duplicate_status"]),
                        ]
                        for label, value in fields:
                            col_lbl, col_val = st.columns([1, 3])
                            with col_lbl:
                                st.markdown(f"**{label}**")
                            with col_val:
                                st.code(value, language=None)

                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                export_csv_filename = f"{event_prefix}_ready_for_oam_{timestamp_str}.csv"

                csv_buffer = io.StringIO()
                writer = csv.DictWriter(csv_buffer, fieldnames=OAM_FIELDNAMES, extrasaction="ignore")
                writer.writeheader()
                for meta in display_oam_items:
                    writer.writerow(meta)

                st.markdown("---")
                st.download_button(
                    label=f"📥 Download Data for OAM Upload",
                    data=csv_buffer.getvalue(),
                    file_name=export_csv_filename,
                    mime="text/csv",
                    help="You can upload this file directly to the OpenAerialMap upload page."
                )

        with tab_adv:
            st.caption("Raw Data Endpoints for Developers")
            for idx, link in enumerate(all_links, 1):
                st.markdown(f"{idx}. [{link}]({link})")
