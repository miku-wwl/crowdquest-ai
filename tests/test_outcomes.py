"""Owner reports cannot change AIG success or replay an executed Action."""

import sqlite3
from contextlib import closing
from uuid import uuid4

import pytest

from tests.phase3_support import product, succeeded, tick
from tests.test_phase2 import LostAckExecutor


@pytest.mark.parametrize("kind", ["Completed", "Failed", "Skipped"])
async def test_outcome_idempotency_display_expiry_reload_and_restart(tmp_path, kind):
    directory = tmp_path / "p3"
    clock = [1000.0, 1800000000.0]
    with product(directory, time_values=clock) as service:
        _, action = await succeeded(service)
        worker = tick(service)
        view = str(uuid4())
        payload = service.renderer.store.current("overlay", view)
        service.renderer.store.acknowledge(
            "overlay", view, payload["render_id"], payload["delivery_id"]
        )
        key = str(uuid4())
        first = service.record_outcome(action.action_id, kind, key)
        assert service.record_outcome(action.action_id, kind, key) == first
        with pytest.raises(ValueError, match="ALREADY_TERMINAL"):
            service.record_outcome(
                action.action_id, "Skipped" if kind != "Skipped" else "Failed", str(uuid4())
            )
        presented = service.renderer.store.current("overlay", view)
        assert presented["state"] == "outcome" and presented["source"] == "OWNER_REPORTED"
        assert presented["outcome"] == kind and presented["remaining_seconds"] == 8
        assert service.renderer.store.current("overlay", str(uuid4()))["state"] == "waiting"
        clock[0] += 3
        tick(service, worker)
        assert service.renderer.store.current("overlay", view)["remaining_seconds"] == 5
        clock[0] += 6
        assert service.renderer.store.current("overlay", view)["state"] == "waiting"
        assert service.base.refresh(action.action_id).state.value == "Succeeded"
        with closing(service.base.store.connect()) as db:
            assert db.execute("SELECT count(*) FROM jobs").fetchone()[0] == 1
    with product(directory, time_values=clock) as restarted:
        assert restarted.renderer.store.outcome(action.effect_key)["kind"] == kind
        assert restarted.renderer.store.current("overlay", str(uuid4()))["state"] == "waiting"
        tick(restarted)
        with closing(restarted.renderer.store.connect()) as db:
            assert db.execute("SELECT count(*) FROM renders").fetchone()[0] == 1


async def test_outcome_requires_confirmed_action_and_ack_not_just_sent(tmp_path):
    with product(tmp_path / "p3") as service:
        _, action = await succeeded(service)
        with pytest.raises(ValueError, match="ACKNOWLEDGED_RENDER"):
            service.record_outcome(action.action_id, "Completed", str(uuid4()))
        tick(service)
        service.renderer.store.current("overlay", str(uuid4()))
        with pytest.raises(ValueError, match="ACKNOWLEDGED_RENDER"):
            service.record_outcome(action.action_id, "Completed", str(uuid4()))


async def test_restart_never_rearms_result_presentation(tmp_path):
    directory = tmp_path / "p3"
    with product(directory) as service:
        _, action = await succeeded(service)
        tick(service)
        view = str(uuid4())
        payload = service.renderer.store.current("overlay", view)
        service.renderer.store.acknowledge(
            "overlay", view, payload["render_id"], payload["delivery_id"]
        )
        service.record_outcome(action.action_id, "Completed", str(uuid4()))
    with product(directory) as restarted:
        assert restarted.renderer.store.current("overlay", str(uuid4()))["state"] == "waiting"
        assert restarted.renderer.store.outcome(action.effect_key)["state"] == "ENDED"


async def test_outcome_lost_commit_ack_preserves_one_immutable_report(tmp_path, monkeypatch):
    with product(tmp_path / "p3") as service:
        _, action = await succeeded(service)
        tick(service)
        store = service.renderer.store
        view = str(uuid4())
        payload = store.current("overlay", view)
        store.acknowledge("overlay", view, payload["render_id"], payload["delivery_id"])
        original = store.connect

        class LostAck:
            def __init__(self):
                self.db = original()

            def __getattr__(self, name):
                return getattr(self.db, name)

            def commit(self):
                self.db.commit()
                raise sqlite3.OperationalError("Fixture outcome commit ack lost")

        monkeypatch.setattr(store, "connect", LostAck)
        key = str(uuid4())
        with pytest.raises(sqlite3.OperationalError, match="commit ack lost"):
            service.record_outcome(action.action_id, "Completed", key)
        monkeypatch.setattr(store, "connect", original)
        assert store.outcome(action.effect_key)["kind"] == "Completed"
        assert service.record_outcome(action.action_id, "Completed", key)["kind"] == "Completed"
        with closing(store.connect()) as db:
            assert db.execute("SELECT count(*) FROM challenge_outcomes").fetchone()[0] == 1
        assert service.base.refresh(action.action_id).state.value == "Succeeded"


async def test_unknown_action_cannot_be_relabelled_as_owner_outcome(tmp_path):
    with product(tmp_path / "p3", executor_factory=LostAckExecutor) as service:
        _, action = await succeeded(service)
        assert action.state.value == "Unknown"
        with pytest.raises(ValueError, match="CONFIRMED_ACTION"):
            service.record_outcome(action.action_id, "Completed", str(uuid4()))
        assert service.renderer.store.outcome(action.effect_key) is None


async def test_wrong_render_payload_cannot_receive_outcome_for_valid_receipt(tmp_path):
    with product(tmp_path / "p3") as service:
        _, action = await succeeded(service)
        tick(service)
        store = service.renderer.store
        view = str(uuid4())
        payload = store.current("overlay", view)
        store.acknowledge("overlay", view, payload["render_id"], payload["delivery_id"])
        with closing(store.connect()) as db:
            db.execute("UPDATE renders SET payload='{}' WHERE effect_key=?", (action.effect_key,))
            db.commit()
        with pytest.raises(ValueError, match="ACKNOWLEDGED_RENDER"):
            service.record_outcome(action.action_id, "Completed", str(uuid4()))
        assert service.base.refresh(action.action_id).state.value == "Succeeded"
