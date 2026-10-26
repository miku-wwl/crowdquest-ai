import json

import pytest

from crowdquest.eventsub import EventSub
from crowdquest.intake import Store
from tests.support import make_auth, notification
from tests.test_auth import state_for
from tests.test_eventsub import Socket, envelope, welcome


@pytest.mark.parametrize("delivery", ["opaque+delivery/id=", "opaque:delivery.id=="])
def test_opaque_delivery_id_is_durably_deduplicated(tmp_path, delivery):
    store = Store(tmp_path / "intake.sqlite3")
    raw = notification(delivery=delivery)
    raw["metadata"]["message_timestamp"] = raw["metadata"]["message_timestamp"].replace(
        "Z", "+00:00"
    )
    raw["payload"]["subscription"]["transport"]["connected_at"] = "2026-10-26T00:00:00Z"
    args = {
        "owner_id": "123",
        "session_id": "session-1",
        "subscription_id": "sub-1",
        "source": "synthetic",
    }
    assert store.ingest(raw, **args) == "ACCEPTED"
    assert Store(store.path).ingest(raw, **args) == "DUPLICATE"
    assert len(store.candidates("123")) == 1


async def test_bad_frame_does_not_disconnect_or_log_sensitive_input(tmp_path):
    _, auth, _ = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    malformed = notification()
    malformed["metadata"]["message_id"] = "DO_NOT_LOG_PRIVATE_INPUT\n"
    good = notification(delivery="opaque+/id=")
    socket = Socket(
        [
            welcome("session-1"),
            malformed,
            good,
            envelope("revocation", {"subscription": {"id": "sub-1"}}),
        ]
    )

    async def connector(*args, **kwargs):
        return socket

    store = Store(tmp_path / "intake.sqlite3")
    service = EventSub(auth, store, connector=connector)
    await service.once()
    assert len(store.candidates("123")) == 1
    journal = (tmp_path / "eventsub-events.jsonl").read_text()
    assert "DO_NOT_LOG_PRIVATE_INPUT" not in journal
    assert "synthetic-access" not in journal and "synthetic-secret" not in journal
    events = [json.loads(line) for line in journal.splitlines()]
    assert any(e["event"] == "frame_rejected" and e["fields"] == ["message_id"] for e in events)
    assert any(e["event"] == "intake_result" and e["result"] == "ACCEPTED" for e in events)
    assert not service.snapshot()["ready"]
    await auth.close()


async def test_ready_requires_real_socket_wait_and_recent_frame(tmp_path):
    clock = [1000.0]
    _, auth, _ = make_auth(tmp_path, clock=lambda: clock[0])
    await auth.callback(*state_for(auth), "synthetic-code")
    service = EventSub(auth, Store(tmp_path / "intake.sqlite3"), clock=lambda: clock[0])
    service.status = "connected"
    assert not service.snapshot()["ready"]
    service._socket = Socket([])
    service.subscription_id = "sub-1"
    service._last_frame_at = clock[0]
    service._waiting = True
    assert service.snapshot()["ready"]
    clock[0] += 13
    assert not service.snapshot()["ready"]
    await auth.close()
