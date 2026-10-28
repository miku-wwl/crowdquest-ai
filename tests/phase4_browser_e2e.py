"""Actual Chromium, AIG/SQLite and separate worker; all chat/model/consent are synthetic."""

import argparse
import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import time
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from tests.process_helpers import start_fixture, stop_fixture
from tests.support import notification


def deliver(directory, *, viewer, text, delivery=None, message=None, expected="VOTE_ACCEPTED"):
    envelope = notification(
        delivery=delivery or str(uuid4()),
        message=message or str(uuid4()),
        viewer=str(viewer),
        text=text,
    )
    filename = "event-" + str(uuid4()) + ".json"
    staging = directory / (filename + ".pending")
    staging.write_text(json.dumps(envelope), encoding="utf-8")
    staging.rename(directory / filename)
    result = directory / ("result-" + filename)
    deadline = time.monotonic() + 5
    while not result.exists() and time.monotonic() < deadline:
        time.sleep(0.05)
    assert result.exists(), "Synthetic fixture mailbox did not acknowledge"
    assert json.loads(result.read_text("utf-8"))["result"] == expected
    return envelope


def fits(page):
    card = page.locator(".overlay-card").bounding_box()
    assert (
        card
        and 0 <= card["x"]
        and 0 <= card["y"]
        and card["x"] + card["width"] <= 1280
        and card["y"] + card["height"] <= 720
    ), card
    dimensions = page.evaluate(
        "({width:document.documentElement.scrollWidth,height:document.documentElement.scrollHeight,innerWidth,innerHeight})"
    )
    if (
        dimensions["width"] > dimensions["innerWidth"]
        or dimensions["height"] > dimensions["innerHeight"]
    ):
        Path(".artifacts/phase4").mkdir(parents=True, exist_ok=True)
        page.screenshot(
            path=".artifacts/phase4/overflow-diagnostic.png", full_page=True, omit_background=True
        )
    assert (
        dimensions["width"] <= dimensions["innerWidth"]
        and dimensions["height"] <= dimensions["innerHeight"]
    ), (dimensions, card)
    assert page.evaluate("getComputedStyle(document.body).backgroundColor") == "rgba(0, 0, 0, 0)"
    assert (
        page.evaluate("getComputedStyle(document.documentElement).backgroundColor")
        == "rgba(0, 0, 0, 0)"
    )
    for box in page.locator(".vote-suggestion,.overlay-text,.challenge-description").all():
        assert box.evaluate("e=>e.scrollHeight<=e.clientHeight+1 && e.scrollWidth<=e.clientWidth+1")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path)
    args = parser.parse_args()
    with tempfile.TemporaryDirectory(prefix="crowdquest-phase4-chromium-") as state:
        directory = Path(state)
        server, origin = start_fixture(directory, phase4=True)
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
                executed = []
                dashboard.on(
                    "request",
                    lambda request: (
                        executed.append(request.url)
                        if request.method == "POST" and request.url.endswith("/execute")
                        else None
                    ),
                )
                errors = []
                dashboard.on("pageerror", lambda error: errors.append(str(error)))
                dashboard.goto(origin)
                dashboard.get_by_role("link", name="Connect Twitch →").click()
                expect(dashboard.get_by_text("@fixture_owner")).to_be_visible()
                contexts = []
                overlays = []
                for _ in range(2):
                    context = browser.new_context(
                        viewport={"width": 1280, "height": 720}, reduced_motion="reduce"
                    )
                    context.route("**/*", isolate)
                    overlay = context.new_page()
                    overlay.on("pageerror", lambda error: errors.append(str(error)))
                    overlay.goto(origin + "/overlay")
                    code = overlay.locator(".pair-code").inner_text()
                    dashboard.get_by_role("button", name="Pair overlay " + code).click()
                    expect(overlay.get_by_text("Ready for your next idea")).to_be_visible()
                    contexts.append(context)
                    overlays.append(overlay)
                panel = dashboard.get_by_role("region", name="Crowd voting")
                panel.get_by_role("checkbox").nth(0).check()
                panel.get_by_role("checkbox").nth(1).check()
                panel.get_by_role("button", name="Create voting round").click()
                panel.get_by_role("button", name="Start voting").click()
                expect(overlays[0].get_by_text("Chat, make the call.")).to_be_visible()
                envelope = deliver(directory, viewer=800, text="!vote 1")
                deliver(directory, viewer=801, text="!vote 1")
                deliver(directory, viewer=802, text="!vote 2")
                deliver(directory, viewer=800, text="!vote 2", expected="DUPLICATE_VOTE")
                deliver(
                    directory,
                    viewer=800,
                    text="!vote 1",
                    delivery=envelope["metadata"]["message_id"],
                    message=envelope["payload"]["event"]["message_id"],
                    expected="DELIVERY_CONFLICT",
                )
                expect(
                    overlays[0].get_by_role("meter", name="Candidate 1 vote share")
                ).to_have_attribute("value", "66.7")
                expect(panel.get_by_text("2 votes", exact=True)).to_be_visible()
                fits(overlays[0])
                if args.output_dir:
                    args.output_dir.mkdir(parents=True, exist_ok=True)
                    overlays[0].screenshot(
                        path=str(args.output_dir / "synthetic-voting.png"), omit_background=True
                    )
                    dashboard.screenshot(
                        path=str(args.output_dir / "synthetic-director-studio.png"), full_page=True
                    )
                panel.get_by_role("button", name="Close voting now").click()
                expect(overlays[0].get_by_text("Chat has spoken.")).to_be_visible()
                panel.get_by_role("button", name="Generate winning Plan").click()
                review = dashboard.get_by_role("region", name="Challenge review")
                expect(review.get_by_text("SYNTHETIC_TEST", exact=False)).to_be_visible()
                expect(review.get_by_text("Chosen by Chat", exact=True)).to_be_visible()
                for label in (
                    "Approve this Plan",
                    "Admit approved Action",
                    "Authorize this Action",
                ):
                    button = review.get_by_role("button", name=label)
                    expect(button).to_be_enabled()
                    button.click()
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
                review.get_by_role("button", name="Execute authorized Action").click()
                for overlay in overlays:
                    expect(overlay.locator(".overlay-text")).to_contain_text(
                        "SYNTHETIC TEST", timeout=10000
                    )
                    expect(overlay.get_by_text("Chosen by Chat", exact=True)).to_be_visible()
                    expect(overlay.get_by_label("Time remaining")).to_be_visible()
                    fits(overlay)
                expect(review.get_by_role("button", name="Completed", exact=True)).to_be_enabled()
                if args.output_dir:
                    overlays[0].screenshot(
                        path=str(args.output_dir / "synthetic-chat-selected-challenge.png"),
                        omit_background=True,
                    )
                review.get_by_role("button", name="Completed", exact=True).click()
                # Each old view must actually consume the result before its reload
                # can test no replay. A first display in an unpolled view is valid.
                for overlay in overlays:
                    expect(overlay.get_by_text("Challenge complete.")).to_be_visible()
                expect(review.get_by_text("Completed · Streamer-reported result")).to_be_visible()
                if args.output_dir:
                    overlays[0].screenshot(
                        path=str(args.output_dir / "synthetic-owner-outcome.png"),
                        omit_background=True,
                    )
                overlays[1].reload()
                expect(overlays[1].get_by_text("Ready for your next idea")).to_be_visible()
                expect(overlays[0].get_by_text("Ready for your next idea")).to_be_visible(
                    timeout=12000
                )
                overlays[0].reload()
                expect(overlays[0].get_by_text("Ready for your next idea")).to_be_visible()
                assert len(executed) == 1, executed
                with closing(sqlite3.connect(directory / "phase3/overlay.sqlite3")) as db:
                    assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
                with closing(sqlite3.connect(directory / "phase3/render.sqlite3")) as db:
                    assert db.execute("SELECT count(*) FROM renders").fetchone()[0] == 1
                    assert db.execute("SELECT kind,state FROM challenge_outcomes").fetchall() == [
                        ("Completed", "ENDED")
                    ]
                # A separate new synthetic round exercises the full 280-char input bound.
                maximum1 = "界" * 280
                maximum2 = "語" * 280
                deliver(directory, viewer=900, text="!quest " + maximum1, expected="ACCEPTED")
                deliver(directory, viewer=901, text="!quest " + maximum2, expected="ACCEPTED")
                for checkbox in panel.get_by_role("checkbox").all():
                    if checkbox.is_checked():
                        checkbox.uncheck()
                panel.get_by_role("checkbox", name="Shortlist " + maximum1).check()
                panel.get_by_role("checkbox", name="Shortlist " + maximum2).check()
                panel.get_by_label("Voting time", exact=True).select_option("15")
                panel.get_by_role("button", name="Create voting round").click()
                panel.get_by_role("button", name="Start voting").click()
                expect(overlays[0].get_by_text(maximum1, exact=True)).to_be_visible()
                expect(overlays[0].get_by_text(maximum2, exact=True)).to_be_visible()
                fits(overlays[0])
                assert overlays[0].locator("img").count() == 0
                assert (
                    overlays[0].evaluate(
                        "getComputedStyle(document.querySelector('.vote-track'),'::-webkit-meter-optimum-value').transitionDuration"
                    )
                    == "0s"
                )
                if args.output_dir:
                    overlays[0].screenshot(
                        path=str(args.output_dir / "synthetic-voting-max-unicode.png"),
                        omit_background=True,
                    )
                expect(
                    panel.get_by_role("button", name="Choose candidate 1 as winner")
                ).to_be_visible(timeout=20000)
                panel.get_by_role("button", name="Choose candidate 1 as winner").click()
                expect(panel.get_by_role("button", name="Generate winning Plan")).to_be_enabled()
                assert len(executed) == 1 and not errors, errors
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
        "PHASE4_CHROMIUM_E2E=PASS; actual Chromium, installed AIG, separate worker, temporary SQLite; synthetic chat/model/consent; votes2:1, duplicate-voter/delivery denial, winner binding, separate gates, one execution/job/render, owner outcome, 8s expiry, reload no replay, 280-char Unicode, 1280x720, transparent/reduced-motion. REAL_TWITCH=NOT_RUN; REAL_MODEL=NOT_RUN; HUMAN_APPROVED=NOT_RUN; REAL_OBS=NOT_RUN"
    )


if __name__ == "__main__":
    main()
