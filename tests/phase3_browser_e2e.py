"""Actual Chromium + separate worker + AIG/SQLite; synthetic OAuth/chat/provider/consent."""

import argparse
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

from playwright.sync_api import expect, sync_playwright

from tests.process_helpers import start_fixture, stop_fixture


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="crowdquest-phase3-browser-") as state:
        directory = Path(state)
        server, origin = start_fixture(directory, phase3=True)
        worker = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                owner = browser.new_context(viewport={"width": 1440, "height": 1100})

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
                                + urlencode({"state": query["state"][0], "code": "synthetic"}),
                            },
                        )
                    else:
                        route.continue_()

                owner.route("**/*", isolate)
                dashboard = owner.new_page()
                dashboard.goto(origin)
                dashboard.get_by_role("link", name="Connect Twitch →").click()
                expect(dashboard.get_by_text("@fixture_owner")).to_be_visible()
                contexts = []
                overlays = []
                for _ in range(2):
                    context = browser.new_context(viewport={"width": 1280, "height": 720})
                    context.route("**/*", isolate)
                    overlay = context.new_page()
                    overlay.goto(origin + "/overlay")
                    expect(overlay.get_by_text("Pair this Browser Source")).to_be_visible()
                    code = overlay.locator(".pair-code").inner_text()
                    dashboard.get_by_role("button", name="Pair overlay " + code).click()
                    expect(overlay.get_by_text("Ready for your next idea")).to_be_visible()
                    contexts.append(context)
                    overlays.append(overlay)
                dashboard.get_by_role("radio").first.click()
                expect(dashboard.get_by_role("button", name="Preview selected →")).to_have_count(0)
                dashboard.get_by_role("button", name="Generate proposed Plan").click()
                expect(dashboard.get_by_text("SYNTHETIC_TEST", exact=False)).to_be_visible()
                expect(dashboard.get_by_role("button", name="Approve this Plan")).to_be_enabled()
                assert dashboard.locator(".plan-fields img").count() == 0
                dashboard.get_by_role("button", name="Approve this Plan").click()
                expect(
                    dashboard.get_by_role("button", name="Admit approved Action")
                ).to_be_enabled()
                with closing(sqlite3.connect(directory / "phase3/overlay.sqlite3")) as db:
                    assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
                dashboard.get_by_role("button", name="Admit approved Action").click()
                expect(
                    dashboard.get_by_role("button", name="Authorize this Action")
                ).to_be_enabled()
                dashboard.get_by_role("button", name="Authorize this Action").click()
                expect(
                    dashboard.get_by_role("button", name="Execute authorized Action")
                ).to_be_enabled()
                with closing(sqlite3.connect(directory / "phase3/overlay.sqlite3")) as db:
                    assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
                worker = subprocess.Popen(
                    [
                        sys.executable,
                        "-m",
                        "crowdquest.worker",
                        "--origin",
                        origin,
                        "--token-file",
                        str(directory / "phase3/worker-token"),
                    ],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
                )
                dashboard.get_by_role("button", name="Execute authorized Action").click()
                for overlay in overlays:
                    expect(overlay.locator(".overlay-text")).to_contain_text(
                        "Safe challenge", timeout=10000
                    )
                    assert overlay.locator("img").count() == 0
                    assert overlay.evaluate("window.pwned") is None
                    expect(overlay.get_by_label("Time remaining")).to_be_visible()
                dashboard.get_by_text("Receipt and audit").click()
                expect(
                    dashboard.get_by_text("Browser acknowledgements: 2.", exact=False)
                ).to_be_visible(timeout=10000)
                expect(dashboard.get_by_text("2 Ready", exact=True)).to_be_visible()
                if args.output_dir:
                    args.output_dir.mkdir(parents=True, exist_ok=True)
                    dashboard.screenshot(
                        path=str(args.output_dir / "synthetic-dashboard.png"), full_page=True
                    )
                    overlays[0].screenshot(path=str(args.output_dir / "synthetic-overlay.png"))
                # A reload is a new view; previously issued content must never be replayed.
                overlays[1].reload()
                expect(overlays[1].get_by_text("Ready for your next idea")).to_be_visible()
                expect(overlays[1].locator(".overlay-text")).to_have_count(0)
                expect(overlays[0].get_by_text("Challenge expired")).to_be_visible(timeout=22000)
                with closing(sqlite3.connect(directory / "phase3/overlay.sqlite3")) as db:
                    assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
                # The browser's request-start anchor can expire slightly before the
                # next server heartbeat materializes EXPIRED. Observe that transition;
                # never mask terminal Unknown/Failed or mutate the fixture database.
                deadline = time.monotonic() + 3
                observed = []
                while True:
                    with closing(sqlite3.connect(directory / "phase3/render.sqlite3")) as db:
                        state = db.execute("SELECT state FROM renders").fetchone()[0]
                        assert db.execute("SELECT count(*) FROM renders").fetchone()[0] == 1
                    if not observed or observed[-1] != state:
                        observed.append(state)
                    assert state not in ("UNKNOWN", "RENDER_FAILED"), (state, worker.poll())
                    if state == "EXPIRED" or time.monotonic() >= deadline:
                        break
                    time.sleep(0.05)
                assert state == "EXPIRED", (state, worker.poll())
                print("PHASE3_EXPIRY_OBSERVATION=" + ",".join(observed), flush=True)
                # Different candidate, fresh exact review and independent Action gates.
                dashboard.get_by_role("radio").last.click()
                dashboard.get_by_role("button", name="Edit a manual draft").click()
                maximum_title = "SYNTHETIC TEST " + "界" * 65
                maximum_description = "界" * 240
                dashboard.get_by_label("Title", exact=True).fill(maximum_title)
                dashboard.get_by_label("Description", exact=True).fill(maximum_description)
                dashboard.get_by_label("Duration in seconds").fill("15")
                dashboard.get_by_role("button", name="Create manual Plan").click()
                for label in [
                    "Approve this Plan",
                    "Admit approved Action",
                    "Authorize this Action",
                    "Execute authorized Action",
                ]:
                    button = dashboard.get_by_role("button", name=label)
                    expect(button).to_be_enabled()
                    button.click()
                expect(overlays[0].locator(".overlay-text")).to_have_text(
                    maximum_title, timeout=10000
                )
                expect(overlays[0].locator(".challenge-description")).to_have_text(
                    maximum_description
                )
                card = overlays[0].locator(".overlay-card").bounding_box()
                assert card and card["y"] >= 0 and card["y"] + card["height"] <= 720
                assert overlays[0].get_by_label("Time remaining").is_visible()
                if args.output_dir:
                    overlays[0].screenshot(
                        path=str(args.output_dir / "synthetic-overlay-max-fields.png")
                    )
                with closing(sqlite3.connect(directory / "phase3/overlay.sqlite3")) as db:
                    assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 2
                for context in contexts:
                    context.close()
                owner.close()
                browser.close()
        finally:
            stop_fixture(server, directory)
            if worker is not None:
                try:
                    worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    worker.terminate()
                    worker.wait(timeout=5)
    print(
        "PHASE3_BROWSER_E2E=PASS; actual Chromium + authenticated separate worker + installed AIG + temporary SQLite; synthetic OAuth/chat/provider/consent; two overlays, escaped/max Unicode fields, separate gates, acknowledgements, reload no replay, 15-second expiry; two intentionally distinct fixture jobs. REAL_TWITCH=NOT_RUN; REAL_MODEL=NOT_RUN; HUMAN_APPROVAL=NOT_RUN; OBS=NOT_RUN"
    )


if __name__ == "__main__":
    main()
