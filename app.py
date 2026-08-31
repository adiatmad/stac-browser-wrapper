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
from shapely.geometry import box, shape

# Try importing GDAL for server-side VRT generation; fallback gracefully if unavailable
try:
    from osgeo import gdal
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False

# ---------- Constants ----------
OAM_DEFAULT_LICENSE = "CC-BY 4.0"
OAM_UPLOADER_ISSUE_URL = "https://github.com/hotosm/openaerialmap/issues/296"
OAM_MAP_URL = "https://map.openaerialmap.org/"
OAM_META_API = "https://api.openaerialmap.org/meta"
OAM_UPLOAD_API = "https://upload-api.openaerialmap.org/upload"

DEFAULT_SAMPLE_URL = (
    "https://browser.moregeo.it/external/vantor-opendata.s3.amazonaws.com/"
    "events/Nepal-Flooding-Aug-2026/collection.json"
)

OAM_FIELDNAMES = [
    "item_url", "title", "platform", "sensor", "date_start", "date_end",
    "image_source_url", "provider", "tags", "license_oam_default", 
    "stac_license_reference", "longitude_risk", "reprojection_command", 
    "provider_item_id", "oam_duplicate_status"
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

def calculate_exact_iou(stac_geom: dict, oam_bbox: list) -> float:
    """Calculates true spatial Intersection over Union (IoU) using Shapely geometries."""
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
    """Extracts event name dynamically from URL path for filenames."""
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

# ---------- VRT & Command Generator Helpers ----------
def build_gdal_cli_command(tiff_urls: list[str], output_filename: str) -> str:
    """Generates a ready-to-run terminal GDAL command for virtual mosaic creation."""
    vsicurl_urls = [f'"/vsicurl/{url}"' for url in tiff_urls if url]
    urls_str = " ".join(vsicurl_urls)
    return f"gdalbuildvrt -srcnodata 0 -vrtnodata 0 -addalpha {output_filename} {urls_str}"

def build_python_script_query(tiff_urls: list[str], output_filename: str) -> str:
    """Generates a ready-to-run Python query script for Google Colab or local execution."""
    urls_json = json.dumps(tiff_urls, indent=4)
    return f'''import os
from osgeo import gdal

urls = {urls_json}
vsicurl_urls = [f"/vsicurl/{{u}}" for u in urls]

print("Building virtual mosaic for {{len(urls)}} scenes...")
options = gdal.BuildVRTOptions(srcNodata=0, vrtNodata=0, addAlpha=True)
vrt_ds = gdal.BuildVRT("{output_filename}", vsicurl_urls, options=options)
vrt_ds.FlushCache()
print("Success! Virtual raster saved to: {output_filename}")
'''

def generate_vrt_bytes(tiff_urls: list[str]) -> str | None:
    """Generates in-memory VRT XML using GDAL C-library if available."""
    if not GDAL_AVAILABLE or not tiff_urls:
        return None
    try:
        vsicurl_urls = [f"/vsicurl/{url}" for url in tiff_urls if url]
        vrt_path = "/vsimem/temp_mosaic.vrt"
        options = gdal.BuildVRTOptions(srcNodata=0, vrtNodata=0, addAlpha=True)
        ds = gdal.BuildVRT(vrt_path, vsicurl_urls, options=options)
        ds.FlushCache()
        
        f = gdal.VSIFOpenL(vrt_path, "rb")
        gdal.VSIFSeekL(f, 0, 2)
        size = gdal.VSIFTellL(f)
        gdal.VSIFSeekL(f, 0, 0)
        vrt_bytes = gdal.VSIFReadL(1, size, f)
        gdal.VSIFCloseL(f)
        gdal.Unlink(vrt_path)
        return vrt_bytes.decode("utf-8")
    except Exception:
        return None

# ---------- OAM Duplicate Check & Upload Helpers ----------
def check_oam_duplicate(meta: dict) -> dict:
    """Checks OAM for existing uploads via Title/ID and Spatial IoU match."""
    provider_item_id = meta.get("provider_item_id", "").strip()
    stac_bbox = parse_bbox_2d(meta.get("bbox"))
    stac_geom = meta.get("geometry")
    headers = {"User-Agent": "STAC-to-OAM-Tool/2.0"}

    # Title query using provider item ID
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
                            "status_str": "Already exists (Exact ID in Title)",
                            "error": None
                        }
        except Exception:
            pass

    # Spatial Overlap match with Shapely (IoU Threshold: 70%)
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
                            return {
                                "exists": True,
                                "oam_id": item.get("_id"),
                                "status_str": f"Already exists (Spatial Overlap {int(iou * 100)}%)",
                                "error": None
                            }
        except Exception as e:
            return {"exists": False, "oam_id": None, "status_str": f"Check Failed: {e}", "error": str(e)}

    return {"exists": False, "oam_id": None, "status_str": "Not found on OAM", "error": None}

