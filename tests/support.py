"""Explicit synthetic dependencies. These are never selectable by production config."""

import asyncio
import json
import time
from datetime import UTC, datetime

import httpx

from crowdquest.auth import SCOPE, TwitchAuth
from crowdquest.config import Settings


class MemoryVault:
    def __init__(self):
        self.values = {"client-secret": "synthetic-secret-not-a-credential"}

    def get(self, name):
        return self.values.get(name)

    def set(self, name, value):
        self.values[name] = value

    def delete(self, name):
        self.values.pop(name, None)


class PassiveEventSub:
    status, reason, last_event_at = "synthetic", "SYNTHETIC_TEST_TRANSPORT", None

    def __init__(self, auth, store):
        pass

    async def run(self):
        await asyncio.Event().wait()


class MockTwitch:
    def __init__(self):
        self.calls = []
        self.validate_status = 200
        self.validation = {
            "client_id": "fixtureclient",
            "login": "fixture_owner",
            "user_id": "123",
            "scopes": [SCOPE],
            "expires_in": 3600,
        }
        self.token = {
            "access_token": "synthetic-access",
            "refresh_token": "synthetic-refresh",
            "expires_in": 3600,
            "scope": [SCOPE],
        }

    def __call__(self, request):
        self.calls.append(request)
        if request.url.path == "/oauth2/token":
            return httpx.Response(200, json=self.token)
        if request.url.path == "/oauth2/validate":
            return httpx.Response(self.validate_status, json=self.validation)
        if request.url.path == "/helix/eventsub/subscriptions":
            body = json.loads(request.content)
            return httpx.Response(
                202, json={"data": [{**body, "id": "sub-1", "status": "enabled"}]}
            )
        raise AssertionError("Unexpected synthetic network destination")


def make_auth(directory, *, clock=time.time, port=8000):
    settings = Settings(
        state_dir=directory, client_id="fixtureclient", owner_login="fixture_owner", port=port
    )
    mock = MockTwitch()
    vault = MemoryVault()
    client = httpx.AsyncClient(transport=httpx.MockTransport(mock), trust_env=False)
    return settings, TwitchAuth(settings, vault, client=client, clock=clock), mock


def notification(
    *,
    delivery="delivery-1",
    message="chat-1",
    viewer="456",
    text="!quest Survive 60 seconds",
    channel="123",
    session="session-1",
    now=None,
):
    now = time.time() if now is None else now
    return {
        "metadata": {
            "message_id": delivery,
            "message_type": "notification",
            "message_timestamp": datetime.fromtimestamp(now, UTC)
            .isoformat()
            .replace("+00:00", "Z"),
            "subscription_type": "channel.chat.message",
            "subscription_version": "1",
        },
        "payload": {
            "subscription": {
                "id": "sub-1",
                "type": "channel.chat.message",
                "version": "1",
                "status": "enabled",
                "condition": {"broadcaster_user_id": channel, "user_id": channel},
                "transport": {"method": "websocket", "session_id": session},
            },
            "event": {
                "broadcaster_user_id": channel,
                "chatter_user_id": viewer,
                "message_id": message,
                "message": {"text": text},
            },
        },
    }
