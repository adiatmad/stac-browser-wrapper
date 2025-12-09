def extract_real_stac_url(browser_url: str) -> str:
    """
    Extract the real JSON URL from a STAC Browser link and ensure:
    - Correct unquoting
    - Correctly handles missing 'https://'
    - Removes optional ?language=en noise
    """

    if "#/external/" not in browser_url:
        st.error("This does not look like a STAC Browser URL with /external/.")
        return None

    # Extract text after "#/external/"
    raw_url = browser_url.split("#/external/")[-1].strip()

    # Decode URL encoding
    real_url = unquote(raw_url)

    # Remove STAC-Browser suffix like ?.language=en
    if "?" in real_url:
        real_url = real_url.split("?")[0]

    # Add https:// if missing
    parsed = urlparse(real_url)
    if not parsed.scheme:
        real_url = "https://" + real_url

    # Warn if not JSON
    if not real_url.endswith(".json"):
        st.warning("Extracted URL does not end with .json — may not be valid STAC.")

    return real_url
