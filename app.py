import streamlit as st
import streamlit_shadcn_ui as ui
import requests
from urllib.parse import urlparse, unquote, urljoin
import re
import io
import csv
import json
import os
from datetime import datetime
import time
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from shapely.geometry import box, shape
from typing import Any
from urllib.parse import quote, urlencode, urlsplit
import xml.etree.ElementTree as ET

OAM_UPLOAD_URL = "https://upload.imagery.hotosm.org/"
SPACE_EYE_LICENSE = "CC-BY 4.0"
SPACE_EYE_PROVIDER = "SI Imaging Services"
SPACE_EYE_PLATFORM = "satellite"
SPACE_EYE_SENSOR = "SpaceEye-T"
SPACE_EYE_VERIFIED_ARCHIVE_KEY = (
    "disasters/Flood in Nepal (Disasters Charter Activation 1052), 2026/"
    "1st/ST1_20260830_043751_SEN_SSI1_001.zip"
)
SPACE_EYE_VERIFIED_ARCHIVE_MEMBER = (
    "ST1_20260830_043751_SEN_SSI1_001/"
    "IMG_01_ST1_PMS/"
    "IMG_ST1_202608300437518_PMS_SEN_LWO_202608_03698_001.TIF"
)
SPACE_EYE_VERIFIED_TIFF_DATETIME = "2026-08-30 04:37:53"

_S3_WEBSITE_RE = re.compile(
    r"^https?://(?P<bucket>[^./]+)\.s3-website[.-](?P<region>[a-z0-9-]+)\.amazonaws\.com/?$",
    re.IGNORECASE,
)


def parse_s3_browser_url(browser_url: str) -> tuple[str | None, str | None, str | None]:
    """Return (bucket, region, prefix) from an AWS S3 website browser URL."""
    parts = urlsplit((browser_url or "").strip())
    match = _S3_WEBSITE_RE.match(f"{parts.scheme}://{parts.netloc}{parts.path}")
    if not match:
        return None, None, None

    prefix = ""
    fragment = parts.fragment
    if fragment.startswith("prefix="):
        prefix = unquote(fragment[len("prefix="):])
    return match.group("bucket"), match.group("region"), prefix


def list_public_s3_objects(
    bucket: str, region: str, prefix: str, timeout: int = 30
) -> list[dict]:
    """List public S3 objects under a prefix using ListObjectsV2."""
    import requests

    endpoint = f"https://{bucket}.s3.{region}.amazonaws.com/"
    objects: list[dict] = []
    token: str | None = None

    while True:
        params = {"list-type": "2", "prefix": prefix}
        if token:
            params["continuation-token"] = token

        response = requests.get(endpoint, params=params, timeout=timeout)
        response.raise_for_status()
        root = ET.fromstring(response.text)
        ns = {"s3": "http://s3.amazonaws.com/doc/2006-03-01/"}

        for node in root.findall("s3:Contents", ns):
            key = node.findtext("s3:Key", default="", namespaces=ns)
            if not key:
                continue
            size = node.findtext("s3:Size", default="", namespaces=ns)
            modified = node.findtext("s3:LastModified", default="", namespaces=ns)
            objects.append(
                {
                    "key": key,
                    "size_bytes": int(size) if size else None,
                    "last_modified": modified,
                }
            )

        truncated = root.findtext("s3:IsTruncated", default="false", namespaces=ns)
        token = root.findtext(
            "s3:NextContinuationToken", default="", namespaces=ns
        ) or None
        if truncated.lower() != "true" or not token:
            return objects


def classify_s3_source_objects(
    objects: list[dict], exclude_masks_lineage: bool = True
) -> str:
    """Classify a public S3 prefix by the object types it actually exposes.

    DIRECT_RASTER means a public TIFF object URL is exposed and can receive the
    OAM direct-source handoff. ARCHIVE_ONLY means an archive object is exposed
    but no direct TIFF object is exposed by the listing; the archive may still
    contain TIFF imagery.
    EMPTY means no supported raster/archive object was found.
    """
    tiffs = filter_tiff_objects(objects, exclude_masks_lineage)
    if tiffs:
        return "DIRECT_RASTER"
    if any(str(obj.get("key", "")).lower().endswith(".zip") for obj in objects):
        return "ARCHIVE_ONLY"
    return "EMPTY"


def filter_tiff_objects(
    objects: list[dict], exclude_masks_lineage: bool = True
) -> list[dict]:
    """Keep GeoTIFF objects and optionally exclude common QA sidecars."""
    result = []
    for obj in objects:
        key = obj.get("key", "")
        upper = key.upper()
        if not key.lower().endswith((".tif", ".tiff")):
            continue
        if exclude_masks_lineage and ("/MASKS/" in upper or "/LINEAGE/" in upper):
            continue
        result.append(obj)
    return result


def public_s3_object_url(bucket: str, region: str, key: str) -> str:
    """Build the public HTTPS URL for an S3 object."""
    return f"https://{bucket}.s3.{region}.amazonaws.com/{quote(key, safe='/')}"


