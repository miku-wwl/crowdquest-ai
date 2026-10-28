"""Isolated documented reconnect compatibility; never connects to Twitch."""

import asyncio
import json
from http import HTTPStatus

import pytest
from websockets.asyncio.client import connect
from websockets.asyncio.server import serve
from websockets.exceptions import ConnectionClosedError, ConnectionClosedOK

from crowdquest import eventsub
from crowdquest.auth import AuthError
from crowdquest.eventsub import ENDPOINT, EventSub, reconnect_url
from crowdquest.intake import InvalidEvent, Store
from tests.support import make_auth, notification
from tests.test_auth import state_for
from tests.test_eventsub import envelope, welcome


@pytest.mark.parametrize("path", ["", "/", "/ws"])
@pytest.mark.parametrize("port", ["", ":443"])
def test_documented_reconnect_forms_are_preserved(path, port):
    value = f"wss://eventsub.wss.twitch.tv{port}{path}?reconnect=synthetic%2Bonly&opaque=a%2Fb"
    assert reconnect_url(value) == value


@pytest.mark.parametrize(
    "value",
    [
        None,
        1,
        "",
        "wss://eventsub.wss.twitch.tv/ws?" + "x" * 2048,
        "ws://eventsub.wss.twitch.tv/",
        "wss://evil.example/",
        "wss://eventsub.wss.twitch.tv.evil.example/",
        "wss://eventsub.wss.twitch.tv./",
        "wss://eventsub.wss.twitch.tv:444/",
        "wss://eventsub.wss.twitch.tv:invalid/",
        "wss://eventsub.wss.twitch.tv:/",
        "wss://@eventsub.wss.twitch.tv/ws",
        "wss://user@eventsub.wss.twitch.tv/ws",
        "wss://user:password@eventsub.wss.twitch.tv/ws",
        "wss://eventsub.wss.twitch.tv/ws#",
        "wss://eventsub.wss.twitch.tv/ws#fragment",
        "wss://eventsub.wss.twitch.tv/other",
        "wss://eventsub.wss.twitch.tv/ws/",
        "wss://eventsub.wss.twitch.tv/%77s",
        " wss://eventsub.wss.twitch.tv/ws",
        "wss://eventsub.wss.twitch.tv/\nws",
        "wss://eventsub.wss.twitch.tv/ws?opaque=\tvalue",
        "wss://eventsub.wss.twitch.tv/ws?opaque=\\value",
        "wss://eventsub.wss.twitch.tv/ws?opaque=\x7f",
        "wss://localhost/ws",
        "wss://127.0.0.1/ws",
        "wss://10.0.0.1/ws",
        "wss://192.168.1.1/ws",
        "wss://169.254.169.254/ws",
        "wss://[::1]/ws",
    ],
    ids=[
        "none",
        "integer",
        "empty",
        "oversize",
        "plaintext",
        "foreign-host",
        "host-suffix",
        "trailing-host-dot",
        "wrong-port",
        "invalid-port",
        "empty-port",
        "empty-userinfo",
        "username",
        "password",
        "empty-fragment",
        "fragment",
        "foreign-path",
        "trailing-path",
        "encoded-path",
        "leading-space",
        "newline-normalization",
        "tab-normalization",
        "backslash",
        "delete-control",
        "localhost",
        "ipv4-loopback",
        "private-10",
        "private-192",
        "link-local",
        "ipv6-loopback",
    ],
)
def test_reconnect_rejects_unsafe_forms_with_fixed_error(value):
    with pytest.raises(InvalidEvent, match="^RECONNECT_URL$"):
        reconnect_url(value)


class QueueSocket:
    """A source socket stays readable until close, like a real WebSocket."""

    def __init__(self, messages=(), *, welcome_gate=None):
        self.queue = asyncio.Queue()
        for message in messages:
            self.queue.put_nowait(message)
        self.closed = False
        self.welcome_gate = welcome_gate
        self.receiving = asyncio.Event()
        self.close_error = None

    async def recv(self):
        self.receiving.set()
        if self.welcome_gate is not None:
            gate, self.welcome_gate = self.welcome_gate, None
            await asyncio.wait_for(gate.wait(), 0.5)
        value = await self.queue.get()
        if value is None:
            raise ConnectionClosedOK(None, None)
        if isinstance(value, BaseException):
            raise value
        return json.dumps(value)

    async def close(self):
        self.closed = True
        self.queue.put_nowait(self.close_error)


