"""Authenticated HTTP integration with fixture OAuth and real installed AIG/SQLite."""

from contextlib import contextmanager
from functools import partial
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from fastapi.testclient import TestClient
from filelock import FileLock

from crowdquest.app import create_app
from crowdquest.phase2 import challenge_runtime, provision
from tests.support import PassiveEventSub, make_auth
from tests.test_phase2 import CHALLENGE


@contextmanager
def http_harness(tmp_path, owner_id="123"):
    directory = tmp_path / "phase2"
    provision(directory, owner_id)
    settings, auth, _ = make_auth(tmp_path / "phase1")
    factory = partial(challenge_runtime, directory, owner_id, predecessor_stopped=True)
    app = create_app(settings, auth=auth, eventsub_factory=PassiveEventSub, phase2_factory=factory)
    with TestClient(app, base_url=settings.origin, follow_redirects=False) as client:
        yield client, app, directory


def login(client):
    start = client.get("/auth/twitch/start")
    state = parse_qs(urlsplit(start.headers["location"]).query)["state"][0]
    result = client.get("/auth/twitch/callback", params={"state": state, "code": "synthetic"})
    assert result.status_code == 303
    csrf = client.get("/api/me").json()["csrf"]
    return {"Origin": "http://localhost:8000", "X-CSRF-Token": csrf}


def command(version):
    return {"expected_version": version, "idempotency_key": str(uuid4())}


def test_http_owner_gates_exact_approval_separate_grant_and_receipt(tmp_path):
    with http_harness(tmp_path) as (client, app, directory):
        base = "/api/phase2"
        assert (
            client.post(
                base + "/runs", json=CHALLENGE, headers={"Origin": "http://localhost:8000"}
            ).status_code
            == 401
        )
        headers = login(client)
        assert (
            client.post(
                base + "/runs", json=CHALLENGE, headers={"Origin": "http://localhost:8000"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                base + "/runs", json=CHALLENGE, headers=headers | {"Origin": "https://evil.example"}
            ).status_code
            == 403
        )
        assert (
            client.post(
                base + "/runs", json=CHALLENGE | {"binding": "viewer-selected"}, headers=headers
            ).status_code
            == 422
        )
        created = client.post(base + "/runs", json=CHALLENGE, headers=headers)
        assert created.status_code == 200
        assert created.json()["planning_mode"] == "OFFLINE_MANUAL"
        run = created.json()["run"]
        run_path = base + "/runs/" + run["run_id"]
        assert client.get(run_path).json()["run"]["plan"]["steps"][0]["arguments"] == CHALLENGE
        assert (
            client.post(
                run_path + "/admit", json=command(run["version"]), headers=headers
            ).status_code
            == 409
        )
        assert (
            client.post(
                run_path + "/decision",
                json={"decision": "APPROVE", "expected_version": run["version"] - 1},
                headers=headers,
            ).status_code
            == 409
        )
        approved = client.post(
            run_path + "/decision",
            json={"decision": "APPROVE", "expected_version": run["version"]},
            headers=headers,
        ).json()["run"]
        admitted = client.post(
            run_path + "/admit", json=command(approved["version"]), headers=headers
        ).json()
        assert admitted["admission"] is None
        action = admitted["action"]
        action_path = base + "/actions/" + action["action_id"]
        assert (
            client.post(
                action_path + "/execute", json=command(action["version"]), headers=headers
            ).status_code
            == 409
        )
        grant = client.post(
            action_path + "/authorize", json=command(action["version"]), headers=headers
        ).json()["action"]
        key = command(grant["version"])
        executed = client.post(action_path + "/execute", json=key, headers=headers)
        assert executed.status_code == 200
        data = executed.json()
        assert data["action"]["state"] == "Succeeded"
        assert data["admission"]["state"] == "ELIGIBLE" and data["rendering"] == "NOT_RUN"
        assert client.post(action_path + "/execute", json=key, headers=headers).json() == data
        assert client.get(action_path).json() == data
        # Runtime authority is backend-only, unrelated to fixture Twitch/owner cookies.
        assert (directory / "capability").read_text("ascii") not in executed.text
        assert "synthetic-access" not in executed.text
        assert app.state.phase2_service is not None
        client.cookies.delete("cq_owner")
        assert client.get(action_path).status_code == 401


def test_valid_twitch_owner_cannot_control_other_channel_phase2(tmp_path):
    with http_harness(tmp_path, owner_id="999") as (client, _, _):
        headers = login(client)  # fixture identity is broadcaster 123
        response = client.post("/api/phase2/runs", json=CHALLENGE, headers=headers)
        assert response.status_code == 403
        assert response.json()["detail"] == "PHASE2_OWNER_MISMATCH"


def test_phase2_is_absent_from_default_app(harness):
    assert harness["client"].get("/api/phase2/runs/" + str(uuid4())).status_code == 404


def test_phase2_startup_failure_releases_application_owner_lock(tmp_path):
    settings, auth, _ = make_auth(tmp_path)

    @contextmanager
    def broken_factory():
        raise ValueError("Test-owned startup fault")
        yield  # pragma: no cover

    app = create_app(
        settings, auth=auth, eventsub_factory=PassiveEventSub, phase2_factory=broken_factory
    )
    try:
        with TestClient(app, base_url=settings.origin):
            raise AssertionError("startup should fail")
    except ValueError as error:
        assert str(error) == "Test-owned startup fault"
    with FileLock(settings.state_dir / "phase1.lock").acquire(timeout=0):
        pass
