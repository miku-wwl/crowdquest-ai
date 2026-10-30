"""Phase 4.5.5 synthetic delivery protocol; deterministic clocks and private fixtures."""

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from uuid import uuid4

import pytest

from tests.phase3_support import product, succeeded, tick


def observation_rows(store):
    with closing(store.connect()) as db:
        return [dict(row) for row in db.execute("SELECT * FROM observations")]


async def test_delayed_visibility_peeks_do_not_start_ack_timeout(tmp_path):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "p3", time_values=clock) as service:
        _, action = await succeeded(service)
        worker = tick(service)
        store, view = service.renderer.store, str(uuid4())
        for _ in range(4):
            assert store.current("studio", view, consume=False)["state"] == "delivery_pending"
            clock[0] += 3
            tick(service, worker)
        assert not observation_rows(store)
        assert store.summary(action.effect_key)["state"] == "SENT"
        peek = store.current("studio", view, consume=False)
        value = store.current("studio", view, expected_id=peek["render_id"])
        assert value["remaining_seconds"] == 48
        store.acknowledge("studio", view, value["render_id"], value["delivery_id"])
        assert store.summary(action.effect_key)["acknowledgements"] == 1


async def test_concurrent_claims_no_theft_duplicate_ack_and_identity_binding(tmp_path):
    with product(tmp_path / "p3") as service:
        _, action = await succeeded(service)
        tick(service)
        store = service.renderer.store
        views = [str(uuid4()), str(uuid4())]
        render = store.current("studio", views[0], consume=False)["render_id"]
        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(
                pool.map(lambda view: store.current("studio", view, expected_id=render), views)
            )
        assert sum(v["state"] == "challenge" for v in values) == 1
        winner = next(i for i, v in enumerate(values) if v["state"] == "challenge")
        value, view = values[winner], views[winner]
        identity = ("studio", view, render, value["delivery_id"])
        for index in range(4):
            bad = list(identity)
            bad[index] = str(uuid4())
            with pytest.raises(ValueError, match="ACK_REJECTED"):
                store.acknowledge(*bad)
        for _ in range(2):
            store.acknowledge(*identity)
        assert store.summary(action.effect_key)["acknowledgements"] == 1
        assert len(observation_rows(store)) == 1
        assert store.current("studio", str(uuid4()), expected_id=render)["reason"] == "NO_REPLAY"
        # Even the acknowledged owner cannot obtain a second payload via claim.
        assert store.current("studio", view, expected_id=render)["state"] == "claimed"
        assert "challenge" not in store.current("studio", view, consume=False)


async def test_lost_claim_or_paint_ack_is_terminal_at_exact_timeout(tmp_path):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "p3", time_values=clock) as service:
        _, action = await succeeded(service)
        worker = tick(service)
        store, view = service.renderer.store, str(uuid4())
        peek = store.current("studio", view, consume=False)
        value = store.current("studio", view, expected_id=peek["render_id"])
        clock[0] += 3
        tick(service, worker)
        clock[0] += 2
        tick(service, worker)
        assert store.summary(action.effect_key)["state"] == "UNKNOWN"
        with pytest.raises(ValueError, match="ACK_REJECTED"):
            store.acknowledge("studio", view, value["render_id"], value["delivery_id"])
        assert observation_rows(store)[0]["status"] == "UNKNOWN"
        assert store.current("studio", view, expected_id=peek["render_id"])["state"] == "unknown"
        assert store.summary(action.effect_key)["acknowledgements"] == 0


async def test_unclaimed_expiration_cannot_be_claimed_or_replayed(tmp_path):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "p3", time_values=clock) as service:
        _, action = await succeeded(service)
        worker = tick(service)
        store, view = service.renderer.store, str(uuid4())
        peek = store.current("studio", view, consume=False)
        for _ in range(20):
            clock[0] += 3
            tick(service, worker)
        assert store.current("studio", view, expected_id=peek["render_id"])["state"] == "expired"
        assert store.summary(action.effect_key)["state"] == "EXPIRED"
        assert not observation_rows(store)


async def test_worker_lease_expiry_preserves_ack_then_normal_deadline_expires(tmp_path):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "p3", time_values=clock) as service:
        _, action = await succeeded(service)
        tick(service)
        store, view = service.renderer.store, str(uuid4())
        peek = store.current("studio", view, consume=False)
        claim = store.current("studio", view, expected_id=peek["render_id"])
        store.acknowledge("studio", view, claim["render_id"], claim["delivery_id"])

        clock[0] += 6  # Lease expired; the 60-second acknowledged Render is still live.
        store.maintain()
        with closing(store.connect()) as db:
            assert (
                db.execute(
                    "SELECT state FROM renders WHERE render_id=?", (peek["render_id"],)
                ).fetchone()[0]
                == "RENDERED"
            )
        assert observation_rows(store)[0]["status"] == "ACKNOWLEDGED"
        assert store.current("studio", view, expected_id=peek["render_id"])["state"] == "claimed"
        assert "challenge" not in store.current("studio", view, consume=False)

        clock[0] += 54
        store.maintain()
        with closing(store.connect()) as db:
            assert (
                db.execute(
                    "SELECT state FROM renders WHERE render_id=?", (peek["render_id"],)
                ).fetchone()[0]
                == "EXPIRED"
            )
        assert observation_rows(store)[0]["status"] == "ACKNOWLEDGED"
        assert store.summary(action.effect_key)["acknowledgements"] == 1


