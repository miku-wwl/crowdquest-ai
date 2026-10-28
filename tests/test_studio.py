import builtins
import sqlite3
from contextlib import closing
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from crowdquest.app import create_app
from tests.support import PassiveEventSub, make_auth
from tests.test_phase2_routes import login
from tests.test_phase3_routes import full_action, http_product
from tests.test_phase4_routes import command, prepare


def studio(client, headers):
    response = client.post("/api/studio/connect", headers=headers)
    assert response.status_code == 200
    return {"X-Overlay-View": str(uuid4())}


def test_startup_has_no_obs_import_credentials_or_service_dependency(tmp_path, monkeypatch):
    original = builtins.__import__

    def no_obs(name, *args, **kwargs):
        if name.startswith(("obsws_python", "websocket")) or name in (
            "crowdquest.obs",
            "obs_admin",
        ):
            pytest.fail("Core must not import OBS")
        return original(name, *args, **kwargs)

    settings, auth, _ = make_auth(tmp_path)
    monkeypatch.setattr(builtins, "__import__", no_obs)
    app = create_app(settings, auth=auth, eventsub_factory=PassiveEventSub)
    with TestClient(
        app, base_url=settings.origin, client=("127.0.0.1", 3), follow_redirects=False
    ) as client:
        headers = login(client)
        studio(client, headers)
        state = client.get("/api/studio/status").json()
        assert state["obs_required"] is False and state["worker"] == "not_enabled"
        assert app.state.obs_adapter is None
        assert client.post("/api/obs-admin/login", json={}, headers=headers).status_code == 404


def test_studio_peer_owner_origin_csrf_and_no_record_upload_endpoints(harness):
    client, app = harness["client"], harness["app"]
    assert client.get("/api/studio/status").status_code == 401
    csrf = harness["login"]()
    headers = {"Origin": harness["origin"], "X-CSRF-Token": csrf}
    for bad in ({}, {"Origin": harness["origin"]}, headers | {"Origin": "https://evil.invalid"}):
        assert client.post("/api/studio/connect", headers=bad).status_code == 403
    view = studio(client, headers)
    cookie = client.cookies.get("cq_studio")
    assert client.post("/api/studio/connect", headers=headers).status_code == 200
    assert (
        client.cookies.get("cq_studio") == cookie
    )  # reconnect/reload cannot acquire a new identity
    assert client.get("/api/studio/current", headers=view).json()["state"] == "waiting"
    for endpoint in ("/api/studio/record", "/api/studio/upload", "/api/studio/files/../../secret"):
        assert client.post(endpoint, content=b"private", headers=headers).status_code == 404
    assert "synthetic-access" not in client.get("/api/studio/status").text
    assert client.get("/api/studio/status", headers={"Host": "evil.invalid"}).status_code == 400
    remote = TestClient(app, base_url=harness["origin"], client=("192.168.1.8", 3))
    try:
        assert remote.get("/broadcast-studio").status_code == 403
        assert (
            remote.get("/api/studio/status", headers={"X-Forwarded-For": "127.0.0.1"}).status_code
            == 403
        )
    finally:
        remote.close()


def test_studio_display_consumes_existing_worker_delivery_and_no_replay(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, directory):
        headers = login(client)
        view = studio(client, headers)
        action = full_action(client, candidate, headers)
        service = app.state.phase3_service
        service.renderer.tick(str(uuid4()), service.renderer.boot)
        assert client.get("/api/studio/status").json()["worker"] == "ready"
        value = client.get("/api/studio/current", headers=view).json()
        assert value["state"] == "challenge"
        ack = {"render_id": value["render_id"], "delivery_id": value["delivery_id"]}
        assert (
            client.post(
                "/api/studio/ack", json=ack, headers=view | {"Origin": headers["Origin"]}
            ).status_code
            == 403
        )
        assert client.post("/api/studio/ack", json=ack, headers=view | headers).status_code == 200
        assert client.get("/api/studio/current", headers=view).json()["state"] == "challenge"
        reloaded = {"X-Overlay-View": str(uuid4())}
        assert client.get("/api/studio/current", headers=reloaded).json()["reason"] == "NO_REPLAY"
        response = client.post(
            f"/api/phase4/actions/{action['action_id']}/outcome",
            json={
                "kind": "Skipped",
                "expected_version": action["version"],
                "idempotency_key": str(uuid4()),
            },
            headers=headers,
        )
        assert response.status_code == 200
        result = client.get("/api/studio/current", headers=view).json()
        assert result["state"] == "outcome" and result["outcome"] == "Skipped"
        assert client.get("/api/studio/status").json()["last_outcome"]["kind"] == "Skipped"
        assert client.get("/api/studio/current", headers=reloaded).json()["state"] == "waiting"
        with closing(sqlite3.connect(directory / "overlay.sqlite3")) as db:
            assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1


def test_studio_voting_uses_authoritative_frozen_choices_and_totals(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, _):
        headers = login(client)
        view = studio(client, headers)
        row = command(client, prepare(client, app, candidate, headers), "start", headers)
        data = client.get("/api/studio/current", headers=view).json()
        assert data["state"] == "voting"
        assert data["round"]["total_votes"] == 0
        assert all("candidate_id" not in choice for choice in data["round"]["choices"])
        command(client, row, "close", headers)
        assert client.get("/api/studio/current", headers=view).json()["state"] == "winner"
