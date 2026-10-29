"""Two-tab Chromium delivery regression; synthetic fixture, native visibility reported honestly."""

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
from contextlib import closing
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit
from uuid import uuid4

from playwright.sync_api import expect, sync_playwright

from tests.process_helpers import start_fixture, stop_fixture
from tests.studio_browser_e2e import canvas_frame


def qualify_delivery(output):
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="crowdquest-delivery-") as temporary:
        directory = Path(temporary)
        server, origin = start_fixture(directory, phase4=True)
        worker = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=os.environ.get("CROWDQUEST_HEADED") != "1")
                context = browser.new_context(viewport={"width": 1500, "height": 1100})

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

                context.route("**/*", isolate)
                dashboard = context.new_page()
                dashboard.goto(origin + "/auth/twitch/start")
                expect(dashboard.get_by_text("@fixture_owner")).to_be_visible()
                csrf = context.request.get(origin + "/api/me").json()["csrf"]
                headers = {"Origin": origin, "X-CSRF-Token": csrf}
                studio = context.new_page()
                errors, claims, acks = [], [], []
                studio.on("pageerror", lambda error: errors.append(str(error)))
                studio.on(
                    "request",
                    lambda request: (
                        claims.append(request)
                        if urlsplit(request.url).path == "/api/studio/claim"
                        else None
                    ),
                )
                studio.on(
                    "response",
                    lambda response: (
                        acks.append(response.status)
                        if urlsplit(response.url).path == "/api/studio/ack"
                        else None
                    ),
                )
                studio.goto(origin + "/broadcast-studio")
                expect(studio.get_by_text("Backend connected", exact=True)).to_be_visible()
                dashboard.bring_to_front()
                dashboard.wait_for_timeout(300)
                native = studio.evaluate("document.hidden")
                if not native:
                    # Playwright on this host reports both tabs visible. This is
                    # an explicit deterministic substitute, never native evidence.
                    studio.evaluate("""() => {
                        window.__cqFixtureHidden = true;
                        Object.defineProperty(document, 'hidden', {configurable:true,get:()=>window.__cqFixtureHidden});
                        document.dispatchEvent(new Event('visibilitychange'));
                    }""")

                def post(path, value):
                    response = context.request.post(origin + path, headers=headers, data=value)
                    assert response.ok, (path, response.status)
                    return response.json()

                candidates = context.request.get(origin + "/api/candidates").json()["candidates"]
                run = post(f"/api/phase3/candidates/{candidates[0]['id']}/generate", {})["run"]
                run = post(
                    f"/api/phase3/runs/{run['run_id']}/decision",
                    {"decision": "APPROVE", "expected_version": run["version"]},
                )["run"]
                action = post(
                    f"/api/phase3/runs/{run['run_id']}/admit",
                    {"expected_version": run["version"], "idempotency_key": str(uuid4())},
                )
                action = post(
                    f"/api/phase3/actions/{action['action_id']}/authorize",
                    {"expected_version": action["version"], "idempotency_key": str(uuid4())},
                )
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
                action = post(
                    f"/api/phase3/actions/{action['action_id']}/execute",
                    {"expected_version": action["version"], "idempotency_key": str(uuid4())},
                )
                assert action["state"] == "Succeeded"
                # Longer than the old ACK timeout, but shorter than fixture expiry.
                dashboard.wait_for_timeout(6200)
                with closing(sqlite3.connect(directory / "phase3/render.sqlite3")) as db:
                    assert db.execute("SELECT state FROM renders").fetchall() == [("SENT",)]
                    assert db.execute("SELECT count(*) FROM observations").fetchone()[0] == 0
                assert not claims and not acks
                studio.bring_to_front()
                if not native:
                    studio.evaluate(
                        "window.__cqFixtureHidden=false; document.dispatchEvent(new Event('visibilitychange'))"
                    )
                expect(studio.get_by_text("Browser ACK verified", exact=True)).to_be_visible(
                    timeout=5000
                )
                expect(studio.locator(".studio-live-description")).to_contain_text("SYNTHETIC TEST")
                canvas_frame(studio, output / "synthetic-visible-challenge.png")
                with closing(sqlite3.connect(directory / "phase3/render.sqlite3")) as db:
                    assert db.execute("SELECT state FROM renders").fetchall() == [("RENDERED",)]
                    assert db.execute("SELECT status FROM observations").fetchall() == [
                        ("ACKNOWLEDGED",)
                    ]
                assert len(claims) == 1 and acks == [200]
                studio.reload()
                expect(
                    studio.get_by_text("Delivery already claimed — no replay", exact=True)
                ).to_be_visible(timeout=5000)
                assert len(claims) == 1 and acks == [200]
                assert not errors
                result = {
                    "status": "PASS",
                    "evidence": "SYNTHETIC_TEST_ONLY",
                    "two_tabs": True,
                    "native_background_visibility": "PASS" if native else "PARTIAL",
                    "visibility_control": "native"
                    if native
                    else "explicit document.hidden fixture override",
                    "limitation": None
                    if native
                    else "Both Chromium tabs report visible in this run. Native background-tab behavior is not proven; visibility is controlled explicitly for the regression.",
                    "hidden_for_seconds": 6.2,
                    "hidden_observations": 0,
                    "visible_claims": len(claims),
                    "ack_http_statuses": acks,
                    "durable_acknowledgements": 1,
                    "browser_ack": "BROWSER_ACK_VERIFIED",
                    "refresh_no_replay": "PASS",
                    "obs": "NOT_VERIFIED",
                    "synthetic_actions": 1,
                    "production_actions": 0,
                    "real_twitch_events": 0,
                }
                (output / "delivery-qualification.json").write_text(
                    json.dumps(result, indent=2) + "\n", encoding="utf-8"
                )
                browser.close()
                return result
        finally:
            stop_fixture(server, directory)
            if worker is not None:
                try:
                    worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    worker.terminate()
                    worker.wait(timeout=5)


if __name__ == "__main__":
    print(json.dumps(qualify_delivery(Path(".artifacts/phase455/delivery"))))