def build_remote_vsizip_path(archive_url: str, member_path: str | None = None) -> str:
    """Build a GDAL /vsizip//vsicurl/ path for a public ZIP object.

    This is a read-only access path: GDAL can stream a selected member from
    the remote archive without this app downloading or extracting the archive.
    The member path is optional so callers can first inspect the archive.
    """
    base = f"/vsizip//vsicurl/{archive_url}"
    if member_path:
        return f"{base}/{member_path.lstrip('/')}"
    return base


def spaceeye_verified_archive_member(archive_key: str) -> str | None:
    """Return the verified TIFF member for the known SpaceEye-T sample archive.

    The member path is evidence-backed for this specific public object only;
    it is not a generic ZIP extraction rule.
    """
    if archive_key == SPACE_EYE_VERIFIED_ARCHIVE_KEY:
        return SPACE_EYE_VERIFIED_ARCHIVE_MEMBER
    return None


def build_archive_proxy_url(
    proxy_base_url: str, archive_url: str, member_path: str
) -> str:
    """Build the public HTTPS URL served by the deployed archive proxy.

    This is only an OAM source URL when the proxy itself is publicly reachable
    by OAM. The proxy streams the selected ZIP member using HTTP Range requests
    rather than exposing a GDAL virtual path.
    """
    base = proxy_base_url.rstrip("/")
    query = urlencode({"archive_url": archive_url, "member": member_path}, quote_via=quote)
    return f"{base}/tiff?{query}"


def format_bytes(size: int | None) -> str:
    if size is None:
        return ""
    value = float(size)
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if value < 1024 or unit == "TB":
            return f"{int(value)} B" if unit == "B" else f"{value:.2f} {unit}"
        value /= 1024
    return ""


def build_oam_prefill_url(
    *,
    title: str,
    source_url: str,
    provider: str | None = None,
    platform: str | None = None,
    sensor: str | None = None,
    license: str | None = None,
    acquisition_start: str | None = None,
    acquisition_end: str | None = None,
    external_id: str | None = None,
    external_url: str | None = None,
) -> str:
    """Build the documented OAM uploader fragment prefill URL.

    Only evidence-backed fields should be passed. In particular, acquisition
    dates must not be inferred from S3 LastModified unless the source documents
    that field as an acquisition timestamp.
    """
    fields = {
        "title": title,
        "source_url": source_url,
        "provider": provider,
        "platform": platform,
        "license": license,
        "sensor": sensor,
        "acquisition_start": acquisition_start,
        "acquisition_end": acquisition_end,
        "external_id": external_id,
        "external_url": external_url,
    }
    clean = {k: v for k, v in fields.items() if v not in (None, "")}
    return OAM_UPLOAD_URL + "#" + urlencode(clean, quote_via=quote)


def spaceeye_oam_prefill(
    *, key: str, object_url: str, source_browser_url: str
) -> str:
    """Create a reviewed OAM handoff for SpaceEye-T open-data imagery."""
    filename = key.rsplit("/", 1)[-1]
    return build_oam_prefill_url(
        title=f"SpaceEye-T {filename}",
        source_url=object_url,
        provider=SPACE_EYE_PROVIDER,
        platform=SPACE_EYE_PLATFORM,
        sensor=SPACE_EYE_SENSOR,
        license=SPACE_EYE_LICENSE,
        external_id=f"spaceeye-t:{key}",
        external_url=source_browser_url,
    )

# ---------- Inlined imagery validation helpers ----------
STATUS_ORDER = {"PASS": 0, "WARN": 1, "FAIL": 2}

def metadata_value(info: dict[str, Any], domain: str, key: str) -> str | None:
    metadata = info.get("metadata") or {}
    values = metadata.get(domain) or {}
    value = values.get(key)
    return str(value) if value is not None else None

def first_band(info: dict[str, Any]) -> dict[str, Any]:
    bands = info.get("bands") or []
    return bands[0] if bands else {}

def band_types(info: dict[str, Any]) -> list[str]:
    return [str(b.get("type", "")) for b in info.get("bands") or []]

def color_interpretations(info: dict[str, Any]) -> list[str]:
    return [str(b.get("colorInterpretation", "")).lower() for b in info.get("bands") or []]

def has_overviews(info: dict[str, Any]) -> bool:
    bands = info.get("bands") or []
    return bool(bands) and all(bool(b.get("overviews")) for b in bands)

def is_tiled(info: dict[str, Any]) -> bool:
    size = info.get("size") or []
    band = first_band(info)
    block = band.get("block") or []
    if len(size) != 2 or len(block) != 2:
        return False
    # A block smaller than the full raster is normally tiled. We deliberately
    # do not require 256x256 or 512x512: COG-compatible block sizes vary.
    return block[0] < size[0] and block[1] < size[1]

def crs_present(info: dict[str, Any]) -> bool:
    cs = info.get("coordinateSystem")
    return bool(cs and (cs.get("wkt") or cs.get("projjson")))

