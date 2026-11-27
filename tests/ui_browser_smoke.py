from __future__ import annotations

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


def assert_no_horizontal_overflow(page, label: str) -> None:
    dimensions = page.evaluate(
        """() => ({
            viewport: document.documentElement.clientWidth,
            document: document.documentElement.scrollWidth,
            body: document.body.scrollWidth
        })"""
    )
    if max(dimensions["document"], dimensions["body"]) > dimensions["viewport"] + 1:
        raise AssertionError(f"{label}: horizontal overflow: {dimensions}")


def main() -> None:
    ARTIFACTS.mkdir(exist_ok=True)
    log_path = ROOT / "streamlit-ui-smoke.log"
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            [
                sys.executable, "-m", "streamlit", "run", "app.py",
                "--server.headless=true", "--server.address=127.0.0.1",
                "--server.port=8501", "--browser.gatherUsageStats=false",
            ],
            cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, text=True,
        )
        try:
            wait_for_streamlit(process, log_path)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                page = browser.new_page(
                    viewport={"width": 1440, "height": 1000}, reduced_motion="reduce"
                )
                page.goto(BASE_URL, wait_until="domcontentloaded", timeout=60_000)
                page.get_by_role("heading", name="STAC Imagery Workbench").wait_for()
                page.get_by_role("heading", name="Choose an imagery source").wait_for()
                wait_for_streamlit_idle(page)
                page.screenshot(path=str(ARTIFACTS / "workbench-discover-desktop.png"), full_page=True)

                page.get_by_role("tab", name="Local processing").click()
                page.get_by_role("heading", name="Local GeoTIFF compression").wait_for()
                # Hosted CI has no GDAL install; local processing must fail gracefully.
                expect(page.get_by_text("GDAL command-line tools were not found", exact=False)).to_be_visible()
                page.screenshot(path=str(ARTIFACTS / "workbench-local-desktop.png"), full_page=True)

                page.get_by_role("tab", name="Discover & map").click()
                page.get_by_role("heading", name="Choose an imagery source").wait_for()
                wait_for_streamlit_idle(page)
                page.set_viewport_size({"width": 390, "height": 844})
                assert_no_horizontal_overflow(page, "Discover at 390px")
                page.screenshot(path=str(ARTIFACTS / "workbench-discover-mobile.png"), full_page=True)

                page.get_by_text("Public S3 bucket folder", exact=True).click()
                wait_for_streamlit_idle(page)
                expect(page.get_by_role("textbox", name="S3 bucket-browser URL")).to_be_visible()
                expect(page.get_by_role("textbox", name="Data Catalog URL:")).to_have_count(0)
                assert_no_horizontal_overflow(page, "S3 source selector at 390px")
                page.screenshot(path=str(ARTIFACTS / "workbench-s3-mobile.png"), full_page=True)

                page.get_by_text("STAC catalog / item", exact=True).click()
                wait_for_streamlit_idle(page)
                expect(page.get_by_role("textbox", name="Data Catalog URL:")).to_be_visible()

                page.get_by_role("tab", name="Local processing").click()
                page.get_by_role("heading", name="Local GeoTIFF compression").wait_for()
                assert_no_horizontal_overflow(page, "Local processing at 390px")
                page.screenshot(path=str(ARTIFACTS / "workbench-local-mobile.png"), full_page=True)
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
