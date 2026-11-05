from __future__ import annotations

import re
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import expect, sync_playwright


ROOT = Path(__file__).resolve().parents[1]
BASE_URL = "http://127.0.0.1:8501"
ARTIFACTS = ROOT / "artifacts"


def wait_for_streamlit(process: subprocess.Popen, log_path: Path, timeout: int = 60) -> None:
    deadline = time.monotonic() + timeout
    health_url = f"{BASE_URL}/_stcore/health"
    while time.monotonic() < deadline:
        if process.poll() is not None:
            raise RuntimeError(
                f"Streamlit exited with {process.returncode}. Log:\n"
                + log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
            )
        try:
            with urlopen(health_url, timeout=2) as response:
                if response.status == 200:
                    return
        except (OSError, URLError):
            time.sleep(0.5)
    raise TimeoutError(
        f"Streamlit did not become healthy. Log:\n"
        + log_path.read_text(encoding="utf-8", errors="replace")[-8000:]
    )


def wait_for_streamlit_idle(page) -> None:
    stop_button = page.get_by_role("button", name="Stop")
    if stop_button.count():
        stop_button.wait_for(state="detached", timeout=60_000)



def exercise_stac_discovery(page) -> None:
    page.locator("summary").filter(has_text="Find a public STAC catalog").click()
    page.get_by_role("button", name="Load public catalog directory").click()
    catalog_search = page.get_by_role("textbox", name="Search catalog name or description")
    catalog_search.wait_for(timeout=60_000)
    catalog_search.fill("OpenAerialMap Example")

    catalog_select = page.get_by_role("combobox", name="Public catalogs")
    catalog_select.click()
    page.get_by_role("option", name="OpenAerialMap Example").click()
    page.get_by_role("button", name="Use selected catalog").click()
    wait_for_streamlit_idle(page)

    catalog_url = page.get_by_role("textbox", name="Data Catalog URL:")
    expect(catalog_url).to_have_value(
        "https://raw.githubusercontent.com/m-mohr/oam-example/main/catalog.json",
        timeout=30_000,
    )

    page.get_by_role("tab", name="OpenAerialMap").click()
    page.locator("summary").filter(has_text="Grytdalen Tjern").click()
    expect(page.get_by_text("STAC thumbnail asset", exact=True)).to_have_count(
        2, timeout=30_000
    )

    api_search_toggle = page.get_by_role(
        "checkbox",
        name="Search this STAC API with filters instead of browsing catalog links",
    )
    api_search_toggle.scroll_into_view_if_needed()
    page.mouse.wheel(0, -350)
    api_search_toggle.check()
    page.get_by_text("does not advertise an HTTPS GET search link", exact=False).wait_for(
        timeout=30_000
    )

    catalog_url.fill("https://earth-search.aws.element84.com/v1/")
    page.get_by_text("STAC Item Search endpoint:", exact=False).wait_for(timeout=30_000)

    bbox = page.get_by_role("textbox", name="Area bbox (optional, WGS84)")
    date_range = page.get_by_role("textbox", name="Date or date interval (optional)")
    collections = page.get_by_role("textbox", name="Collection IDs (optional, comma-separated)")
    limit = page.get_by_role("spinbutton", name="Maximum items per page")

    bbox.fill("not-a-bbox")
    date_range.fill("2099-01-01/2099-01-02")
    collections.fill("sentinel-2-l2a")
    limit.fill("1")
    page.get_by_role("button", name="Search STAC API").click()
    page.get_by_text("BBox must contain four comma-separated numbers", exact=False).wait_for(
        timeout=15_000
    )

    bbox.fill("106.6,-6.5,107.1,-6.0")
    page.get_by_role("button", name="Search STAC API").click()
    wait_for_streamlit_idle(page)
    page.get_by_text("Search URL:", exact=False).wait_for(timeout=30_000)
    page.get_by_text("No STAC imagery links were found", exact=False).wait_for(
        timeout=15_000
    )
    server_log = (ROOT / "streamlit-ui-smoke.log").read_text(encoding="utf-8")
    assert "Failed to fetch https://earth-search.aws.element84.com/v1/search" not in server_log


def assert_no_horizontal_overflow(page, label: str) -> None:
    dimensions = page.evaluate(
        """() => ({
            viewport: document.documentElement.clientWidth,
            document: document.documentElement.scrollWidth,
            body: document.body.scrollWidth
        })"""
    )
    widest = max(dimensions["document"], dimensions["body"])
    if widest > dimensions["viewport"] + 1:
        raise AssertionError(f"{label}: horizontal overflow: {dimensions}")


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    log_path = ROOT / "streamlit-ui-smoke.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.headless=true",
                "--server.address=127.0.0.1",
                "--server.port=8501",
                "--browser.gatherUsageStats=false",
            ],
            cwd=ROOT,
            stdout=log,
            stderr=subprocess.STDOUT,
            text=True,
        )
        try:
            wait_for_streamlit(process, log_path)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(
                    viewport={"width": 1440, "height": 1000},
                    reduced_motion="reduce",
                )
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60_000)
                page.get_by_role("heading", name="STAC Imagery Workbench").wait_for()
                page.get_by_role("heading", name="Choose an imagery source").wait_for()
                wait_for_streamlit_idle(page)
                page.screenshot(
                    path=str(ARTIFACTS / "workbench-discover-desktop.png"),
                    full_page=True,
                )
                exercise_stac_discovery(page)

                local_tab = page.get_by_role("tab", name="Local preparation")
                local_tab.click()
                page.get_by_role("heading", name="Local geospatial imagery preparation").wait_for()
                assert page.get_by_role(
                    "heading", name="Choose an imagery source"
                ).count() == 0
                page.screenshot(
                    path=str(ARTIFACTS / "workbench-local-desktop.png"),
                    full_page=True,
                )

                discover_tab = page.get_by_role("tab", name="Discover & map")
                discover_tab.focus()
                discover_tab.press("Enter")
                page.get_by_role("heading", name="Choose an imagery source").wait_for()
                page.get_by_role("heading", name="Local geospatial imagery preparation").wait_for(state="detached")
                wait_for_streamlit_idle(page)

                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(300)
                assert_no_horizontal_overflow(page, "Discover & map at 390px")
                page.screenshot(
                    path=str(ARTIFACTS / "workbench-discover-mobile.png"),
                    full_page=True,
                )

                page.get_by_role("tab", name="Local preparation").click()
                page.get_by_role("heading", name="Local geospatial imagery preparation").wait_for()
                page.wait_for_timeout(300)
                assert_no_horizontal_overflow(page, "Local preparation at 390px")
                page.screenshot(
                    path=str(ARTIFACTS / "workbench-local-mobile.png"),
                    full_page=True,
                )
                browser.close()
        finally:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    main()