def bounds_summary(info: dict[str, Any]) -> dict[str, Any]:
    corners = info.get("cornerCoordinates") or {}
    return {
        "upperLeft": corners.get("upperLeft"),
        "lowerRight": corners.get("lowerRight"),
        "wgs84Extent": info.get("wgs84Extent"),
    }

def add_check(checks: list[dict[str, Any]], status: str, name: str, detail: str) -> None:
    checks.append({"status": status, "name": name, "detail": detail})

def parse_gdalinfo_text(text: str) -> dict[str, Any]:
    """Parse standard plain-text gdalinfo output without requiring JSON."""
    import re

    raw = text.strip()
    if not raw:
        raise ValueError("No gdalinfo output was provided.")

    def search(pattern: str, flags: int = re.MULTILINE):
        return re.search(pattern, raw, flags)

    driver_match = search(r"^Driver:\s*([^/\r\n]+)")
    driver = driver_match.group(1).strip() if driver_match else ""

    size_match = search(r"^Size is\s+(\d+)\s*,\s*(\d+)")
    size = [int(size_match.group(1)), int(size_match.group(2))] if size_match else None

    crs_present_text = bool(search(r"^Coordinate System is:\s*$", re.MULTILINE))
    epsg_match = search(r'ID\["EPSG",\s*(\d+)\]')
    epsg = int(epsg_match.group(1)) if epsg_match else None

    block_matches = re.findall(
        r"^Band\s+(\d+)\s+Block=(\d+)x(\d+)\s+Type=([^,\r\n]+),\s*ColorInterp=([^\r\n]+)",
        raw,
        re.MULTILINE,
    )
    bands: list[dict[str, Any]] = []
    for number, bx, by, dtype, color in block_matches:
        bands.append({
            "band": int(number),
            "block": [int(bx), int(by)],
            "type": dtype.strip(),
            "colorInterpretation": color.strip(),
            "overviews": [],
        })

    # Plain gdalinfo prints overview dimensions on the line after each band.
    # Attach them by walking band sections rather than assuming a fixed count.
    sections = re.split(r"(?=^Band\s+\d+\s+)", raw, flags=re.MULTILINE)[1:]
    for band, section in zip(bands, sections):
        overview_match = re.search(r"^\s*Overviews:\s*(.+)$", section, re.MULTILINE)
        if overview_match:
            band["overviews"] = [x.strip() for x in overview_match.group(1).split(",") if x.strip()]

    wgs_match = search(
        r"^(?:Upper Left|Lower Left|Upper Right|Lower Right)\s+\([^\r\n]+\)"
    )
    has_corners = bool(wgs_match)

    image_structure = "\\n".join(
        f"{key}={value}" for key, value in re.findall(
            r"^\s+(LAYOUT|COMPRESSION)=([^\s\r\n]+)",
            raw,
            re.MULTILINE,
        )
    )
    layout_match = re.search(r"LAYOUT=([^\\s\\r\\n]+)", image_structure)
    compression_match = re.search(r"COMPRESSION=([^\\s\\r\\n]+)", image_structure)

    return {
        "driverShortName": driver,
        "size": size,
        "coordinateSystem": {
            "wkt": "present" if crs_present_text else "",
            "epsg": epsg,
        } if crs_present_text else None,
        "bands": bands,
        "cornerCoordinates": {"present": True} if has_corners else {},
        "wgs84Extent": {"epsg": epsg} if has_corners and epsg == 4326 else ({"present": True} if has_corners and crs_present_text else None),
        "metadata": {
            "IMAGE_STRUCTURE": {
                "LAYOUT": layout_match.group(1) if layout_match else "",
                "COMPRESSION": compression_match.group(1) if compression_match else "",
            }
        },
    }

