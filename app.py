import streamlit as st
import streamlit_shadcn_ui as ui
import requests
from urllib.parse import urlparse, unquote, urljoin
import re
import io
import csv
import json
import os
import shutil
import subprocess
from pathlib import Path
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
        # Never silently replace a pre-existing user file.
        quoted_output = "'" + output_path.replace("'", "''") + "'"
        guard = (
            f"$out={quoted_output}; "
            "if (Test-Path -LiteralPath $out) { "
            "throw 'Output already exists; choose a different output path.' }; "
        )
        if source_epsg:
            command = (guard + f'gdalwarp -s_srs EPSG:{int(source_epsg)} -of COG '
                       f'-co COMPRESS=DEFLATE "{input_path}" "$out"')
        else:
            command = guard + f'gdal_translate -of COG -co COMPRESS=DEFLATE "{input_path}" "$out"'
    return {"ready": not issues, "issues": issues, "output": output_path, "command": command,
            "notes": ["Creates a new file and does not overwrite the source.",
                      "Uses lossless DEFLATE so RGB and RGBA are preserved.",
                      "COG is a local output target; OAM may still perform server-side validation/transcoding."]}


# ---------- Local GDAL / OAM imagery workbench ----------
OAM_STAC_SCHEMA_URL = "https://docs.imagery.hotosm.org/oam/v0.3.0/schema.json"
OAM_SUPPORTED_PRODUCTS = ("visual", "multispectral", "sar", "elevation", "pseudocolor")
OAM_SUPPORTED_PLATFORMS = ("kite", "balloon", "uav", "aircraft", "satellite")
OAM_SUPPORTED_LICENSES = ("CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-NC-4.0")
OAM_MAX_UPLOAD_BYTES = 100 * 1024**3


def resolve_local_gdal_tools(gdal_bin_dir: str = "") -> dict[str, str]:
    """Find both GDAL CLI tools without requiring a shell or changing PATH."""
    suffix = ".exe" if os.name == "nt" else ""
    candidates: list[Path] = []
    if gdal_bin_dir.strip():
        custom = Path(gdal_bin_dir.strip().strip('"')).expanduser()
        candidates.append(custom.parent if custom.is_file() else custom)
    for env_name in ("OSGEO4W_ROOT", "QGIS_PREFIX_PATH"):
        root = os.environ.get(env_name, "").strip()
        if root:
            base = Path(root)
            candidates.extend((base, base / "bin", base.parent / "bin"))
    if os.name == "nt":
        candidates.extend((Path("C:/OSGeo4W/bin"), Path("C:/OSGeo4W64/bin")))
        program_files = Path(os.environ.get("ProgramFiles", "C:/Program Files"))
        candidates.extend(program_files.glob("QGIS */bin"))
    found: dict[str, str] = {}
    for candidate in candidates:
        if not candidate.is_dir():
            continue
        for tool in ("gdalinfo", "gdal_translate"):
            executable = candidate / f"{tool}{suffix}"
            if executable.is_file():
                found[tool] = str(executable)
        if len(found) == 2:
            return found
    for tool in ("gdalinfo", "gdal_translate"):
        found.setdefault(tool, shutil.which(f"{tool}{suffix}") or shutil.which(tool) or "")
    return found if all(found.values()) else {}


def run_local_gdalinfo(path: str, tools: dict[str, str]) -> dict[str, Any]:
    """Read raster metadata locally; raster bytes are never sent to a service."""
    source = Path(str(path).strip().strip('"')).expanduser()
    if not source.is_file():
        raise FileNotFoundError(f"Raster file does not exist: {source}")
    if not tools.get("gdalinfo"):
        raise RuntimeError("gdalinfo was not found. Set the GDAL bin directory or launch Streamlit from the QGIS/OSGeo4W shell.")
    try:
        proc = subprocess.run(
            [tools["gdalinfo"], "-json", str(source)],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=600, check=False,
        )
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError("gdalinfo timed out after 10 minutes. Check the file and local storage, then retry.") from exc
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"gdalinfo exited with code {proc.returncode}.")
    try:
        info = json.loads(proc.stdout)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"gdalinfo returned invalid JSON: {exc}") from exc
    if not isinstance(info, dict) or not info.get("size") or not info.get("bands"):
        raise RuntimeError("GDAL did not return a usable raster dataset description.")
    return info


def _local_decoded_bytes(info: dict[str, Any]) -> int | None:
    sizes = {
        "BYTE": 1, "UINT8": 1, "INT8": 1, "UINT16": 2, "INT16": 2,
        "UINT32": 4, "INT32": 4, "FLOAT32": 4, "FLOAT64": 8,
        "CINT16": 4, "CINT32": 8, "CFLOAT32": 8, "CFLOAT64": 16,
    }
    width, height = (info.get("size") or [0, 0])[:2]
    bands = info.get("bands") or []
    if not width or not height or not bands:
        return None
    per_band = [sizes.get(str(b.get("type", "")).upper()) for b in bands]
    if any(value is None for value in per_band):
        return None
    return int(width) * int(height) * sum(int(value) for value in per_band)


