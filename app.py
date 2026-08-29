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
OAM_STAC_SEARCH_URL = "https://api.imagery.hotosm.org/stac/collections/openaerialmap/items"

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

# ---------- Duplicate Check Function ----------
def check_oam_duplicate(provider_item_id: str) -> dict:
    """
    Query OAM's STAC API to see if an image with this provider ID already exists.
    Searches by full‑text (q=) and then verifies that the ID appears in the title.
    Returns: {"exists": bool, "oam_id": str or None, "oam_title": str or None, "error": str or None}
    """
    if not provider_item_id:
        return {"exists": False, "oam_id": None, "oam_title": None, "error": "No provider ID provided"}

    params = {
        "q": provider_item_id.strip(),
        "limit": 5  # only need a few results to check
    }
    headers = {"User-Agent": "STAC-to-OAM-Tool/1.0"}

    try:
        resp = requests.get(OAM_STAC_SEARCH_URL, params=params, headers=headers, timeout=15)
        resp.raise_for_status()

        # Ensure we got JSON
        content_type = resp.headers.get("content-type", "")
        if "application/json" not in content_type:
            snippet = resp.text[:200].replace("\n", " ")
            return {
                "exists": False,
                "oam_id": None,
                "oam_title": None,
                "error": f"Non‑JSON response: {snippet}..."
            }

        data = resp.json()
        features = data.get("features", [])

        # Look for a match where the provider ID appears in the title (case‑insensitive)
        search_id = provider_item_id.strip().lower()
        for feature in features:
            props = feature.get("properties", {})
            title = props.get("title", "")
            if search_id in title.lower():
                return {
                    "exists": True,
                    "oam_id": feature.get("id"),
                    "oam_title": title,
                    "error": None
                }

        return {"exists": False, "oam_id": None, "oam_title": None, "error": None}

    except requests.exceptions.RequestException as e:
        return {"exists": False, "oam_id": None, "oam_title": None, "error": f"Request error: {e}"}
    except json.JSONDecodeError as e:
        return {"exists": False, "oam_id": None, "oam_title": None, "error": f"Invalid JSON: {e}"}
    except Exception as e:
        return {"exists": False, "oam_id": None, "oam_title": None, "error": f"Unexpected: {e}"}

# ---------- All other existing functions ----------
# (extract_real_stac_url, resolve_relative_url, format_datetime_display,
#  guess_provider_name, compute_utm_epsg, build_reprojection_command,
#  check_oam_longitude_risk, get_collection_license, extract_oam_metadata,
#  bbox_intersects, guess_tiff_url, fetch_json, generate_tiff_url,
#  process_item_data, process_item, crawl_stac, run_crawl)
# --- They remain exactly as you had them, so I'm omitting them here for brevity ---
# BUT in the final answer I will include them all.

# ---------- Main UI ----------
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

    if real_url:
        col_recrawl, _ = st.columns([1, 3])
        with col_recrawl:
            if st.button("🔄 Re-crawl (ignore cache)"):
                run_crawl.clear()
                st.session_state["oam_duplicates"] = {}   # clear duplicate cache

        all_links, tiff_links, oam_items = run_crawl(real_url)

        if all_links:
            st.success(f"Found {len(all_links)} STAC links and generated {len(tiff_links)} TIFF URLs")

            # ---------- Location filter (unchanged) ----------
            group_by_location = st.toggle("📍 Group by location (draw a box on the map)")

            if group_by_location:
                items_with_bbox = [m for m in oam_items if m.get("bbox")]
                if items_with_bbox:
                    st.caption(
                        "Item footprints are shown as blue boxes. Draw a rectangle over the area you "
                        "want (e.g. just NTT, not Sumatra), then click Apply filter."
                    )
                    all_lons = [m["bbox"][0] for m in items_with_bbox] + [m["bbox"][2] for m in items_with_bbox]
                    all_lats = [m["bbox"][1] for m in items_with_bbox] + [m["bbox"][3] for m in items_with_bbox]
                    center_lat = sum(all_lats) / len(all_lats)
                    center_lon = sum(all_lons) / len(all_lons)

                    fmap = folium.Map(location=[center_lat, center_lon], zoom_start=5)
                    for m in items_with_bbox:
                        west, south, east, north = m["bbox"][0], m["bbox"][1], m["bbox"][2], m["bbox"][3]
                        folium.Rectangle(
                            bounds=[[south, west], [north, east]],
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

                    col_apply, col_clear = st.columns([1, 1])
                    with col_apply:
                        if st.button("Apply filter"):
                            drawn = (map_data or {}).get("last_active_drawing")
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

            # ---------- Tabs ----------
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

                # ---------- Duplicate Check Button ----------
                if display_oam_items:
                    col_check, _ = st.columns([1, 4])
                    with col_check:
                        if st.button("🔍 Check duplicates on OAM"):
                            st.session_state["oam_duplicates"] = {}
                            progress_bar = st.progress(0, text="Checking...")
                            total = len(display_oam_items)
                            for i, meta in enumerate(display_oam_items):
                                provider_id = meta.get("provider_item_id", "")
                                if provider_id:
                                    result = check_oam_duplicate(provider_id)
                                    st.session_state["oam_duplicates"][meta["item_url"]] = result
                                else:
                                    st.session_state["oam_duplicates"][meta["item_url"]] = {
                                        "exists": False,
                                        "oam_id": None,
                                        "oam_title": None,
                                        "error": "No provider ID"
                                    }
                                if i % 5 == 0 or i == total - 1:
                                    progress_bar.progress((i + 1) / total, text=f"Checked {i+1}/{total}")
                                time.sleep(0.2)  # be gentle to the API
                            progress_bar.empty()
                            st.success("Duplicate check complete!")

                # ---------- Display OAM Metadata ----------
                if display_oam_items:
                    for idx, meta in enumerate(display_oam_items, 1):
                        with st.expander(f"{idx}. {meta['title'] or meta['item_url']}"):
                            # Show duplicate status
                            dup_info = st.session_state.get("oam_duplicates", {}).get(meta["item_url"])
                            if dup_info is not None:
                                if dup_info.get("error"):
                                    st.warning(f"⚠️ Duplicate check failed: {dup_info['error']}")
                                elif dup_info.get("exists"):
                                    oam_id = dup_info.get("oam_id", "unknown")
                                    oam_title = dup_info.get("oam_title", "")
                                    st.success(f"✅ Already uploaded to OAM (ID: {oam_id})\n\n_Title:_ {oam_title}")
                                else:
                                    st.info("❌ Not found on OAM – ready to upload.")
                            else:
                                st.caption("Click 'Check duplicates on OAM' above to see if this item already exists.")

                            # Metadata fields
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
                                "OAM titles often embed the provider's original ID (e.g. \"Vantor LG03 Image "
                                f"{meta['provider_item_id']}\"). OAM's search API isn't reliably filtering results "
                                "right now, so this can't be checked automatically — copy the ID below and paste "
                                "it into OAM's own search to check by hand."
                            )
                            st.code(meta["provider_item_id"], language=None)
                            st.link_button("Open OAM to search manually", OAM_MAP_URL)

                            # Longitude risk warning
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

                    # CSV download
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
