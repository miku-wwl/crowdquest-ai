from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from copy import deepcopy

import pytest

from crowdquest.intake import Store, parse_command
from tests.support import notification

NOW = 1_800_000_000.0


def ingest(store, raw, now=NOW):
    return store.ingest(
        raw,
        owner_id="123",
        session_id="session-1",
        subscription_id="sub-1",
        now=now,
        source="synthetic",
    )


@pytest.mark.parametrize(
    "text,reason",
    [
        ("!quest", "EMPTY_QUEST"),
        ("!quest  ", "EMPTY_QUEST"),
        ("", "NOT_QUEST"),
        ("!other abc", "NOT_QUEST"),
        ("!questing abc", "NOT_QUEST"),
        ("!quest " + "a" * 281, "SUGGESTION_SIZE"),
        ("a" * 1121, "MESSAGE_SIZE"),
        ("!quest a\nb", "UNSAFE_CONTROL"),
        ("!quest a\u202eb", "UNSAFE_CONTROL"),
        (None, "MESSAGE_SIZE"),
        ("!quest \ud800", "INVALID_UNICODE"),
    ],
)
def test_parser_rejects(text, reason):
    assert parse_command(text) == (None, reason)


@pytest.mark.parametrize(
    "text",
    [
        "!quest Survive 60 seconds",
        "!quest " + "a" * 280,
        "!quest " + "😀" * 280,
        "!quest <script>window.pwned=1</script>",
    ],
)
def test_parser_bounded_text_is_data(text):
    value, reason = parse_command(text)
    assert reason == "ACCEPTED"
    assert value == text[6:].strip()


def test_first_duplicate_restart_and_persisted_rows(tmp_path):
    path = tmp_path / "intake.sqlite3"
    store = Store(path)
    raw = notification(now=NOW)
    assert ingest(store, raw) == "ACCEPTED"
    assert ingest(store, raw) == "DUPLICATE"
    assert ingest(Store(path), raw) == "DUPLICATE"
    raw["metadata"]["message_id"] = "new-delivery"
    assert ingest(Store(path), raw) == "DUPLICATE"
    with closing(store.connect()) as db:
        assert db.execute("SELECT count(*) FROM candidates").fetchone()[0] == 1
        assert db.execute("SELECT count(*) FROM deliveries").fetchone()[0] == 2
        assert db.execute("SELECT count(*) FROM messages").fetchone()[0] == 1
        assert db.execute("SELECT count FROM reasons WHERE code='DUPLICATE'").fetchone()[0] == 3


def test_concurrent_duplicates_are_atomic(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    raw = notification(now=NOW)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda _: ingest(store, raw), range(16)))
    assert results.count("ACCEPTED") == 1
    assert results.count("DUPLICATE") == 15
    with closing(store.connect()) as db:
        assert db.execute("SELECT count(*) FROM candidates").fetchone()[0] == 1


@pytest.mark.parametrize(
    "where,value,reason",
    [
        (("metadata", "subscription_type"), "channel.follow", "SUBSCRIPTION_TYPE"),
        (("metadata", "subscription_version"), "2", "SUBSCRIPTION_TYPE"),
        (("payload", "subscription", "id"), "wrong", "SUBSCRIPTION_IDENTITY"),
        (("payload", "subscription", "status"), "disabled", "SUBSCRIPTION_IDENTITY"),
        (("payload", "subscription", "transport", "session_id"), "other", "SESSION_IDENTITY"),
        (("payload", "event", "broadcaster_user_id"), "999", "CHANNEL_IDENTITY"),
        (("payload", "subscription", "condition", "user_id"), "999", "CHANNEL_IDENTITY"),
        (("payload", "event", "chatter_user_id"), "", "CHATTER_IDENTITY"),
        (("payload", "event", "message", "text"), [], "EVENT_SHAPE"),
    ],
)
def test_invalid_identity_and_shapes(tmp_path, where, value, reason):
    store = Store(tmp_path / "intake.sqlite3")
    raw = notification(now=NOW)
    target = raw
    for key in where[:-1]:
        target = target[key]
    target[where[-1]] = value
    assert ingest(store, raw) == reason
    assert store.candidates("123") == []


@pytest.mark.parametrize(
    "age,expected", [(600, "ACCEPTED"), (601, "EVENT_TIMESTAMP"), (-31, "EVENT_TIMESTAMP")]
)
def test_event_age(tmp_path, age, expected):
    store = Store(tmp_path / "intake.sqlite3")
    assert ingest(store, notification(now=NOW - age)) == expected


def test_shared_chat_and_wrong_broadcaster(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    assert ingest(store, notification(channel="999", now=NOW)) == "CHANNEL_IDENTITY"
    raw = notification(now=NOW)
    raw["payload"]["event"]["source_broadcaster_user_id"] = "999"
    assert ingest(store, raw) == "SHARED_CHAT_SOURCE"
    assert not store.candidates("123")


def test_identity_conflict(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    raw = notification(now=NOW)
    assert ingest(store, raw) == "ACCEPTED"
    conflict = deepcopy(raw)
    conflict["payload"]["event"]["message"]["text"] = "!quest Different text"
    assert ingest(store, conflict) == "DELIVERY_CONFLICT"
    conflict["metadata"]["message_id"] = "another-delivery"
    assert ingest(store, conflict) == "CHAT_CONFLICT"
    assert len(store.candidates("123")) == 1
    assert store.candidates("123")[0]["suggestion"] == "Survive 60 seconds"


def test_viewer_rate_limit_persists_and_boundary(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    assert ingest(store, notification(now=NOW)) == "ACCEPTED"
    second = notification(delivery="d2", message="m2", now=NOW + 1)
    assert ingest(store, second, NOW + 1) == "VIEWER_RATE_LIMIT"
    assert ingest(Store(store.path), second, NOW + 31) == "DUPLICATE"
    assert (
        ingest(store, notification(delivery="d3", message="m3", now=NOW + 30), NOW + 30)
        == "ACCEPTED"
    )


def test_channel_rate_limit(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    for i in range(10):
        assert (
            ingest(
                store,
                notification(delivery=f"d{i}", message=f"m{i}", viewer=str(1000 + i), now=NOW),
            )
            == "ACCEPTED"
        )
    assert (
        ingest(store, notification(delivery="over", message="over", viewer="9999", now=NOW))
        == "CHANNEL_RATE_LIMIT"
    )
    assert len(store.candidates("123")) == 10


def test_queue_capacity_and_manual_preview_frees_slot(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    for i in range(50):
        now = NOW + i * 61
        assert (
            ingest(store, notification(delivery=f"d{i}", message=f"m{i}", now=now), now)
            == "ACCEPTED"
        )
    now += 61
    assert (
        ingest(store, notification(delivery="full", message="full", now=now), now)
        == "QUEUE_CAPACITY"
    )
    candidate = store.candidates("123")[0]
    assert store.select(candidate["id"], "999") is None
    assert store.select(candidate["id"], "123") is not None
    assert (
        ingest(store, notification(delivery="freed", message="freed", now=now + 61), now + 61)
        == "ACCEPTED"
    )


@pytest.mark.parametrize(
    "text,reason", [("!quest", "EMPTY_QUEST"), ("!quest " + "a" * 281, "SUGGESTION_SIZE")]
)
def test_invalid_commands_persist_rejection_without_candidate(tmp_path, text, reason):
    store = Store(tmp_path / "intake.sqlite3")
    raw = notification(text=text, now=NOW)
    assert ingest(store, raw) == reason
    assert ingest(store, raw) == "DUPLICATE"
    assert not store.candidates("123")