def validate_info(info: dict[str, Any]) -> dict[str, Any]:
    """Validate already-collected gdalinfo JSON without touching the raster."""
    driver = str(info.get("driverShortName") or info.get("driver", ""))
    bands_data = info.get("bands") or []
    summary = {
        "file": "", "extension": "", "driver": driver, "size": info.get("size"),
        "bands": len(bands_data), "bandTypes": band_types(info),
        "colorInterpretations": color_interpretations(info), "crsPresent": crs_present(info),
        "isTiled": is_tiled(info), "hasOverviews": has_overviews(info),
        "cogLayout": metadata_value(info, "IMAGE_STRUCTURE", "LAYOUT"),
        "compression": metadata_value(info, "IMAGE_STRUCTURE", "COMPRESSION"),
        "bounds": bounds_summary(info),
    }
    checks: list[dict[str, Any]] = []
    d = driver.upper(); ext = ""; bands = summary["bands"]; types = summary["bandTypes"]; colors = summary["colorInterpretations"]
    add_check(checks, "PASS" if d == "GTIFF" else "WARN", "GeoTIFF driver", "GDAL reports GTiff." if d == "GTIFF" else f"GDAL reports {d or 'unknown'}; conversion to GeoTIFF is recommended.")
    add_check(checks, "PASS" if crs_present(info) else "FAIL", "CRS", "A coordinate reference system is present." if crs_present(info) else "No CRS was reported by GDAL.")
    size = info.get("size") or []
    if len(size) == 2 and bands_data:
        width, height = size
        bytes_per_sample = {"BYTE": 1, "UINT8": 1, "INT8": 1, "UINT16": 2, "INT16": 2, "UINT32": 4, "INT32": 4, "FLOAT32": 4, "FLOAT64": 8}
        first_size = bytes_per_sample.get((band_types(info)[0] if band_types(info) else "").upper())
        if first_size:
            decoded_gb = (width * height * len(bands_data) * first_size) / 1e9
            add_check(checks, "PASS" if decoded_gb <= 130 else "FAIL", "OAM decoded size", f"Estimated decoded size is {decoded_gb:.1f} GB (current OAM validation limit: 130 GB)." if decoded_gb <= 130 else f"Estimated decoded size is {decoded_gb:.1f} GB, above the current OAM validation limit of 130 GB.")
        else:
            add_check(checks, "WARN", "OAM decoded size", "Could not estimate decoded size because the pixel type is unknown.")
    else:
        add_check(checks, "WARN", "OAM decoded size", "Could not estimate decoded size from the supplied GDAL output.")
    add_check(checks, "PASS" if bands in (3, 4) else "FAIL", "Band count", f"{bands} bands; suitable for visual RGB/RGBA imagery." if bands in (3,4) else f"Found {bands} bands; visual target expects 3 RGB or 4 RGBA bands.")
    add_check(checks, "PASS" if types and all(t.upper() == "BYTE" for t in types) else "WARN", "Pixel type", "All bands are Byte/uint8." if types and all(t.upper() == "BYTE" for t in types) else f"Band types are {types or 'unknown'}; verify this is visual RGB/RGBA data.")
    rgb_ok = colors[:3] == ["red", "green", "blue"]
    alpha_ok = bands == 4 and len(colors) >= 4 and colors[3] in {"alpha", "undefined"}
    add_check(checks, "PASS" if rgb_ok and (bands == 3 or alpha_ok) else "WARN", "Color interpretation", "Bands are consistent with RGB/RGBA imagery." if rgb_ok and (bands == 3 or alpha_ok) else f"GDAL reports {colors or 'unknown'}; verify the bands.")
    add_check(checks, "PASS" if str(summary["cogLayout"]).upper() == "COG" else "WARN", "COG layout", "GDAL reports IMAGE_STRUCTURE LAYOUT=COG." if str(summary["cogLayout"]).upper() == "COG" else "Not reported as COG; the generated local output can create a COG.")
    add_check(checks, "PASS" if summary["isTiled"] else "WARN", "Internal tiling", "Raster blocks are tiled." if summary["isTiled"] else "Raster is not reported as internally tiled.")
    add_check(checks, "PASS" if summary["hasOverviews"] else "WARN", "Overviews", "All bands contain overviews." if summary["hasOverviews"] else "One or more bands have no reported overviews.")
    add_check(checks, "PASS" if summary["bounds"]["wgs84Extent"] else "WARN", "Geographic extent", "GDAL produced a WGS84 extent." if summary["bounds"]["wgs84Extent"] else "No WGS84 extent was reported; inspect georeferencing.")
    overall = max((STATUS_ORDER[x["status"]] for x in checks), default=2)
    return {"status": {0:"PASS",1:"WARN",2:"FAIL"}[overall], "summary": summary, "checks": checks}

def build_oam_recommendation(info: dict[str, Any], input_path: str, source_epsg: int | None = None, output_path: str | None = None) -> dict[str, Any]:
    """Return a conservative local target for OAM visual RGB/RGBA imagery."""
    bands = len(info.get("bands") or [])
    types = band_types(info)
    issues: list[str] = []
    if bands not in (3, 4):
        issues.append(f"Expected 3 or 4 bands for visual imagery; found {bands}.")
    if types and not all(t.upper() == "BYTE" for t in types):
        issues.append(f"Visual target normally uses Byte/uint8; found {types}.")
    if not crs_present(info) and source_epsg is None:
        issues.append("CRS is missing; supply the correct source EPSG before generating the command.")
    output_path = output_path or str(Path(input_path).with_name(Path(input_path).stem + "_oam_ready.tif"))
    command = None
    if not issues:
        if source_epsg:
            command = (f'gdalwarp -overwrite -s_srs EPSG:{int(source_epsg)} -of COG '
                       f'-co COMPRESS=DEFLATE "{input_path}" "{output_path}"')
        else:
            command = f'gdal_translate -of COG -co COMPRESS=DEFLATE "{input_path}" "{output_path}"'
    return {"ready": not issues, "issues": issues, "output": output_path, "command": command,
            "notes": ["Creates a new file and does not overwrite the source.",
                      "Uses lossless DEFLATE so RGB and RGBA are preserved.",
                      "COG is a local output target; OAM may still perform server-side validation/transcoding."]}