def upload_item_to_oam(token: str, meta: dict) -> tuple[bool, str]:
    """Submits single imagery metadata payload to OpenAerialMap upload API."""
    if not token or not token.strip():
        return False, "OAM API Token missing. Enter your token in the sidebar."
    
    headers = {
        "Authorization": f"Bearer {token.strip()}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "title": meta["title"],
        "platform": meta["platform"].lower(),
        "sensor": meta["sensor"],
        "provider": meta["provider"],
        "license": meta["license_oam_default"],
        "acquisition_start": meta["raw_datetime"] or datetime.utcnow().isoformat() + "Z",
        "acquisition_end": meta["raw_datetime"] or datetime.utcnow().isoformat() + "Z",
        "remote_url": meta["image_source_url"],
        "tags": meta["tags"] if meta["tags"] else "STAC Ingest"
    }
    
    try:
        resp = requests.post(OAM_UPLOAD_API, json=payload, headers=headers, timeout=25)
        if resp.status_code in [200, 201, 202]:
            upload_id = resp.json().get("upload", {}).get("_id", "Queued")
            return True, f"Successfully submitted to OAM (Upload ID: {upload_id})"
        else:
            return False, f"Upload API Error ({resp.status_code}): {resp.text}"
    except Exception as e:
        return False, f"HTTP Exception: {str(e)}"

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

