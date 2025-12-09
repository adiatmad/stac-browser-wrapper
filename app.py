import streamlit as st
import requests
from urllib.parse import urlparse, unquote
import re
from urllib.parse import urljoin
import pandas as pd

st.title("CATID Extractor from STAC Collections (Improved & Robust)")

# -----------------------------
# CONSTANTS
# -----------------------------

# CATID pattern for Maxar (strict)
CATID_REGEX = re.compile(r"10[2345][0-9A-F]{14}")

# Allowed STAC link relationships for traversal
VALID_RELS = {"item", "collection", "child", "self"}

# -----------------------------
# Utility: Extract remote JSON URL from STAC Browser URL
# -----------------------------
def extract_real_stac_url(browser_url: str) -> str:
    """
    Extract the real JSON URL from a STAC Browser URL such as:
    https://radiantearth.github.io/stac-browser/#/external/<REMOTE_URL>

    Returns the direct JSON URL.
    """
    if "#/external/" not in browser_url:
        st.error("This does not look like a STAC Browser URL with /external/.")
        return None

    # Extract everything after "#/external/"
    real_url = browser_url.split("#/external/")[-1]
    real_url = unquote(real_url).strip()

    if not real_url.endswith(".json"):
        st.warning("Extracted URL does not end with .json — may not be valid STAC.")
    return real_url


# -----------------------------
# Recursive crawler
# -----------------------------
def crawl_stac(url: str, visited: set, catid_links: set):
    """
    Crawl a STAC JSON URL, extract CATID-containing links, and traverse rel links.
    """
    if url in visited:
        return
    visited.add(url)

    # Fetch JSON
    try:
        resp = requests.get(url, timeout=15)
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        st.warning(f"Failed to fetch {url}: {e}")
        return

    # Check if this JSON represents a CATID item/collection
    stac_id = data.get("id", "")
    if CATID_REGEX.fullmatch(stac_id):
        catid_links.add(url)

    # Traverse STAC links
    for link in data.get("links", []):
        href = link.get("href")
        rel = link.get("rel")

        if not href or rel not in VALID_RELS:
            continue

        # Absolute URL resolution
        next_url = urljoin(url, href)

        # Only crawl JSONs
        if next_url.endswith(".json"):
            crawl_stac(next_url, visited, catid_links)


# -----------------------------
# Streamlit UI
# -----------------------------
st.subheader("Input STAC Browser Root URL")

root_input = st.text_input(
    "Paste STAC Browser URL (must contain '#/external/...')"
)

if root_input:
    real_url = extract_real_stac_url(root_input)

    if real_url:
        st.write(f"**Extracted JSON URL:** `{real_url}`")

        if st.button("Start Crawling"):
            with st.spinner("Crawling STAC recursively…"):

                visited = set()
                catid_links = set()

                crawl_stac(real_url, visited, catid_links)

            # -----------------------------
            # Output results
            # -----------------------------

            if catid_links:
                st.success(f"Found **{len(catid_links)}** CATID JSON links!")

                sorted_links = sorted(catid_links)
                for i, link in enumerate(sorted_links, 1):
                    st.markdown(f"{i}. [{link}]({link})")

                # Prepare downloadable CSV
                df = pd.DataFrame({"CATID JSON URL": sorted_links})
                csv = df.to_csv(index=False).encode("utf-8")

                st.download_button(
                    "Download CATID Links CSV",
                    csv,
                    "catid_links.csv",
                    "text/csv"
                )
            else:
                st.info("No CATID JSON links detected in this catalog.")
