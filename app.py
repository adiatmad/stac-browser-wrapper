import streamlit as st
import streamlit_shadcn_ui as ui
import requests
from urllib.parse import urlparse, unquote, urljoin
import re
import io
import csv
import json
import os
import math
from pathlib import Path
from datetime import datetime
import time
import folium
from folium.plugins import Draw
from streamlit_folium import st_folium
from shapely.geometry import box, shape
from typing import Any
from urllib.parse import quote, urlencode, urlsplit, urlunsplit, parse_qsl
import xml.etree.ElementTree as ET
from local_processing import find_gdal_tools, inspect_geotiff, process_lossless_geotiff

OAM_UPLOAD_URL = "https://upload.imagery.hotosm.org/"
DEFAULT_SAMPLE_URL = (
    "https://browser.moregeo.it/external/vantor-opendata.s3.amazonaws.com/"
    "events/Indonesia-Earthquakes-Aug-2026/collection.json"
)

SPACE_EYE_LICENSE = "CC-BY-4.0"
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
    license_values = {
        "CC-BY-4.0": "CC-BY 4.0",
        "CC-BY-SA-4.0": "CC BY-SA 4.0",
        "CC-BY-NC-4.0": "CC BY-NC 4.0",
        "CC-BY 4.0": "CC-BY 4.0",
        "CC BY-SA 4.0": "CC BY-SA 4.0",
        "CC BY-NC 4.0": "CC BY-NC 4.0",
    }
    fields = {
        "title": title,
        "source_url": source_url,
        "provider": provider,
        "platform": platform,
        "license": license_values.get(license),
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

def _fetch_oam_duplicate_features(
    params: dict, headers: dict, max_pages: int = 10
) -> tuple[list[dict], int, bool]:
    """Fetch OAM search pages, following only same-endpoint HTTPS GET links.

    Returns (features, pages_checked, incomplete). The ten-page cap bounds
    external requests while making an incomplete search explicit to callers.
    """
    api_parts = urlsplit(HOTOSM_STAC_ITEMS_API)
    current_url = HOTOSM_STAC_ITEMS_API
    current_params = params
    visited: set[str] = set()
    features: list[dict] = []
    page_limit = max(1, min(int(max_pages), 10))

    for page_number in range(1, page_limit + 1):
        parsed_url = urlsplit(current_url)
        if (
            parsed_url.scheme != "https"
            or parsed_url.netloc.lower() != api_parts.netloc.lower()
            or parsed_url.path.rstrip("/") != api_parts.path.rstrip("/")
        ):
            raise ValueError("OAM pagination link left the trusted items endpoint.")
        if current_url in visited:
            raise ValueError("OAM pagination returned a repeated next link.")
        visited.add(current_url)

        response = requests.get(
            current_url,
            params=current_params,
            headers=headers,
            timeout=10,
            allow_redirects=False,
        )
        if response.status_code != 200:
            raise ValueError(f"OAM API returned HTTP {response.status_code}.")
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("OAM API returned an invalid page.")
        page_features = payload.get("features", [])
        if not isinstance(page_features, list):
            raise ValueError("OAM API returned an invalid features list.")
        remaining_items = 1000 - len(features)
        features.extend(
            item for item in page_features[:remaining_items] if isinstance(item, dict)
        )
        if len(page_features) > remaining_items:
            return features, page_number, True

        links = payload.get("links") or []
        if not isinstance(links, list):
            raise ValueError("OAM API returned invalid pagination links.")
        next_link = next(
            (
                link for link in links
                if isinstance(link, dict) and link.get("rel") == "next"
            ),
            None,
        )
        if not next_link:
            return features, page_number, False
        if len(features) >= 1000:
            return features, page_number, True

        method = str(next_link.get("method") or "GET").upper()
        if method != "GET":
            raise ValueError("OAM pagination advertised an unsupported non-GET link.")
        href = next_link.get("href")
        if not isinstance(href, str) or not href.strip():
            raise ValueError("OAM pagination advertised an empty next link.")
        next_url = urljoin(current_url, href.strip())
        next_parts = urlsplit(next_url)
        if (
            next_parts.scheme != "https"
            or next_parts.netloc.lower() != api_parts.netloc.lower()
            or next_parts.path.rstrip("/") != api_parts.path.rstrip("/")
        ):
            raise ValueError("OAM pagination link left the trusted items endpoint.")

        if page_number == page_limit:
            return features, page_number, True
        current_url = next_url
        current_params = None

    return features, page_limit, False


def check_oam_duplicate(meta: dict) -> dict:
    provider_item_id = str(meta.get("provider_item_id") or "").strip()
    stac_bbox = parse_bbox_2d(meta.get("bbox"))
    stac_geom = meta.get("geometry")
    headers = {"User-Agent": "STAC-to-OAM-Tool/8.1"}

    if not stac_bbox:
        return {
            "exists": False,
            "oam_id": None,
            "status_str": "Unable to check: missing or invalid imagery bounding box",
            "link": "",
            "error": "Missing or invalid imagery bounding box",
            "pages_checked": 0,
        }

    bbox_str = ",".join(str(v) for v in stac_bbox)
    params = {"bbox": bbox_str, "limit": 100}
    try:
        features, pages_checked, incomplete = _fetch_oam_duplicate_features(
            params, headers
        )
        for item in features:
            stac_id = str(item.get("id") or "")

            # STAC IDs are identifiers, not title fragments. Exact equality
            # avoids matching unrelated items whose titles merely contain an ID.
            if provider_item_id and stac_id == provider_item_id:
                return {
                    "exists": True,
                    "oam_id": stac_id,
                    "status_str": "Already exists (Exact ID match)",
                    "link": generate_oam_map_link(stac_id),
                    "error": None,
                    "pages_checked": pages_checked,
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
                        "error": None,
                        "pages_checked": pages_checked,
                    }

        if incomplete:
            return {
                "exists": False,
                "oam_id": None,
                "status_str": (
                    f"Inconclusive: OAM search reached the {pages_checked}-page "
                    "safety limit; additional results may exist"
                ),
                "link": "",
                "error": None,
                "pages_checked": pages_checked,
            }

        return {
            "exists": False,
            "oam_id": None,
            "status_str": "Not found in v2 database (all returned pages checked)",
            "link": "",
            "error": None,
            "pages_checked": pages_checked,
        }
    except Exception as e:
        return {
            "exists": False,
            "oam_id": None,
            "status_str": f"Check Failed: {e}",
            "link": "",
            "error": str(e),
            "pages_checked": 0,
        }



# ---------- Public STAC discovery and API search ----------
def parse_stac_catalog_registry(records: Any) -> list[dict[str, Any]]:
    """Keep public, HTTPS STAC catalog records from the OpenGeo registry."""
    if not isinstance(records, list):
        raise ValueError("The STAC catalog registry must contain a JSON list.")
    public_records = []
    for record in records:
        if not isinstance(record, dict):
            continue
        if record.get("access") != "public" or record.get("isPrivate") is not False:
            continue
        title = str(record.get("title") or "").strip()
        url = str(record.get("url") or "").strip()
        try:
            parsed = urlsplit(url)
        except ValueError:
            continue
        if not title or parsed.scheme != "https" or not parsed.netloc:
            continue
        public_records.append({
            "title": title,
            "url": url,
            "summary": str(record.get("summary") or "").strip(),
            "updated": str(record.get("updated") or "").strip(),
            "is_api": bool(record.get("isApi")),
            "slug": str(record.get("slug") or "").strip(),
        })
    return sorted(public_records, key=lambda item: item["title"].casefold())


def filter_public_stac_catalogs(
    catalogs: list[dict[str, Any]], query: str = ""
) -> list[dict[str, Any]]:
    """Filter catalog titles and summaries without changing the source records."""
    term = str(query or "").strip().casefold()
    if not term:
        return list(catalogs)
    return [
        catalog for catalog in catalogs
        if term in catalog.get("title", "").casefold()
        or term in catalog.get("summary", "").casefold()
    ]


@st.cache_data(ttl=3600, show_spinner=False)
def load_public_stac_catalogs() -> list[dict[str, Any]]:
    """Load the public catalog directory on demand; do not block normal browsing."""
    response = requests.get(STAC_CATALOG_REGISTRY_URL, timeout=20)
    response.raise_for_status()
    return parse_stac_catalog_registry(response.json())


@st.cache_data(ttl=600, show_spinner=False)
def fetch_stac_api_root(root_url: str) -> dict[str, Any]:
    """Fetch a STAC API root document for search-link discovery."""
    response = requests.get(root_url, timeout=15)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict) or not isinstance(payload.get("links"), list):
        raise ValueError("The URL did not return a STAC root document with links.")
    return payload