# Try importing GDAL for server-side VRT generation; fallback gracefully if unavailable
try:
    from osgeo import gdal
    GDAL_AVAILABLE = True
except ImportError:
    GDAL_AVAILABLE = False

# ---------- Constants ----------
OAM_DEFAULT_LICENSE = ""
HOTOSM_STAC_ITEMS_API = "https://api.imagery.hotosm.org/stac/collections/openaerialmap/items"

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
    headers = {"User-Agent": "STAC-to-OAM-Tool/8.1"}

    if stac_bbox:
        bbox_str = ",".join(str(v) for v in stac_bbox)
        params = {"bbox": bbox_str, "limit": 100}
        try:
            resp = requests.get(HOTOSM_STAC_ITEMS_API, params=params, headers=headers, timeout=10)
            if resp.status_code == 200:
                features = resp.json().get("features", [])
                
                for item in features:
                    stac_id = item.get("id", "")
                    title = item.get("properties", {}).get("title", "")
                    
                    if provider_item_id and (provider_item_id.lower() in title.lower() or provider_item_id.lower() == stac_id.lower()):
                        return {
                            "exists": True,
                            "oam_id": stac_id,
                            "status_str": "Already exists (Exact ID match)",
                            "link": generate_oam_map_link(stac_id),
                            "error": None
                        }
                    
                    oam_bbox = item.get("bbox")
                    if oam_bbox:
                        iou = calculate_exact_iou(stac_geom, oam_bbox)
                        if iou > 0.70:
                            return {
                                "exists": True,
                                "oam_id": stac_id,
                                "status_str": f"Already exists (Spatial Overlap {int(iou * 100)}%)",
                                "link": generate_oam_map_link(stac_id),
                                "error": None
                            }
        except Exception as e:
            return {"exists": False, "oam_id": None, "status_str": f"Check Failed: {e}", "link": "", "error": str(e)}

    return {"exists": False, "oam_id": None, "status_str": "Not found in v2 database", "link": "", "error": None}

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
        "license_oam_default": stac_license,
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
    
    # Handle FeatureCollections (paginated item lists)
    if data.get("type") == "FeatureCollection":
        for feature in data.get("features", []):
            item_href = url
            for l in feature.get("links", []):
                if l.get("rel") == "self":
                    item_href = urljoin(url, l.get("href"))
                    break
            if item_href not in all_links:
                all_links.append(item_href)
                process_item_data(item_href, feature, tiff_links, oam_items)
    
    # Follow relational links for pagination and children
    links = data.get("links", [])
    for link in links:
        href = link.get("href")
        rel = link.get("rel")
        if not href:
            continue
        abs_href = urljoin(url, href)
        
        if rel == "item" and data.get("type") != "FeatureCollection":
            if abs_href not in all_links:
                all_links.append(abs_href)
                item_data = fetch_json(abs_href)
                if item_data:
                    process_item_data(abs_href, item_data, tiff_links, oam_items)
        elif rel in ["collection", "child", "next"]:
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

# ---------- Local DroneTM Progress Mosaic ----------
ui.card(
    title="DroneTM progress mosaic",
    description="Run locally on your computer",
    content=(
        "Large orthophoto downloads and mosaic/COG processing run on your own computer, "
        "not on this hosted Streamlit app. Your task cache and raster files stay under your control."
    ),
    footer=(
        "This app cannot access local files and never automatically uploads or publishes to OpenAerialMap."
    ),
    key="drone-mosaic-workflow",
)
st.link_button(
    "Open DroneTM Progress Mosaic on GitHub",
    "https://github.com/adiatmad/dronetm-progress-mosaic",
    help="Download or update the local-first tool. This hosted app does not access your local files or DroneTM token.",
)
with st.expander("Which local workflow should I use?"):
    st.markdown(
        "- **Download task orthophotos and build a mosaic:** use the local DroneTM app, paste your project link, "
        "load/review tasks, download selected orthophotos, then build the mosaic.\n"
        "- **Rebuild mosaic.vrt and mosaic.tif as a COG from files already downloaded:** use "
        "rebuild_cog.bat on Windows with OSGeo4W/QGIS installed.\n"
        "- **Keep your data safe:** the local tool preserves task_*.tif source orthophotos and does not "
        "automatically upload or publish anything to OpenAerialMap. Review the output before any separate upload."
    )
st.caption(
    "The hosted app cannot read your Windows folders or run OSGeo4W. Local downloads, cache, and mosaic outputs "
    "remain in the separate DroneTM tool."
)

# ---------- Local OAM Drone Preflight ----------
st.header("🛩️ OAM Drone Preflight")
st.caption("A guided local workflow: select an imagery path → run one GDAL command → paste the report → get the final local preparation command.")

with st.container(border=True):
    st.markdown("### 1 · Select imagery")
    preflight_path = st.text_input(
        "Imagery path on your computer",
        placeholder=r"C:\drone\orthomosaic.ecw",
        key="preflight_path",
        help="This is only a local path used to build commands. The imagery is never uploaded to this app.",
    )
    run_gdal = st.button("Generate GDAL check command", type="primary", disabled=not preflight_path.strip(), key="run_gdal_check")
    if run_gdal:
        st.session_state["preflight_gdal_command"] = f'gdalinfo "{preflight_path.strip()}"'