def compute_utm_epsg(lon: float, lat: float) -> int:
    zone = int((lon + 180) // 6) + 1
    zone = max(1, min(60, zone))
    return (32600 if lat >= 0 else 32700) + zone

def build_reprojection_command(item_id: str, epsg: int) -> str:
    return (
        f"gdalwarp -multi -wo NUM_THREADS=ALL_CPUS -t_srs EPSG:{epsg} -r cubic -of COG "
        f"-co COMPRESS=JPEG -co QUALITY=85 -co OVERVIEWS=IGNORE_EXISTING "
        f"-co BLOCKSIZE=512 -co BIGTIFF=YES {item_id}.tif {item_id}_utm.tif"
    )

def check_oam_longitude_risk(item_data: dict) -> dict:
    bbox = parse_bbox_2d(item_data.get("bbox"))
    if not bbox:
        return {"at_risk": False, "epsg": None, "command": ""}
    west, south, east, north = bbox
    at_risk = abs(west) > 90 or abs(east) > 90
    if not at_risk:
        return {"at_risk": False, "epsg": None, "command": ""}

    center_lon = (west + east + 360) / 2 if west > east else (west + east) / 2
    if center_lon > 180:
        center_lon -= 360

    center_lat = (south + north) / 2
    epsg = compute_utm_epsg(center_lon, center_lat)
    item_id = item_data.get("id", "item")
    return {"at_risk": True, "epsg": epsg, "command": build_reprojection_command(item_id, epsg)}

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
    longitude_risk = check_oam_longitude_risk(item_data)
    stac_license = item_data.get("license") or properties.get("license", "")

    return {
        "item_url": item_url,
        "title": title,
        "platform": "Satellite",
        "sensor": sensor,
        "date_start": dt_display,
        "date_end": dt_display,
        "raw_datetime": raw_dt,
        "provider": guess_provider_name(item_data, item_url),
        "tags": "",
        "license_oam_default": OAM_DEFAULT_LICENSE,
        "stac_license_reference": stac_license,
        "image_source_url": tiff_url or "",
        "longitude_risk": longitude_risk["at_risk"],
        "reprojection_command": longitude_risk["command"],
        "bbox": item_data.get("bbox"),
        "geometry": item_data.get("geometry"),
        "provider_item_id": item_data.get("id", ""),
        "oam_duplicate_status": "Not checked"
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
    if tiff_url:
        tiff_links.append({"item_url": item_url, "tiff_url": tiff_url, "guessed": is_guessed})
    oam_items.append(extract_oam_metadata(item_url, item_data, tiff_url))

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

@st.cache_data(show_spinner="Crawling STAC catalog and resolving asset links...", ttl=600)
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
st.set_page_config(page_title="STAC-to-OAM Tool", layout="wide")
st.title("STAC-to-OAM Humanitarian Ingest & Online Mosaic Tool")

# Sidebar - OAM Settings
st.sidebar.header("OAM Upload Settings")
oam_token = st.sidebar.text_input("OAM API Token (Optional)", type="password", help="Paste your OpenAerialMap token for direct 1-click uploads.")
if oam_token:
    st.sidebar.success("Token Loaded – Ready for Direct Uploads")
else:
    st.sidebar.info("Provide a token above to enable direct Streamlit-to-OAM uploads.")

# Input Field
root_url_input = st.text_input("Enter STAC Catalog / Collection / Item Browser URL", value=DEFAULT_SAMPLE_URL)

if root_url_input:
    real_url = extract_real_stac_url(root_url_input)
    event_prefix = extract_event_name_from_url(real_url)

    if real_url != st.session_state["last_processed_url"]:
        st.session_state["oam_duplicates"] = {}
        st.session_state["location_filter_bbox"] = None
        st.session_state["pending_drawing"] = None
        st.session_state["last_processed_url"] = real_url

    if real_url:
        col_recrawl, _ = st.columns([1, 3])
        with col_recrawl:
            if st.button("🔄 Re-crawl Endpoint"):
                run_crawl.clear()
                st.session_state["oam_duplicates"] = {}
                st.session_state["location_filter_bbox"] = None

        all_links, tiff_links, oam_items = run_crawl(real_url)

        if all_links:
            st.success(f"Found {len(all_links)} STAC items and generated {len(tiff_links)} valid GeoTIFF URLs.")

            group_by_location = st.toggle("📍 Group by location (Draw bounding box on map)")

            if group_by_location:
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

            tab1, tab2, tab3 = st.tabs(["STAC Links", "TIFF URLs & Mosaics", "OAM Metadata & Ingestion"])

            with tab1:
                st.subheader("Original STAC Links")
                for idx, link in enumerate(all_links, 1):
                    st.markdown(f"{idx}. [{link}]({link})")

            with tab2:
                st.subheader("Validated GeoTIFF URLs & Online Merged Mosaics")
                
                # --- Categorize Imagery Mosaics (PRE / POST / ALL) ---
                pre_urls = [e["tiff_url"] for e in display_tiff_links if "PRE" in e["tiff_url"].upper() or "PRE" in e["item_url"].upper()]
                post_urls = [e["tiff_url"] for e in display_tiff_links if "POST" in e["tiff_url"].upper() or "POST" in e["item_url"].upper()]
                all_urls = [e["tiff_url"] for e in display_tiff_links]

                st.markdown("### 🌐 Ready-to-Run Mosaics (No Hardware Constraints)")
                st.caption("Merge remote Cloud-Optimized GeoTIFFs online into virtual layers without downloading large raster files.")

                mosaic_tab_pre, mosaic_tab_post, mosaic_tab_all = st.tabs([
                    f"PRE-Event ({len(pre_urls)} scenes)", 
                    f"POST-Event ({len(post_urls)} scenes)", 
                    f"ALL Scenes ({len(all_urls)} scenes)"
                ])

                def render_mosaic_queries(urls: list[str], category_name: str):
                    if not urls:
                        st.info(f"No {category_name} images found in this selection.")
                        return
                    
                    vrt_filename = f"{event_prefix}_{category_name.upper()}_mosaic.vrt"

                    # 1. Ready-to-run terminal command
                    st.markdown("#### 1. Ready-to-Run Terminal Command (GDAL CLI)")
                    st.caption("Copy and paste this into OSGeo4W Shell, Terminal, or Command Prompt:")
                    cli_cmd = build_gdal_cli_command(urls, vrt_filename)
                    st.code(cli_cmd, language="bash")

                    # 2. Ready-to-run Python script query
                    st.markdown("#### 2. Ready-to-Run Python Query (Google Colab / Jupyter)")
                    py_script = build_python_script_query(urls, vrt_filename)
                    st.code(py_script, language="python")

                    # 3. Server-side VRT download button (if GDAL binary available)
                    if GDAL_AVAILABLE:
                        vrt_xml = generate_vrt_bytes(urls)
                        if vrt_xml:
                            st.download_button(
                                label=f"📥 Download Merged {category_name} VRT (.vrt)",
                                data=vrt_xml,
                                file_name=vrt_filename,
                                mime="application/xml",
                                help="Open this lightweight .vrt file directly in QGIS to stream the combined imagery online."
                            )
                    else:
                        st.caption("ℹ️ *Note: Install GDAL Python package locally to enable direct .vrt file downloads in Streamlit.*")

                with mosaic_tab_pre:
                    render_mosaic_queries(pre_urls, "PRE")
                with mosaic_tab_post:
                    render_mosaic_queries(post_urls, "POST")
                with mosaic_tab_all:
                    render_mosaic_queries(all_urls, "ALL")

                st.markdown("---")
                st.markdown("### Raw Individual GeoTIFF Links")
                if display_tiff_links:
                    for idx, entry in enumerate(display_tiff_links, 1):
                        st.code(entry["tiff_url"], language=None)

                    tiff_text = "\n".join(entry["tiff_url"] for entry in display_tiff_links)
                    st.download_button(
                        label="Download Complete TIFF URLs List",
                        data=tiff_text,
                        file_name=f"{event_prefix}_tiff_urls.txt",
                        mime="text/plain"
                    )

            with tab3:
                st.subheader("OpenAerialMap Ingestion & Duplicate Protection")
                st.link_button("Open OAM Map", OAM_MAP_URL)

                if display_oam_items:
                    col_check, col_batch_upload = st.columns([1, 1])
                    with col_check:
                        if st.button("🔍 Check duplicates on OAM"):
                            st.session_state["oam_duplicates"] = {}
                            progress_bar = st.progress(0, text="Checking OAM API for duplicates...")
                            total = len(display_oam_items)
                            for i, meta in enumerate(display_oam_items):
                                result = check_oam_duplicate(meta)
                                st.session_state["oam_duplicates"][meta["item_url"]] = result
                                progress_bar.progress((i + 1) / total)
                                time.sleep(0.10)
                            progress_bar.empty()
                            st.success("Duplicate check complete!")

                    with col_batch_upload:
                        if st.button("🚀 Upload All Non-Duplicates to OAM"):
                            if not oam_token:
                                st.error("Please enter your OAM API Token in the sidebar first.")
                            else:
                                upload_bar = st.progress(0, text="Submitting non-duplicate items...")
                                total_upload = len(display_oam_items)
                                success_count = 0
                                
                                for i, meta in enumerate(display_oam_items):
                                    dup_status = st.session_state.get("oam_duplicates", {}).get(meta["item_url"], {})
                                    if dup_status.get("exists"):
                                        st.warning(f"Skipped '{meta['title']}' – Duplicate detected.")
                                    else:
                                        ok, msg = upload_item_to_oam(oam_token, meta)
                                        if ok:
                                            success_count += 1
                                            st.success(f"Uploaded #{i+1}: {meta['title']}")
                                        else:
                                            st.error(f"Failed #{i+1}: {msg}")
                                    upload_bar.progress((i + 1) / total_upload)
                                upload_bar.empty()
                                st.info(f"Batch upload finished. {success_count} item(s) submitted.")

                    # Build detailed meta items with duplicate status
                    for meta in display_oam_items:
                        dup_info = st.session_state.get("oam_duplicates", {}).get(meta["item_url"])
                        if dup_info:
                            meta["oam_duplicate_status"] = dup_info.get("status_str", "Not checked")
                        else:
                            meta["oam_duplicate_status"] = "Not checked"

                    # Item Cards
                    for idx, meta in enumerate(display_oam_items, 1):
                        status_label = meta["oam_duplicate_status"]
                        with st.expander(f"{idx}. {meta['title']} | Status: [{status_label}]"):
                            if "Already exists" in status_label:
                                st.warning(f"⚠️ {status_label}")
                            elif "Not found" in status_label:
                                st.success(f"✅ {status_label} – Ready for submission.")
                            else:
                                st.caption("Click 'Check duplicates on OAM' above to refresh status.")

                            if oam_token and not ("Already exists" in status_label):
                                if st.button(f"Upload item #{idx} to OAM", key=f"btn_up_{idx}"):
                                    ok, msg = upload_item_to_oam(oam_token, meta)
                                    if ok:
                                        st.success(msg)
                                    else:
                                        st.error(msg)

                            fields = [
                                ("Title", meta["title"]),
                                ("Platform", meta["platform"]),
                                ("Sensor", meta["sensor"]),
                                ("Date start", meta["date_start"]),
                                ("Image source (Url)", meta["image_source_url"]),
                                ("Provider", meta["provider"]),
                                ("OAM Duplicate Status", meta["oam_duplicate_status"]),
                            ]
                            for label, value in fields:
                                col_lbl, col_val = st.columns([1, 3])
                                with col_lbl:
                                    st.markdown(f"**{label}**")
                                with col_val:
                                    st.code(value, language=None)

                            if meta["longitude_risk"]:
                                st.warning("±90° Longitude Risk Detected. Reprojection command:")
                                st.code(meta["reprojection_command"], language="bash")

                    # CSV Export
                    timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                    export_csv_filename = f"{event_prefix}_oam_metadata_{timestamp_str}.csv"

                    csv_buffer = io.StringIO()
                    writer = csv.DictWriter(csv_buffer, fieldnames=OAM_FIELDNAMES, extrasaction="ignore")
                    writer.writeheader()
                    for meta in display_oam_items:
                        writer.writerow(meta)

                    st.markdown("---")
                    st.download_button(
                        label=f"📥 Download CSV Metadata ({export_csv_filename})",
                        data=csv_buffer.getvalue(),
                        file_name=export_csv_filename,
                        mime="text/csv"
                    )
