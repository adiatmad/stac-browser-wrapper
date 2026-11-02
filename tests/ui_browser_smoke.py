from __future__ import annotations

import subprocess
import sys
import time
from pathlib import Path
from urllib.error import URLError
from urllib.request import urlopen

from playwright.sync_api import sync_playwright


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

                local_tab = page.get_by_role("tab", name="Local preparation")
                local_tab.click()
                page.get_by_role("heading", name="OAM Drone Preflight").wait_for()
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

                page.set_viewport_size({"width": 390, "height": 844})
                page.wait_for_timeout(300)
                assert_no_horizontal_overflow(page, "Discover & map at 390px")
                page.screenshot(
                    path=str(ARTIFACTS / "workbench-discover-mobile.png"),
                    full_page=True,
                )

                page.get_by_role("tab", name="Local preparation").click()
                page.get_by_role("heading", name="OAM Drone Preflight").wait_for()
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