if st.session_state.get("preflight_gdal_command"):
    st.markdown("### 2 · Run the GDAL check")
    st.caption("Copy this command into PowerShell on the computer that has the imagery.")
    st.code(st.session_state["preflight_gdal_command"], language="powershell")
    st.markdown("After it finishes, copy the **complete output** and paste it below.")
    preflight_text = st.text_area(
        "GDAL result",
        height=220,
        placeholder="Paste the complete gdalinfo output here…",
        key="preflight_text",
    )
else:
    preflight_text = ""

if preflight_text.strip():
    try:
        raw = preflight_text.strip()
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1] if "\n" in raw else raw
            if raw.endswith("```"):
                raw = raw[:-3].strip()
        if raw.lstrip().startswith("{"):
            info = json.loads(raw)
            evidence_format = "gdalinfo -json"
        else:
            info = parse_gdalinfo_text(raw)
            evidence_format = "gdalinfo"

        result = validate_info(info)
        hard_fails = [c for c in result["checks"] if c["status"] == "FAIL"]
        warnings = [c for c in result["checks"] if c["status"] == "WARN"]

        st.markdown("### 3 · OAM check")
        if hard_fails:
            st.error("❌ **Not ready** — a required check failed. Fix the item marked ❌ before upload.")
        elif warnings:
            st.warning("⚠️ **Review before upload** — no hard OAM requirement failed, but some details need verification.")
        else:
            st.success("✅ **Ready based on this report** — no OAM preflight checks failed.")
        st.caption(f"Parsed from {evidence_format}. The raster itself was not uploaded.")

        for check_index, check in enumerate(result["checks"]):
            badge_variant = {"PASS": "default", "WARN": "secondary", "FAIL": "destructive"}[check["status"]]
            ui.badge(
                check["status"],
                variant=badge_variant,
                key=f"preflight-status-{check_index}",
            )
            st.markdown(f"**{check['name']}**  \n{check['detail']}")

        source_epsg = None
        if not result["summary"]["crsPresent"]:
            st.markdown("**CRS needed**")
            epsg_text = st.text_input("Source EPSG", placeholder="Example: 32751", key="preflight_epsg", help="Enter the CRS actually used by your workflow. Do not guess.")
            if epsg_text.strip():
                try:
                    source_epsg = int(epsg_text.strip())
                except ValueError:
                    st.error("Source EPSG must be an integer, e.g. 32751.")

        needs_conversion = result["summary"]["driver"].upper() != "GTIFF"
        if needs_conversion and not hard_fails and (result["summary"]["crsPresent"] or source_epsg is not None):
            rec = build_oam_recommendation(info, preflight_path.strip(), source_epsg=source_epsg)
            if rec["ready"]:
                st.markdown("### 4 · Final local preparation command")
                st.caption("Copy this one combined PowerShell command. It creates a new file and then runs gdalinfo on that output for verification. The original is not overwritten.")
                output = rec["output"]
                combined = f'$out="{output}"; if (Test-Path $out) {{ Remove-Item $out -Force }}; {rec["command"]}; if ($LASTEXITCODE -eq 0) {{ gdalinfo "$out" }}'
                st.code(combined, language="powershell")
                st.caption("Paste the resulting gdalinfo output back into the GDAL result box above to verify the converted file.")
        elif not needs_conversion:
            st.info("This report is already for GeoTIFF. No conversion command is needed; review the OAM checks above and upload the source if they are satisfied.")
    except json.JSONDecodeError as exc:
        st.error(f"Could not parse the GDAL output: {exc}")
    except Exception as exc:
        st.error(f"Preflight could not be processed: {exc}")
st.header("Remote source import")
source_mode = st.radio(
    "Source type",
    ["STAC catalog / item", "Public S3 bucket folder"],
    horizontal=True,
    key="source_mode",
)

