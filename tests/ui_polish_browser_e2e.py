"""Chromium presentation regression with isolated synthetic owner and Twitch fixtures."""

import argparse
import sqlite3
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from playwright.sync_api import expect, sync_playwright

from tests.process_helpers import start_fixture, stop_fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="crowdquest-ui-polish-") as temporary:
        directory = Path(temporary)
        server, origin = start_fixture(directory, phase4=True)
        try:
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch()
                context = browser.new_context(viewport={"width": 1440, "height": 1000})

                def isolate(route):
                    url = urlsplit(route.request.url)
                    if url.netloc != urlsplit(origin).netloc:
                        route.abort()
                    elif url.path == "/auth/twitch/start":
                        response = route.fetch(max_redirects=0)
                        query = parse_qs(urlsplit(response.headers["location"]).query)
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

                context.route("**/*", isolate)
                dashboard = context.new_page()
                dashboard.goto(origin + "/auth/twitch/start")
                expect(dashboard).to_have_title("CrowdQuest AI · Director Dashboard")
                expect(dashboard.get_by_text("@fixture_owner")).to_be_visible()
                expect(dashboard.locator(".phase")).to_contain_text("DIRECTOR DASHBOARD")
                expect(dashboard.locator(".phase")).to_contain_text("Broadcast Studio")
                expect(
                    dashboard.get_by_role("button", name="Hide Earlier Activity", exact=True)
                ).to_be_visible()
                expect(
                    dashboard.get_by_text("STREAMER REVIEW REQUIRED", exact=False)
                ).to_be_visible()

                dialogs = []

                def accept_confirmation(dialog):
                    dialogs.append(dialog.message)
                    dialog.accept()

                dashboard.on("dialog", accept_confirmation)
                dashboard.get_by_role("button", name="Hide Earlier Activity", exact=True).click()
                confirmation = (
                    "Hide earlier suggestions and voting rounds from this view? "
                    "Historical records and audit evidence will be preserved."
                )
                expect(
                    dashboard.get_by_text(
                        "Waiting for 2 new suggestions before a fresh vote can start."
                    )
                ).to_be_visible()
                expect(
                    dashboard.get_by_role("status").filter(
                        has_text="Earlier activity is hidden. New suggestions will appear here."
                    )
                ).to_be_visible()
                assert dialogs == [confirmation], dialogs
                expect(dashboard.get_by_role("radio")).to_have_count(0)

                with closing(sqlite3.connect(directory / "intake.sqlite3")) as db:
                    assert db.execute("SELECT count(*) FROM candidates").fetchone()[0] == 2

                dashboard.wait_for_timeout(6100)
                expect(
                    dashboard.get_by_text(
                        "Earlier activity is hidden. New suggestions will appear here."
                    )
                ).to_have_count(0)
                dashboard.reload()
                expect(dashboard).to_have_title("CrowdQuest AI · Director Dashboard")
                expect(dashboard.get_by_role("radio")).to_have_count(0)
                expect(dashboard.get_by_text("Waiting for your first quest")).to_be_visible()
                expect(
                    dashboard.get_by_text(
                        "Waiting for 2 new suggestions before a fresh vote can start."
                    )
                ).to_be_visible()
                dashboard.screenshot(
                    path=str(output / "synthetic-dashboard-after.png"), full_page=True
                )

                studio = context.new_page()
                studio.goto(origin + "/broadcast-studio")
                expect(studio).to_have_title("CrowdQuest AI · Broadcast Studio")
                expect(studio.get_by_text("Backend connected", exact=True)).to_be_visible()
                expect(studio.locator(".studio-stage-heading")).to_contain_text(
                    "CURRENT PRESENTATION"
                )
                expect(
                    studio.get_by_role("button", name="Follow current state", exact=True)
                ).to_be_visible()
                expect(studio.get_by_text("LIVE PRESENTATION", exact=True)).to_have_count(0)
                studio.screenshot(path=str(output / "synthetic-studio-after.png"), full_page=True)

                studio.set_viewport_size({"width": 390, "height": 844})
                assert studio.evaluate("document.documentElement.scrollWidth <= window.innerWidth")

                overlay = context.new_page()
                overlay.goto(origin + "/overlay")
                expect(overlay).to_have_title("CrowdQuest AI · Overlay")

                browser.close()
        finally:
            stop_fixture(server, directory)

    print(
        "UI_POLISH_BROWSER_E2E=PASS; Chromium; synthetic owner/Twitch; "
        "history watermark persisted without deletion; titles and responsive Studio verified; "
        "actions=0; real_twitch=NOT_RUN"
    )


if __name__ == "__main__":
    main()
