"""Helpers for turning public imagery-source records into OAM uploader inputs.

These helpers never download imagery. They only discover public object URLs,
derive metadata from source evidence, and build the OAM uploader's documented
fragment prefill link.
"""

from __future__ import annotations

import re
from urllib.parse import quote, unquote, urlencode, urlsplit

import xml.etree.ElementTree as ET

OAM_UPLOAD_URL = "https://upload.imagery.hotosm.org/"
SPACE_EYE_LICENSE = "CC-BY 4.0"
SPACE_EYE_PROVIDER = "SI Imaging Services"
SPACE_EYE_PLATFORM = "satellite"
SPACE_EYE_SENSOR = "SpaceEye-T"

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
