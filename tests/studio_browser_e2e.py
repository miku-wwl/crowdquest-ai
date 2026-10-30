"""Actual Canvas/MediaRecorder/video decoding; isolated synthetic Twitch/model/consent."""

import argparse
import base64
import hashlib
import json
import os
import re
import shutil
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

from tests.phase4_browser_e2e import deliver
from tests.process_helpers import start_fixture, stop_fixture


def canvas_frame(page, path):
    page.evaluate(
        "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"
    )
    value = page.locator("canvas").evaluate("canvas => canvas.toDataURL('image/png').split(',')[1]")
    path.write_bytes(base64.b64decode(value))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir", type=Path, default=Path(".artifacts/phase45-browser/evidence")
    )
    parser.add_argument(
        "--ffmpeg", default=os.environ.get("CROWDQUEST_FFMPEG") or shutil.which("ffmpeg")
    )
    args = parser.parse_args()
    from tests.studio_delivery_browser_e2e import qualify_delivery

    qualify_delivery(args.output_dir / "delivery")
    output = args.output_dir.resolve()
    output.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="crowdquest-studio-chromium-") as temporary:
        directory = Path(temporary)
        server, origin = start_fixture(directory, phase4=True)
        worker = None
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(
                    viewport={"width": 1600, "height": 1200}, accept_downloads=True
                )

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
                page = context.new_page()
                errors = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(origin + "/auth/twitch/start")
                expect(page.get_by_text("@fixture_owner")).to_be_visible()
                csrf = context.request.get(origin + "/api/me").json()["csrf"]
                headers = {"Origin": origin, "X-CSRF-Token": csrf}

                def get(path):
                    result = context.request.get(origin + path)
                    assert result.ok, result.status
                    return result.json()

                def post(path, body):
                    result = context.request.post(origin + path, data=body, headers=headers)
                    assert result.ok, (path, result.status, result.text())
                    return result.json()

                page.goto(origin + "/broadcast-studio")
                expect(page).to_have_title("CrowdQuest AI · Broadcast Studio")
                expect(page.get_by_text("Backend connected", exact=True)).to_be_visible()
                expect(page.get_by_text("SYNTHETIC TEST DATA", exact=True)).to_be_visible()
                expect(page.locator(".studio-stage-heading")).to_contain_text(
                    "CURRENT PRESENTATION"
                )
                expect(
                    page.get_by_role("button", name="Follow live state", exact=True)
                ).to_have_count(0)
                expect(
                    page.get_by_role("button", name="Start Recording", exact=True)
                ).to_be_enabled()
                assert page.locator("canvas").get_attribute("width") == "1920"
                assert page.locator("canvas").get_attribute("height") == "1080"
                for scene in ("Waiting", "Voting", "Challenge Active", "Challenge Result"):
                    page.get_by_role("button", name=scene, exact=True).click()
                    expect(
                        page.get_by_role("button", name="Start Recording", exact=True)
                    ).to_be_disabled()
                page.get_by_role("button", name="Follow current state", exact=True).click()
                canvas_frame(page, output / "synthetic-waiting-preview.png")
                started = time.monotonic()
                page.get_by_role("button", name="Start Recording", exact=True).dblclick()
                expect(page.get_by_label("Recording state")).to_contain_text("Recording")
                page.wait_for_timeout(1500)
                candidates = get("/api/candidates")["candidates"]
                round_ = post(
                    "/api/phase4/rounds",
                    {
                        "candidate_ids": [item["id"] for item in candidates[:2]],
                        "duration_seconds": 30,
                        "idempotency_key": str(uuid4()),
                    },
                )["round"]
                round_ = post(
                    f"/api/phase4/rounds/{round_['id']}/start",
                    {"expected_version": round_["version"], "idempotency_key": str(uuid4())},
                )["round"]
                expect(page.locator(".studio-live-description")).to_contain_text("Open")
                deliver(directory, viewer=820, text="!vote 1")
                deliver(directory, viewer=821, text="!vote 1")
                deliver(directory, viewer=822, text="!vote 2")
                deliver(directory, viewer=820, text="!vote 2", expected="DUPLICATE_VOTE")
                expect(page.locator(".studio-live-description")).to_contain_text("3 votes")
                expect(page.locator(".studio-live-description")).to_contain_text("Candidate 1: 2")
                canvas_frame(page, output / "synthetic-voting-preview.png")
                page.wait_for_timeout(2200)
                round_ = get("/api/phase4/voting")["round"]
                round_ = post(
                    f"/api/phase4/rounds/{round_['id']}/close",
                    {"expected_version": round_["version"], "idempotency_key": str(uuid4())},
                )["round"]
                expect(page.locator(".studio-live-description")).to_contain_text("Closed")
                proposal = post(
                    f"/api/phase4/rounds/{round_['id']}/plan",
                    {"expected_version": round_["version"]},
                )
                run = proposal["proposal"]["run"]
                approved = post(
                    f"/api/phase3/runs/{run['run_id']}/decision",
                    {"decision": "APPROVE", "expected_version": run["version"]},
                )["run"]
                action = post(
                    f"/api/phase3/runs/{run['run_id']}/admit",
                    {"expected_version": approved["version"], "idempotency_key": str(uuid4())},
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
                expect(page.locator(".studio-live-description")).to_contain_text(
                    "SYNTHETIC TEST", timeout=10000
                )
                expect(page.locator(".studio-live-description")).to_contain_text("Challenge Active")
                canvas_frame(page, output / "synthetic-challenge-preview.png")
                page.screenshot(path=str(output / "synthetic-studio.png"), full_page=True)
                expect(page.locator(".studio-live-description")).to_contain_text(
                    "Challenge expired", timeout=18000
                )
                post(
                    f"/api/phase4/actions/{action['action_id']}/outcome",
                    {
                        "kind": "Skipped",
                        "expected_version": action["version"],
                        "idempotency_key": str(uuid4()),
                    },
                )
                expect(page.locator(".studio-live-description")).to_contain_text(
                    "Skipped, reported"
                )
                canvas_frame(page, output / "synthetic-outcome-preview.png")
                expect(page.locator(".studio-live-description")).to_contain_text(
                    "No active presentation", timeout=12000
                )
                remaining = 32 - (time.monotonic() - started)
                if remaining > 0:
                    page.wait_for_timeout(remaining * 1000)
                captured_seconds = float(
                    re.search(r"([0-9.]+)s", page.get_by_label("Recording state").inner_text())[1]
                )
                page.get_by_role("button", name="Stop Recording", exact=True).click()
                expect(page.get_by_text("Finalized · playback verified", exact=True)).to_be_visible(
                    timeout=15000
                )
                assert page.locator(".studio-downloads article").count() == 1
                with page.expect_download() as pending:
                    page.get_by_role("link", name="Download crowdquest-", exact=False).click()
                download = pending.value
                assert download.suggested_filename.endswith(".webm")
                video_path = output / ("synthetic-" + download.suggested_filename)
                download.save_as(str(video_path))
                assert video_path.stat().st_size > 10000
                video = page.locator(".studio-downloads video")
                metadata = video.evaluate(
                    "v => ({width:v.videoWidth,height:v.videoHeight,duration:v.duration,ready:v.readyState,error:v.error?.code||null})"
                )
                assert 30 <= metadata["duration"] <= 180
                assert abs(metadata["duration"] - captured_seconds) < 1
                assert (
                    metadata["width"] == 1920
                    and metadata["height"] == 1080
                    and not metadata["error"]
                )
                video.evaluate("v=>v.play()")
                page.wait_for_timeout(600)
                assert video.evaluate("v=>v.currentTime") > 0.1
                video.evaluate("v=>v.pause()")
                comparison = page.evaluate(
                    """async reference => {
                    const video = document.querySelector('.studio-downloads video');
                    await new Promise(resolve => { video.addEventListener('seeked', resolve, {once:true}); video.currentTime = 0.5; });
                    const bytes = Uint8Array.from(atob(reference), char => char.charCodeAt(0));
                    const image = await createImageBitmap(new Blob([bytes], {type:'image/png'}));
                    const surface = document.createElement('canvas'); surface.width = video.videoWidth; surface.height = video.videoHeight;
                    const ctx = surface.getContext('2d'); ctx.drawImage(video,0,0);
                    const actual = ctx.getImageData(0,0,surface.width,surface.height).data;
                    ctx.drawImage(image,0,0); const expected = ctx.getImageData(0,0,surface.width,surface.height).data;
                    let error=0; for(let i=0;i<actual.length;i++) if(i%4!==3) error += Math.abs(actual[i]-expected[i]);
                    return {mean_absolute_rgb_error:error/(surface.width*surface.height*3), width:surface.width,height:surface.height};
                }""",
                    base64.b64encode(
                        (output / "synthetic-waiting-preview.png").read_bytes()
                    ).decode(),
                )
                assert comparison["mean_absolute_rgb_error"] < 6, comparison
                page.reload()
                expect(page.locator(".studio-live-description")).to_contain_text(
                    "No active presentation"
                )
                expect(page.get_by_label("Recording state")).to_contain_text("Idle")
                page.set_viewport_size({"width": 390, "height": 844})
                assert page.evaluate("document.documentElement.scrollWidth <= innerWidth")
                assert not errors, errors
                with closing(sqlite3.connect(directory / "phase3/overlay.sqlite3")) as db:
                    assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
                with closing(sqlite3.connect(directory / "phase3/render.sqlite3")) as db:
                    assert db.execute("SELECT kind,state FROM challenge_outcomes").fetchall() == [
                        ("Skipped", "ENDED")
                    ]
                result = {
                    "status": "PASS",
                    "evidence": "SYNTHETIC_TEST",
                    "actual_canvas_recording": True,
                    "dimensions": [1920, 1080],
                    "wall_elapsed_seconds": round(time.monotonic() - started, 3),
                    "file": video_path.name,
                    "bytes": video_path.stat().st_size,
                    "sha256": hashlib.sha256(video_path.read_bytes()).hexdigest(),
                    "playback": metadata,
                    "preview_video_comparison": comparison,
                    "real_twitch": "NOT_RUN",
                    "real_aig_actions": 0,
                    "synthetic_aig_actions": 1,
                    "obs_used": False,
                    "desktop_automation": False,
                }
                if args.ffmpeg:
                    decoded = subprocess.run(
                        [
                            args.ffmpeg,
                            "-hide_banner",
                            "-xerror",
                            "-i",
                            str(video_path),
                            "-f",
                            "null",
                            "-",
                        ],
                        capture_output=True,
                        check=False,
                        text=True,
                        timeout=90,
                    )
                    assert decoded.returncode == 0, "Full video decode failed"
                    assert "Unknown-sized element" not in decoded.stderr, "Invalid Cluster nesting"
                    duration = re.findall(r"time=(\d+):(\d+):([\d.]+)", decoded.stderr)[-1]
                    duration_seconds = (
                        int(duration[0]) * 3600 + int(duration[1]) * 60 + float(duration[2])
                    )
                    assert abs(duration_seconds - metadata["duration"]) < 1
                    frames = int(re.findall(r"frame=\s*(\d+)", decoded.stderr)[-1])
                    result["decoded_duration_seconds"] = duration_seconds
                    result["decoded_frames"] = frames
                    result["average_fps"] = round(frames / duration_seconds, 2)
                    result["ffmpeg_full_decode"] = "PASS"
                    (output / "synthetic-video-decode.txt").write_text(
                        decoded.stderr.replace(str(video_path), video_path.name), encoding="utf-8"
                    )
                else:
                    result["ffmpeg_full_decode"] = "NOT_RUN"
                (output / "qualification.json").write_text(
                    json.dumps(result, indent=2) + "\n", encoding="utf-8"
                )
                browser.close()
                print(json.dumps(result))
        finally:
            stop_fixture(server, directory)
            if worker is not None:
                try:
                    worker.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    worker.terminate()
                    worker.wait(timeout=5)


if __name__ == "__main__":
    main()
