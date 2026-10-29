"""Persistent display-only dashboard session boundaries; all data is temporary fixture state."""

import sqlite3
from contextlib import closing
from uuid import uuid4

from tests.support import notification
from tests.test_phase2_routes import login
from tests.test_phase3_routes import full_action, http_product


def add_candidate(store, *, delivery, message, viewer, text):
    return store.ingest(
        notification(delivery=delivery, message=message, viewer=viewer, text=text),
        owner_id="123",
        session_id="session-1",
        subscription_id="sub-1",
        source="synthetic",
    )


def post_round(client, headers, candidates):
    response = client.post(
        "/api/phase4/rounds",
        json={
            "candidate_ids": candidates,
            "duration_seconds": 30,
            "idempotency_key": str(uuid4()),
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["round"]


def command(client, headers, round_, operation, **extra):
    response = client.post(
        f"/api/phase4/rounds/{round_['id']}/{operation}",
        json={
            "expected_version": round_["version"],
            "idempotency_key": str(uuid4()),
            **extra,
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()["round"]


def test_clear_hides_old_candidates_and_closed_vote_but_preserves_history(tmp_path):
    with http_product(tmp_path) as (client, app, first, _):
        headers = login(client)
        assert (
            add_candidate(
                app.state.store,
                delivery="old-delivery",
                message="old-chat",
                viewer="789",
                text="!quest Old second idea",
            )
            == "ACCEPTED"
        )
        ids = [item["id"] for item in app.state.store.candidates("123")]
        round_ = post_round(client, headers, ids)
        round_ = command(client, headers, round_, "start")
        assert (
            add_candidate(
                app.state.store,
                delivery="old-vote-delivery",
                message="old-vote-chat",
                viewer="790",
                text="!vote 1",
            )
            == "VOTE_ACCEPTED"
        )
        round_ = command(client, headers, round_, "close")
        assert round_["state"] == "Closed"
        assert client.get("/api/phase4/voting").json()["round"]["id"] == round_["id"]

        response = client.post("/api/demo/session/clear", headers=headers)
        assert response.status_code == 200, response.text
        session = response.json()["session"]
        assert session["generation"] == 1
        assert session["candidate_after"] > 0 and session["round_after"] > 0
        # A second read represents a page refresh: the DB-backed session survives it.
        assert client.get("/api/demo/session").json()["session"] == session
        assert client.get("/api/candidates").json() == {"session": session, "candidates": []}
        assert client.get("/api/phase4/voting").json()["round"] is None
        assert client.get(f"/api/phase3/candidates/{first}").status_code == 404
        assert client.get(f"/api/phase3/candidates/{ids[0]}").status_code == 404
        assert (
            client.post(
                f"/api/phase4/rounds/{round_['id']}/winner",
                json={
                    "expected_version": round_["version"],
                    "idempotency_key": str(uuid4()),
                    "choice": 1,
                },
                headers=headers,
            ).status_code
            == 409
        )

        with closing(sqlite3.connect(app.state.store.path)) as db:
            assert db.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
            assert db.execute("SELECT count(*) FROM candidates").fetchone()[0] == 2
            assert db.execute("SELECT count(*) FROM deliveries").fetchone()[0] == 3
            assert db.execute("SELECT count(*) FROM crowd_votes").fetchone()[0] == 1
            assert (
                db.execute(
                    "SELECT count(*) FROM voting_rounds WHERE id=? AND state='Closed'",
                    (round_["id"],),
                ).fetchone()[0]
                == 1
            )
            assert (
                db.execute("SELECT count(*) FROM voting_audit WHERE channel='123'").fetchone()[0]
                >= 3
            )

        assert (
            add_candidate(
                app.state.store,
                delivery="new-delivery-1",
                message="new-chat-1",
                viewer="801",
                text="!quest New first idea",
            )
            == "ACCEPTED"
        )
        assert (
            add_candidate(
                app.state.store,
                delivery="new-delivery-2",
                message="new-chat-2",
                viewer="802",
                text="!quest New second idea",
            )
            == "ACCEPTED"
        )
        current = client.get("/api/candidates").json()
        assert [item["suggestion"] for item in current["candidates"]] == [
            "New second idea",
            "New first idea",
        ]
        fresh_ids = [item["id"] for item in current["candidates"]]
        fresh_round = post_round(client, headers, fresh_ids)
        assert client.get("/api/phase4/voting").json()["round"]["id"] == fresh_round["id"]
        fresh_round = command(client, headers, fresh_round, "start")
        assert (
            add_candidate(
                app.state.store,
                delivery="new-vote-delivery",
                message="new-vote-chat",
                viewer="803",
                text="!vote 2",
            )
            == "VOTE_ACCEPTED"
        )
        assert client.get("/api/phase4/voting").json()["round"]["total_votes"] == 1


def test_demo_reset_requires_owner_csrf_and_refuses_active_vote(tmp_path):
    with http_product(tmp_path) as (client, app, _, _):
        assert (
            client.post(
                "/api/demo/session/clear", headers={"Origin": "http://localhost:8000"}
            ).status_code
            == 401
        )
        headers = login(client)
        assert (
            client.post(
                "/api/demo/session/clear", headers={"Origin": headers["Origin"]}
            ).status_code
            == 403
        )
        second = add_candidate(
            app.state.store,
            delivery="active-delivery",
            message="active-chat",
            viewer="789",
            text="!quest Active second idea",
        )
        assert second == "ACCEPTED"
        ids = [item["id"] for item in app.state.store.candidates("123")]
        round_ = command(client, headers, post_round(client, headers, ids), "start")
        response = client.post("/api/demo/session/clear", headers=headers)
        assert response.status_code == 409
        assert response.json()["detail"] == "DEMO_HISTORY_RESET_BUSY"
        assert client.get("/api/demo/session").json()["session"]["generation"] == 0
        assert len(client.get("/api/candidates").json()["candidates"]) == 2
        assert client.get("/api/phase4/voting").json()["round"]["id"] == round_["id"]


def test_demo_reset_waits_for_an_eligible_worker_job_to_be_claimed(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, _):
        headers = login(client)
        action = full_action(client, candidate, headers)
        service = app.state.phase3_service
        with closing(service.base.store.connect()) as db:
            job = db.execute("SELECT state FROM jobs").fetchone()[0]
        with closing(service.renderer.store.connect()) as db:
            assert db.execute("SELECT count(*) FROM renders").fetchone()[0] == 0
        assert job == "ELIGIBLE"
        response = client.post("/api/demo/session/clear", headers=headers)
        assert response.status_code == 409
        assert response.json()["detail"] == "DEMO_HISTORY_RESET_BUSY"
        assert client.get("/api/candidates").json()["candidates"][0]["id"] == candidate
        assert service.base.refresh(action["action_id"]).state.value == "Succeeded"


def test_clear_hides_old_plan_and_never_replays_terminal_unknown(tmp_path):
    with http_product(tmp_path) as (client, app, candidate, _):
        headers = login(client)
        # A synthetic AIG Action and browser delivery exercise preservation only.
        # This fixture does not contact Twitch or create a production Action.
        action = full_action(client, candidate, headers)
        service = app.state.phase3_service
        service.renderer.tick(str(uuid4()), service.renderer.boot)
        pair_code = client.post("/api/overlay/pair", headers=headers).json()["code"]
        assert (
            client.post(
                "/api/overlays/authorize", json={"code": pair_code}, headers=headers
            ).status_code
            == 200
        )
        view = str(uuid4())
        delivery = client.get("/api/overlay/current", headers={"X-Overlay-View": view}).json()
        assert delivery["state"] == "challenge"
        original_monotonic = service.renderer.store.monotonic
        service.renderer.store.monotonic = lambda: original_monotonic() + 6
        service.renderer.store.maintain()
        service.renderer.store.monotonic = original_monotonic
        action_state = service.base.refresh(action["action_id"]).state.value
        assert action_state == "Succeeded"
        assert (
            service.snapshot(service.base.refresh(action["action_id"]))["rendering"]["state"]
            == "UNKNOWN"
        )

        response = client.post("/api/demo/session/clear", headers=headers)
        assert response.status_code == 200, response.text
        assert client.get(f"/api/phase3/candidates/{candidate}").status_code == 404
        assert client.get("/api/candidates").json()["candidates"] == []
        replay = client.get("/api/overlay/current", headers={"X-Overlay-View": str(uuid4())}).json()
        assert replay["state"] == "unknown"
        assert (
            service.snapshot(service.base.refresh(action["action_id"]))["rendering"]["state"]
            == "UNKNOWN"
        )
        with closing(service.renderer.store.connect()) as db:
            assert db.execute("SELECT state FROM renders").fetchone()[0] == "UNKNOWN"
            assert db.execute("SELECT status FROM observations").fetchone()[0] == "UNKNOWN"
        with closing(service.base.store.connect()) as db:
            assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
        assert (
            client.post(
                f"/api/phase3/actions/{action['action_id']}/execute",
                json={"expected_version": action["version"], "idempotency_key": str(uuid4())},
                headers=headers,
            ).status_code
            == 409
        )