if source_mode == "Public S3 bucket folder":
    st.caption("For public S3 Open Data buckets. The bucket-browser #prefix is read in your browser; imagery is never downloaded by this app.")
    s3_browser_url = st.text_input(
        "S3 bucket-browser URL",
        value="http://st-vvhr-opendata.s3-website.us-west-2.amazonaws.com/#prefix=disasters%2FFlood%20in%20Nepal%20(Disasters%20Charter%20Activation%201052)%2C%202026%2F",
        key="s3_browser_url",
    )
    exclude_masks = st.checkbox("Exclude MASKS/LINEAGE folders", value=True, key="exclude_s3_artifacts")

    bucket, region, prefix = parse_s3_browser_url(s3_browser_url)
    if not bucket:
        st.error("Use an AWS S3 website browser URL with a #prefix= fragment.")
    elif st.button("List public imagery objects", type="primary"):
        try:
            with st.spinner(f"Listing s3://{bucket}/{prefix} ..."):
                objects = list_public_s3_objects(bucket, region, prefix)
            source_kind = classify_s3_source_objects(objects, exclude_masks_lineage=exclude_masks)
            tiffs = filter_tiff_objects(objects, exclude_masks_lineage=exclude_masks)
            st.session_state["remote_s3_results"] = {
                "bucket": bucket, "region": region, "prefix": prefix, "objects": tiffs,
                "all_objects": objects, "source_kind": source_kind,
                "browser_url": s3_browser_url,
            }
        except Exception as exc:
            st.error(f"Could not list the public S3 prefix: {exc}")

    s3_results = st.session_state.get("remote_s3_results")
    if s3_results and s3_results.get("objects"):
        st.success(f"Found {len(s3_results['objects'])} GeoTIFF object(s).")
        st.caption("Source facts are limited to the public S3 object listing. Last modified is shown for reference only and is not treated as acquisition time.")
        for idx, obj in enumerate(s3_results["objects"], 1):
            key = obj["key"]
            object_url = public_s3_object_url(s3_results["bucket"], s3_results["region"], key)
            with st.expander(f"{idx}. {key.rsplit('/', 1)[-1]} — {format_bytes(obj.get('size_bytes'))}"):
                st.code(object_url, language=None)
                st.caption(f"S3 last modified: {obj.get('last_modified') or 'not reported'}")
                st.markdown(f"Provider: **{SPACE_EYE_PROVIDER}** · Platform: **{SPACE_EYE_PLATFORM}** · Sensor: **{SPACE_EYE_SENSOR}** · License: **{SPACE_EYE_LICENSE}**")
                prefill = spaceeye_oam_prefill(
                    key=key, object_url=object_url, source_browser_url=s3_results["browser_url"]
                )
                st.link_button("Prepare OAM v2 upload", prefill)
                st.caption("The handoff uses OAM's documented source_url flow. OAM requires a valid acquisition date before submission; this app leaves it blank unless source evidence provides one. S3 LastModified is not treated as capture time.")
    elif s3_results is not None:
        if s3_results.get("source_kind") == "ARCHIVE_ONLY":
            archive_names = [
                obj["key"].rsplit("/", 1)[-1]
                for obj in s3_results.get("all_objects", [])
                if str(obj.get("key", "")).lower().endswith(".zip")
            ]
            st.warning(
                "This public prefix exposes an imagery archive, not a direct TIFF object. "
                "The archive may contain GeoTIFF imagery, but the S3 object listing cannot see inside it. "
                "OAM v2 accepts direct public TIFF URLs and a narrow ODM `all.zip` special case; it does not "
                "accept arbitrary commercial imagery ZIP archives."
            )
            if archive_names:
                st.caption("Detected archive(s): " + ", ".join(archive_names[:5]))
                archive_key = next(
                    obj["key"] for obj in s3_results.get("all_objects", [])
                    if str(obj.get("key", "")).lower().endswith(".zip")
                )
                archive_url = public_s3_object_url(
                    s3_results["bucket"], s3_results["region"], archive_key
                )
                st.markdown("**Remote GDAL access (no full ZIP download)**")
                st.caption(
                    "GDAL can stream a member from this public ZIP through `/vsicurl/` + `/vsizip/`. "
                    "The app does not extract or upload the archive."
                )
                st.code(build_remote_vsizip_path(archive_url), language="text")
                verified_member = spaceeye_verified_archive_member(archive_key)
                proxy_base_url = os.getenv("OAM_ARCHIVE_PROXY_BASE_URL", "").strip()
                if verified_member:
                    st.markdown("**Verified archive member**")
                    st.code(build_remote_vsizip_path(archive_url, verified_member), language="text")
                    st.caption(
                        "This exact member was verified with GDAL as a GeoTIFF (29,560 × 36,720, "
                        "WGS 84 / EPSG:4326). Its TIFF acquisition timestamp is "
                        f"`{SPACE_EYE_VERIFIED_TIFF_DATETIME}`; the source output does not state a timezone, "
                        "so the app does not pass this timestamp to OAM."
                    )
                    if proxy_base_url:
                        proxy_url = build_archive_proxy_url(proxy_base_url, archive_url, verified_member)
                        st.markdown("**OAM-ready HTTPS TIFF URL**")
                        st.code(proxy_url, language="text")
                        st.caption(
                            "This URL is OAM-ready only when the configured archive proxy is publicly "
                            "reachable by OAM. The proxy streams the selected TIFF member from S3 using "
                            "HTTP Range requests; it does not expose the GDAL virtual path."
                        )
                        prefill = build_oam_prefill_url(
                            title="SpaceEye-T " + archive_key.rsplit("/", 1)[-1],
                            source_url=proxy_url,
                            provider=SPACE_EYE_PROVIDER,
                            platform=SPACE_EYE_PLATFORM,
                            sensor=SPACE_EYE_SENSOR,
                            license=SPACE_EYE_LICENSE,
                            external_id=f"spaceeye-t:{archive_key}:{verified_member}",
                            external_url=s3_results["browser_url"],
                        )
                        st.link_button("Prepare OAM v2 upload", prefill)
                    else:
                        st.info(
                            "Archive proxy not configured. Set OAM_ARCHIVE_PROXY_BASE_URL to the public "
                            "HTTPS base URL of the standalone archive proxy to enable the direct TIFF URL "
                            "and OAM handoff. No fake .TIF URL is generated."
                        )
                else:
                    st.caption(
                        "Append the exact path inside the ZIP after the final `/` once you inspect the archive. "
                        "This is a local GDAL/QGIS access path, not an OAM `source_url`."
                    )
            st.info(
                "The ZIP itself is not an OAM source_url. When an archive proxy is configured, the app can "
                "hand OAM a real HTTPS URL that serves the verified TIFF member. Without that deployment, "
                "no misleading OAM handoff is generated. The app never bulk-downloads the archive."
            )
        else:
            st.info("No GeoTIFFs matched this prefix and filter.")

