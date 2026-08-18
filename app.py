import streamlit as st
import requests
from urllib.parse import urlparse, unquote, urljoin
import re
import io
import csv
from datetime import datetime
import json  # for escaping text in copy buttons

st.title("Recursive STAC Links Extractor & TIFF URL Generator")

root_url_input = st.text_input("Enter STAC Browser URL")

all_links = []
tiff_links = []  # list of dicts: {"item_url": str, "tiff_url": str, "guessed": bool}
oam_items = []  # list of dicts from extract_oam_metadata()

OAM_DEFAULT_LICENSE = "CC-BY 4.0"
OAM_FIELDNAMES = [
    "item_url", "title", "platform", "sensor", "date_start", "date_end",
    "provider", "tags", "license_oam_default", "stac_license_reference", "image_source_url",
]


def extract_real_stac_url(browser_url: str) -> str:
    if "#/external/" in browser_url:
        raw_url = browser_url.split("#/external/")[-1].strip()
    elif "/external/" in browser_url:
        raw_url = browser_url.split("/external/")[-1].strip()
    else:
        st.error("This does not look like a STAC Browser URL (no '/external/' segment found)")
        return None

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


def guess_provider_name(domain: str) -> str:
    d = domain.lower()
    if "vantor" in d:
        return "Vantor"
    if "maxar" in d:
        return "Maxar"
    return domain


def extract_oam_metadata(item_url: str, item_data: dict, tiff_url: str) -> dict:
    properties = item_data.get("properties", {})
    domain = urlparse(item_url).netloc
    title = properties.get("title") or item_data.get("id", "")
    constellation = properties.get("constellation", "") or ""
    vehicle_name = properties.get("vehicle_name", "") or ""
    if constellation and vehicle_name:
        sensor = f"{constellation.title()} {vehicle_name}"
    else:
        sensor = constellation.title() or vehicle_name
    dt_display = format_datetime_display(properties.get("datetime", ""))
    date_start = dt_display
    date_end = dt_display
    return {
        "item_url": item_url,
        "title": title,
        "platform": "Satellite",
        "sensor": sensor,
        "date_start": date_start,
        "date_end": date_end,
        "provider": guess_provider_name(domain),
        "tags": "",
        "license_oam_default": OAM_DEFAULT_LICENSE,
        "stac_license_reference": item_data.get("license", ""),
        "image_source_url": tiff_url or "",
    }


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
            guessed = guess_tiff_url(stac_item_url, item_data)
            if guessed:
                return guessed, True
        return None, False
    except Exception as e:
        st.warning(f"Could not generate TIFF URL for {stac_item_url}: {e}")
        return None, False


def process_item_data(item_url: str, item_data: dict):
    tiff_url, is_guessed = generate_tiff_url(item_url, item_data)
    if tiff_url:
        tiff_links.append({"item_url": item_url, "tiff_url": tiff_url, "guessed": is_guessed})
    oam_items.append(extract_oam_metadata(item_url, item_data, tiff_url))


def process_item(item_url: str):
    item_data = fetch_json(item_url)
    if item_data is None:
        return
    process_item_data(item_url, item_data)


def crawl_stac(url, visited=None):
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
        if rel in ["item", "collection"]:
            if abs_href not in all_links:
                all_links.append(abs_href)
                if rel == "item":
                    process_item(abs_href)
            if rel == "collection":
                crawl_stac(abs_href, visited)


# MAIN EXECUTION
if root_url_input:
    real_url = extract_real_stac_url(root_url_input)
    if real_url:
        with st.spinner("Crawling STAC links and generating TIFF URLs..."):
            root_data = fetch_json(real_url)
            if root_data is not None and root_data.get("type") == "Feature":
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

                # NEW: Import components for copy buttons
                import streamlit.components.v1 as components

                if oam_items:
                    field_mappings = [
                        ("Item URL", "item_url"),
                        ("Title", "title"),
                        ("Platform", "platform"),
                        ("Sensor", "sensor"),
                        ("Date start", "date_start"),
                        ("Date end", "date_end"),
                        ("Provider", "provider"),
                        ("Tags", "tags"),
                        ("License (OAM default)", "license_oam_default"),
                        ("STAC license reference", "stac_license_reference"),
                        ("Image source URL", "image_source_url"),
                    ]

                    for idx, meta in enumerate(oam_items, 1):
                        with st.expander(f"{idx}. {meta['title'] or meta['item_url']}"):
                            for label, key in field_mappings:
                                value = meta.get(key, "")
                                cols = st.columns([2, 4, 1])
                                with cols[0]:
                                    st.markdown(f"**{label}**")
                                with cols[1]:
                                    st.markdown(value)
                                with cols[2]:
                                    # Render a tiny HTML component with a copy button
                                    # The button copies the value and changes text momentarily
                                    button_html = f"""
                                    <button style="background: #f0f2f6; border: 1px solid #d0d0d0; border-radius: 4px; padding: 4px 8px; cursor: pointer; font-size: 12px;"
                                            onclick="navigator.clipboard.writeText({json.dumps(value)}).then(() => {{ this.textContent='Copied!'; setTimeout(() => {{ this.textContent='Copy'; }}, 2000); }})">
                                        Copy
                                    </button>
                                    """
                                    components.html(button_html, height=30)
                            # License note
                            if meta.get("stac_license_reference"):
                                st.caption(
                                    f"STAC item's own license field: **{meta['stac_license_reference']}** — "
                                    f"the OAM License above defaults to {OAM_DEFAULT_LICENSE} regardless; "
                                    f"double-check this if the source license isn't CC-BY."
                                )

                    # CSV download (unchanged)
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
