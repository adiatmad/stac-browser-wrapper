import streamlit as st
import requests
from urllib.parse import urlparse, unquote, urljoin, urlparse
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


def resolve_relative_url(base_url: str, relative_url: str) -> str:
    """Convert relative URL to absolute URL."""
    if relative_url.startswith(('http://', 'https://')):
        return relative_url
    elif relative_url.startswith('./'):
        # Remove leading ./
        relative_url = relative_url[2:]
    
    # Use urljoin to create absolute URL
    return urljoin(base_url, relative_url)


def generate_tiff_url(stac_item_url: str) -> str:
    """Generate complete TIFF URL from STAC item URL or item data."""
    try:
        # Try to fetch the STAC item to get metadata
        response = requests.get(stac_item_url, timeout=10)
        if response.status_code == 200:
            item_data = response.json()
            
            # Check if this is a STAC Item
            if item_data.get("type") == "Feature" and item_data.get("stac_version"):
                # Try to extract assets
                assets = item_data.get("assets", {})
                
                # Look for visual asset first
                visual_assets = []
                for asset_name, asset_info in assets.items():
                    href = asset_info.get("href", "")
                    title = asset_info.get("title", "")
                    description = asset_info.get("description", "")
                    
                    # Check if it's a TIFF file
                    if href and href.endswith((".tif", ".tiff")):
                        # Make URL absolute
                        absolute_href = resolve_relative_url(stac_item_url, href)
                        
                        # Prioritize visual assets
                        if any(keyword in asset_name.lower() for keyword in ["visual", "rgb", "natural"]):
                            visual_assets.insert(0, absolute_href)  # Add to beginning
                        else:
                            visual_assets.append(absolute_href)
                
                # Return the first visual asset if found, otherwise first TIFF
                if visual_assets:
                    return visual_assets[0]
                
                # If no TIFF assets in assets, try to construct from item properties
                properties = item_data.get("properties", {})
                
                # Check for common Maxar properties
                event_name = None
                grid = None
                tile = None
                date = None
                image_id = None
                
                # Try to extract from properties
                if "event" in properties:
                    event_name = properties.get("event")
                if "grid" in properties:
                    grid = properties.get("grid")
                if "tile" in properties:
                    tile = properties.get("tile")
                if "datetime" in properties:
                    date_str = properties.get("datetime")
                    if date_str:
                        date = date_str.split("T")[0]  # Get just the date part
                if "id" in item_data:
                    image_id = item_data.get("id")
                
                # Also try to extract from the URL itself as fallback
                parsed_url = urlparse(stac_item_url)
                path_parts = parsed_url.path.split('/')
                
                # Look for event name pattern
                for i, part in enumerate(path_parts):
                    if "events" in part and i + 1 < len(path_parts):
                        event_name = path_parts[i + 1]
                    if part.isdigit() and len(part) == 2:  # Grid like "44"
                        grid = part
                    if part.isdigit() and len(part) == 12:  # Tile like "033313123002"
                        tile = part
                    if re.match(r"\d{4}-\d{2}-\d{2}", part):  # Date pattern
                        date = part
                
                # If we have enough info, construct the URL
                if event_name and grid and tile and date:
                    # Try to get image ID from the STAC item ID
                    if image_id:
                        # Check if image_id looks like a Maxar image ID
                        if len(image_id) >= 16 and any(c.isalpha() for c in image_id):
                            base_image_id = image_id[:16]  # Use first 16 chars
                        else:
                            base_image_id = "10400100AFC26500"  # Default
                    else:
                        base_image_id = "10400100AFC26500"  # Default
                    
                    return f"https://maxar-opendata.s3.amazonaws.com/events/{event_name}/ard/{grid}/{tile}/{date}/{base_image_id}-visual.tif"
        
        # If all else fails, return None
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
                        # Ensure it's a complete URL
                        if not tiff_url.startswith(('http://', 'https://')):
                            tiff_url = resolve_relative_url(abs_href, tiff_url)
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
            st.success(f"Found {len(all_links)} STAC links and generated {len(tiff_links)} TIFF URLs")
            
            # Display tabs for different views
            tab1, tab2 = st.tabs(["STAC Links", "TIFF URLs"])
            
            with tab1:
                st.subheader("Original STAC Links")
                for idx, link in enumerate(all_links, 1):
                    st.markdown(f"{idx}. [{link}]({link})")
            
            with tab2:
                st.subheader("Complete TIFF URLs")
                if tiff_links:
                    # Filter out any incomplete URLs (those starting with ./ or relative)
                    complete_tiff_links = []
                    for tiff_url in tiff_links:
                        if tiff_url.startswith(('http://', 'https://')):
                            complete_tiff_links.append(tiff_url)
                        else:
                            # Try to make it complete
                            complete_url = f"https://maxar-opendata.s3.amazonaws.com/{tiff_url.lstrip('./')}"
                            complete_tiff_links.append(complete_url)
                    
                    for idx, tiff_url in enumerate(complete_tiff_links, 1):
                        # Display full URL
                        st.code(tiff_url, language=None)
                        
                        # Also show as clickable link
                        st.markdown(f"{idx}. [{tiff_url}]({tiff_url})")
                    
                    # Add download option for TIFF URLs
                    tiff_text = "\n".join(complete_tiff_links)
                    st.download_button(
                        label="Download Complete TIFF URLs",
                        data=tiff_text,
                        file_name="complete_tiff_urls.txt",
                        mime="text/plain"
                    )
                else:
                    st.info("No TIFF URLs could be generated.")
                    
        else:
            st.info("No item or collection links found.")
