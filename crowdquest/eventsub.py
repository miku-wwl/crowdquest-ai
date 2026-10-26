"""Authenticated outbound Twitch EventSub connection; no chat writes."""

import asyncio
import json
import time
from urllib.parse import urlsplit

from websockets.asyncio.client import connect

from .auth import AuthError
from .intake import InvalidEvent, Metadata, timestamp

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
        return sub["id"]

    async def once(self):
        identity = await self.auth.ensure()
        if identity is None:
            self.status, self.reason = "unauthenticated", self.auth.reason
            return
        socket = None
        try:
            self.status, self.reason = "connecting", "CONNECTING"
            socket = await self._open(ENDPOINT)
            self.session_id, keepalive = await self._welcome(socket)
            self.status = "subscribing"
            self.subscription_id = await self._subscribe(identity.user_id, self.session_id)
            self.status, self.reason = "connected", "CONNECTED"
            while True:
                if not await self.auth.ensure():
                    self.status, self.reason = "revoked", "REAUTHENTICATION_REQUIRED"
                    return
                raw, meta = await self._message(socket, keepalive + 2)
                if meta.message_type == "session_keepalive":
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
                    self.session_id, keepalive = new_session, new_keepalive
                    self.status, self.reason = "connected", "RECONNECTED"
                    # Twitch migrates existing subscriptions: no second POST.
                elif meta.message_type == "revocation":
                    if raw["payload"]["subscription"]["id"] != self.subscription_id:
                        raise InvalidEvent("REVOCATION_IDENTITY")
                    self.auth.invalidate("SUBSCRIPTION_REVOKED")
                    self.status, self.reason = "revoked", "SUBSCRIPTION_REVOKED"
                    return
                elif meta.message_type == "notification":
                    result = self.store.ingest(
                        raw,
                        owner_id=identity.user_id,
                        session_id=self.session_id,
                        subscription_id=self.subscription_id,
                        now=self.clock(),
                    )
                    if result == "ACCEPTED":
                        self.last_event_at = self.clock()
                else:
                    self.store.reject("MESSAGE_TYPE", self.clock())
        finally:
            if socket is not None:
                await socket.close()

    async def run(self):
        delay = 2
        while True:
            try:
                await self.once()
                delay = 2
            except asyncio.CancelledError:
                raise
            except Exception:  # noqa: BLE001 -- sanitize network/credential-bearing exceptions
                # Never log exceptions/URLs/payloads from credential-bearing HTTP clients.
                self.status, self.reason = "disconnected", "CONNECTION_INTERRUPTED"
                delay = min(30, delay * 2)
            await asyncio.sleep(delay)
