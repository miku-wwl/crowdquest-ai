"""Strict EventSub admission into consumer SQLite, independent of AIG."""

import hashlib
import json
import re
import sqlite3
import time
import unicodedata
from contextlib import closing
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from pydantic import BaseModel, ConfigDict, Field, ValidationError

ID = r"^[A-Za-z0-9_-]{1,128}$"
OPAQUE_DELIVERY_ID = r"^[\x21-\x7e]{1,128}$"
USER_ID = r"^[1-9][0-9]{0,24}$"


class InvalidEvent(ValueError):
    pass


class Metadata(BaseModel):
    model_config = ConfigDict(strict=True, extra="ignore")
    # Twitch delivery IDs are opaque strings, not UUIDs or URL-safe identifiers.
    # Preserve printable ASCII (including Base64 + / =) exactly for deduplication.
    message_id: str = Field(pattern=OPAQUE_DELIVERY_ID)
    message_type: str
    message_timestamp: str
    subscription_type: str | None = None
    subscription_version: str | None = None


def timestamp(value: str, now: float) -> float:
    try:
        if not re.fullmatch(
            r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d{1,9})?"
            r"(?:Z|[+-](?:[01]\d|2[0-3]):[0-5]\d)",
            value,
        ):
            raise ValueError
        parsed = datetime.fromisoformat(value).timestamp()
        if not now - 600 <= parsed <= now + 30:
            raise ValueError
        return parsed
    except (ValueError, TypeError, OverflowError):
        raise InvalidEvent("EVENT_TIMESTAMP") from None


def parse_command(text):
    if not isinstance(text, str) or len(text) > 1120:
        return None, "MESSAGE_SIZE"
    if not text.startswith("!quest") or (len(text) > 6 and not text[6].isspace()):
        return None, "NOT_QUEST"
    if len(text) < 7 or not text[6:].strip():
        return None, "EMPTY_QUEST"
    suggestion = text[6:].strip()
    try:
        if len(suggestion) > 280 or len(suggestion.encode("utf-8")) > 1120:
            return None, "SUGGESTION_SIZE"
        if any(unicodedata.category(c).startswith("C") or c in "\r\n" for c in suggestion):
            return None, "UNSAFE_CONTROL"
    except UnicodeError:
        return None, "INVALID_UNICODE"
    return suggestion, "ACCEPTED"


def canonical(value):
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=True, separators=(",", ":")).encode()
    ).hexdigest()


def validate_notification(raw, *, owner_id, session_id, subscription_id, now):
    try:
        meta = Metadata.model_validate(raw["metadata"])
        if (meta.message_type, meta.subscription_type, meta.subscription_version) != (
            "notification",
            "channel.chat.message",
            "1",
        ):
            raise InvalidEvent("SUBSCRIPTION_TYPE")
        event_time = timestamp(meta.message_timestamp, now)
        sub = raw["payload"]["subscription"]
        if (sub["id"], sub["type"], sub["version"], sub["status"]) != (
            subscription_id,
            "channel.chat.message",
            "1",
            "enabled",
        ):
            raise InvalidEvent("SUBSCRIPTION_IDENTITY")
        if (
            sub["transport"].get("method") != "websocket"
            or sub["transport"].get("session_id") != session_id
        ):
            raise InvalidEvent("SESSION_IDENTITY")
        if sub["condition"] != {"broadcaster_user_id": owner_id, "user_id": owner_id}:
            raise InvalidEvent("CHANNEL_IDENTITY")
        event = raw["payload"]["event"]
        if event["broadcaster_user_id"] != owner_id:
            raise InvalidEvent("CHANNEL_IDENTITY")
        if event.get("source_broadcaster_user_id") not in (None, owner_id):
            raise InvalidEvent("SHARED_CHAT_SOURCE")
        if not re.fullmatch(USER_ID, event["chatter_user_id"]):
            raise InvalidEvent("CHATTER_IDENTITY")
        if not re.fullmatch(ID, event["message_id"]):
            raise InvalidEvent("CHAT_MESSAGE_ID")
        text = event["message"]["text"]
        if type(text) is not str:
            raise InvalidEvent("EVENT_SHAPE")
        # Only the stable chat fields are hashed; no private fragments/display names retained.
        stable = {
            "channel": owner_id,
            "message": event["message_id"],
            "viewer": event["chatter_user_id"],
            "text": text,
            "source": event.get("source_broadcaster_user_id"),
        }
        return meta.message_id, event_time, stable, canonical(stable), canonical(raw)
    except InvalidEvent:
        raise
    except (KeyError, TypeError, ValueError, ValidationError):
        raise InvalidEvent("EVENT_SHAPE") from None