def find_stac_search_endpoint(root_url: str, root_data: dict[str, Any]) -> str:
    """Resolve an advertised GET /search link; never guess an endpoint path."""
    for link in root_data.get("links", []):
        if not isinstance(link, dict) or link.get("rel") != "search":
            continue
        if str(link.get("method") or "GET").upper() != "GET":
            continue
        href = str(link.get("href") or "").strip()
        if not href:
            continue
        try:
            endpoint = urljoin(root_url, href)
            parsed = urlsplit(endpoint)
        except ValueError:
            continue
        if parsed.scheme == "https" and parsed.netloc:
            return endpoint
    raise ValueError(
        "This STAC root does not advertise an HTTPS GET search link. "
        "Use catalog browsing or another STAC API endpoint; POST-only search is not supported here."
    )


def build_stac_search_url(
    search_url: str,
    bbox: str = "",
    datetime_range: str = "",
    collections: str = "",
    limit: int = 100,
) -> str:
    """Build a STAC Item Search GET URL from validated core search parameters."""
    try:
        parsed = urlsplit(str(search_url or "").strip())
    except ValueError as exc:
        raise ValueError("The STAC search endpoint must be a valid HTTPS URL.") from exc
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("The STAC search endpoint must be an HTTPS URL.")
    try:
        result_limit = int(limit)
    except (TypeError, ValueError) as exc:
        raise ValueError("Search limit must be a whole number from 1 to 1000.") from exc
    if not 1 <= result_limit <= 1000:
        raise ValueError("Search limit must be a whole number from 1 to 1000.")

    params = dict(parse_qsl(parsed.query, keep_blank_values=True))
    bbox_value = str(bbox or "").strip()
    if bbox_value:
        try:
            coordinates = [float(value.strip()) for value in bbox_value.split(",")]
        except ValueError as exc:
            raise ValueError("BBox must contain four comma-separated numbers: west,south,east,north.") from exc
        if len(coordinates) != 4 or not all(math.isfinite(value) for value in coordinates):
            raise ValueError("BBox must contain four finite numbers: west,south,east,north.")
        west, south, east, north = coordinates
        if not (-180 <= west <= 180 and -180 <= east <= 180 and -90 <= south <= 90 and -90 <= north <= 90):
            raise ValueError("BBox coordinates must use WGS84 longitude/latitude ranges.")
        if west == east or south >= north:
            raise ValueError("BBox must have non-zero width and height; south must be less than north.")
        params["bbox"] = ",".join(value.strip() for value in bbox_value.split(","))

    datetime_value = str(datetime_range or "").strip()
    if datetime_value:
        params["datetime"] = datetime_value

    collection_values = [value.strip() for value in str(collections or "").split(",") if value.strip()]
    if collection_values:
        params["collections"] = ",".join(collection_values)

    params["limit"] = str(result_limit)
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, urlencode(params), ""))


