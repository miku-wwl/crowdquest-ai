"""Synthetic OAuth, real consumer API/AIG/SQLite. No genuine human approval claim."""

from contextlib import contextmanager
from functools import partial
from uuid import uuid4

from fastapi.testclient import TestClient

from crowdquest.app import create_app
from crowdquest.intake import Store
from crowdquest.phase3 import production_runtime, provision
from tests.phase3_support import SyntheticProvider
from tests.support import PassiveEventSub, make_auth, notification
from tests.test_phase2 import CHALLENGE
from tests.test_phase2_routes import login


@contextmanager
def http_product(tmp_path, *, owner="123"):
    directory = tmp_path / "p3"
    provision(directory, owner)
    settings, auth, _ = make_auth(tmp_path / "intake")
    store = Store(settings.state_dir / "intake.sqlite3")
    store.ingest(
        notification(),
        owner_id="123",
        session_id="session-1",
        subscription_id="sub-1",
        source="synthetic",
    )
    candidate = store.candidates("123")[0]["id"]
    factory = partial(
        production_runtime,
        directory,
        owner,
        predecessor_stopped=True,
        provider_factory=SyntheticProvider,
    )
    app = create_app(
        settings, auth=auth, store=store, eventsub_factory=PassiveEventSub, phase3_factory=factory
    )
    with TestClient(app, base_url=settings.origin, follow_redirects=False) as client:
        yield client, app, candidate, directory


def full_action(client, candidate, headers):
    proposal = client.post(
        "/api/phase3/candidates/" + candidate + "/generate", json={}, headers=headers
    ).json()
    run = proposal["run"]
    path = "/api/phase3/runs/" + run["run_id"]
    approved = client.post(
        path + "/decision",
        json={"decision": "APPROVE", "expected_version": run["version"]},
        headers=headers,
    ).json()["run"]
    action = client.post(
        path + "/admit",
        json={"expected_version": approved["version"], "idempotency_key": str(uuid4())},
        headers=headers,
    ).json()
    for operation in ["authorize", "execute"]:
        action = client.post(
            "/api/phase3/actions/" + action["action_id"] + "/" + operation,
            json={"expected_version": action["version"], "idempotency_key": str(uuid4())},
            headers=headers,
        ).json()
    return action


def test_full_http_production_flow_worker_and_ack_roles(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, directory):
        headers = login(client)
        assert client.get("/api/me").json()["workflow"] == "production"
        assert (
            client.post(
                "/api/preview", json={"candidate_id": candidate}, headers=headers
            ).status_code
            == 403
        )
        action = full_action(client, candidate, headers)
        assert action["state"] == "Succeeded" and action["rendering"]["state"] == "Waiting"
        assert len(action["admission"]["receipt_hash"]) == 12
        assert "execution_scope" not in str(action)
        pair = client.post("/api/overlay/pair", headers=headers).json()["code"]
        assert (
            client.post("/api/overlays/authorize", json={"code": pair}, headers=headers).status_code
            == 200
        )
        worker_headers = {
            "Origin": "http://localhost:8000",
            "Authorization": "Bearer " + (directory / "worker-token").read_text("ascii"),
        }
        session = client.get("/api/worker/session", headers=worker_headers).json()[
            "server_instance"
        ]
        assert (
            client.post(
                "/api/worker/tick",
                json={"worker_instance": str(uuid4()), "server_instance": session},
                headers=worker_headers,
            ).status_code
            == 200
        )
        view = str(uuid4())
        result = client.get("/api/overlay/current", headers={"X-Overlay-View": view}).json()
        assert result["state"] == "challenge" and result["mode"] == "production"
        assert client.get("/api/overlays").json()["ready"] == 1
        ack = {"render_id": result["render_id"], "delivery_id": result["delivery_id"]}
        assert (
            client.post(
                "/api/overlay/ack", json=ack, headers=headers | {"X-Overlay-View": view}
            ).json()["evidence"]
            == "BROWSER_ACK_ONLY"
        )
        current = client.get("/api/phase3/candidates/" + candidate).json()
        assert current["action"]["rendering"]["state"] == "RENDERED"
        assert current["action"]["rendering"]["acknowledgements"] == 1
        assert (
            client.get("/api/overlay/current", headers={"X-Overlay-View": str(uuid4())}).json()[
                "reason"
            ]
            == "NO_REPLAY"
        )
        assert app.state.store.candidates("123")[0]["state"] == "candidate"  # no intake mutation
        assert (directory / "capability").read_text("ascii") not in str(current)