@pytest.mark.parametrize(
    "delay_welcome", [True, False], ids=["before-welcome", "queued-at-welcome"]
)
async def test_source_notifications_continue_until_replacement_welcome(
    tmp_path, monkeypatch, delay_welcome
):
    _, auth, mock = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    store = Store(tmp_path / "intake.sqlite3")
    old_received = asyncio.Event()
    ingested = []
    original = store.ingest

    def ingest(raw, **kwargs):
        result = original(raw, **kwargs)
        ingested.append(result)
        if len(ingested) == 2:
            old_received.set()
        return result

    monkeypatch.setattr(store, "ingest", ingest)
    url = "wss://eventsub.wss.twitch.tv/ws?reconnect=synthetic-sensitive-marker"
    source = QueueSocket(
        [
            welcome("session-1"),
            envelope(
                "session_reconnect",
                {
                    "session": {
                        "id": "session-1",
                        "status": "reconnecting",
                        "reconnect_url": url,
                    }
                },
            ),
            notification(delivery="late-1", message="chat-1", viewer="456"),
            notification(delivery="late-2", message="chat-2", viewer="457"),
        ]
    )
    replacement = QueueSocket(
        [
            welcome("session-2"),
            notification(
                delivery="migrated-duplicate", message="chat-1", viewer="456", session="session-2"
            ),
            envelope("revocation", {"subscription": {"id": "sub-1"}}),
        ],
        welcome_gate=old_received if delay_welcome else None,
    )
    sockets = iter([source, replacement])
    opened = []

    async def connector(destination, **kwargs):
        if opened:
            assert not source.closed  # Never close before the new welcome.
        opened.append(destination)
        return next(sockets)

    service = EventSub(auth, store, connector=connector)
    try:
        await asyncio.wait_for(service.once(), 2)
        assert opened[1] == url
        assert len(store.candidates("123")) == 2
        assert ingested[:2] == ["ACCEPTED", "ACCEPTED"]
        assert ingested[2] != "ACCEPTED"  # Same chat after migration is not another candidate.
        assert service.status == "revoked"
        assert source.closed and replacement.closed
        assert len([r for r in mock.calls if r.url.path.endswith("subscriptions")]) == 1
        journal = (tmp_path / "eventsub-events.jsonl").read_text("utf-8")
        assert "synthetic-sensitive-marker" not in journal and "wss://" not in journal
    finally:
        await auth.close()


@pytest.mark.parametrize(
    "failure",
    ["invalid-welcome", "cancel", "deadline", "revoked", "source-lost", "source-close-failed"],
)
async def test_failed_handover_closes_both_sockets_without_resubscribing(
    tmp_path, monkeypatch, failure
):
    _, auth, mock = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    source = QueueSocket(
        [
            welcome("session-1"),
            envelope(
                "session_reconnect",
                {
                    "session": {
                        "id": "session-1",
                        "status": "reconnecting",
                        "reconnect_url": "wss://eventsub.wss.twitch.tv?opaque=synthetic",
                    }
                },
            ),
        ]
    )
    replacement = QueueSocket()
    if failure == "invalid-welcome":
        invalid = welcome("session-2")
        invalid["payload"]["session"]["status"] = "reconnecting"
        replacement.queue.put_nowait(invalid)
    elif failure == "deadline":
        monkeypatch.setattr(eventsub, "HANDOVER_TIMEOUT", 0.02)
    elif failure == "revoked":
        source.queue.put_nowait(envelope("revocation", {"subscription": {"id": "sub-1"}}))
    elif failure == "source-lost":
        source.queue.put_nowait(None)
    elif failure == "source-close-failed":
        source.close_error = ConnectionClosedError(None, None)
        replacement.queue.put_nowait(welcome("session-2"))
    sockets = iter([source, replacement])

    async def connector(*args, **kwargs):
        return next(sockets)

    service = EventSub(auth, Store(tmp_path / "intake.sqlite3"), connector=connector)
    task = asyncio.create_task(service.once())
    try:
        if failure == "cancel":
            await asyncio.wait_for(replacement.receiving.wait(), 1)
            task.cancel()
        expected = {
            "invalid-welcome": InvalidEvent,
            "cancel": asyncio.CancelledError,
            "deadline": TimeoutError,
            "revoked": AuthError,
            "source-lost": ConnectionClosedOK,
            "source-close-failed": ConnectionClosedError,
        }[failure]
        with pytest.raises(expected):
            await asyncio.wait_for(task, 2)
        assert source.closed and replacement.closed
        assert service._socket is None and not service._waiting
        assert len([r for r in mock.calls if r.url.path.endswith("subscriptions")]) == 1
        assert not service.store.candidates("123")
    finally:
        if not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        await auth.close()