def find_stac_thumbnail_url(item_data: dict[str, Any], item_url: str) -> str | None:
    """Return an advertised HTTPS raster-independent thumbnail image, if present."""
    assets = item_data.get("assets") or {}
    if not isinstance(assets, dict):
        return None
    for key, asset in assets.items():
        if not isinstance(asset, dict):
            continue
        roles = [str(role).casefold() for role in (asset.get("roles") or [])]
        asset_key = str(key).casefold()
        media_type = str(asset.get("type") or "").split(";", 1)[0].casefold()
        href = str(asset.get("href") or "").strip()
        is_thumbnail = "thumbnail" in roles or "thumbnail" in asset_key
        if not is_thumbnail or not href:
            continue
        try:
            is_image = media_type.startswith("image/") or urlsplit(href).path.casefold().endswith(
                (".jpg", ".jpeg", ".png", ".webp")
            )
            if not is_image:
                continue
            absolute_url = resolve_relative_url(item_url, href)
            parsed = urlsplit(absolute_url)
        except ValueError:
            continue
        if parsed.scheme == "https" and parsed.netloc:
            return absolute_url
    return None

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
        "thumbnail_url": find_stac_thumbnail_url(item_data, item_url),
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

def crawl_stac(
    url: str,
    all_links: list,
    tiff_links: list,
    oam_items: list,
    visited=None,
    data=None,
    max_items: int | None = None,
    max_pages: int | None = None,
    crawl_state: dict | None = None,
):
    if visited is None:
        visited = set()
    if crawl_state is None:
        crawl_state = {"pages": 0, "capped": False, "post_next": False}
    if max_items is not None and len(all_links) >= max_items:
        crawl_state["capped"] = True
        return
    if url in visited:
        return
    visited.add(url)
    if data is None:
        data = fetch_json(url)
    if data is None:
        return

    # Handle FeatureCollections (paginated item lists).
    if data.get("type") == "FeatureCollection":
        crawl_state["pages"] += 1
        if max_pages is not None and crawl_state["pages"] > max_pages:
            crawl_state["capped"] = True
            return
        for feature in data.get("features", []):
            if max_items is not None and len(all_links) >= max_items:
                crawl_state["capped"] = True
                break
            item_href = url
            for link in feature.get("links", []):
                if link.get("rel") == "self":
                    item_href = urljoin(url, link.get("href"))
                    break
            if item_href not in all_links:
                all_links.append(item_href)
                process_item_data(item_href, feature, tiff_links, oam_items)

    # Follow relational links. Search pagination is GET-only and bounded when requested.
    links = data.get("links", [])
    for link in links:
        href = link.get("href")
        rel = link.get("rel")
        if not href:
            continue
        abs_href = urljoin(url, href)

        if rel == "item" and data.get("type") != "FeatureCollection":
            if max_items is not None and len(all_links) >= max_items:
                crawl_state["capped"] = True
                continue
            if abs_href not in all_links:
                all_links.append(abs_href)
                item_data = fetch_json(abs_href)
                if item_data:
                    process_item_data(abs_href, item_data, tiff_links, oam_items)
        elif rel in ["collection", "child", "next"]:
            if rel == "next":
                method = str(link.get("method") or "GET").upper()
                if method != "GET":
                    crawl_state["post_next"] = True
                    continue
                if max_pages is not None and crawl_state["pages"] >= max_pages:
                    crawl_state["capped"] = True
                    continue
                if max_items is not None and len(all_links) >= max_items:
                    crawl_state["capped"] = True
                    continue
            crawl_stac(
                abs_href,
                all_links,
                tiff_links,
                oam_items,
                visited=visited,
                max_items=max_items,
                max_pages=max_pages,
                crawl_state=crawl_state,
            )


