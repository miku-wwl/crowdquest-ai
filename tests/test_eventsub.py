import json
from datetime import UTC, datetime

import pytest

from crowdquest.eventsub import EventSub, reconnect_url
from crowdquest.intake import InvalidEvent, Store
from tests.support import make_auth, notification
from tests.test_auth import state_for


def envelope(kind, payload):
    return {
        "metadata": {
            "message_id": "control-1",
            "message_type": kind,
            "message_timestamp": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
        },
        "payload": payload,
    }


def welcome(session):
    return envelope(
        "session_welcome",
        {"session": {"id": session, "status": "connected", "keepalive_timeout_seconds": 10}},
    )


class Socket:
    def __init__(self, messages):
        self.messages, self.closed = list(messages), False

    async def recv(self):
        if not self.messages:
            raise ConnectionError("synthetic ordinary disconnect")
        value = self.messages.pop(0)
        return json.dumps(value) if type(value) is not str else value

    async def close(self):
        self.closed = True


async def test_welcome_keepalive_notification_migration_and_revocation(tmp_path):
    _, auth, mock = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    store = Store(tmp_path / "intake.sqlite3")
    first = Socket(
        [
            welcome("session-1"),
            envelope("session_keepalive", {}),
            notification(),
            envelope(
                "session_reconnect",
                {
                    "session": {
                        "id": "session-1",
                        "status": "reconnecting",
                        "reconnect_url": "wss://eventsub.wss.twitch.tv/ws?reconnect=synthetic",
                    }
                },
            ),
        ]
    )
    second = Socket(
        [
            welcome("session-2"),
            notification(delivery="duplicate-new-session", session="session-2"),
            envelope("revocation", {"subscription": {"id": "sub-1"}}),
        ]
    )
    sockets = iter([first, second])

    async def connector(url, **kwargs):
        assert url.startswith("wss://eventsub.wss.twitch.tv/ws")
        assert kwargs["max_size"] == 65536 and kwargs["proxy"] is None
        assert kwargs["ping_interval"] is None  # Library responds to Twitch Ping with Pong.
        return next(sockets)

    service = EventSub(auth, store, connector=connector)
    await service.once()
    assert service.status == "revoked"
    assert first.closed and second.closed
    assert len(store.candidates("123")) == 1
    assert len([r for r in mock.calls if r.url.path.endswith("subscriptions")]) == 1
    assert auth.identity is None
    await auth.close()


async def test_ordinary_disconnect_requires_new_subscription(tmp_path):
    _, auth, mock = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    sockets = iter([Socket([welcome("first")]), Socket([welcome("second")])])

    async def connector(*args, **kwargs):
        return next(sockets)

    service = EventSub(auth, Store(tmp_path / "intake.sqlite3"), connector=connector)
    for _ in range(2):
        with pytest.raises(ConnectionError):
            await service.once()
    assert len([r for r in mock.calls if r.url.path.endswith("subscriptions")]) == 2
    await auth.close()


@pytest.mark.parametrize(
    "url",
    [
        "ws://eventsub.wss.twitch.tv/ws",
        "wss://evil.example/ws",
        "wss://eventsub.wss.twitch.tv.evil.example/ws",
        "wss://user:password@eventsub.wss.twitch.tv/ws",
        "wss://eventsub.wss.twitch.tv:444/ws",
        "wss://eventsub.wss.twitch.tv/other",
    ],
)
def test_reconnect_destination_rejected(url):
    with pytest.raises(InvalidEvent):
        reconnect_url(url)


async def test_duplicate_json_keys_and_oversized_frame(tmp_path):
    _, auth, _ = make_auth(tmp_path)
    service = EventSub(auth, Store(tmp_path / "intake.sqlite3"))
    with pytest.raises(InvalidEvent, match="DUPLICATE_JSON_KEY"):
        await service._message(Socket(['{"a":1,"a":2}']), 1)
    with pytest.raises(InvalidEvent, match="FRAME_SIZE"):
        await service._message(Socket(["x" * 65537]), 1)
    await auth.close()