def validate_local_oam_raster(
    info: dict[str, Any], product_type: str, file_size_bytes: int | None = None
) -> dict[str, Any]:
    """Apply current OAM product-aware raster checks without guessing semantics."""
    checks: list[dict[str, str]] = []

    def check(status: str, name: str, detail: str) -> None:
        checks.append({"status": status, "name": name, "detail": detail})

    driver = str(info.get("driverShortName") or info.get("driver") or "")
    bands = info.get("bands") or []
    types = [str(b.get("type", "")).upper() for b in bands]
    colors = [str(b.get("colorInterpretation", "")).lower() for b in bands]
    crs = info.get("coordinateSystem") or {}
    crs_ok = bool(crs.get("wkt") or crs.get("projjson"))
    width, height = (info.get("size") or [0, 0])[:2]
    product = str(product_type or "").lower()

    check("PASS" if driver.upper() == "GTIFF" else "FAIL", "GeoTIFF driver",
          f"GDAL driver is {driver or 'unknown'}." if driver.upper() == "GTIFF" else f"OAM ingests GeoTIFF; GDAL reports {driver or 'unknown'}.")
    check("PASS" if crs_ok else "FAIL", "Coordinate reference system",
          "A CRS is declared." if crs_ok else "No CRS is declared. Do not assign one unless the source CRS is known.")
    check("PASS" if width and height and bands else "FAIL", "Raster dimensions and bands",
          f"{width:,} × {height:,}; {len(bands)} band(s)." if width and height and bands else "GDAL did not report valid dimensions and bands.")
    check("PASS" if product in OAM_SUPPORTED_PRODUCTS else "FAIL", "OAM product type",
          f"Declared {product}." if product in OAM_SUPPORTED_PRODUCTS else f"Choose one of: {', '.join(OAM_SUPPORTED_PRODUCTS)}.")

    if product == "visual":
        visual_ok = len(bands) in (3, 4) and bool(types) and all(t in {"BYTE", "UINT8"} for t in types)
        check("PASS" if visual_ok else "FAIL", "Visual pixel contract",
              f"{len(bands)} band(s), types {types}; visual requires 3–4 8-bit bands." if visual_ok else f"Found {len(bands)} band(s), types {types}; declared visual requires 3–4 8-bit bands.")
        if visual_ok and colors[:3] != ["red", "green", "blue"]:
            check("WARN", "Color interpretation", f"GDAL reports {colors}; verify the band order is really RGB before declaring visual.")
        elif visual_ok and len(bands) == 4 and len(colors) > 3 and colors[3] not in {"alpha", "undefined"}:
            check("WARN", "Fourth band", f"Band 4 is {colors[3]}, not clearly alpha. OAM may treat it as multispectral.")
        else:
            check("PASS", "Color interpretation", "Band interpretation is consistent with the declared visual product.")
    elif product in OAM_SUPPORTED_PRODUCTS:
        check("PASS", "Native data preservation", f"{product} products retain their native {types or ['unknown']} data types and band count; no RGB/Byte coercion is applied.")

    decoded = _local_decoded_bytes(info)
    # Match OAM's current validator budget: JPEG visual conversion gets
    # 130 / 0.6 GB; all lossless paths retain the 130 GB default.
    lossy_visual = (
        product == "visual"
        and len(bands) in (3, 4)
        and bool(types)
        and types[0] in {"BYTE", "UINT8"}
        and (len(bands) == 3 or (len(colors) > 3 and colors[3] == "alpha"))
    )
    max_decoded_gb = round(130.0 / 0.6, 1) if lossy_visual else 130.0
    decoded_limit_bytes = max_decoded_gb * 1_000_000_000
    if decoded is None:
        check("WARN", "Decoded size", "Could not estimate decoded size from the reported band types.")
    elif decoded > decoded_limit_bytes:
        check(
            "WARN", "Decoded size",
            f"Estimated decoded size is {decoded / 1e9:.1f} GB; OAM's current default for this conversion path is {max_decoded_gb:g} GB. Deployments may override this.",
        )
    else:
        check(
            "PASS", "Decoded size",
            f"Estimated decoded size is {decoded / 1e9:.2f} GB; OAM's current default for this conversion path is {max_decoded_gb:g} GB (deployment-configurable).",
        )

    if file_size_bytes is not None:
        check("PASS" if file_size_bytes <= OAM_MAX_UPLOAD_BYTES else "FAIL", "Upload file size",
              f"{file_size_bytes / 1024**3:.2f} GiB; current OAM uploader ceiling is 100 GiB." if file_size_bytes <= OAM_MAX_UPLOAD_BYTES else f"{file_size_bytes / 1024**3:.2f} GiB exceeds the current 100 GiB uploader ceiling.")

    metadata = (info.get("metadata") or {}).get("IMAGE_STRUCTURE") or {}
    is_cog = str(metadata.get("LAYOUT", "")).upper() == "COG"
    check("PASS" if is_cog else "WARN", "Cloud Optimized GeoTIFF",
          "GDAL reports LAYOUT=COG." if is_cog else "Source is not reported as a COG; local preparation can create a separate COG.")
    has_overviews = bool(bands) and all(bool(b.get("overviews")) for b in bands)
    check("PASS" if has_overviews else "WARN", "Overviews",
          "Every band reports internal overviews." if has_overviews else "One or more bands have no reported overviews; COG preparation will build them when needed.")
    extent = info.get("wgs84Extent")
    check("PASS" if isinstance(extent, dict) and extent.get("coordinates") else "WARN", "WGS84 extent",
          "GDAL supplied an EPSG:4326 geometry for metadata generation." if isinstance(extent, dict) and extent.get("coordinates") else "GDAL did not supply a WGS84 extent; metadata geometry needs manual investigation.")

    failures = [item for item in checks if item["status"] == "FAIL"]
    warnings = [item for item in checks if item["status"] == "WARN"]
    return {"status": "FAIL" if failures else ("WARN" if warnings else "PASS"), "checks": checks, "decodedBytes": decoded}