async def test_worker_lease_expiry_fails_claimed_and_quarantines_unacked_sent(tmp_path):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "claimed", time_values=clock) as service:
        _, action = await succeeded(service)
        store = service.renderer.store
        worker, boot = str(uuid4()), service.renderer.boot
        epoch = store.take_leadership(worker, boot)
        job = service.base.store.job(action.effect_key)
        render_id = store.claim(job, worker, epoch, boot)
        assert render_id
        clock[0] += 6
        store.maintain()
        with closing(store.connect()) as db:
            assert (
                db.execute("SELECT state FROM renders WHERE render_id=?", (render_id,)).fetchone()[
                    0
                ]
                == "RENDER_FAILED"
            )

    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "sent", time_values=clock) as service:
        _, action = await succeeded(service)
        tick(service)
        store = service.renderer.store
        render_id = store.summary(action.effect_key)["render_id"]
        clock[0] += 6
        store.maintain()
        with closing(store.connect()) as db:
            assert (
                db.execute("SELECT state FROM renders WHERE render_id=?", (render_id,)).fetchone()[
                    0
                ]
                == "UNKNOWN"
            )


async def test_ack_racing_expired_worker_lease_is_rejected_without_replay(tmp_path):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "p3", time_values=clock) as service:
        _, action = await succeeded(service)
        worker = tick(service)
        store, view = service.renderer.store, str(uuid4())
        payload = store.current("studio", view)
        clock[0] += 6
        with pytest.raises(ValueError, match="ACK_REJECTED"):
            store.acknowledge("studio", view, payload["render_id"], payload["delivery_id"])
        assert store.summary(action.effect_key)["state"] == "UNKNOWN"
        assert observation_rows(store)[0]["status"] == "UNKNOWN"
        tick(service, worker)
        assert store.summary(action.effect_key)["state"] == "UNKNOWN"
        assert len(observation_rows(store)) == 1
        with closing(store.connect()) as db:
            assert db.execute("SELECT count(*) FROM renders").fetchone()[0] == 1


async def test_boot_recovery_keeps_ack_audit_and_never_releases_old_payload(tmp_path):
    directory = tmp_path / "p3"
    clock = [1000.0, 1800000000.0]
    view = str(uuid4())
    with product(directory, time_values=clock) as service:
        _, action = await succeeded(service)
        tick(service)
        store = service.renderer.store
        peek = store.current("studio", view, consume=False)
        claim = store.current("studio", view, expected_id=peek["render_id"])
        store.acknowledge("studio", view, claim["render_id"], claim["delivery_id"])
        render_id = claim["render_id"]

    with product(directory, time_values=clock) as restarted:
        store = restarted.renderer.store
        tick(restarted)
        assert store.summary(action.effect_key)["state"] == "UNKNOWN"
        assert store.summary(action.effect_key)["acknowledgements"] == 1
        assert observation_rows(store)[0]["status"] == "ACKNOWLEDGED"
        assert store.current("studio", view, expected_id=render_id)["state"] == "unknown"
        with closing(store.connect()) as db:
            assert db.execute("SELECT count(*) FROM renders").fetchone()[0] == 1


async def test_pending_successful_action_renders_once_without_replaying_unknown(tmp_path):
    clock = [1000.0, 1800000000.0]
    with product(tmp_path / "p3", time_values=clock) as service:
        _, old_action = await succeeded(service)
        worker = tick(service)
        store = service.renderer.store
        old_render = store.summary(old_action.effect_key)["render_id"]
        old_view = str(uuid4())
        store.current("studio", old_view)
        clock[0] += 6
        store.maintain()
        assert store.summary(old_action.effect_key)["state"] == "UNKNOWN"

        _, pending_action = await succeeded(service)
        assert pending_action.state.value == "Succeeded"
        new_worker = tick(service, worker)
        assert store.summary(old_action.effect_key)["state"] == "UNKNOWN"
        assert store.summary(pending_action.effect_key)["state"] == "SENT"
        new_render = store.summary(pending_action.effect_key)["render_id"]
        assert new_render != old_render

        # Repeated ticks cannot create a second Render or re-execute either Action.
        tick(service, new_worker)
        assert store.summary(old_action.effect_key)["state"] == "UNKNOWN"
        assert store.summary(pending_action.effect_key)["render_id"] == new_render
        with closing(service.renderer.store.connect()) as db:
            assert db.execute("SELECT count(*) FROM renders").fetchone()[0] == 2
        gate = tmp_path / "p3" / "gate.sqlite3"
        with sqlite3.connect(gate.resolve().as_uri() + "?mode=ro", uri=True) as db:
            assert (
                db.execute(
                    "SELECT count(*) FROM action_attempts WHERE action_id IN (?,?)",
                    (old_action.action_id, pending_action.action_id),
                ).fetchone()[0]
                == 2
            )

        new_view = str(uuid4())
        peek = store.current("studio", new_view, consume=False)
        claim = store.current("studio", new_view, expected_id=new_render)
        store.acknowledge("studio", new_view, claim["render_id"], claim["delivery_id"])
        assert store.summary(pending_action.effect_key)["acknowledgements"] == 1
        assert store.summary(old_action.effect_key)["acknowledgements"] == 0
        assert peek["render_id"] == new_render


@pytest.mark.parametrize("claimed", [False, True])
async def test_restart_never_releases_another_payload(tmp_path, claimed):
    directory = tmp_path / "p3"
    view = str(uuid4())
    with product(directory) as service:
        _, action = await succeeded(service)
        tick(service)
        peek = service.renderer.store.current("studio", view, consume=False)
        if claimed:
            service.renderer.store.current("studio", view, expected_id=peek["render_id"])
    with product(directory) as restarted:
        tick(restarted)
        store = restarted.renderer.store
        assert (
            store.current("studio", str(uuid4()), expected_id=peek["render_id"])["state"]
            == "unknown"
        )
        assert store.summary(action.effect_key)["acknowledgements"] == 0
        assert all(row["status"] == "UNKNOWN" for row in observation_rows(store))