class Store:
    def __init__(self, path: Path):
        self.path = path
        path.parent.mkdir(parents=True, exist_ok=True)
        with closing(self.connect()) as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE IF NOT EXISTS deliveries (
                    id TEXT PRIMARY KEY, digest TEXT NOT NULL, received REAL NOT NULL
                ) STRICT;
                CREATE TABLE IF NOT EXISTS messages (
                    channel TEXT NOT NULL, id TEXT NOT NULL, digest TEXT NOT NULL,
                    reason TEXT NOT NULL, PRIMARY KEY(channel,id)
                ) STRICT;
                CREATE TABLE IF NOT EXISTS candidates (
                    id TEXT PRIMARY KEY, channel TEXT NOT NULL, chat_id TEXT NOT NULL,
                    delivery_id TEXT NOT NULL UNIQUE, viewer_hash TEXT NOT NULL,
                    suggestion TEXT NOT NULL, received REAL NOT NULL, event_time REAL NOT NULL,
                    state TEXT NOT NULL CHECK(state IN ('candidate','previewed')),
                    source TEXT NOT NULL CHECK(source IN ('twitch_eventsub','synthetic')),
                    UNIQUE(channel,chat_id)
                ) STRICT;
                CREATE TABLE IF NOT EXISTS reasons (
                    code TEXT PRIMARY KEY, count INTEGER NOT NULL, last_time REAL NOT NULL
                ) STRICT;
            """)

    def connect(self):
        db = sqlite3.connect(self.path, timeout=2)
        db.row_factory = sqlite3.Row
        db.execute("PRAGMA foreign_keys=ON")
        return db

    @staticmethod
    def _reason(db, reason, now):
        db.execute(
            "INSERT INTO reasons VALUES (?,1,?) ON CONFLICT(code) DO UPDATE SET "
            "count=count+1,last_time=excluded.last_time",
            (reason, now),
        )
        return reason

    def reject(self, reason, now=None):
        with closing(self.connect()) as db, db:
            return self._reason(db, reason, time.time() if now is None else now)

    def ingest(
        self, raw, *, owner_id, session_id, subscription_id, now=None, source="twitch_eventsub"
    ):
        now = time.time() if now is None else now
        try:
            delivery, event_time, stable, digest, delivery_digest = validate_notification(
                raw,
                owner_id=owner_id,
                session_id=session_id,
                subscription_id=subscription_id,
                now=now,
            )
        except InvalidEvent as error:
            return self.reject(str(error), now)
        suggestion, reason = parse_command(stable["text"])
        if reason == "NOT_QUEST":
            return reason  # Normal chat is neither persisted nor counted as a rejection.
        viewer = canonical({"channel": owner_id, "viewer": stable["viewer"]})
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            previous = db.execute(
                "SELECT digest FROM deliveries WHERE id=?", (delivery,)
            ).fetchone()
            if previous:
                return self._reason(
                    db, "DUPLICATE" if previous[0] == delivery_digest else "DELIVERY_CONFLICT", now
                )
            if db.execute("SELECT count(*) FROM deliveries").fetchone()[0] >= 10000:
                return self._reason(db, "DEDUP_CAPACITY", now)
            db.execute("INSERT INTO deliveries VALUES (?,?,?)", (delivery, delivery_digest, now))
            previous = db.execute(
                "SELECT digest FROM messages WHERE channel=? AND id=?",
                (owner_id, stable["message"]),
            ).fetchone()
            if previous:
                return self._reason(
                    db, "DUPLICATE" if previous[0] == digest else "CHAT_CONFLICT", now
                )
            if suggestion is not None:
                if db.execute("SELECT count(*) FROM candidates").fetchone()[0] >= 500:
                    reason = "HISTORY_CAPACITY"
                elif (
                    db.execute(
                        "SELECT count(*) FROM candidates WHERE state='candidate'"
                    ).fetchone()[0]
                    >= 50
                ):
                    reason = "QUEUE_CAPACITY"
                elif (
                    db.execute(
                        "SELECT count(*) FROM candidates WHERE viewer_hash=? AND received>?",
                        (viewer, now - 30),
                    ).fetchone()[0]
                    >= 1
                ):
                    reason = "VIEWER_RATE_LIMIT"
                elif (
                    db.execute(
                        "SELECT count(*) FROM candidates WHERE channel=? AND received>?",
                        (owner_id, now - 60),
                    ).fetchone()[0]
                    >= 10
                ):
                    reason = "CHANNEL_RATE_LIMIT"
                elif (
                    db.execute(
                        "SELECT count(*) FROM candidates WHERE received>?", (now - 60,)
                    ).fetchone()[0]
                    >= 20
                ):
                    reason = "GLOBAL_RATE_LIMIT"
            db.execute(
                "INSERT INTO messages VALUES (?,?,?,?)",
                (owner_id, stable["message"], digest, reason),
            )
            if reason == "ACCEPTED":
                db.execute(
                    "INSERT INTO candidates VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (
                        str(uuid4()),
                        owner_id,
                        stable["message"],
                        delivery,
                        viewer,
                        suggestion,
                        now,
                        event_time,
                        "candidate",
                        source,
                    ),
                )
            return self._reason(db, reason, now)

    def candidates(self, owner_id):
        with closing(self.connect()) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT id,suggestion,event_time,state,source FROM candidates WHERE channel=? "
                    "ORDER BY received DESC LIMIT 50",
                    (owner_id,),
                )
            ]

    def select(self, candidate_id, owner_id):
        with closing(self.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT suggestion,source FROM candidates WHERE id=? AND channel=?",
                (candidate_id, owner_id),
            ).fetchone()
            if row:
                db.execute("UPDATE candidates SET state='previewed' WHERE id=?", (candidate_id,))
                return dict(row)
        return None