def create_local_thumbnail(
    raster_path: str, info: dict[str, Any], product_type: str, tools: dict[str, str]
) -> str | None:
    """Create a small PNG preview; never modify the raster or replace an existing preview."""
    source = Path(raster_path).expanduser().resolve()
    output = source.with_name(source.stem + "_thumbnail.png")
    if output.exists():
        raise FileExistsError(f"Thumbnail already exists; choose another output path: {output}")
    if not tools.get("gdal_translate"):
        raise RuntimeError("gdal_translate was not found.")
    args = [tools["gdal_translate"], "-of", "PNG", "-outsize", "1024", "0"]
    bands = info.get("bands") or []
    types = [str(b.get("type", "")).upper() for b in bands]
    if product_type != "visual" or len(bands) < 3 or not all(t in {"BYTE", "UINT8"} for t in types[:3]):
        return None
    args.extend(["-b", "1", "-b", "2", "-b", "3"])
    args.extend([str(source), str(output)])
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=900, check=False)
    if proc.returncode != 0 or not output.is_file():
        raise RuntimeError(proc.stderr.strip() or "GDAL did not create the thumbnail.")
    return str(output)


def build_local_cog(
    source_path: str, output_path: str, source_info: dict[str, Any],
    product_type: str, tools: dict[str, str],
) -> dict[str, Any]:
    """Create and verify a separate lossless COG; never overwrite source/output."""
    source = Path(str(source_path).strip().strip('"')).expanduser().resolve(strict=True)
    output = Path(str(output_path).strip().strip('"')).expanduser().resolve()
    if source == output:
        raise ValueError("Output path must differ from the source raster.")
    if output.exists():
        raise FileExistsError(f"Output already exists; choose another path: {output}")
    if not output.parent.is_dir():
        raise FileNotFoundError(f"Output directory does not exist: {output.parent}")
    if not tools.get("gdal_translate") or not tools.get("gdalinfo"):
        raise RuntimeError("Both gdal_translate and gdalinfo are required.")
    args = [
        tools["gdal_translate"], "-of", "COG",
        "-co", "COMPRESS=DEFLATE",
        "-co", "BIGTIFF=IF_SAFER",
        "-co", "BLOCKSIZE=512",
        "-co", "RESAMPLING=AVERAGE",
        "-co", "NUM_THREADS=ALL_CPUS",
        str(source), str(output),
    ]
    proc = subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=14400, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"gdal_translate exited with code {proc.returncode}. Any partial output was left untouched for inspection.")
    if not output.is_file():
        raise RuntimeError("gdal_translate reported success but the output file was not created.")
    output_info = run_local_gdalinfo(str(output), tools)
    output_structure = (output_info.get("metadata") or {}).get("IMAGE_STRUCTURE") or {}
    if str(output_structure.get("LAYOUT", "")).upper() != "COG":
        raise RuntimeError("GDAL created an output, but gdalinfo did not confirm LAYOUT=COG. The output was not deleted.")
    if output_info.get("size") != source_info.get("size"):
        raise RuntimeError("COG verification failed: raster dimensions changed. The output was not deleted.")
    source_bands, output_bands = source_info.get("bands") or [], output_info.get("bands") or []
    if len(source_bands) != len(output_bands):
        raise RuntimeError("COG verification failed: band count changed. The output was not deleted.")
    if [str(b.get("type", "")).upper() for b in source_bands] != [str(b.get("type", "")).upper() for b in output_bands]:
        raise RuntimeError("COG verification failed: band data types changed. The output was not deleted.")
    if source_info.get("geoTransform") != output_info.get("geoTransform"):
        raise RuntimeError("COG verification failed: geotransform changed. The output was not deleted.")
    source_crs = source_info.get("coordinateSystem") or {}
    output_crs = output_info.get("coordinateSystem") or {}
    if bool(source_crs.get("wkt") or source_crs.get("projjson")) != bool(output_crs.get("wkt") or output_crs.get("projjson")):
        raise RuntimeError("COG verification failed: CRS presence changed. The output was not deleted.")
    source_crs_id, output_crs_id = source_crs.get("id"), output_crs.get("id")
    if source_crs_id and output_crs_id and source_crs_id != output_crs_id:
        raise RuntimeError("COG verification failed: CRS identifier changed. The output was not deleted.")
    thumbnail = None
    thumbnail_error = None
    try:
        thumbnail = create_local_thumbnail(str(output), output_info, product_type, tools)
    except Exception as exc:
        thumbnail_error = str(exc)
    return {"path": str(output), "info": output_info, "thumbnail": thumbnail, "thumbnail_error": thumbnail_error}