def test_owner_origin_csrf_extra_authority_and_wrong_channel(tmp_path):
    with http_product(tmp_path) as (client, _, candidate, _):
        path = "/api/phase3/candidates/" + candidate + "/generate"
        assert (
            client.post(path, json={}, headers={"Origin": "http://localhost:8000"}).status_code
            == 401
        )
        headers = login(client)
        assert (
            client.post(path, json={}, headers={"Origin": "http://localhost:8000"}).status_code
            == 403
        )
        assert (
            client.post(
                path, json={}, headers=headers | {"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        # Manual bodies cannot register a tool or choose trusted identity.
        assert (
            client.post(
                "/api/phase3/candidates/" + candidate + "/manual",
                json={"expected_version": 0, "challenge": CHALLENGE, "target": "other"},
                headers=headers,
            ).status_code
            == 422
        )
    with http_product(tmp_path / "other", owner="999") as (client, _, candidate, _):
        headers = login(client)
        assert (
            client.post(
                "/api/phase3/candidates/" + candidate + "/generate", json={}, headers=headers
            ).status_code
            == 403
        )


def test_worker_and_overlay_cannot_gain_owner_authority_or_forge_ack(tmp_path):
    with http_product(tmp_path) as (client, _, candidate, directory):
        headers = login(client)
        assert client.get("/api/worker/session").status_code == 401
        assert (
            client.post(
                "/api/overlay/ack",
                json={"render_id": str(uuid4()), "delivery_id": str(uuid4())},
                headers=headers | {"X-Overlay-View": str(uuid4())},
            ).status_code
            == 401
        )
        client.cookies.delete("cq_owner")
        worker_headers = {
            "Origin": "http://localhost:8000",
            "Authorization": "Bearer " + (directory / "worker-token").read_text("ascii"),
        }
        assert client.get("/api/worker/session", headers=worker_headers).status_code == 200
        assert (
            client.post(
                "/api/phase3/candidates/" + candidate + "/generate", json={}, headers=worker_headers
            ).status_code
            == 401
        )


def test_missing_or_stale_action_authorization_has_zero_effects(tmp_path):
    from contextlib import closing

    with http_product(tmp_path) as (client, app, candidate, _):
        headers = login(client)
        path = "/api/phase3/candidates/" + candidate + "/generate"
        assert client.post(path, json={"tool": "run_shell"}, headers=headers).status_code == 422
        run = client.post(path, json={}, headers=headers).json()["run"]
        base = "/api/phase3/runs/" + run["run_id"]
        approved = client.post(
            base + "/decision",
            json={"decision": "APPROVE", "expected_version": run["version"]},
            headers=headers,
        ).json()["run"]
        action = client.post(
            base + "/admit",
            json={"expected_version": approved["version"], "idempotency_key": str(uuid4())},
            headers=headers,
        ).json()
        action_path = "/api/phase3/actions/" + action["action_id"]
        assert (
            client.post(
                action_path + "/execute",
                json={"expected_version": action["version"], "idempotency_key": str(uuid4())},
                headers=headers,
            ).status_code
            == 409
        )
        assert (
            client.post(
                action_path + "/authorize",
                json={"expected_version": 999, "idempotency_key": str(uuid4())},
                headers=headers,
            ).status_code
            == 409
        )
        service = app.state.phase3_service
        with closing(service.base.store.connect()) as db:
            assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
        with closing(service.renderer.store.connect()) as db:
            assert db.execute("SELECT count(*) FROM renders").fetchone()[0] == 0


def test_logout_stops_worker_and_quarantines_dispatch(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, directory):
        headers = login(client)
        action = full_action(client, candidate, headers)
        service = app.state.phase3_service
        service.renderer.tick(str(uuid4()), service.renderer.boot)
        assert client.post("/api/logout", headers=headers).status_code == 200
        worker_headers = {
            "Authorization": "Bearer " + (directory / "worker-token").read_text("ascii")
        }
        assert client.get("/api/worker/session", headers=worker_headers).status_code == 401
        assert (
            service.renderer.store.summary(service.base.refresh(action["action_id"]).effect_key)[
                "state"
            ]
            == "UNKNOWN"
        )


def test_overlay_storage_failure_is_not_a_ready_heartbeat(tmp_path, monkeypatch):
    import sqlite3

    with http_product(tmp_path) as (client, app, _, _):
        headers = login(client)
        code = client.post("/api/overlay/pair", headers=headers).json()["code"]
        client.post("/api/overlays/authorize", json={"code": code}, headers=headers)

        def unavailable(*args):
            raise sqlite3.OperationalError("Fixture private error must not leave the backend")

        monkeypatch.setattr(app.state.phase3_service.renderer.store, "current", unavailable)
        response = client.get("/api/overlay/current", headers={"X-Overlay-View": str(uuid4())})
        assert (
            response.status_code == 503 and response.json()["detail"] == "RENDER_STATE_UNAVAILABLE"
        )
        assert "private error" not in response.text
        assert client.get("/api/overlays").json()["ready"] == 0
