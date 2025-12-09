import streamlit as st
import requests
from urllib.parse import urlparse, unquote, urljoin
import re
import json


st.title("Recursive STAC Links Extractor & TIFF URL Generator")

root_url_input = st.text_input("Enter STAC Browser URL")

all_links = []
tiff_links = []


def extract_real_stac_url(browser_url: str) -> str:
    """Extract and normalize real STAC JSON URL from STAC Browser URL."""
    if "#/external/" not in browser_url:
        st.error("This does not look like a STAC Browser URL with /external/")
        return None

    raw_url = browser_url.split("#/external/")[-1].strip()
    real_url = unquote(raw_url)

    if "?" in real_url:
        real_url = real_url.split("?")[0]

    parsed = urlparse(real_url)
    if not parsed.scheme:
        real_url = "https://" + real_url

    if not real_url.endswith(".json"):
        st.warning("Extracted URL does not end with .json — may not be a valid STAC JSON")

    return real_url


def generate_tiff_url(stac_item_url: str) -> str:
    """Generate TIFF URL from STAC item URL or item data."""
    try:
        # Try to fetch the STAC item to get metadata
        response = requests.get(stac_item_url, timeout=10)
        if response.status_code == 200:
            item_data = response.json()
            
            # Check if this is a STAC Item
            if item_data.get("type") == "Feature" and item_data.get("stac_version"):
                # Try to extract assets
                assets = item_data.get("assets", {})
                
                # Look for visual/visual.tif asset
                for asset_name, asset_info in assets.items():
                    href = asset_info.get("href", "")
                    if "visual" in asset_name.lower() and href.endswith(".tif"):
                        return href
                    
                    # Also check for common patterns
                    if href.endswith((".tif", ".tiff")) and "visual" in href.lower():
                        return href
                
                # If no visual asset found, return the first TIFF asset
                for asset_name, asset_info in assets.items():
                    href = asset_info.get("href", "")
                    if href.endswith((".tif", ".tiff")):
                        return href
            
            # If we can't get item data or no assets, try to parse from URL
            parsed_url = urlparse(stac_item_url)
            path_parts = parsed_url.path.split('/')
            
            # Look for patterns in the URL that match Maxar structure
            for i, part in enumerate(path_parts):
                if part.endswith('.json'):
                    # This might be a STAC item ID
                    item_id = part.replace('.json', '')
                    
                    # Try to extract components from item_id or URL
                    # Example: 44/033313123002/2025-12-01/10400100AFC26500
                    # Assuming the URL contains the necessary path components
                    
                    # Look for event name (e.g., Cyclone-Ditwah-Sri-Lanka-Nov-2025)
                    event_pattern = r"events/([^/]+)"
                    event_match = re.search(event_pattern, stac_item_url)
                    
                    if event_match:
                        event_name = event_match.group(1)
                        
                        # Try to extract the tile/grid path components
                        # Look for patterns like 44/033313123002
                        tile_pattern = r"(\d+)/(\d+)"
                        tile_match = re.search(tile_pattern, stac_item_url)
                        
                        if tile_match:
                            grid = tile_match.group(1)
                            tile = tile_match.group(2)
                            
                            # Try to extract date
                            date_pattern = r"(\d{4}-\d{2}-\d{2})"
                            date_match = re.search(date_pattern, stac_item_url)
                            
                            if date_match:
                                date = date_match.group(1)
                                
                                # Construct the URL
                                return f"https://maxar-opendata.s3.amazonaws.com/events/{event_name}/ard/{grid}/{tile}/{date}/10400100AFC26500-visual.tif"
        
        # Fallback: If we can't parse the URL, return a placeholder or the original
        return None
        
    except Exception as e:
        st.warning(f"Could not generate TIFF URL for {stac_item_url}: {e}")
        return None


def crawl_stac(url, visited=None):
    """Recursive STAC crawler for links with rel=item or rel=collection."""
    if visited is None:
        visited = set()

    if url in visited:
        return

    visited.add(url)

    try:
        resp = requests.get(url)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        st.warning(f"Failed to fetch {url}: {e}")
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
                
                # Generate TIFF URL for item links
                if rel == "item":
                    tiff_url = generate_tiff_url(abs_href)
                    if tiff_url:
                        tiff_links.append(tiff_url)

            if rel == "collection":
                crawl_stac(abs_href, visited)


# MAIN EXECUTION
if root_url_input:
    real_url = extract_real_stac_url(root_url_input)

    if real_url:
        with st.spinner("Crawling STAC links and generating TIFF URLs..."):
            crawl_stac(real_url)

        if all_links:
            st.success(f"Found {len(all_links)} STAC links:")
            
            # Display tabs for different views
            tab1, tab2 = st.tabs(["STAC Links", "TIFF URLs"])
            
            with tab1:
                st.subheader("Original STAC Links")
                for idx, link in enumerate(all_links, 1):
                    st.markdown(f"{idx}. [{link}]({link})")
            
            with tab2:
                st.subheader("Generated TIFF URLs")
                if tiff_links:
                    for idx, tiff_url in enumerate(tiff_links, 1):
                        st.markdown(f"{idx}. [{tiff_url}]({tiff_url})")
                    
                    # Add download option for TIFF URLs
                    tiff_text = "\n".join(tiff_links)
                    st.download_button(
                        label="Download TIFF URLs as text file",
                        data=tiff_text,
                        file_name="tiff_urls.txt",
                        mime="text/plain"
                    )
                else:
                    st.info("No TIFF URLs could be generated. You may need to customize the URL pattern.")
                    
        else:
            st.info("No item or collection links found.")