def _geojson_positions(value: Any):
    """Yield longitude/latitude pairs from nested GeoJSON coordinates."""
    if isinstance(value, (list, tuple)) and len(value) >= 2 and all(isinstance(x, (int, float)) for x in value[:2]):
        yield float(value[0]), float(value[1])
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _geojson_positions(child)


def build_local_oam_item(
    info: dict[str, Any], asset_path: str, metadata: dict[str, Any],
    thumbnail_path: str | None = None,
) -> dict[str, Any]:
    """Build an OAM v0.3.0 STAC draft from GDAL geometry and user-confirmed fields."""
    extent = info.get("wgs84Extent")
    if not isinstance(extent, dict) or not extent.get("coordinates"):
        raise ValueError("GDAL did not provide a WGS84 extent. Do not guess the Item geometry.")
    positions = list(_geojson_positions(extent["coordinates"]))
    if not positions:
        raise ValueError("Could not extract longitude/latitude coordinates from GDAL's WGS84 extent.")
    longitudes = [point[0] for point in positions]
    latitudes = [point[1] for point in positions]
    if max(longitudes) - min(longitudes) > 180:
        raise ValueError("This extent crosses the antimeridian. The geometry must be split before creating a valid OAM STAC Item.")
    required = ("title", "producer", "platform", "product_type", "license", "datetime", "gsd")
    missing = [key for key in required if metadata.get(key) in (None, "")]
    if missing:
        raise ValueError("Missing user-confirmed metadata: " + ", ".join(missing))
    if metadata["product_type"] not in OAM_SUPPORTED_PRODUCTS:
        raise ValueError("Choose a supported OAM product type.")
    if metadata["platform"] not in OAM_SUPPORTED_PLATFORMS:
        raise ValueError("Choose the actual platform type; it is not inferred.")
    if metadata["license"] not in OAM_SUPPORTED_LICENSES:
        raise ValueError("Choose one of OAM's accepted Creative Commons licenses.")
    gsd = float(metadata["gsd"])
    if gsd <= 0:
        raise ValueError("GSD must be greater than zero.")
    captured = datetime.fromisoformat(str(metadata["datetime"]).replace("Z", "+00:00"))
    if captured.tzinfo is None:
        raise ValueError("Acquisition datetime must include a timezone, e.g. Z or +07:00.")
    producer = str(metadata["producer"]).strip()
    if not producer:
        raise ValueError("Producer cannot be empty.")
    title = str(metadata["title"]).strip()
    if not title:
        raise ValueError("Title cannot be empty.")
    asset_name = Path(asset_path).name
    item_id = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(asset_path).stem).strip("-") or "local-imagery"
    properties: dict[str, Any] = {
        "title": title,
        "datetime": captured.isoformat().replace("+00:00", "Z"),
        "license": metadata["license"],
        "gsd": gsd,
        "providers": [{"name": producer, "roles": ["producer", "licensor"]}],
        "oam:platform_type": metadata["platform"],
        "oam:producer_name": producer,
        "oam:product_type": metadata["product_type"],
        "oam:product_type_source": "declared",
        "oam:footprint_source": "bbox",
    }
    sensor = str(metadata.get("sensor", "")).strip()
    if sensor:
        properties["instruments"] = [sensor]
    item: dict[str, Any] = {
        "type": "Feature",
        "stac_version": "1.0.0",
        "stac_extensions": [OAM_STAC_SCHEMA_URL],
        "id": item_id,
        "geometry": extent,
        "bbox": [min(longitudes), min(latitudes), max(longitudes), max(latitudes)],
        "properties": properties,
        "assets": {
            "visual": {
                "href": "./" + asset_name,
                "type": "image/tiff; application=geotiff; profile=cloud-optimized",
                "roles": ["data"],
                "title": asset_name,
            }
        },
        "links": [{"rel": "self", "href": "./" + item_id + "_oam_item.json", "type": "application/geo+json"}],
    }
    if thumbnail_path:
        item["assets"]["thumbnail"] = {
            "href": "./" + Path(thumbnail_path).name,
            "type": "image/png",
            "roles": ["thumbnail"],
        }
    return item


