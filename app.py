import streamlit as st
import requests
from urllib.parse import urljoin, urlparse

st.title("Recursive STAC Links Extractor (STAC Browser Friendly)")

# Input for root STAC Browser URL

root_url_input = st.text_input("Enter STAC Browser URL or direct JSON URL")

# To store all found links

all_links = []

def normalize_stac_url(url):
"""Convert STAC Browser URL to direct JSON URL if needed."""
# Remove hash fragment
url = url.split('#')[0]
# If URL ends with /, remove it
url = url.rstrip('/')
# If URL ends with .json, keep as is; else, assume user pasted browser folder URL
if not url.endswith('.json'):
st.warning("Please ensure the URL points to a JSON file (item or collection).")
return url

def crawl_stac(url, visited=set()):
"""Recursively fetch STAC JSON and extract item/collection links."""
if url in visited:
return
visited.add(url)

```
try:
    resp = requests.get(url)
    resp.raise_for_status()
    data = resp.json()
except Exception as e:
    st.warning(f"Failed to fetch {url}: {e}")
    return

# Extract item/collection links
links = data.get("links", [])
for link in links:
    href = link.get("href")
    rel = link.get("rel")
    if href and rel in ["item", "collection"]:
        abs_href = urljoin(url, href)
        if abs_href not in all_links:
            all_links.append(abs_href)
        if rel == "collection":
            crawl_stac(abs_href, visited)
```

if root_url_input:
root_url = normalize_stac_url(root_url_input)
with st.spinner("Crawling STAC links..."):
crawl_stac(root_url)

```
if all_links:
    st.success(f"Found {len(all_links)} links!")
    # Display clickable links
    for idx, link in enumerate(all_links, 1):
        st.markdown(f"{idx}. [{link}]({link})")
    
    # Optional: download links as CSV
    import pandas as pd
    df = pd.DataFrame({"Link Number": list(range(1, len(all_links)+1)), "URL": all_links})
    csv = df.to_csv(index=False).encode("utf-8")
    st.download_button("Download CSV", csv, "stac_links.csv", "text/csv")
else:
    st.info("No item or collection links found.")
```
