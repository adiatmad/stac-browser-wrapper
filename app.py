import streamlit as st
import requests
from urllib.parse import urlparse, unquote, urljoin


st.title("Recursive STAC Links Extractor (STAC Browser Friendly)")

root_url_input = st.text_input("Enter STAC Browser URL")

all_links = []


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

            if rel == "collection":
                crawl_stac(abs_href, visited)


# MAIN EXECUTION
if root_url_input:
    real_url = extract_real_stac_url(root_url_input)

    if real_url:
        with st.spinner("Crawling STAC links..."):
            crawl_stac(real_url)

        if all_links:
            st.success(f"Found {len(all_links)} links:")
            for idx, link in enumerate(all_links, 1):
                st.markdown(f"{idx}. [{link}]({link})")
        else:
            st.info("No item or collection links found.")