def write_local_oam_item(item: dict[str, Any], output_path: str) -> str:
    """Write a metadata sidecar once; never replace an existing file."""
    output = Path(output_path).expanduser().resolve()
    if output.exists():
        raise FileExistsError(f"Metadata file already exists; choose another path: {output}")
    if not output.parent.is_dir():
        raise FileNotFoundError(f"Metadata directory does not exist: {output.parent}")
    output.write_text(json.dumps(item, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return str(output)


def build_oam_local_prefill_url(metadata: dict[str, Any]) -> str:
    """Build the documented OAM uploader handoff without a local path/source_url."""
    fields = {
        "title": metadata.get("title"),
        "provider": metadata.get("producer"),
        "platform": metadata.get("platform"),
        "license": metadata.get("license"),
        "acquisition_start": metadata.get("datetime"),
        "sensor": metadata.get("sensor"),
        "product_type": metadata.get("product_type"),
    }
    clean = {key: value for key, value in fields.items() if value not in (None, "")}
    return OAM_UPLOAD_URL + "#" + urlencode(clean, quote_via=quote)


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
st.set_page_config(page_title="STAC Imagery Workbench", layout="wide", initial_sidebar_state="collapsed")

st.markdown(
    """<style>
/* Hallmark · app screen · modern-minimal · full redesign · v2.0.0 */
/* Hallmark · pre-emit critique: P4 H5 E5 S5 R5 V4 · weakest: P, keep the workbench task-led rather than adding a marketing hero */
:root {
    --app-canvas: #f2f6f7;
    --app-surface: #f9fbfb;
    --app-ink: #20343a;
    --app-muted: #5a6e73;
    --app-border: #d7e2e3;
    --app-accent: #176b72;
    --app-accent-soft: #e2f0ef;
    --app-focus: #0c7881;
    --app-font: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
    --app-radius: 12px;
}
html, body { overflow-x: clip; }
body, [data-testid="stAppViewContainer"] { font-family: var(--app-font); color: var(--app-ink); }
[data-testid="stAppViewContainer"] { background: var(--app-canvas); }
[data-testid="stHeader"] { background: transparent; }
[data-testid="stMainBlockContainer"] { max-width: 1480px; padding-top: 1.75rem; padding-bottom: 3rem; }
h1 { color: var(--app-ink); font-size: 1.8rem; letter-spacing: -0.025em; }
h2, h3 { color: var(--app-ink); letter-spacing: -0.012em; }
[data-testid="stMarkdownContainer"] p { color: var(--app-ink); line-height: 1.55; }
[data-testid="stTabs"] [role="tablist"] { gap: 0.25rem; border-bottom: 1px solid var(--app-border); }
[data-testid="stTabs"] button[role="tab"] { min-height: 44px; padding: 0.55rem 1rem; color: var(--app-muted); }
[data-testid="stTabs"] button[aria-selected="true"] { color: var(--app-accent); border-bottom-color: var(--app-accent); }
[data-testid="stVerticalBlockBorderWrapper"] { background: var(--app-surface); border-color: var(--app-border); border-radius: var(--app-radius); }
[data-testid="stTextInput"] input, [data-testid="stTextArea"] textarea { font-size: 16px; }
button:focus-visible, input:focus-visible, textarea:focus-visible, select:focus-visible, [role="tab"]:focus-visible { outline: 2px solid var(--app-focus); outline-offset: 2px; }
::selection { background: var(--app-accent-soft); color: var(--app-ink); }
@media (max-width: 768px) {
    [data-testid="stMainBlockContainer"] { padding-left: 1rem; padding-right: 1rem; }
    [data-testid="stTabs"] [role="tablist"] { overflow-x: auto; flex-wrap: nowrap; }
}
@media (prefers-reduced-motion: reduce) {
    *, *::before, *::after { scroll-behavior: auto !important; animation-duration: 0.01ms !important; animation-iteration-count: 1 !important; transition-duration: 0.01ms !important; }
}
</style>""",
    unsafe_allow_html=True,
)

st.title("STAC Imagery Workbench")
st.markdown("Find imagery, inspect coverage, and prepare mapping or OpenAerialMap handoffs.")

active_workflow = ui.tabs(
    options=["Discover & map", "Local preparation"],
    value="Discover & map",
    label="Workflow",
    variant="line",
    key="active-workflow-tabs",
)

if active_workflow == "Local preparation":
    # ---------- Local DroneTM Progress Mosaic ----------
    ui.card(
        title="DroneTM progress mosaic",
        description="Run locally on your computer",
        content=(
            "Large orthophoto downloads and mosaic/COG processing run on your computer, "
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

    # ---------- Local imagery preparation and OAM handoff ----------
    st.header("Local geospatial imagery preparation")
    st.caption(
        "Inspect → validate → prepare → create metadata → hand off to OAM. "
        "GDAL runs on the machine hosting this Streamlit process."
    )
    st.info(
        "This feature needs Streamlit running locally on the same computer as the raster and GDAL/QGIS. "
        "A cloud-hosted copy cannot read your Windows paths or use your local QGIS installation."
    )

    with st.expander("Separate DroneTM task-download and mosaic workflow"):
        st.markdown(
            "For downloading Tasking Manager orthophotos and building a DroneTM progress mosaic, "
            "use the separate local tool. This workbench handles preparation of an existing raster."
        )
        st.link_button(
            "Open DroneTM Progress Mosaic on GitHub",
            "https://github.com/adiatmad/dronetm-progress-mosaic",
        )

    gdal_bin_dir = st.text_input(
        "GDAL bin directory (optional)",
        placeholder=r"C:\OSGeo4W\bin",
        key="local_gdal_bin_dir",
        help="Leave blank when gdalinfo and gdal_translate are already on PATH or launch this app from the QGIS/OSGeo4W shell.",
    )
    local_gdal_tools = resolve_local_gdal_tools(gdal_bin_dir)
    if local_gdal_tools:
        st.success("Local GDAL tools detected.")
        st.caption(f"gdalinfo: {local_gdal_tools['gdalinfo']} · gdal_translate: {local_gdal_tools['gdal_translate']}")
    else:
        st.warning(
            "GDAL CLI tools were not detected. Launch Streamlit from the QGIS/OSGeo4W shell, "
            "or enter the folder containing both gdalinfo and gdal_translate."
        )

    source_path = st.text_input(
        "Source raster path",
        placeholder=r"D:\imagery\orthomosaic.tif",
        key="preflight_path",
        help="The source is opened read-only. It is never copied to a remote service or overwritten.",
    )
    inspect_clicked = st.button(
        "Inspect raster with GDAL",
        type="primary",
        disabled=not (source_path.strip().strip('"') and local_gdal_tools),
        key="run_gdal_check",
    )
    if inspect_clicked:
        try:
            with st.spinner("Reading raster metadata locally with gdalinfo…"):
                inspected_info = run_local_gdalinfo(source_path.strip().strip('"'), local_gdal_tools)
            st.session_state["local_imagery_inspection"] = {
                "path": str(Path(source_path.strip().strip('"')).expanduser().resolve()),
                "info": inspected_info,
                "file_size": Path(source_path.strip().strip('"')).expanduser().stat().st_size,
            }
            st.session_state.pop("local_imagery_cog_result", None)
            st.session_state.pop("local_oam_item_result", None)
            st.session_state["local_cog_output_path"] = str(
                Path(source_path.strip().strip('"')).expanduser().with_name(
                    Path(source_path.strip().strip('"')).expanduser().stem + "_prepared_cog.tif"
                )
            )
        except Exception as exc:
            st.error(f"Local GDAL inspection failed: {exc}")

    inspection = st.session_state.get("local_imagery_inspection")
    current_source = str(Path(source_path.strip().strip('"')).expanduser().resolve()) if source_path.strip().strip('"') else ""
    if inspection and inspection.get("path") == current_source:
        info = inspection["info"]
        bands = info.get("bands") or []
        width, height = info.get("size") or [0, 0]
        crs = info.get("coordinateSystem") or {}
        crs_id = crs.get("id") or {}
        epsg = crs_id.get("code") if isinstance(crs_id, dict) else crs_id
        image_structure = (info.get("metadata") or {}).get("IMAGE_STRUCTURE") or {}
        decoded = _local_decoded_bytes(info)

        st.markdown("### 1 · Inspect")
        metric_cols = st.columns(4)
        metric_cols[0].metric("Raster", f"{width:,} × {height:,}" if width and height else "Unknown")
        metric_cols[1].metric("Bands", str(len(bands)))
        metric_cols[2].metric("CRS", f"EPSG:{epsg}" if epsg else ("Declared" if crs.get("wkt") else "Missing"))
        metric_cols[3].metric("File size", format_bytes(inspection["file_size"]))
        if decoded is not None:
            st.caption(f"Estimated decoded size: {decoded / 1_000_000_000:.2f} GB · GDAL compression: {image_structure.get('COMPRESSION', 'not reported')} · COG layout: {image_structure.get('LAYOUT', 'not reported')}")
        st.markdown("**Band details**")
        for band in bands:
            block = band.get("block") or []
            overview = band.get("overviews") or []
            st.markdown(
                f"- Band {band.get('band', '?')}: **{band.get('type', 'unknown')}** · "
                f"{band.get('colorInterpretation', 'unknown')} · "
                f"block {block[0]}×{block[1] if len(block) > 1 else '?'} · "
                f"{len(overview)} overview level(s)"
            )
        with st.expander("Georeferencing and full GDAL metadata"):
            st.json({
                "driver": info.get("driverShortName") or info.get("driver"),
                "size": info.get("size"),
                "geoTransform": info.get("geoTransform"),
                "coordinateSystem": info.get("coordinateSystem"),
                "cornerCoordinates": info.get("cornerCoordinates"),
                "wgs84Extent": info.get("wgs84Extent"),
                "imageStructure": image_structure,
            })

        st.markdown("### 2 · Validate against OAM")
        product_type = st.selectbox(
            "OAM product type",
            options=["Select product type", *OAM_SUPPORTED_PRODUCTS],
            index=0,
            key="local_oam_product_type",
            help="Choose from the actual data. Only visual requires 3–4 8-bit bands; other products retain native values.",
        )
        validation = validate_local_oam_raster(info, product_type, inspection["file_size"])
        for check_index, check in enumerate(validation["checks"]):
            variant = {"PASS": "default", "WARN": "secondary", "FAIL": "destructive"}[check["status"]]
            ui.badge(check["status"], variant=variant, key=f"local-oam-check-{check_index}")
            st.markdown(f"**{check['name']}**  \n{check['detail']}")
        hard_fails = [item for item in validation["checks"] if item["status"] == "FAIL"]
        if hard_fails:
            st.error("This raster fails one or more OAM checks. Resolve the failed items before preparing it for publication.")
        elif validation["status"] == "WARN":
            st.warning("No hard OAM raster failure was detected, but review the warnings and confirm the source metadata.")
        else:
            st.success("The raster passes the current local OAM checks.")

        st.markdown("### 3 · Prepare a separate COG")
        st.caption(
            "Creates a lossless DEFLATE COG with internal overviews where needed. "
            "It preserves the source data type and all bands; it does not reproject, rescale, or alter the source. "
            "OAM will still run its own server-side conversion after upload."
        )
        output_path = st.text_input(
            "Prepared COG output path",
            key="local_cog_output_path",
            help="The output must be a new path. Existing files are never overwritten.",
        )
        prepare_clicked = st.button(
            "Prepare lossless COG and thumbnail",
            disabled=bool(hard_fails) or not output_path.strip() or not local_gdal_tools,
            key="prepare_local_cog",
        )
        if prepare_clicked:
            try:
                with st.spinner("Creating and verifying the COG locally. Large rasters may take time…"):
                    cog_result = build_local_cog(
                        source_path.strip().strip('"'), output_path.strip(), info,
                        product_type, local_gdal_tools,
                    )
                st.session_state["local_imagery_cog_result"] = {
                    "source": current_source,
                    **cog_result,
                }
                st.session_state.pop("local_oam_item_result", None)
            except Exception as exc:
                st.error(f"Local COG preparation failed: {exc}")

        cog_result = st.session_state.get("local_imagery_cog_result")
        if cog_result and cog_result.get("source") == current_source:
            st.success(f"Verified COG created: {cog_result['path']}")
            st.caption("GDAL confirms LAYOUT=COG; dimensions, band count, data types, and geotransform match the source.")
            if cog_result.get("thumbnail"):
                st.image(cog_result["thumbnail"], caption="Local downsampled preview", use_container_width=True)
            elif cog_result.get("thumbnail_error"):
                st.warning(f"COG is ready, but thumbnail creation failed: {cog_result['thumbnail_error']}")

        st.markdown("### 4 · Create OAM metadata and hand off")
        st.caption(
            "Metadata is built from GDAL's WGS84 extent and details you confirm below. "
            "Acquisition time, producer, GSD, platform, and license are never guessed."
        )
        with st.form("local_oam_metadata_form"):
            metadata_title = st.text_input(
                "Title",
                value=Path(source_path.strip().strip('"')).stem,
                key="local_oam_title",
            )
            st.caption("Review the filename-based title suggestion. Producer, platform, GSD, acquisition time, and license must reflect the real source.")
            metadata_producer = st.text_input(
                "Imagery producer",
                placeholder="Person or organisation that produced the imagery",
                key="local_oam_producer",
            )
            metadata_platform = st.selectbox(
                "Platform type",
                options=["Select platform type", *OAM_SUPPORTED_PLATFORMS],
                index=0,
                key="local_oam_platform",
            )
            metadata_gsd = st.text_input(
                "GSD (metres per pixel)",
                placeholder="Example: 0.05",
                key="local_oam_gsd",
                help="Enter the measured/known GSD. Do not use angular pixel size as metres.",
            )
            metadata_datetime = st.text_input(
                "Acquisition datetime (ISO 8601 with timezone)",
                placeholder="2026-11-03T02:03:04Z",
                key="local_oam_datetime",
            )
            metadata_license = st.selectbox(
                "License",
                options=["Select license", *OAM_SUPPORTED_LICENSES],
                index=0,
                key="local_oam_license",
            )
            extent_confirmed = st.checkbox(
                "I understand the generated geometry is the GDAL extent rectangle, not a traced valid-pixel footprint.",
                key="local_oam_extent_confirmed",
            )
            metadata_sensor = st.text_input(
                "Sensor / camera (optional)",
                placeholder="Camera model or sensor name",
                key="local_oam_sensor",
            )
            metadata_submitted = st.form_submit_button("Generate local STAC metadata")
        if metadata_submitted:
            try:
                if not extent_confirmed:
                    raise ValueError("Confirm that the generated geometry is a rectangular GDAL extent, not a traced valid-pixel footprint.")
                gsd_value = float(metadata_gsd)
                confirmed_metadata = {
                    "title": metadata_title.strip(),
                    "producer": metadata_producer.strip(),
                    "platform": metadata_platform,
                    "product_type": product_type,
                    "gsd": gsd_value,
                    "datetime": metadata_datetime.strip(),
                    "license": metadata_license,
                    "sensor": metadata_sensor.strip(),
                }
                selected_asset = cog_result["path"] if cog_result and cog_result.get("source") == current_source else source_path.strip().strip('"')
                selected_thumbnail = cog_result.get("thumbnail") if cog_result and cog_result.get("source") == current_source else None
                if Path(selected_asset).stat().st_size > OAM_MAX_UPLOAD_BYTES:
                    raise ValueError("Selected raster exceeds the current OAM 100 GiB upload ceiling.")
                stac_item = build_local_oam_item(info, selected_asset, confirmed_metadata, selected_thumbnail)
                metadata_path = str(
                    Path(selected_asset).with_name(Path(selected_asset).stem + "_oam_item.json")
                )
                written_metadata_path = write_local_oam_item(stac_item, metadata_path)
                st.session_state["local_oam_item_result"] = {
                    "item": stac_item,
                    "path": written_metadata_path,
                    "metadata": confirmed_metadata,
                    "asset": selected_asset,
                }
            except Exception as exc:
                st.error(f"Could not create OAM metadata: {exc}")

        oam_item_result = st.session_state.get("local_oam_item_result")
        if oam_item_result and oam_item_result.get("asset") == (
            cog_result["path"] if cog_result and cog_result.get("source") == current_source else source_path.strip().strip('"')
        ):
            item_json = json.dumps(oam_item_result["item"], indent=2, ensure_ascii=False)
            st.success(f"Local STAC/OAM metadata draft saved: {oam_item_result['path']}")
            st.download_button(
                "Download STAC metadata JSON",
                data=item_json,
                file_name=Path(oam_item_result["path"]).name,
                mime="application/geo+json",
            )
            st.caption(
                "The local Item uses a relative asset href. It is a preparation draft, not a published catalogue Item; "
                "replace the relative href with a public asset URL if you later reuse it as a remote STAC Item."
            )
            oam_prefill = build_oam_local_prefill_url(oam_item_result["metadata"])
            st.link_button("Open official OAM uploader with metadata", oam_prefill)
            st.warning(
                "In the OAM uploader, select the prepared COG (or original raster if you skipped preparation), "
                "review the prefilled metadata, and submit there yourself. No file is uploaded by this workbench."
            )
    elif inspection and source_path.strip().strip('"'):
        st.caption("The source path changed. Run Inspect raster with GDAL again to refresh the evidence.")


elif active_workflow == "Discover & map":
    st.header("Choose an imagery source")
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

    st.header("Find event imagery")
    st.info("Enter a STAC catalog or item URL to discover imagery that can be filtered and handed off to mapping tools.")

    root_url_input = st.text_input("Data Catalog URL:", value=DEFAULT_SAMPLE_URL, disabled=source_mode != "STAC catalog / item")

    if source_mode == "STAC catalog / item" and root_url_input:
        real_url = extract_real_stac_url(root_url_input)
        event_prefix = extract_event_name_from_url(real_url)

        if real_url != st.session_state["last_processed_url"]:
            st.session_state["oam_duplicates"] = {}
            st.session_state["location_filter_bbox"] = None
            st.session_state["pending_drawing"] = None
            st.session_state["last_processed_url"] = real_url

        with st.spinner("Discovering STAC items and imagery assets..."):
            all_links, tiff_links, oam_items = run_crawl(real_url)

        if all_links:
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
            
            st.subheader("Imagery found")
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
                            if "Already exists" in status_label:
                                st.warning(status_label)
                                if meta.get("oam_existing_link"):
                                    if "Exact ID" in status_label:
                                        st.link_button("View exact image (HOTOSM Viewer)", meta["oam_existing_link"])
                                    else:
                                        st.link_button("View overlapping image (HOTOSM Viewer)", meta["oam_existing_link"])
                            elif "Not found" in status_label:
                                st.success(f"{status_label} – Ready for submission.")
                            
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

        else:
            st.info("No STAC imagery links were found. Check the catalog URL or try another STAC item.")