st.header("Step 1: Fetch Event Imagery")
st.info("💡 Paste the URL of the data catalog you found. We will automatically find all the usable map images inside it.")

root_url_input = st.text_input("Data Catalog URL:", value=DEFAULT_SAMPLE_URL, disabled=source_mode != "STAC catalog / item")

if source_mode == "STAC catalog / item" and root_url_input:
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
        with m1:
            ui.metric_card(
                "Total usable images",
                len(display_tiff_links),
                description="GeoTIFF scenes available for the selected area",
                variant="dashboard",
                key="metric-total-usable-images",
            )
        with m2:
            ui.metric_card(
                "PRE-event",
                len(pre_items),
                description="Before-disaster baseline scenes",
                variant="dashboard",
                key="metric-pre-event",
            )
        with m3:
            ui.metric_card(
                "POST-event",
                len(post_items),
                description="After-disaster scenes",
                variant="dashboard",
                key="metric-post-event",
            )

        st.divider()
        st.header("Step 3: Choose Your Goal")

        tab_tm, tab_oam, tab_adv = st.tabs([
            "🎯 Goal A: Setup a Mapping Project", 
            "🌍 Goal B: Publish to OAM v2", 
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
            st.info("🛑 **Why check for duplicates?** Uploading the exact same footprint twice clutters the map. Use the button below to check if someone from the community has already uploaded these images to the new OAM v2 database.")
            st.markdown("**Ready to upload?** Use the prefilled OAM v2 handoff for each selected scene. The source GeoTIFF stays at its public URL; OAM fetches it server-side.")

            if display_oam_items:
                if st.button("🔍 Check OAM v2 for Duplicates"):
                    st.session_state["oam_duplicates"] = {}
                    progress_bar = st.progress(0, text="Checking v2 STAC database...")
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
                        
                        if meta.get("image_source_url"):
                            prefill = build_oam_prefill_url(
                                title=meta["title"],
                                source_url=meta["image_source_url"],
                                provider=meta.get("provider") or None,
                                platform=meta.get("platform") or None,
                                sensor=meta.get("sensor") or None,
                                license=meta.get("stac_license_reference") or None,
                                acquisition_start=meta.get("raw_datetime") or None,
                                acquisition_end=meta.get("raw_datetime") or None,
                                external_id=meta.get("provider_item_id") or None,
                                external_url=meta.get("item_url") or None,
                            )
                            st.link_button("Prepare OAM v2 upload", prefill)
                            st.caption("Review the prefilled metadata in OAM before submitting. The source URL is passed to OAM; this app does not download the imagery.")

                        fields = [
                            ("Title", meta["title"]),
                            ("Platform", meta["platform"]),
                            ("Sensor", meta["sensor"]),
                            ("Date start", meta["date_start"]),
                            ("Image source (Url)", meta["image_source_url"]),
                            ("Provider", meta["provider"]),
                            ("Duplicate Status", meta["oam_duplicate_status"]),
                        ]
                        for label, value in fields:
                            col_lbl, col_val = st.columns([1, 3])
                            with col_lbl:
                                st.markdown(f"**{label}**")
                            with col_val:
                                st.code(value, language=None)

                timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
                export_csv_filename = f"{event_prefix}_audit_log_{timestamp_str}.csv"

                csv_buffer = io.StringIO()
                writer = csv.DictWriter(csv_buffer, fieldnames=OAM_FIELDNAMES, extrasaction="ignore")
                writer.writeheader()
                for meta in display_oam_items:
                    writer.writerow(meta)

                st.markdown("---")
                st.download_button(
                    label=f"📥 Download Audit Log / Checklist (CSV)",
                    data=csv_buffer.getvalue(),
                    file_name=export_csv_filename,
                    mime="text/csv",
                    help="Use this CSV as a checklist to keep track of which URLs you have manually uploaded to OAM v2."
                )

        with tab_adv:
            st.caption("Raw Data Endpoints for Developers")
            for idx, link in enumerate(all_links, 1):
                st.markdown(f"{idx}. [{link}]({link})")
