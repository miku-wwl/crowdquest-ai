"""Phase 4.5.5 synthetic delivery protocol; deterministic clocks and private fixtures."""

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
