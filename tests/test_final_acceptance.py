import asyncio
import json
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from crowdquest.app import create_app
from crowdquest.eventsub import EventSub
from crowdquest.intake import Store
from tests.support import PassiveEventSub, make_auth, notification
from tests.test_app import headers, pair
from tests.test_auth import state_for
from tests.test_eventsub import Socket, envelope, welcome


def test_pair_code_one_use_and_bounded_guesses(harness):
    h = harness
    csrf = h["login"]()
    client = h["client"]
    code = client.post("/api/overlay/pair", headers=headers(h, csrf)).json()["code"]
    assert len(code) == 16 and all(c in "0123456789ABCDEF" for c in code)
    for _ in range(5):
        assert (
            client.post(
                "/api/overlays/authorize",
                json={
                    "code": "FFFFFFFFFFFFFFFF" if code != "FFFFFFFFFFFFFFFF" else "0000000000000000"
                },
                headers=headers(h, csrf),
            ).status_code
            == 404
        )
    assert (
        client.post(
            "/api/overlays/authorize", json={"code": code}, headers=headers(h, csrf)
        ).status_code
        == 429
    )
    h["clock"][0] += 61
    assert (
        client.post(
            "/api/overlays/authorize", json={"code": code}, headers=headers(h, csrf)
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/api/overlays/authorize", json={"code": code}, headers=headers(h, csrf)
        ).status_code
        == 409
    )
    assert client.get("/api/overlays").json()["ready"] == 0
    h["clock"][0] += 6 * 3600 + 1
    assert (
        client.get("/api/overlay/current", headers={"X-Overlay-View": str(uuid4())}).status_code
        == 401
    )


def test_pending_code_expiry_and_pairing_csrf(harness):
    h = harness
    csrf = h["login"]()
    client = h["client"]
    code = client.post("/api/overlay/pair", headers=headers(h, csrf)).json()["code"]
    assert (
        client.post(
            "/api/overlays/authorize", json={"code": code}, headers=headers(h, "wrong")
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/overlays/authorize",
            json={"code": code},
            headers={"Origin": "https://evil.example", "X-CSRF-Token": csrf},
        ).status_code
        == 403
    )
    h["clock"][0] += 301
    assert (
        client.post(
            "/api/overlays/authorize", json={"code": code}, headers=headers(h, csrf)
        ).status_code
        == 404
    )


def test_only_owner_can_pair_and_cookie_is_read_only(harness):
    h = harness
    csrf = h["login"]()
    client = h["client"]
    code = client.post("/api/overlay/pair", headers=headers(h, csrf)).json()["code"]
    cookie = next(c for c in client.cookies.jar if c.name == "cq_overlay")
    assert cookie.has_nonstandard_attr("HttpOnly") and cookie.path == "/api/overlay"
    assert cookie.get_nonstandard_attr("SameSite") == "strict"
    assert len(cookie.value) >= 43
    client.cookies.delete("cq_owner")
    assert (
        client.post(
            "/api/overlays/authorize", json={"code": code}, headers=headers(h, csrf)
        ).status_code
        == 401
    )


def test_two_overlay_sessions_clear_expiry_and_repeat_preview(harness):
    h = harness
    csrf, candidate = h["login"](), h["seed"]()
    client = h["client"]
    overlay_headers = []
    for _ in range(2):
        pair(h, csrf)
        token = client.cookies.get("cq_overlay")
        view = {"X-Overlay-View": str(uuid4()), "Cookie": f"cq_overlay={token}"}
        assert client.get("/api/overlay/current", headers=view).json()["state"] == "waiting"
        overlay_headers.append(view)
        client.cookies.delete("cq_overlay")

    def preview():
        return client.post(
            "/api/preview", json={"candidate_id": candidate}, headers=headers(h, csrf)
        )

    assert preview().status_code == 200
    for view in overlay_headers:
        body = client.get("/api/overlay/current", headers=view).json()
        assert body["text"] == "Survive 60 seconds" and body["remaining_seconds"] == 60
    h["clock"][0] += 59
    assert (
        client.get("/api/overlay/current", headers=overlay_headers[0]).json()["remaining_seconds"]
        == 1
    )
    assert (
        preview().status_code == 200
    )  # Deliberate repeat replaces the preview with a fresh 60s window.
    assert (
        client.get("/api/overlay/current", headers=overlay_headers[0]).json()["remaining_seconds"]
        == 60
    )
    client.post("/api/preview/clear", headers=headers(h, csrf))
    assert all(
        client.get("/api/overlay/current", headers=view).json()["state"] == "waiting"
        for view in overlay_headers
    )
    assert preview().status_code == 200
    h["clock"][0] += 60
    assert all(
        client.get("/api/overlay/current", headers=view).json()["state"] == "waiting"
        for view in overlay_headers
    )


