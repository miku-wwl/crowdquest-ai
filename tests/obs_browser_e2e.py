"""Actual Chromium + synthetic OBS. No installed OBS, Twitch or AIG effects."""

import json
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import expect, sync_playwright

from tests.obs_support import ADMIN_PASSWORD
from tests.process_helpers import start_fixture, stop_fixture


def main():
    with tempfile.TemporaryDirectory(prefix="crowdquest-obs-chromium-") as state:
        directory = Path(state)
        process, origin = start_fixture(directory, obs_admin=True)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context(viewport={"width": 1280, "height": 900})
                context.route(
                    "**/*",
                    lambda route: (
                        route.continue_()
                        if urlsplit(route.request.url).netloc == urlsplit(origin).netloc
                        else route.abort()
                    ),
                )
                page = context.new_page()
                posts, errors = [], []
                page.on(
                    "request",
                    lambda request: posts.append(request.url) if request.method == "POST" else None,
                )
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(origin + "/obs-admin")
                expect(page.get_by_role("heading", name="Local Admin sign-in")).to_be_visible()
                page.get_by_label("Admin passphrase").fill(ADMIN_PASSWORD)
                page.get_by_role("button", name="Sign in locally").click()
                expect(page.get_by_text("32.2.2", exact=True)).to_be_visible()
                expect(page.get_by_text("Stopped", exact=True)).to_be_visible()
                assert len(posts) == 1  # login is the only mutation so far
                page.get_by_label("Existing scene").select_option("Other existing scene")
                page.get_by_role("button", name="Switch scene").click()
                expect(page.locator("dd").filter(has_text="Other existing scene")).to_be_visible()
                page.get_by_role("button", name="Refresh CrowdQuest overlay").click()
                expect(page.get_by_role("status")).to_contain_text("acknowledged the refresh")
                page.get_by_role("button", name="Start Recording").dblclick()
                expect(page.get_by_role("button", name="Stop Recording")).to_be_enabled()
                expect(page.get_by_text("Recording", exact=True)).to_be_visible()
                assert sum(url.endswith("/record/start") for url in posts) == 1
                page.get_by_role("button", name="Stop Recording").click()
                expect(page.get_by_text("C:/synthetic-recordings/test.mkv")).to_be_visible()
                expect(page.get_by_text("Stopped", exact=True)).to_be_visible()
                assert sum(url.endswith("/record/stop") for url in posts) == 1
                page.reload()
                expect(page.get_by_text("Stopped", exact=True)).to_be_visible()
                assert sum(url.endswith("/record/start") for url in posts) == 1
                captures = Path(".artifacts/phase45")
                captures.mkdir(parents=True, exist_ok=True)
                page.screenshot(
                    path=str(captures / "synthetic-obs-admin-desktop.png"), full_page=True
                )
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                page.screenshot(
                    path=str(captures / "synthetic-obs-admin-mobile.png"), full_page=True
                )
                assert not page.get_by_role("button", name="StartStream").count()
                assert not errors, errors
                assert not list(
                    directory.glob("*.sqlite3")
                )  # OBS-only mode has no application stores
                page.get_by_role("button", name="Sign out").click()
                expect(page.get_by_role("heading", name="Local Admin sign-in")).to_be_visible()
                browser.close()
                print(
                    json.dumps(
                        {
                            "status": "PASS",
                            "evidence": "SYNTHETIC_TEST",
                            "browser": "actual Chromium",
                            "start_commands": 1,
                            "stop_commands": 1,
                            "real_obs": "NOT_RUN",
                        }
                    )
                )
        finally:
            stop_fixture(process, directory)


if __name__ == "__main__":
    main()
