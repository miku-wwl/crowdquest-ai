"""Phase 3 durability/worker assertions. No live Twitch or human consent is claimed."""

import asyncio
import sqlite3
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from uuid import uuid4

import pytest

from crowdquest.admission import AdmissionExecutor
from crowdquest.product import GenerationBusy
from tests.phase3_support import SyntheticProvider, product, succeeded, tick
from tests.test_phase2 import CHALLENGE, LostAckExecutor


def rows(service, table):
    with closing(service.renderer.store.connect()) as db:
        return db.execute("SELECT count(*) FROM " + table).fetchone()[0]


async def test_distinct_review_authorization_execution_and_render_ack(tmp_path):
    with product(tmp_path / "p3") as service:
        _, action = await succeeded(service)
        assert action.state.value == "Succeeded"
        assert rows(service, "renders") == 0
        tick(service)
        assert rows(service, "renders") == 1
        payload = service.renderer.store.current("overlay-hash", str(uuid4()))
        assert payload["state"] == "challenge"
        assert payload["challenge"] == CHALLENGE
        assert "effect_key" not in payload and "receipt" not in payload
        assert service.snapshot(action)["rendering"]["state"] == "SENT"


async def test_reject_has_no_admission_and_old_approval_cannot_cross_manual_edit(tmp_path):
    with product(tmp_path / "p3") as service:
        candidate = {"id": str(uuid4()), "suggestion": "Synthetic suggestion"}
        first = await service.generate(candidate)
        run = first["run"]
        approved = service.decide(run["run_id"], run["version"], "APPROVE", "123")
        edited = await service.manual(
            candidate["id"], CHALLENGE | {"title": "Edited draft"}, approved.version
        )
        assert edited["run"]["state"] == "AwaitingApproval"
        with pytest.raises(ValueError, match="STALE_PROPOSAL"):
            service.admit(approved.run_id, approved.version, str(uuid4()))
        new = edited["run"]
        service.decide(new["run_id"], new["version"], "REJECT", "123")
        with pytest.raises(ValueError, match="EXACT_OWNER_REVIEW_REQUIRED"):
            service.admit(new["run_id"], service.base.run(new["run_id"]).version, str(uuid4()))
        tick(service)
        assert rows(service, "renders") == 0


async def test_generation_is_one_attempt_per_candidate_and_admitted_cannot_be_replaced(tmp_path):
    with product(tmp_path / "p3") as service:
        candidate, action = await succeeded(service)
        with pytest.raises(Exception, match="UNIQUE"):
            await service.generate(candidate)
        with pytest.raises(ValueError, match="NO_REPLACEMENT"):
            await service.manual(
                candidate["id"], CHALLENGE, service.base.run(action.spec.run_id).version
            )
        assert service.base.runtime.planning.provider.calls == 1


async def test_local_model_concurrency_is_bounded_without_reserving_second_candidate(tmp_path):
    entered, release = asyncio.Event(), asyncio.Event()

    class Paused(SyntheticProvider):
        async def generate_plan(self, intent, **kwargs):
            entered.set()
            await release.wait()
            return await super().generate_plan(intent, **kwargs)

    with product(tmp_path / "p3", provider_factory=Paused) as service:
        first = asyncio.create_task(service.generate({"id": str(uuid4()), "suggestion": "first"}))
        await asyncio.wait_for(entered.wait(), 3)
        second = {"id": str(uuid4()), "suggestion": "second"}
        try:
            with pytest.raises(GenerationBusy):
                await service.generate(second)
            assert service.proposals.item(second["id"]) is None
        finally:
            release.set()
        await first
        await service.generate(second)  # A new explicit request, never an automatic retry.
        assert service.base.runtime.planning.provider.calls == 2