@pytest.mark.parametrize("jump", [-86400, 86400])
def test_preview_uses_monotonic_time_when_server_wall_clock_jumps(tmp_path, jump):
    wall, mono = [1_800_000_000.0], [1000.0]
    settings, auth, _ = make_auth(tmp_path, clock=lambda: wall[0])
    store = Store(tmp_path / "intake.sqlite3")
    store.ingest(
        notification(now=wall[0]),
        owner_id="123",
        session_id="session-1",
        subscription_id="sub-1",
        now=wall[0],
        source="synthetic",
    )
    app = create_app(
        settings,
        auth=auth,
        store=store,
        eventsub_factory=PassiveEventSub,
        clock=lambda: wall[0],
        monotonic=lambda: mono[0],
    )
    with TestClient(app, base_url=settings.origin, follow_redirects=False) as client:
        state = parse_qs(urlsplit(client.get("/auth/twitch/start").headers["location"]).query)[
            "state"
        ][0]
        client.get("/auth/twitch/callback", params={"state": state, "code": "synthetic-code"})
        csrf = client.get("/api/me").json()["csrf"]
        h = {"client": client, "origin": settings.origin}
        view = pair(h, csrf)
        client.get("/api/overlay/current", headers=view)
        candidate = store.candidates("123")[0]["id"]
        client.post("/api/preview", json={"candidate_id": candidate}, headers=headers(h, csrf))
        wall[0] += jump
        mono[0] += 59
        assert client.get("/api/overlay/current", headers=view).json()["remaining_seconds"] == 1
        mono[0] += 1
        assert client.get("/api/overlay/current", headers=view).json()["state"] == "waiting"


async def test_temporary_validation_error_retains_consent_and_recovers(tmp_path):
    clock = [10000.0]
    _, auth, mock = make_auth(tmp_path, clock=lambda: clock[0])
    await auth.callback(*state_for(auth), "synthetic-code")
    generation, saved = auth.generation, auth.vault.get("tokens")
    auth.validated_at = 0
    mock.validate_status = 503
    assert await auth.ensure() is None
    assert auth.identity is None and auth.generation == generation
    assert auth.vault.get("tokens") == saved
    assert auth.reason == "TWITCH_AUTH_TEMPORARILY_UNAVAILABLE"
    calls = len(mock.calls)
    assert await auth.ensure() is None and len(mock.calls) == calls
    mock.validate_status = 200
    clock[0] += 6
    assert await auth.ensure()
    assert auth.generation == generation
    await auth.close()


async def test_rotated_refresh_is_persisted_before_transient_validation(tmp_path):
    clock = [10000.0]
    _, auth, mock = make_auth(tmp_path, clock=lambda: clock[0])
    await auth.callback(*state_for(auth), "synthetic-code")
    clock[0] += 3541
    mock.token.update(
        access_token="synthetic-rotated-access", refresh_token="synthetic-rotated-refresh"
    )
    mock.validate_status = 503
    assert await auth.ensure() is None
    assert json.loads(auth.vault.get("tokens"))["refresh_token"] == "synthetic-rotated-refresh"
    _, restarted, _ = make_auth(tmp_path, clock=lambda: clock[0])
    restarted.vault = auth.vault
    assert await restarted.ensure()
    await auth.close()
    await restarted.close()


async def test_real_sqlite_write_lock_is_diagnosed_and_new_delivery_recovers(tmp_path, monkeypatch):
    _, auth, _ = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    store = Store(tmp_path / "intake.sqlite3")
    sockets = iter(
        [
            Socket([welcome("session-1"), notification()]),
            Socket(
                [
                    welcome("session-2"),
                    notification(session="session-2"),
                    envelope("revocation", {"subscription": {"id": "sub-1"}}),
                ]
            ),
        ]
    )

    async def connector(*args, **kwargs):
        return next(sockets)

    service = EventSub(auth, store, connector=connector)
    connection = store.connect()
    connection.execute("BEGIN IMMEDIATE")

    async def stop_after_failure(seconds):
        raise asyncio.CancelledError

    try:
        with monkeypatch.context() as patched:
            patched.setattr("crowdquest.eventsub.asyncio.sleep", stop_after_failure)
            with pytest.raises(asyncio.CancelledError):
                await service.run()
        assert service.snapshot()["last_failure"]["sqlite_errorname"] == "SQLITE_BUSY"
        assert store.candidates("123") == []
    finally:
        connection.rollback()
        connection.close()
    await service.once()
    assert len(store.candidates("123")) == 1
    await auth.close()
