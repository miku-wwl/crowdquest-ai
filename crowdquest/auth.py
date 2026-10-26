"""Backend-only Twitch code flow and validated owner identity."""

import asyncio
import hashlib
import json
import re
import secrets
import time
from dataclasses import dataclass, field
from urllib.parse import urlencode

import httpx

from .intake import USER_ID

SCOPE = "user:read:chat"
TOKEN_URL = "https://id.twitch.tv/oauth2/token"
VALIDATE_URL = "https://id.twitch.tv/oauth2/validate"


class AuthError(Exception):
    """Only fixed safe reason codes cross into UI/logs."""


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


@dataclass(frozen=True)
class Identity:
    user_id: str
    login: str


@dataclass
class Tokens:
    access: str = field(repr=False)
    refresh: str = field(repr=False)
    expires: float


class TwitchAuth:
    def __init__(self, settings, vault, client=None, clock=time.time):
        self.settings, self.vault, self.clock = settings, vault, clock
        self.client = client or httpx.AsyncClient(
            timeout=10, trust_env=False, follow_redirects=False
        )
        self.identity = None
        self.tokens = None
        self.validated_at = 0
        self.generation = 0
        self.reason = "USER_ACTION_REQUIRED"
        self.states = {}
        self.lock = asyncio.Lock()

    def begin(self):
        if not self.settings.configured:
            raise AuthError("SETUP_REQUIRED")
        now = self.clock()
        self.states = {k: v for k, v in self.states.items() if v[1] > now}
        if len(self.states) >= 8:
            raise AuthError("OAUTH_RATE_LIMIT")
        state, browser = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        self.states[digest(state)] = (digest(browser), now + 300)
        return "https://id.twitch.tv/oauth2/authorize?" + urlencode(
            {
                "client_id": self.settings.client_id,
                "redirect_uri": self.settings.redirect_uri,
                "response_type": "code",
                "scope": SCOPE,
                "state": state,
                "force_verify": "true",
            }
        ), browser

    async def callback(self, state, browser, code):
        saved = self.states.pop(digest(state), None)
        if (
            not saved
            or saved[1] <= self.clock()
            or not secrets.compare_digest(saved[0], digest(browser))
        ):
            raise AuthError("OAUTH_STATE")
        if not code or len(code) > 1024:
            raise AuthError("OAUTH_CODE")
        secret = self.vault.get("client-secret")
        if not secret:
            raise AuthError("SETUP_REQUIRED")
        async with self.lock:
            token_data = await self._post(
                {
                    "client_id": self.settings.client_id,
                    "client_secret": secret,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": self.settings.redirect_uri,
                }
            )
            tokens = self._tokens(token_data)
            identity, expiry = await self._validate(tokens.access)
            tokens.expires = self.clock() + expiry
            self._save(tokens, identity)
            self.generation += 1
            return identity

    def _tokens(self, value):
        try:
            access, refresh, expires = (
                value["access_token"],
                value["refresh_token"],
                value["expires_in"],
            )
            if (
                type(access) is not str
                or not 1 <= len(access) <= 2048
                or type(refresh) is not str
                or not 1 <= len(refresh) <= 2048
                or type(expires) is not int
                or expires <= 0
                or value.get("scope") != [SCOPE]
            ):
                raise ValueError
            return Tokens(access, refresh, self.clock() + expires)
        except (KeyError, TypeError, ValueError):
            raise AuthError("TOKEN_SHAPE_OR_SCOPE") from None

    async def _post(self, data):
        try:
            result = await self.client.post(TOKEN_URL, data=data)
            if result.status_code != 200 or len(result.content) > 16384:
                raise AuthError("TOKEN_EXCHANGE_REJECTED")
            return result.json()
        except (httpx.HTTPError, ValueError):
            raise AuthError("TWITCH_AUTH_UNAVAILABLE") from None

    async def _validate(self, access):
        try:
            result = await self.client.get(
                VALIDATE_URL, headers={"Authorization": f"OAuth {access}"}
            )
            if result.status_code == 401:
                raise AuthError("TOKEN_REVOKED")
            if result.status_code != 200 or len(result.content) > 16384:
                raise AuthError("TOKEN_VALIDATION_FAILED")
            value = result.json()
            if (
                value.get("client_id") != self.settings.client_id
                or value.get("login") != self.settings.owner_login
                or value.get("scopes") != [SCOPE]
                or type(value.get("user_id")) is not str
                or not re.fullmatch(USER_ID, value["user_id"])
                or type(value.get("expires_in")) is not int
                or value["expires_in"] <= 0
            ):
                raise AuthError("OWNER_CLIENT_OR_SCOPE_MISMATCH")
            return Identity(value["user_id"], value["login"]), value["expires_in"]
        except (httpx.HTTPError, ValueError):
            raise AuthError("TWITCH_AUTH_UNAVAILABLE") from None

    def _save(self, tokens, identity):
        # Save before publishing identity; vault failure cannot produce an authenticated session.
        self.vault.set(
            "tokens",
            json.dumps(
                {
                    "access_token": tokens.access,
                    "refresh_token": tokens.refresh,
                    "expires_in": max(1, int(tokens.expires - self.clock())),
                    "scope": [SCOPE],
                    "expires_at": tokens.expires,
                }
            ),
        )
        self.tokens, self.identity = tokens, identity
        self.validated_at, self.reason = self.clock(), "AUTHENTICATED"

    def invalidate(self, reason):
        self.identity, self.tokens = None, None
        self.generation += 1
        self.reason = reason
        try:
            self.vault.delete("tokens")
        except RuntimeError:
            pass

    async def ensure(self):
        async with self.lock:
            if not self.settings.configured:
                return None
            try:
                if self.tokens is None:
                    saved = self.vault.get("tokens")
                    if not saved:
                        return None
                    value = json.loads(saved)
                    self.tokens = self._tokens(value)
                    self.tokens.expires = float(value["expires_at"])
                tokens = self.tokens
                if tokens.expires <= self.clock() + 60:
                    secret = self.vault.get("client-secret")
                    if not secret:
                        raise AuthError("SETUP_REQUIRED")
                    refreshed = await self._post(
                        {
                            "client_id": self.settings.client_id,
                            "client_secret": secret,
                            "grant_type": "refresh_token",
                            "refresh_token": tokens.refresh,
                        }
                    )
                    tokens = self._tokens(refreshed)
                    # Retain rotated refresh token even if subsequent validation fails.
                    self.tokens = tokens
                    self.identity = None
                    self.validated_at = 0
                if self.identity is None or self.clock() - self.validated_at >= 3600:
                    identity, expires = await self._validate(tokens.access)
                    tokens.expires = self.clock() + expires
                    self._save(tokens, identity)
                return self.identity
            except (AuthError, RuntimeError, KeyError, TypeError, ValueError):
                self.invalidate("REAUTHENTICATION_REQUIRED")
                return None

    async def close(self):
        await self.client.aclose()
