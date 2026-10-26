"""Authenticated outbound Twitch EventSub connection; no chat writes."""

import asyncio
import hashlib
import json
import os
import re
import sqlite3
import time
from urllib.parse import urlsplit

from pydantic import ValidationError
from websockets.asyncio.client import connect
from websockets.protocol import State

from .auth import AuthError
from .intake import ID, InvalidEvent, Metadata, timestamp

ENDPOINT = "wss://eventsub.wss.twitch.tv/ws"
SUBSCRIPTIONS = "https://api.twitch.tv/helix/eventsub/subscriptions"


def reconnect_url(value):
    if type(value) is not str or len(value) > 2048:
        raise InvalidEvent("RECONNECT_URL")
    url = urlsplit(value)
    if (
        url.scheme != "wss"
        or url.hostname != "eventsub.wss.twitch.tv"
        or url.port not in (None, 443)
        or url.path != "/ws"
        or url.username
        or url.password
        or url.fragment
    ):
        raise InvalidEvent("RECONNECT_URL")
    return value


class EventSub:
    def __init__(self, auth, store, connector=connect, clock=time.time):
        self.auth, self.store, self.connector, self.clock = auth, store, connector, clock
        self.status, self.reason = "disconnected", "USER_ACTION_REQUIRED"
        self.session_id, self.subscription_id = None, None
        self.last_event_at = None
        self._socket = None
        self._waiting = False
        self._keepalive = 10
        self._last_frame_at = None
        self._stage = "idle"
        self._counters = {
            "welcomes": 0,
            "subscriptions": 0,
            "keepalives": 0,
            "notifications": 0,
            "accepted": 0,
            "votes": 0,
            "failures": 0,
        }
        self._last_failure = None
        self._last_intake_result = None

    def snapshot(self):
        socket_open = (
            self._socket is not None and getattr(self._socket, "state", State.OPEN) == State.OPEN
        )
        fresh = (
            self._last_frame_at is not None
            and self.clock() - self._last_frame_at <= self._keepalive + 2
        )

        def identity_hash(value):
            return hashlib.sha256(value.encode()).hexdigest()[:12] if value else None

        return {
            "pid": os.getpid(),
            "updated_at": self.clock(),
            "status": self.status,
            "reason": self.reason,
            "stage": self._stage,
            "ready": bool(
                self.status == "connected"
                and socket_open
                and self._waiting
                and fresh
                and self.subscription_id
                and self.auth.identity
            ),
            "socket_open": socket_open,
            "waiting_for_message": self._waiting,
            "last_frame_at": self._last_frame_at,
            "keepalive_timeout": self._keepalive,
            "session_hash": identity_hash(self.session_id),
            "subscription_hash": identity_hash(self.subscription_id),
            "owner_hash": identity_hash(self.auth.identity.user_id) if self.auth.identity else None,
            "counters": dict(self._counters),
            "last_failure": self._last_failure,
            "last_intake_result": self._last_intake_result,
        }

    def _record(self, event, **safe_fields):
        # Callers supply only fixed codes, booleans, numbers or hashed identities.
        # Never include exception text, URLs, raw frames, chat text or credentials.
        directory = self.store.path.parent
        record = {"at": self.clock(), "event": event, **safe_fields}
        journal = directory / "eventsub-events.jsonl"
        if journal.exists() and journal.stat().st_size > 262144:
            journal.replace(directory / "eventsub-events.previous.jsonl")
        with journal.open("a", encoding="utf-8") as output:
            output.write(json.dumps(record) + "\n")
        temporary = directory / "eventsub-status.tmp"
        temporary.write_text(json.dumps(self.snapshot(), indent=2), encoding="utf-8")
        temporary.replace(directory / "eventsub-status.json")

    async def _open(self, url):
        return await self.connector(
            url,
            open_timeout=10,
            close_timeout=3,
            ping_interval=None,
            max_size=65536,
            max_queue=8,
            compression=None,
            proxy=None,
        )

    async def _message(self, socket, timeout):
        value = await asyncio.wait_for(socket.recv(), timeout)
        if type(value) is not str or len(value.encode("utf-8")) > 65536:
            raise InvalidEvent("FRAME_SIZE")

        def pairs(items):
            result = {}
            for key, val in items:
                if key in result:
                    raise InvalidEvent("DUPLICATE_JSON_KEY")
                result[key] = val
            return result

        raw = json.loads(value, object_pairs_hook=pairs)
        meta = Metadata.model_validate(raw["metadata"])
        timestamp(meta.message_timestamp, self.clock())
        self._last_frame_at = self.clock()
        return raw, meta

    async def _welcome(self, socket):
        raw, meta = await self._message(socket, 10)
        session = raw["payload"]["session"]
        if (
            meta.message_type != "session_welcome"
            or session["status"] != "connected"
            or type(session["id"]) is not str
            or not 1 <= len(session["id"]) <= 256
            or type(session["keepalive_timeout_seconds"]) is not int
            or not 10 <= session["keepalive_timeout_seconds"] <= 600
        ):
            raise InvalidEvent("SESSION_WELCOME")
        self._counters["welcomes"] += 1
        self._record("session_welcome", keepalive_timeout=session["keepalive_timeout_seconds"])
        return session["id"], session["keepalive_timeout_seconds"]

    async def _subscribe(self, owner, session):
        if not await self.auth.ensure():
            raise AuthError("REAUTHENTICATION_REQUIRED")
        response = await self.auth.client.post(
            SUBSCRIPTIONS,
            headers={
                "Client-ID": self.auth.settings.client_id,
                "Authorization": f"Bearer {self.auth.tokens.access}",
            },
            json={
                "type": "channel.chat.message",
                "version": "1",
                "condition": {"broadcaster_user_id": owner, "user_id": owner},
                "transport": {"method": "websocket", "session_id": session},
            },
        )
        self._record("subscription_response", http_status=response.status_code)
        if response.status_code == 401:
            self.auth.invalidate("TOKEN_REVOKED")
        if response.status_code != 202 or len(response.content) > 16384:
            raise InvalidEvent("SUBSCRIPTION_REJECTED")
        rows = response.json()["data"]
        if not isinstance(rows, list) or len(rows) != 1:
            raise InvalidEvent("SUBSCRIPTION_RESPONSE")
        sub = rows[0]
        if (sub["type"], sub["version"], sub["status"], sub["condition"]) != (
            "channel.chat.message",
            "1",
            "enabled",
            {"broadcaster_user_id": owner, "user_id": owner},
        ):
            raise InvalidEvent("SUBSCRIPTION_RESPONSE")
        if (
            sub["transport"].get("session_id") != session
            or sub["transport"].get("method") != "websocket"
        ):
            raise InvalidEvent("SUBSCRIPTION_RESPONSE")
        if type(sub["id"]) is not str or not 1 <= len(sub["id"]) <= 128:
            raise InvalidEvent("SUBSCRIPTION_RESPONSE")
        self._counters["subscriptions"] += 1
        self._record("subscription_enabled", broadcaster_matches=True, user_matches=True)
        return sub["id"]

    async def once(self):
        identity = await self.auth.ensure()
        if identity is None:
            self.status, self.reason = "unauthenticated", self.auth.reason
            return
        socket = None
        try:
            self.status, self.reason = "connecting", "CONNECTING"
            self._stage = "websocket_connect"
            self._record("connect_started")
            socket = await self._open(ENDPOINT)
            self._socket = socket
            self._stage = "welcome"
            self.session_id, keepalive = await self._welcome(socket)
            self._keepalive = keepalive
            self.status = "subscribing"
            self._stage = "subscription"
            self.subscription_id = await self._subscribe(identity.user_id, self.session_id)
            self.status, self.reason = "connected", "CONNECTED"
            while True:
                if not await self.auth.ensure():
                    self.status, self.reason = "revoked", "REAUTHENTICATION_REQUIRED"
                    return
                self._stage = "receive"
                self._waiting = True
                self._record("listening")
                try:
                    raw, meta = await self._message(socket, keepalive + 2)
                except (ValidationError, InvalidEvent, json.JSONDecodeError) as error:
                    # Reject a malformed frame without taking down a healthy authenticated
                    # stream. Keep details bounded; Pydantic's default error includes input.
                    fields = []
                    if isinstance(error, ValidationError):
                        allowed = {
                            "message_id",
                            "message_type",
                            "message_timestamp",
                            "subscription_type",
                            "subscription_version",
                        }
                        fields = [
                            e["loc"][0]
                            for e in error.errors(
                                include_input=False, include_context=False, include_url=False
                            )
                            if e["loc"] and e["loc"][0] in allowed
                        ]
                    self.store.reject("FRAME_REJECTED", self.clock())
                    self._record("frame_rejected", kind=type(error).__name__, fields=fields)
                    continue
                finally:
                    self._waiting = False
                if meta.message_type == "session_keepalive":
                    self._counters["keepalives"] += 1
                    self._record("keepalive_received")
                    continue
                if meta.message_type == "session_reconnect":
                    session = raw["payload"]["session"]
                    if session["id"] != self.session_id or session["status"] != "reconnecting":
                        raise InvalidEvent("RECONNECT_SESSION")
                    self.status = "reconnecting"
                    replacement = await self._open(reconnect_url(session["reconnect_url"]))
                    try:
                        new_session, new_keepalive = await self._welcome(replacement)
                    except BaseException:
                        await replacement.close()
                        raise
                    await socket.close()
                    socket = replacement
                    self._socket = socket
                    self.session_id, keepalive = new_session, new_keepalive
                    self._keepalive = keepalive
                    self.status, self.reason = "connected", "RECONNECTED"
                    # Twitch migrates existing subscriptions: no second POST.
                elif meta.message_type == "revocation":
                    if raw["payload"]["subscription"]["id"] != self.subscription_id:
                        raise InvalidEvent("REVOCATION_IDENTITY")
                    self.auth.invalidate("SUBSCRIPTION_REVOKED")
                    self.status, self.reason = "revoked", "SUBSCRIPTION_REVOKED"
                    return
                elif meta.message_type == "notification":
                    self._counters["notifications"] += 1
                    self._stage = "intake"
                    self._record(
                        "notification_received",
                        delivery_hash=hashlib.sha256(meta.message_id.encode()).hexdigest()[:12],
                        legacy_delivery_id_would_reject=not bool(re.fullmatch(ID, meta.message_id)),
                    )
                    result = self.store.ingest(
                        raw,
                        owner_id=identity.user_id,
                        session_id=self.session_id,
                        subscription_id=self.subscription_id,
                        now=self.clock(),
                    )
                    self._last_intake_result = result
                    if result == "ACCEPTED":
                        self._counters["accepted"] += 1
                        self.last_event_at = self.clock()
                    elif result == "VOTE_ACCEPTED":
                        self._counters["votes"] += 1
                        self.last_event_at = self.clock()
                    self._record("intake_result", result=result)
                else:
                    self.store.reject("MESSAGE_TYPE", self.clock())
        finally:
            self._waiting = False
            if socket is not None:
                await socket.close()
            self._socket = None
            self._record("socket_closed")

    async def run(self):
        delay = 2
        while True:
            try:
                await self.once()
                delay = 2
            except asyncio.CancelledError:
                raise
            except Exception as error:  # noqa: BLE001 -- sanitize network/credential-bearing exceptions
                code = (
                    str(error)
                    if isinstance(error, (AuthError, InvalidEvent))
                    else "CONNECTION_INTERRUPTED"
                )
                if not code.replace("_", "").isupper() or len(code) > 64:
                    code = "CONNECTION_INTERRUPTED"
                self._counters["failures"] += 1
                self._last_failure = {
                    "kind": type(error).__name__,
                    "code": code,
                    "stage": self._stage,
                }
                if isinstance(error, sqlite3.Error):
                    self._last_failure["sqlite_errorcode"] = getattr(
                        error, "sqlite_errorcode", None
                    )
                    name = getattr(error, "sqlite_errorname", "SQLITE_ERROR")
                    self._last_failure["sqlite_errorname"] = (
                        name if re.fullmatch(r"SQLITE_[A-Z_]+", name) else "SQLITE_ERROR"
                    )
                self.status, self.reason = "disconnected", "CONNECTION_INTERRUPTED"
                self._record("connection_failed", **self._last_failure)
                delay = min(30, delay * 2)
            await asyncio.sleep(delay)
