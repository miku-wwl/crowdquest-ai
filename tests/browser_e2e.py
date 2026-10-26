"""Actual Chromium with synthetic Twitch/OAuth fixtures. Never claim live Twitch/OBS."""

import argparse
import tempfile
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from playwright.sync_api import expect, sync_playwright

from tests.process_helpers import start_fixture, stop_fixture


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="crowdquest-synthetic-") as state:
        server, origin = start_fixture(Path(state))
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context(viewport={"width": 1440, "height": 1000})

                def isolated_transport(route):
                    url = urlsplit(route.request.url)
                    if url.netloc != urlsplit(origin).netloc:
                        route.abort()  # No external browser request is permitted in this fixture.
                    elif url.path == "/auth/twitch/start":
                        # Exercise the real state/cookie creation, replace only external consent.
                        response = route.fetch(max_redirects=0)
                        target = urlsplit(response.headers["location"])
                        assert target.netloc == "id.twitch.tv"
                        query = parse_qs(target.query)
                        assert query["scope"] == ["user:read:chat"]
                        route.fulfill(
                            status=303,
                            headers={
                                "Set-Cookie": response.headers["set-cookie"],
                                "Location": origin
                                + "/auth/twitch/callback?"
                                + urlencode({"state": query["state"][0], "code": "synthetic-code"}),
                            },
                        )
                    else:
                        route.continue_()

                context.route("**/*", isolated_transport)
                dashboard = context.new_page()
                dashboard.goto(origin)
                dashboard.get_by_role("link", name="Connect Twitch →").click()
                expect(dashboard.get_by_text("@fixture_owner")).to_be_visible()
                expect(dashboard.get_by_role("radio")).to_have_count(2)
                expect(dashboard.locator(".candidate img")).to_have_count(0)
                overlay = context.new_page()
                overlay.goto(origin + "/overlay")
                expect(overlay.get_by_text("Pair this Browser Source")).to_be_visible()
                code = overlay.locator(".pair-code").inner_text()
                dashboard.get_by_role("button", name=f"Pair overlay {code}").click()
                expect(overlay.get_by_text("Ready for your next idea")).to_be_visible()
                dashboard.get_by_role("radio").filter(has_text="onerror").click()
                dashboard.get_by_role("button", name="Preview selected →").click()
                expect(overlay.locator(".overlay-text")).to_contain_text(
                    "<img src=x onerror=window.pwned=1>"
                )
                expect(
                    overlay.get_by_text("DEVELOPMENT PREVIEW — NOT APPROVED / NOT EXECUTED")
                ).to_be_visible()
                assert overlay.evaluate("window.pwned") is None
                expect(overlay.locator("img")).to_have_count(0)
                if args.output_dir:
                    args.output_dir.mkdir(parents=True, exist_ok=True)
                    dashboard.screenshot(
                        path=str(args.output_dir / "synthetic-dashboard.png"), full_page=True
                    )
                    overlay.screenshot(path=str(args.output_dir / "synthetic-overlay.png"))
                overlay.reload()
                expect(overlay.get_by_text("Ready for your next idea")).to_be_visible()
                expect(overlay.locator(".overlay-text")).to_have_count(0)
                dashboard.get_by_role("radio").filter(has_text="Long untrusted").click()
                dashboard.get_by_role("button", name="Preview selected →").click()
                expect(overlay.locator(".overlay-text")).to_contain_text(
                    "Long untrusted viewer text"
                )
                assert overlay.locator(".overlay-text").evaluate(
                    "el => el.scrollWidth <= el.clientWidth + 1"
                )
                context.set_offline(True)
                expect(overlay.get_by_text("Connection lost")).to_be_visible(timeout=10000)
                context.set_offline(False)
                expect(overlay.get_by_text("Ready for your next idea")).to_be_visible(timeout=10000)
                expect(overlay.locator(".overlay-text")).to_have_count(0)
                context.close()
                browser.close()
        finally:
            stop_fixture(server, Path(state))
    print(
        "BROWSER_E2E=PASS; actual Chromium; synthetic OAuth/EventSub; owner selection; "
        "pairing; escaping; long text; refresh/reconnect no replay; cleanup acknowledged. "
        "LIVE_TWITCH=NOT_RUN; OBS=NOT_RUN"
    )


if __name__ == "__main__":
    main()