@st.cache_data(show_spinner="Searching for imagery...", ttl=600)
def run_crawl(real_url: str, max_items: int | None = None, max_pages: int | None = None):
    all_links = []
    tiff_links = []
    oam_items = []
    crawl_state = {"pages": 0, "capped": False, "post_next": False}
    root_data = fetch_json(real_url)

    if root_data is not None and root_data.get("type") == "Feature":
        all_links.append(real_url)
        process_item_data(real_url, root_data, tiff_links, oam_items)
    elif root_data is not None:
        crawl_stac(
            real_url,
            all_links,
            tiff_links,
            oam_items,
            data=root_data,
            max_items=max_items,
            max_pages=max_pages,
            crawl_state=crawl_state,
        )

    return all_links, tiff_links, oam_items, crawl_state

# ---------- Streamlit Main Application UI ----------
st.set_page_config(page_title="STAC Imagery Workbench", layout="wide", initial_sidebar_state="collapsed")

st.title("STAC Imagery Workbench")
st.markdown("Find imagery, inspect coverage, and prepare mapping or OpenAerialMap handoffs.")

active_workflow = ui.tabs(
    options=["Discover & map", "Local processing"],
    value="Discover & map",
    label="Workflow",
    variant="line",
    key="active-workflow-tabs",
)