async def test_unknown_aig_action_never_creates_a_render(tmp_path):
    with product(tmp_path / "p3", executor_factory=LostAckExecutor) as service:
        _, action = await succeeded(service)
        assert action.state.value == "Unknown"
        tick(service)
        assert rows(service, "renders") == 0
        assert service.base.store.job(action.effect_key)["state"] == "QUARANTINED"


async def test_unconfirmed_inflight_job_is_not_rendered(tmp_path):
    committed, release = asyncio.Event(), asyncio.Event()

    class Barrier(AdmissionExecutor):
        async def execute(self, spec, key, context):
            result = await super().execute(spec, key, context)
            committed.set()
            await release.wait()
            return result

    with product(tmp_path / "p3", executor_factory=Barrier) as service:
        task = asyncio.create_task(succeeded(service))
        await asyncio.wait_for(committed.wait(), 3)
        try:
            worker = tick(service)
            assert rows(service, "renders") == 0
        finally:
            release.set()
        _, action = await task
        assert action.state.value == "Succeeded"
        tick(service, worker)
        assert rows(service, "renders") == 1


async def test_dispatch_commit_lost_ack_is_not_republished(tmp_path, monkeypatch):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "p3", time_values=clock) as service:
        _, action = await succeeded(service)
        original = service.renderer.store.publish

        def lose_ack(*args):
            original(*args)
            raise sqlite3.OperationalError("Fixture dispatch COMMIT acknowledgement lost")

        monkeypatch.setattr(service.renderer.store, "publish", lose_ack)
        with pytest.raises(sqlite3.OperationalError):
            tick(service)
        monkeypatch.setattr(service.renderer.store, "publish", original)
        clock[0] += 6
        tick(service)
        assert service.snapshot(action)["rendering"]["state"] == "UNKNOWN"
        assert rows(service, "renders") == 1


async def test_crash_before_dispatch_marker_is_failed_and_not_retried(tmp_path, monkeypatch):
    directory = tmp_path / "p3"
    with product(directory) as service:
        await succeeded(service)

        def before_dispatch(*args):
            raise RuntimeError("Fixture worker stopped before dispatch COMMIT")

        monkeypatch.setattr(service.renderer.store, "publish", before_dispatch)
        with pytest.raises(RuntimeError, match="before dispatch"):
            tick(service)
    with product(directory) as restarted:
        tick(restarted)
        with closing(restarted.renderer.store.connect()) as db:
            assert db.execute("SELECT state FROM renders").fetchone()[0] == "RENDER_FAILED"
        assert rows(restarted, "renders") == 1


async def test_two_overlays_one_effect_and_refresh_never_replays(tmp_path):
    with product(tmp_path / "p3") as service:
        _, action = await succeeded(service)
        tick(service)
        a, b = str(uuid4()), str(uuid4())
        first = service.renderer.store.current("overlay-a", a)
        second = service.renderer.store.current("overlay-b", b)
        assert (
            first["render_id"] == second["render_id"]
            and first["delivery_id"] != second["delivery_id"]
        )
        for key, view, payload in [("overlay-a", a, first), ("overlay-b", b, second)]:
            service.renderer.store.acknowledge(
                key, view, payload["render_id"], payload["delivery_id"]
            )
        assert service.snapshot(action)["rendering"]["acknowledgements"] == 2
        assert service.renderer.store.current("overlay-a", str(uuid4()))["state"] == "waiting"
        again = service.renderer.store.current("overlay-a", a)
        assert (
            again["render_id"] == first["render_id"]
            and again["remaining_seconds"] <= first["remaining_seconds"]
        )
        assert rows(service, "renders") == 1


