"""Real HTTP authentication/control boundaries, installed AIG; synthetic owner/chat/model."""

import json
from contextlib import closing
from uuid import uuid4

import pytest

from tests.support import notification
from tests.test_phase2_routes import login
from tests.test_phase3_routes import full_action, http_product


def prepare(client, app, candidate, headers):
    store = app.state.store
    assert (
        store.ingest(
            notification(
                delivery="second", message="second", viewer="789", text="!quest Second challenge"
            ),
            owner_id="123",
            session_id="session-1",
            subscription_id="sub-1",
            source="synthetic",
        )
        == "ACCEPTED"
    )
    second = next(c["id"] for c in store.candidates("123") if c["id"] != candidate)
    result = client.post(
        "/api/phase4/rounds",
        json={
            "candidate_ids": [candidate, second],
            "duration_seconds": 30,
            "idempotency_key": str(uuid4()),
        },
        headers=headers,
    )
    assert result.status_code == 200, result.text
    return result.json()["round"]


def command(client, row, operation, headers, **extra):
    response = client.post(
        f"/api/phase4/rounds/{row['id']}/{operation}",
        json={"expected_version": row["version"], "idempotency_key": str(uuid4()), **extra},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["round"]


def test_owner_csrf_origin_and_overlay_cannot_manage_rounds(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, _):
        assert client.get("/api/phase4/voting").status_code == 401
        headers = login(client)
        row = prepare(client, app, candidate, headers)
        payload = {"expected_version": row["version"], "idempotency_key": str(uuid4())}
        path = f"/api/phase4/rounds/{row['id']}/start"
        assert client.post(path, json=payload).status_code == 403
        assert (
            client.post(path, json=payload, headers={"Origin": headers["Origin"]}).status_code
            == 403
        )
        assert (
            client.post(
                path, json=payload, headers=headers | {"Origin": "https://attacker.invalid"}
            ).status_code
            == 403
        )
        client.cookies.delete("cq_owner")
        assert client.post(path, json=payload, headers=headers).status_code == 401
        assert app.state.store.voting.current("123")["state"] == "Draft"


def test_vote_winner_plan_binding_and_four_independent_gates(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, directory):
        headers = login(client)
        row = command(client, prepare(client, app, candidate, headers), "start", headers)
        assert (
            client.post(
                f"/api/phase3/candidates/{candidate}/generate", json={}, headers=headers
            ).status_code
            == 409
        )
        store = app.state.store
        assert (
            store.ingest(
                notification(delivery="vote", message="vote", text="!vote 2"),
                owner_id="123",
                session_id="session-1",
                subscription_id="sub-1",
                source="synthetic",
            )
            == "VOTE_ACCEPTED"
        )
        row = command(client, row, "close", headers)
        winner = row["choices"][1]["candidate_id"]
        response = client.post(
            f"/api/phase4/rounds/{row['id']}/plan",
            json={"expected_version": row["version"]},
            headers=headers,
        )
        assert response.status_code == 200, response.text
        proposal = response.json()["proposal"]
        assert response.json()["candidate_id"] == winner
        assert proposal["audience_selected"] and proposal["provenance"]["voting_round"] == row["id"]
        assert proposal["provenance"]["source"] == "SYNTHETIC_TEST"
        # Verify the frozen winner's exact suggestion crossed the provider boundary.
        assert (
            json.loads(app.state.phase3_service.base.runtime.planning.provider.last_intent)[
                "suggestion"
            ]
            == row["choices"][1]["text"]
        )
        assert proposal["run"]["state"] == "AwaitingApproval" and proposal["action"] is None
        assert (
            client.post(
                f"/api/phase4/rounds/{row['id']}/plan",
                json={"expected_version": row["version"]},
                headers=headers,
            ).status_code
            == 409
        )
        with closing(app.state.phase3_service.base.store.connect()) as db:
            assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 0
        assert client.get(f"/api/phase3/candidates/{candidate}").json()["run"] is None
        # Exact schema and trusted sole-tool composition remain unchanged.
        step = proposal["run"]["plan"]["steps"][0]
        assert step["tool_name"] == "enqueue_overlay_challenge"
        assert set(step["arguments"]) == {"title", "description", "duration_seconds", "difficulty"}
        assert (directory / "capability").read_text("ascii") not in json.dumps(response.json())


@pytest.mark.parametrize(
    "extra",
    [
        {"deadline": 123},
        {"votes": [4, 7]},
        {"duration_seconds": 15.0},
        {"duration_seconds": True},
        {"duration_seconds": 999},
    ],
)
def test_client_cannot_supply_deadlines_tallies_or_invalid_duration(tmp_path, extra):
    with http_product(tmp_path) as (client, _, candidate, _):
        headers = login(client)
        payload = {
            "candidate_ids": [candidate, str(uuid4())],
            "duration_seconds": 30,
            "idempotency_key": str(uuid4()),
            **extra,
        }
        assert client.post("/api/phase4/rounds", json=payload, headers=headers).status_code == 422


def test_overlay_voting_is_read_only_and_redacted(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, directory):
        headers = login(client)
        row = command(client, prepare(client, app, candidate, headers), "start", headers)
        code = client.post("/api/overlay/pair", headers=headers).json()["code"]
        client.post("/api/overlays/authorize", json={"code": code}, headers=headers)
        client.cookies.delete("cq_owner")
        result = client.get("/api/overlay/current", headers={"X-Overlay-View": str(uuid4())})
        assert result.status_code == 200 and result.json()["state"] == "voting"
        value = result.json()
        assert "candidate_id" not in result.text and "voter" not in result.text
        assert (directory / "capability").read_text("ascii") not in result.text
        assert "execution_scope" not in result.text and row["id"] not in result.text
        assert (
            client.post(
                f"/api/phase4/rounds/{row['id']}/close",
                json={"expected_version": row["version"], "idempotency_key": str(uuid4())},
                headers=headers,
            ).status_code
            == 401
        )
        assert value["round"]["choices"][0]["text"]


def test_outcome_owner_csrf_receipt_and_aig_result(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, _):
        headers = login(client)
        action = full_action(client, candidate, headers)
        path = f"/api/phase4/actions/{action['action_id']}/outcome"
        payload = {
            "kind": "Completed",
            "expected_version": action["version"],
            "idempotency_key": str(uuid4()),
        }
        assert client.post(path, json=payload, headers=headers).status_code == 409
        renderer = app.state.phase3_service.renderer
        renderer.tick(str(uuid4()), renderer.boot)
        view = str(uuid4())
        rendered = renderer.store.current("fixture-overlay", view)
        renderer.store.acknowledge(
            "fixture-overlay", view, rendered["render_id"], rendered["delivery_id"]
        )
        assert client.post(path, json=payload).status_code == 403
        assert client.post(path, json=payload, headers=headers).status_code == 200
        assert client.post(path, json=payload, headers=headers).status_code == 200
        assert (
            client.post(
                path,
                json=payload | {"kind": "Failed", "idempotency_key": str(uuid4())},
                headers=headers,
            ).status_code
            == 409
        )
        current = client.get(f"/api/phase3/candidates/{candidate}").json()["action"]
        assert (
            current["state"] == "Succeeded"
            and current["rendering"]["outcome"]["kind"] == "Completed"
        )
        with closing(app.state.phase3_service.base.store.connect()) as db:
            assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1


def test_wrong_channel_product_cannot_access_voting(tmp_path):
    with http_product(tmp_path, owner="999") as (client, _, _, _):
        login(client)
        assert client.get("/api/phase4/voting").status_code == 403


def test_tie_choice_rejects_boolean_or_model_authority(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, _):
        headers = login(client)
        row = command(client, prepare(client, app, candidate, headers), "start", headers)
        row = command(client, row, "close", headers)
        path = f"/api/phase4/rounds/{row['id']}/winner"
        payload = {
            "expected_version": row["version"],
            "idempotency_key": str(uuid4()),
            "choice": True,
        }
        assert client.post(path, json=payload, headers=headers).status_code == 422
        assert (
            client.post(
                path, json=payload | {"choice": 1, "authorize": True}, headers=headers
            ).status_code
            == 422
        )