if active_workflow == "Local processing":
    st.header("Local GeoTIFF preflight")
    st.caption(
        "Inspect a local orthomosaic with GDAL, then create a separate lossless GeoTIFF copy if needed. "
        "All processing happens on this computer; the original is never changed."
    )

    gdalinfo_path, gdal_translate_path = find_gdal_tools()
    if not gdalinfo_path or not gdal_translate_path:
        st.warning(
            "GDAL command-line tools were not found. Install QGIS/GDAL or start this app from the "
            "QGIS / OSGeo4W shell so gdalinfo and gdal_translate are available."
        )
    else:
        st.caption(f"GDAL: {gdalinfo_path}")
        def _update_local_output_path():
            current_source = st.session_state.get("local_processing_source", "").strip().strip('"')
            if current_source:
                st.session_state["local_processing_output"] = str(
                    Path(current_source).with_name(Path(current_source).stem + "_oam.tif")
                )

        source_path = st.text_input(
            "Source GeoTIFF",
            placeholder=r"D:\orthomosaic.tif",
            key="local_processing_source",
            on_change=_update_local_output_path,
            help="Full path to the stitched orthomosaic on this computer.",
        )
        source = source_path.strip().strip('"')
        output_path = st.text_input(
            "Output GeoTIFF (new file)",
            value=(
                str(Path(source).with_name(Path(source).stem + "_oam.tif"))
                if source else ""
            ),
            key="local_processing_output",
            help="A separate output file. Existing files are never overwritten.",
        )
        if st.button("Inspect GeoTIFF", type="primary", disabled=not bool(source)):
            st.session_state.pop("local_processing_inspection", None)
            st.session_state.pop("local_processing_result", None)
            try:
                with st.spinner("Running gdalinfo…"):
                    inspection = inspect_geotiff(
                        gdalinfo_path, gdal_translate_path, source, output_path.strip().strip('"')
                    )
                st.session_state["local_processing_inspection"] = inspection
            except Exception as exc:
                st.error(f"Inspection failed: {exc}")

        inspection = st.session_state.get("local_processing_inspection")
        if (inspection and inspection.get("source_path") == source
                and inspection.get("output_path") == output_path.strip().strip('"')):
            info = inspection["info"]
            size = info.get("size") or [None, None]
            bands = info.get("bands") or []
            crs = info.get("coordinateSystem") or {}
            structure = (info.get("metadata") or {}).get("IMAGE_STRUCTURE") or {}
            st.subheader("Inspection")
            st.write(f"**Dimensions:** {size[0]} × {size[1]} pixels")
            st.write(f"**Bands:** {len(bands)} · **Data types:** {', '.join(str(b.get('type', 'unknown')) for b in bands)}")
            st.write(f"**CRS:** {'Present' if crs else 'Missing'}")
            st.write(f"**Geotransform:** {'Present' if info.get('geoTransform') else 'Missing'}")
            st.write(f"**Current compression:** {structure.get('COMPRESSION', 'Not reported')}")
            st.write(f"**File size:** {format_bytes(inspection['source_size_bytes'])}")
            if inspection["under_upload_limit"]:
                st.success("Below the upstream default 100 GiB upload limit. Deployment settings may differ.")
            else:
                st.warning("Above the upstream default 100 GiB upload limit.")
            if inspection["ready"]:
                st.success("Basic preflight passed: readable GeoTIFF, CRS and valid georeferencing.")
            else:
                st.error(inspection["reason"])
            st.caption(
                "These are basic file and georeferencing checks, not a guarantee of acceptance: "
                "OAM performs additional validation during ingestion. ZSTD/tiled output is an optional "
                "lossless optimization, not a mandatory OAM upload format."
            )
            with st.expander("GDAL inspection command and full report"):
                st.code(inspection["inspect_command"], language="powershell")
                st.json(info)
            if inspection["ready"]:
                st.subheader("Optional lossless output")
                st.caption(
                    "Creates a tiled ZSTD GeoTIFF without resampling, resizing or JPEG. "
                    "OAM creates its serving COG during ingestion."
                )
                st.code(" ".join(inspection["compression_command"]), language="powershell")
                if st.button(
                    "Create lossless GeoTIFF",
                    type="primary",
                    disabled=not bool(output_path.strip()),
                ):
                    st.session_state.pop("local_processing_result", None)
                    try:
                        with st.spinner("Creating and validating the lossless GeoTIFF…"):
                            result = process_lossless_geotiff(
                                gdalinfo_path, gdal_translate_path, source,
                                output_path.strip().strip('"'), verify_checksums=False
                            )
                        st.session_state["local_processing_result"] = result
                    except Exception as exc:
                        st.error(f"Processing failed: {exc}")
                        st.caption("The original is unchanged. Any partial output is removed on failure.")
        result = st.session_state.get("local_processing_result")
        if (result and result.get("source_path") == source
                and result.get("output_path") == output_path.strip().strip('"')):
            st.subheader("Output verification")
            st.write(f"**Output:** {result['output_path']}")
            st.write(f"**Output size:** {format_bytes(result['output_size_bytes'])}")
            st.write(f"**Size reduction:** {result['reduction_percent']:.1f}%")
            if result["under_upload_limit"]:
                st.success("Output is below the upstream default 100 GiB upload limit.")
            else:
                st.warning("Output remains above the upstream default 100 GiB upload limit.")
            issues = result.get("verification_issues") or []
            if issues:
                st.error("Output verification found differences:")
                for issue in issues:
                    st.markdown(f"- {issue}")
            else:
                st.success("Output structure verified: dimensions, geotransform, bands, CRS, tiling and ZSTD.")
            with st.expander("GDAL output details"):
                st.json({"source": result["source_info"], "output": result["output_info"]})
            st.link_button("Open OAM uploader", OAM_UPLOAD_URL)
            st.caption("Upload the output manually. This app never uploads imagery or credentials.")