async def test_missing_ack_is_terminal_unknown_no_second_payload_or_late_reconciliation(tmp_path):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "p3", time_values=clock) as service:
        _, action = await succeeded(service)
        worker = tick(service)
        view = str(uuid4())
        payload = service.renderer.store.current("a", view)
        assert service.renderer.store.current("a", view)["reason"] == "ACK_PENDING"
        clock[0] += 3
        tick(service, worker)
        clock[0] += 3
        tick(service, worker)
        assert service.snapshot(action)["rendering"]["state"] == "UNKNOWN"
        with pytest.raises(ValueError, match="ACK_REJECTED"):
            service.renderer.store.acknowledge(
                "a", view, payload["render_id"], payload["delivery_id"]
            )
        tick(service, worker)
        assert (
            rows(service, "renders") == 1
            and service.renderer.store.current("a", view)["state"] == "unknown"
        )


@pytest.mark.parametrize("duration", [15, 60, 120])
async def test_countdown_uses_monotonic_clock_and_expires_without_restart(tmp_path, duration):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "p3", time_values=clock) as service:
        _, action = await succeeded(service, challenge=CHALLENGE | {"duration_seconds": duration})
        worker = tick(service)
        view = str(uuid4())
        payload = service.renderer.store.current("a", view)
        service.renderer.store.acknowledge("a", view, payload["render_id"], payload["delivery_id"])
        clock[1] += 86400
        assert service.renderer.store.current("a", view)["remaining_seconds"] == duration
        for _ in range(duration // 3):
            clock[0] += 3
            clock[1] -= 1000
            tick(service, worker)
        assert service.renderer.store.current("a", view)["state"] == "expired"
        assert service.snapshot(action)["rendering"]["state"] == "EXPIRED"
        assert rows(service, "renders") == 1


async def test_worker_races_authentication_and_old_epoch_fenced(tmp_path):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "p3", time_values=clock) as service:
        await succeeded(service)

        def contender():
            try:
                tick(service)
                return True
            except ValueError:
                return False

        with ThreadPoolExecutor(max_workers=2) as pool:
            result = list(pool.map(lambda _: contender(), range(2)))
        assert sum(result) == 1 and rows(service, "renders") == 1
        with pytest.raises(ValueError, match="AUTH_REQUIRED"):
            service.renderer.require_worker("Bearer " + "0" * 64)
        with pytest.raises(ValueError, match="FENCED"):
            service.renderer.tick(str(uuid4()), str(uuid4()))
        clock[0] += 6
        tick(service)
        assert rows(service, "renders") == 1


async def test_forged_ack_and_wrong_receipt_cannot_render(tmp_path):
    with product(tmp_path / "p3") as service:
        _, action = await succeeded(service)
        with closing(service.base.store.connect()) as db:
            db.execute("UPDATE jobs SET receipt=?", (str(uuid4()),))
            db.commit()
        tick(service)
        assert rows(service, "renders") == 0
        with pytest.raises(ValueError, match="ACK_REJECTED"):
            service.renderer.store.acknowledge("other", str(uuid4()), str(uuid4()), str(uuid4()))
        assert service.base.store.job(action.effect_key)["state"] == "QUARANTINED"


async def test_server_restart_quarantines_marked_dispatch_without_replay(tmp_path):
    directory = tmp_path / "p3"
    with product(directory) as service:
        _, action = await succeeded(service)
        tick(service)
        assert service.snapshot(action)["rendering"]["state"] == "SENT"
    with product(directory) as restarted:
        tick(restarted)
        assert (
            restarted.snapshot(restarted.base.refresh(action.action_id))["rendering"]["state"]
            == "UNKNOWN"
        )
        assert rows(restarted, "renders") == 1


def test_actual_process_crash_after_dispatch_commit_does_not_republish(tmp_path):
    directory = tmp_path / "p3"
    done = subprocess.run(
        [sys.executable, "-m", "tests.phase3_crash", str(directory)],
        check=False,
        capture_output=True,
        timeout=20,
    )
    assert done.returncode == 74
    with product(directory) as restarted:
        tick(restarted)
        with closing(restarted.renderer.store.connect()) as db:
            assert db.execute("SELECT state FROM renders").fetchall()[0][0] == "UNKNOWN"
        assert rows(restarted, "renders") == 1
