"""Pure local checks for the current OpenAerialMap STAC v0.3.0 contract.

This module does not inspect or upload raster bytes. It evaluates metadata already
collected from GDAL or a local STAC Item and separates raster readiness from the
metadata required to publish a visual OAM Item.
"""

from __future__ import annotations

from typing import Any

OAM_SCHEMA_URL = "https://docs.imagery.hotosm.org/oam/v0.3.0/schema.json"
OAM_LICENSES = {"CC-BY-4.0", "CC-BY-SA-4.0", "CC-BY-NC-4.0"}
OAM_PLATFORM_TYPES = {"kite", "balloon", "uav", "aircraft", "satellite"}
OAM_PRODUCT_TYPES = {"visual", "multispectral", "sar", "elevation", "pseudocolor"}


def _props(item: dict[str, Any]) -> dict[str, Any]:
    return item.get("properties") or {}


def _asset_visual(item: dict[str, Any]) -> dict[str, Any]:
    return (item.get("assets") or {}).get("visual") or {}


def _result(status: str, name: str, detail: str) -> dict[str, str]:
    return {"status": status, "name": name, "detail": detail}


def check_oam_item(item: dict[str, Any]) -> dict[str, Any]:
    """Check the current OAM v0.3.0 minimum Item contract.

    This intentionally does not invent missing metadata. Missing fields are FAIL
    only where the current schema/docs make them required; useful optional fields
    remain informational.
    """
    props = _props(item)
    visual = _asset_visual(item)
    checks: list[dict[str, str]] = []

    gsd = item.get("gsd")
    checks.append(_result("PASS" if isinstance(gsd, (int, float)) and gsd > 0 else "FAIL",
                          "GSD", f"Ground sampling distance is {gsd} m/pixel." if isinstance(gsd, (int, float)) and gsd > 0 else "Required: provide a positive gsd in metres per pixel."))

    platform = str(item.get("oam:platform_type") or props.get("oam:platform_type") or "").lower()
    checks.append(_result("PASS" if platform in OAM_PLATFORM_TYPES else "FAIL",
                          "Platform type", f"oam:platform_type={platform}." if platform in OAM_PLATFORM_TYPES else "Required: oam:platform_type must be kite, balloon, uav, aircraft, or satellite."))

    producer = str(item.get("oam:producer_name") or props.get("oam:producer_name") or "").strip()
    checks.append(_result("PASS" if producer else "FAIL",
                          "Producer", f"oam:producer_name={producer}." if producer else "Required: provide the imagery producer name."))

    geometry = item.get("geometry")
    bbox = item.get("bbox")
    checks.append(_result("PASS" if geometry else "FAIL", "Geometry", "GeoJSON image geometry is present." if geometry else "Required: provide image geometry in longitude/latitude (EPSG:4326)."))
    checks.append(_result("PASS" if isinstance(bbox, list) and len(bbox) >= 4 else "FAIL", "BBox", "bbox is present." if isinstance(bbox, list) and len(bbox) >= 4 else "Required: bbox in [west, south, east, north] order."))

    dt = props.get("datetime")
    has_range = props.get("start_datetime") and props.get("end_datetime")
    checks.append(_result("PASS" if dt is not None or has_range else "FAIL", "Acquisition time", "Capture datetime/range is present." if dt is not None or has_range else "Required: provide datetime, or start_datetime/end_datetime with datetime=null for a range."))

    title = str(props.get("title") or "").strip()
    checks.append(_result("PASS" if title else "FAIL", "Title", "A readable title is present." if title else "Required: provide a short readable title."))

    license_value = str(item.get("license") or props.get("license") or "").strip()
    checks.append(_result("PASS" if license_value in OAM_LICENSES else "FAIL", "License", f"Accepted OAM license: {license_value}." if license_value in OAM_LICENSES else "Required: CC-BY-4.0, CC-BY-SA-4.0, or CC-BY-NC-4.0."))

    providers = item.get("providers") or props.get("providers") or []
    provider_names = [str(p.get("name", "")).strip() for p in providers if isinstance(p, dict)]
    provider_ok = bool(provider_names and producer and provider_names[0] == producer)
    checks.append(_result("PASS" if provider_ok else "FAIL", "Provider", "First provider matches oam:producer_name." if provider_ok else "Required: put the producer first in providers and match oam:producer_name."))

    visual_href = str(visual.get("href") or "").strip()
    visual_roles = visual.get("roles") or []
    visual_is_cog = "cog" in {str(x).lower() for x in (visual.get("file:format"), visual.get("type")) if x}
    asset_ok = bool(visual_href) and ("visual" in visual_roles or not visual_roles)
    checks.append(_result("PASS" if asset_ok else "FAIL", "assets.visual", "A visual asset URL is present." if asset_ok else "Required: assets.visual must point to the public visual COG."))
    if visual_is_cog:
        checks.append(_result("PASS", "Visual asset format", "Asset metadata identifies a COG."))
    elif visual_href:
        checks.append(_result("WARN", "Visual asset format", "A visual asset URL exists, but this metadata alone cannot prove that the remote file is a COG."))
    else:
        checks.append(_result("WARN", "Visual asset format", "COG status cannot be checked until assets.visual exists."))

    schema_extensions = item.get("stac_extensions") or []
    checks.append(_result("PASS" if OAM_SCHEMA_URL in schema_extensions else "FAIL", "OAM schema", "Current OAM v0.3.0 schema URL is declared." if OAM_SCHEMA_URL in schema_extensions else "Required: include the current OAM v0.3.0 schema URL in stac_extensions."))

    product = str(item.get("oam:product_type") or props.get("oam:product_type") or "").lower()
    if product:
        checks.append(_result("PASS" if product in OAM_PRODUCT_TYPES else "FAIL", "Product type", f"oam:product_type={product}." if product in OAM_PRODUCT_TYPES else f"Unknown OAM product type: {product}."))
    else:
        checks.append(_result("INFO", "Product type", "Optional. For this workflow, declare visual when the asset is a photograph/RGB orthomosaic."))

    failures = [c for c in checks if c["status"] == "FAIL"]
    warnings = [c for c in checks if c["status"] == "WARN"]
    status = "FAIL" if failures else ("WARN" if warnings else "PASS")
    return {"status": status, "checks": checks, "schema": OAM_SCHEMA_URL}


def visual_oam_metadata_template(*, title: str, producer: str, gsd: float, acquisition_datetime: str,
                                  source_url: str, license_value: str = "CC-BY-4.0") -> dict[str, Any]:
    """Build a small, explicit starting template without inventing geometry."""
    return {
        "type": "Feature",
        "stac_extensions": [OAM_SCHEMA_URL],
        "properties": {
            "title": title,
            "datetime": acquisition_datetime,
            "license": license_value,
            "oam:platform_type": "uav",
            "oam:producer_name": producer,
            "oam:product_type": "visual",
        },
        "gsd": gsd,
        "assets": {"visual": {"href": source_url, "roles": ["visual"]}},
    }