async def test_real_loopback_websocket_handover_preserves_subscriptions_and_queued_events(tmp_path):
    _, auth, mock = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    welcome_sent = asyncio.Event()
    source_closed = asyncio.Event()
    url = "wss://eventsub.wss.twitch.tv?opaque=synthetic-loopback-only"

    async def handler(socket):
        if socket.request.path == "/initial":
            messages = [
                welcome("session-1"),
                envelope(
                    "session_reconnect",
                    {
                        "session": {
                            "id": "session-1",
                            "status": "reconnecting",
                            "reconnect_url": url,
                        }
                    },
                ),
                notification(delivery="wire-late-1", message="wire-chat-1", viewer="456"),
                notification(delivery="wire-late-2", message="wire-chat-2", viewer="457"),
            ]
        else:
            assert socket.request.path == "/replacement"
            messages = [
                welcome("session-2"),
                notification(
                    delivery="wire-retransmission",
                    message="wire-chat-1",
                    viewer="456",
                    session="session-2",
                ),
                envelope("revocation", {"subscription": {"id": "sub-1"}}),
            ]
        for message in messages:
            await socket.send(json.dumps(message))
            if (
                socket.request.path == "/replacement"
                and message["metadata"]["message_type"] == "session_welcome"
            ):
                welcome_sent.set()
        await socket.wait_closed()
        if socket.request.path == "/initial":
            assert welcome_sent.is_set()
            source_closed.set()

    try:
        async with serve(handler, "127.0.0.1", 0) as server:
            port = server.sockets[0].getsockname()[1]
            destinations = []

            async def connector(destination, **kwargs):
                assert destination in (ENDPOINT, url)
                destinations.append(destination)
                path = "/initial" if destination == ENDPOINT else "/replacement"
                # Trusted test-only dependency injection; production validation stays WSS/Twitch-only.
                return await connect(f"ws://127.0.0.1:{port}{path}", **kwargs)

            service = EventSub(auth, Store(tmp_path / "intake.sqlite3"), connector=connector)
            await asyncio.wait_for(service.once(), 3)
            await asyncio.wait_for(source_closed.wait(), 1)
            assert destinations == [ENDPOINT, url]
            assert len(service.store.candidates("123")) == 2
            assert service.snapshot()["counters"]["reconnects"] == 1
            assert len([r for r in mock.calls if r.url.path.endswith("subscriptions")]) == 1
            assert service.status == "revoked"
    finally:
        await auth.close()


@pytest.mark.parametrize(
    "changed", [False, True], ids=["same-destination", "conflicting-destination"]
)
async def test_repeated_reconnect_does_not_open_another_connection(tmp_path, changed):
    _, auth, mock = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    url = "wss://eventsub.wss.twitch.tv?opaque=synthetic"

    def control(destination):
        return envelope(
            "session_reconnect",
            {
                "session": {
                    "id": "session-1",
                    "status": "reconnecting",
                    "reconnect_url": destination,
                }
            },
        )

    source = QueueSocket(
        [welcome("session-1"), control(url), control(url + "-changed" if changed else url)]
    )
    replacement = QueueSocket(
        [welcome("session-2"), envelope("revocation", {"subscription": {"id": "sub-1"}})]
    )
    sockets = iter([source, replacement])
    opened = []

    async def connector(destination, **kwargs):
        opened.append(destination)
        return next(sockets)

    service = EventSub(auth, Store(tmp_path / "intake.sqlite3"), connector=connector)
    try:
        if changed:
            with pytest.raises(InvalidEvent, match="RECONNECT_IN_PROGRESS"):
                await asyncio.wait_for(service.once(), 2)
        else:
            await asyncio.wait_for(service.once(), 2)
            assert service.snapshot()["counters"]["reconnects"] == 1
        assert len(opened) == 2 and source.closed and replacement.closed
        assert len([r for r in mock.calls if r.url.path.endswith("subscriptions")]) == 1
    finally:
        await auth.close()