elif active_workflow == "Discover & map":
    st.header("Choose an imagery source")
    source_mode = st.radio(
        "Source type",
        ["STAC catalog / item", "Public S3 bucket folder"],
        horizontal=True,
        key="source_mode",
    )

    if source_mode == "Public S3 bucket folder":
        with st.container(border=True):
            st.subheader("Public S3 bucket folder")
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
                with st.expander(f"{idx}. {key.rsplit('/', 1)[-1]} · {format_bytes(obj.get('size_bytes'))}"):
                    st.code(object_url, language=None)
                    st.caption(f"S3 last modified: {obj.get('last_modified') or 'not reported'}")
                    st.markdown(f"**Provider:** {SPACE_EYE_PROVIDER}\n\n**Platform:** {SPACE_EYE_PLATFORM}\n\n**Sensor:** {SPACE_EYE_SENSOR}\n\n**License:** {SPACE_EYE_LICENSE}")
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

    if source_mode == "STAC catalog / item":
        with st.container(border=True):
            st.subheader("STAC catalog or item")
            st.caption("Choose a public catalog from the directory, or paste a STAC catalog or item URL.")
            if "stac_catalog_url" not in st.session_state:
                st.session_state["stac_catalog_url"] = DEFAULT_SAMPLE_URL
            with st.expander("Find a public STAC catalog", expanded=False):
                st.caption(
                    "Search the public catalog directory maintained by OpenGeo. "
                    "Catalog metadata is discoverable here; individual assets may still have separate access or license terms."
                )
                if st.button("Load public catalog directory", key="load-public-stac-catalogs"):
                    try:
                        with st.spinner("Loading public STAC catalog directory..."):
                            st.session_state["public_stac_catalogs"] = load_public_stac_catalogs()
                        st.session_state.pop("public_stac_catalogs_error", None)
                    except Exception as exc:
                        st.session_state["public_stac_catalogs_error"] = str(exc)
                catalog_error = st.session_state.get("public_stac_catalogs_error")
                if catalog_error:
                    st.warning(f"Could not load the OpenGeo catalog directory: {catalog_error}. You can still paste a STAC URL below.")
                catalogs = st.session_state.get("public_stac_catalogs", [])
                if catalogs:
                    catalog_query = st.text_input("Search catalog name or description", key="stac_catalog_query")
                    matching_catalogs = filter_public_stac_catalogs(catalogs, catalog_query)
                    if matching_catalogs:
                        selected_index = st.selectbox(
                            "Public catalogs",
                            options=list(range(len(matching_catalogs))),
                            format_func=lambda index: matching_catalogs[index]["title"],
                            key="stac_catalog_selection",
                        )
                        selected_catalog = matching_catalogs[selected_index]
                        st.caption(selected_catalog["summary"] or "No summary is provided in the registry.")
                        registry_updated = selected_catalog.get("updated")
                        if registry_updated:
                            st.caption(f"Registry record updated: {registry_updated[:10]} · "
                                       f"{'STAC API' if selected_catalog['is_api'] else 'Static STAC catalog'}")
                        if st.button("Use selected catalog", key="use-selected-stac-catalog"):
                            st.session_state["stac_catalog_url"] = selected_catalog["url"]
                    else:
                        st.info("No public catalog matches that search.")
        
            root_url_input = st.text_input(
                "Data Catalog URL:",
                key="stac_catalog_url",
            )

    if source_mode == "STAC catalog / item" and root_url_input:
        real_url = extract_real_stac_url(root_url_input)
        event_prefix = extract_event_name_from_url(real_url)

        if real_url != st.session_state.get("last_processed_url"):
            st.session_state["oam_duplicates"] = {}
            st.session_state["location_filter_bbox"] = None
            st.session_state["pending_drawing"] = None
            st.session_state.pop("active_stac_search", None)
            st.session_state["last_processed_url"] = real_url

        crawl_url = real_url
        use_api_search = st.checkbox(
            "Search this STAC API with filters instead of browsing catalog links",
            key="use_stac_api_search",
            help="Requires the STAC root to advertise an HTTPS GET search link. Uses core bbox, datetime, collections and limit parameters.",
        )
        if use_api_search:
            try:
                with st.spinner("Checking STAC API search capabilities..."):
                    stac_root = fetch_stac_api_root(real_url)
                search_endpoint = find_stac_search_endpoint(real_url, stac_root)
                st.caption(f"STAC Item Search endpoint: {search_endpoint}")
                st.caption(
                    f"To keep discovery responsive, this search stops after {STAC_SEARCH_MAX_ITEMS:,} items "
                    f"or {STAC_SEARCH_MAX_PAGES} pages, whichever comes first."
                )
                with st.form("stac_api_search_form", clear_on_submit=False):
                    search_bbox = st.text_input(
                        "Area bbox (optional, WGS84)",
                        placeholder="west,south,east,north · e.g. 106.6,-6.5,107.1,-6.0",
                    )
                    search_datetime = st.text_input(
                        "Date or date interval (optional)",
                        placeholder="2026-01-01/2026-03-31",
                        help="Use an RFC 3339 timestamp or interval supported by the STAC API.",
                    )
                    search_collections = st.text_input(
                        "Collection IDs (optional, comma-separated)",
                        placeholder="sentinel-2-l2a,landsat-c2-l2",
                    )
                    search_limit = st.number_input(
                        "Maximum items per page",
                        min_value=1,
                        max_value=1000,
                        value=100,
                        step=25,
                    )
                    submit_search = st.form_submit_button("Search STAC API", type="primary")
                if submit_search:
                    try:
                        requested_url = build_stac_search_url(
                            search_endpoint,
                            bbox=search_bbox,
                            datetime_range=search_datetime,
                            collections=search_collections,
                            limit=search_limit,
                        )
                        st.session_state["active_stac_search"] = {
                            "root": real_url,
                            "url": requested_url,
                        }
                    except ValueError as exc:
                        st.error(str(exc))
                active_search = st.session_state.get("active_stac_search") or {}
                if active_search.get("root") == real_url and active_search.get("url"):
                    crawl_url = active_search["url"]
                    st.caption("Search URL: " + crawl_url)
                else:
                    crawl_url = None
                    st.info("Set any filters you need, then submit the STAC API search form.")
            except Exception as exc:
                crawl_url = None
                st.error(f"Could not prepare STAC API search: {exc}. You can turn this option off to browse the catalog links.")

        all_links, tiff_links, oam_items = [], [], []
        crawl_state = {"pages": 0, "capped": False, "post_next": False}
        if crawl_url:
            with st.spinner("Discovering STAC items and imagery assets..."):
                if use_api_search:
                    all_links, tiff_links, oam_items, crawl_state = run_crawl(
                        crawl_url,
                        max_items=STAC_SEARCH_MAX_ITEMS,
                        max_pages=STAC_SEARCH_MAX_PAGES,
                    )
                else:
                    all_links, tiff_links, oam_items, crawl_state = run_crawl(crawl_url)
            if crawl_state.get("capped"):
                st.warning(
                    f"Discovery reached its safety cap ({STAC_SEARCH_MAX_ITEMS:,} items or "
                    f"{STAC_SEARCH_MAX_PAGES} pages). Narrow the bbox, date interval, or collections to inspect a smaller result set."
                )
            if crawl_state.get("post_next"):
                st.warning(
                    "This STAC API returned a POST-only pagination link. The current workbench follows GET pagination only, so discovery stopped before that page."
                )

        if crawl_url and all_links:
            st.divider()
            st.header("Filter by area (optional)")
            
            group_by_location = st.toggle("Draw a box on the map to filter images")
            
            if group_by_location:
                st.info("Draw an area around the activation you need. Filtering reduces the number of scenes sent to mapping software.")
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

            st.subheader("Discovery results")
            st.caption("STAC items found vs. usable GeoTIFF scenes (current area filter).")
            m1, m2, m3, m4 = st.columns(4)
            with m1:
                ui.metric_card(
                    "STAC items inspected",
                    len(display_oam_items),
                    description="Items discovered in the selected area",
                    variant="dashboard",
                    key="metric-stac-items-inspected",
                )
            with m2:
                ui.metric_card(
                    "Usable GeoTIFFs",
                    len(display_tiff_links),
                    description="Scenes with a usable GeoTIFF asset",
                    variant="dashboard",
                    key="metric-total-usable-images",
                )
            with m3:
                ui.metric_card(
                    "PRE-event",
                    len(pre_items),
                    description="Before-disaster baseline scenes",
                    variant="dashboard",
                    key="metric-pre-event",
                )
            with m4:
                ui.metric_card(
                    "POST-event",
                    len(post_items),
                    description="After-disaster scenes",
                    variant="dashboard",
                    key="metric-post-event",
                )

            st.divider()
            st.header("Prepare a handoff")

            tab_tm, tab_oam, tab_adv = st.tabs([
                "Tasking Manager / JOSM", 
                "OpenAerialMap", 
                "Advanced data"
            ])

            with tab_tm:
                st.info("These links let HOT Tasking Manager, iD Editor, and JOSM stream selected imagery as a tracing background.")
                
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
                    
                    with st.expander("Advanced: View the exact image IDs in this layer"):
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
                st.info("Check for an existing image before preparing a handoff. Duplicate footprints make the imagery catalog harder to use.")
                st.markdown("**Ready to upload?** Use the prefilled OAM v2 handoff for each selected scene. The source GeoTIFF stays at its public URL; OAM fetches it server-side.")

                if display_oam_items:
                    if st.button("Check OAM v2 for Duplicates"):
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
                            if meta.get("thumbnail_url"):
                                st.image(meta["thumbnail_url"], caption="STAC thumbnail asset")
                            if "Already exists" in status_label:
                                st.warning(status_label)
                                if meta.get("oam_existing_link"):
                                    if "Exact ID" in status_label:
                                        st.link_button("View exact image (HOTOSM Viewer)", meta["oam_existing_link"])
                                    else:
                                        st.link_button("View overlapping image (HOTOSM Viewer)", meta["oam_existing_link"])
                            elif "Not found" in status_label:
                                st.success(f"{status_label} – Ready for submission.")
                            elif "Inconclusive" in status_label or "Unable to check" in status_label:
                                st.warning(status_label)
                            elif "Check Failed" in status_label:
                                st.error(status_label)
                            
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
                        label="Download audit log / checklist (CSV)",
                        data=csv_buffer.getvalue(),
                        file_name=export_csv_filename,
                        mime="text/csv",
                        help="Use this CSV as a checklist to keep track of which URLs you have manually uploaded to OAM v2."
                    )

                else:
                    st.info("No OAM-compatible STAC items are available for the current selection.")

            with tab_adv:
                st.caption("Raw Data Endpoints for Developers")
                for idx, link in enumerate(all_links, 1):
                    st.markdown(f"{idx}. [{link}]({link})")

        elif crawl_url:
            st.info("No STAC imagery links were found. Check the catalog URL or try another STAC item.")