async def test_new_connection_failure_does_not_resubscribe_or_mutate_intake(tmp_path):
    _, auth, mock = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    source = QueueSocket(
        [
            welcome("session-1"),
            envelope(
                "session_reconnect",
                {
                    "session": {
                        "id": "session-1",
                        "status": "reconnecting",
                        "reconnect_url": "wss://eventsub.wss.twitch.tv?opaque=synthetic",
                    }
                },
            ),
        ]
    )
    opened = []

    async def connector(destination, **kwargs):
        opened.append(destination)
        if len(opened) == 1:
            return source
        raise ConnectionError("synthetic connect failure")

    service = EventSub(auth, Store(tmp_path / "intake.sqlite3"), connector=connector)
    try:
        with pytest.raises(ConnectionError):
            await asyncio.wait_for(service.once(), 2)
        assert len(opened) == 2 and source.closed
        assert not service.store.candidates("123")
        assert len([r for r in mock.calls if r.url.path.endswith("subscriptions")]) == 1
    finally:
        await auth.close()


async def test_redirect_response_is_rejected_without_contacting_its_destination(tmp_path):
    _, auth, mock = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    destinations = []

    async def forbidden(socket):
        destinations.append(True)
        await socket.wait_closed()

    try:
        async with serve(forbidden, "127.0.0.1", 0) as foreign:
            foreign_port = foreign.sockets[0].getsockname()[1]

            async def redirect(socket, request):
                response = socket.respond(HTTPStatus.FOUND, "Synthetic redirect")
                response.headers["Location"] = f"ws://127.0.0.1:{foreign_port}/forbidden"
                return response

            async with serve(forbidden, "127.0.0.1", 0, process_request=redirect) as server:
                port = server.sockets[0].getsockname()[1]

                async def connector(destination, **kwargs):
                    assert destination == ENDPOINT
                    return await connect(f"ws://127.0.0.1:{port}/initial", **kwargs)

                service = EventSub(auth, Store(tmp_path / "intake.sqlite3"), connector=connector)
                with pytest.raises(InvalidEvent, match="^WEBSOCKET_REDIRECT_DENIED$"):
                    await asyncio.wait_for(service.once(), 2)
        assert destinations == []
        assert not [r for r in mock.calls if r.url.path.endswith("subscriptions")]
    finally:
        await auth.close()


async def test_application_shutdown_during_handover_leaves_no_stream_tasks(tmp_path):
    from crowdquest.app import create_app

    settings, auth, _ = make_auth(tmp_path)
    await auth.callback(*state_for(auth), "synthetic-code")
    source = QueueSocket(
        [
            welcome("session-1"),
            envelope(
                "session_reconnect",
                {
                    "session": {
                        "id": "session-1",
                        "status": "reconnecting",
                        "reconnect_url": "wss://eventsub.wss.twitch.tv?opaque=synthetic",
                    }
                },
            ),
        ]
    )
    replacement = QueueSocket()
    sockets = iter([source, replacement])

    async def connector(*args, **kwargs):
        return next(sockets)

    before = set(asyncio.all_tasks())
    app = create_app(
        settings, auth=auth, eventsub_factory=lambda a, s: EventSub(a, s, connector=connector)
    )
    async with app.router.lifespan_context(app):
        await asyncio.wait_for(replacement.receiving.wait(), 1)
    assert source.closed and replacement.closed
    assert not {task for task in asyncio.all_tasks() - before if not task.done()}


async def test_intake_dedup_survives_eventsub_instance_restart(tmp_path):
    database = tmp_path / "intake.sqlite3"
    for attempt in (1, 2):
        _, auth, _ = make_auth(tmp_path)
        await auth.callback(*state_for(auth), "synthetic-code")
        session = f"session-{attempt}"
        socket = QueueSocket(
            [
                welcome(session),
                notification(
                    delivery=f"restart-delivery-{attempt}",
                    message="same-persisted-chat",
                    session=session,
                ),
                envelope("revocation", {"subscription": {"id": "sub-1"}}),
            ]
        )

        async def connector(*args, _socket=socket, **kwargs):
            return _socket

        service = EventSub(auth, Store(database), connector=connector)
        try:
            await service.once()
            assert len(service.store.candidates("123")) == 1
            assert service.snapshot()["counters"]["accepted"] == (1 if attempt == 1 else 0)
        finally:
            await auth.close()
