"""Synthetic EventSub envelopes and real temporary SQLite voting transactions."""

import json
import os
import sqlite3
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
from uuid import uuid4

import pytest

from crowdquest.intake import Store
from crowdquest.voting import parse_vote
from tests.support import notification

NOW = 1800000000.0


def ingest(store, number, text, *, viewer=None, channel="123", now=NOW):
    return store.ingest(
        notification(
            delivery=f"delivery-{number}",
            message=f"message-{number}",
            viewer=str(viewer or 400 + number),
            text=text,
            channel=channel,
            now=now,
        ),
        owner_id=channel,
        session_id="session-1",
        subscription_id="sub-1",
        now=now,
        source="synthetic",
    )


def draft(store, *, channel="123", now=NOW):
    for number in (1, 2):
        assert (
            ingest(
                store, int(channel) * 10 + number, "!quest " + str(number), channel=channel, now=now
            )
            == "ACCEPTED"
        )
    candidates = [c["id"] for c in store.candidates(channel)]
    return store.voting.create(channel, candidates, 15, str(uuid4()), now=now)


def opened(store, **kwargs):
    row = draft(store, **kwargs)
    return store.voting.transition(
        kwargs.get("channel", "123"),
        row["id"],
        "start",
        row["version"],
        str(uuid4()),
        now=kwargs.get("now", NOW),
    )


@pytest.mark.parametrize(
    "text",
    [
        "!vote 0",
        "!vote 3",
        "!vote 01",
        "!vote 1 ",
        "!vote\t1",
        "!vote 1\n",
        "!vote 1<script>",
        "!vote",
        "!vote １",
        "!vote " + "1" * 1200,
    ],
)
def test_strict_vote_commands(text):
    assert parse_vote(text)[0] is None


def test_state_machine_timeout_tie_selection_and_binding(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    row = opened(store)
    assert row["state"] == "Open" and row["remaining_seconds"] <= 15
    assert ingest(store, 10, "!vote 1", now=NOW + 1) == "VOTE_ACCEPTED"
    assert ingest(store, 11, "!vote 2", now=NOW + 1) == "VOTE_ACCEPTED"
    closed = store.voting.current("123", now=NOW + 15)
    assert closed["state"] == "Closed" and closed["winner"] is None
    assert ingest(store, 12, "!vote 1", now=NOW + 15) == "VOTING_CLOSED"
    with pytest.raises(ValueError, match="WINNER_NOT_READY"):
        store.voting.bind_winner("123", row["id"], closed["version"], now=NOW + 16)
    chosen = store.voting.transition(
        "123", row["id"], "winner", closed["version"], str(uuid4()), choice=2, now=NOW + 16
    )
    candidate = store.voting.bind_winner("123", row["id"], chosen["version"], now=NOW + 17)
    assert candidate["id"] == chosen["choices"][1]["candidate_id"]
    with pytest.raises(sqlite3.IntegrityError):
        store.voting.bind_winner("123", row["id"], chosen["version"], now=NOW + 17)


def test_eventsub_dedup_privacy_and_one_vote_per_viewer(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    row = opened(store)
    assert ingest(store, 10, "!vote 1", viewer=789012345, now=NOW + 1) == "VOTE_ACCEPTED"
    assert ingest(store, 10, "!vote 1", viewer=789012345, now=NOW + 1) == "DUPLICATE"
    assert ingest(store, 11, "!vote 2", viewer=789012345, now=NOW + 2) == "DUPLICATE_VOTE"
    envelope = notification(
        delivery="another-delivery",
        message="message-10",
        viewer="789012345",
        text="!vote 1",
        now=NOW + 3,
    )
    assert (
        store.ingest(
            envelope, owner_id="123", session_id="session-1", subscription_id="sub-1", now=NOW + 3
        )
        == "DUPLICATE"
    )
    snapshot = store.voting.current("123", now=NOW + 3)
    assert [c["votes"] for c in snapshot["choices"]] == [1, 0]
    assert "789012345" not in json.dumps(snapshot)
    with closing(store.connect()) as db:
        voter = db.execute("SELECT voter FROM crowd_votes").fetchone()[0]
        assert len(voter) == 64 and "789012345" not in voter
        assert "viewer" not in [r[1] for r in db.execute("PRAGMA table_info(crowd_votes)")]
    assert snapshot["id"] == row["id"]


def test_concurrent_votes_and_duplicate_race_are_transactional(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    opened(store)
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda n: ingest(store, n, "!vote 1", now=NOW + 1), range(20, 60)))
    assert results.count("VOTE_ACCEPTED") == 40
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(
            pool.map(
                lambda n: ingest(store, n, "!vote 2", viewer=9999, now=NOW + 2), range(100, 108)
            )
        )
    assert results.count("VOTE_ACCEPTED") == 1 and results.count("DUPLICATE_VOTE") == 7
    assert store.voting.current("123", now=NOW + 2)["total_votes"] == 41


def test_one_active_round_cas_and_command_conflict(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    row = draft(store)
    candidates = [c["candidate_id"] for c in row["choices"]]
    with pytest.raises(sqlite3.IntegrityError):
        store.voting.create("123", candidates, 15, str(uuid4()), now=NOW)
    key = str(uuid4())
    first = store.voting.transition("123", row["id"], "start", 1, key, now=NOW)
    assert (
        store.voting.transition("123", row["id"], "start", 1, key, now=NOW)["version"]
        == first["version"]
    )
    with pytest.raises(ValueError, match="COMMAND_CONFLICT"):
        store.voting.transition("123", row["id"], "close", 2, key, now=NOW)
    with ThreadPoolExecutor(max_workers=2) as pool:

        def close():
            try:
                return store.voting.transition(
                    "123", row["id"], "close", 2, str(uuid4()), now=NOW + 1
                )["state"]
            except ValueError as error:
                return str(error)

        results = list(pool.map(lambda _: close(), range(2)))
    assert sorted(results) == ["Closed", "STALE_ROUND"]


def test_restart_retains_key_tallies_deadline_and_no_reopening(tmp_path):
    path = tmp_path / "intake.sqlite3"
    store = Store(path)
    row = opened(store)
    ingest(store, 10, "!vote 1", now=NOW + 1)
    restarted = Store(path)
    assert restarted.voting.key == store.voting.key
    current = restarted.voting.current("123", now=NOW + 10)
    assert current["total_votes"] == 1 and current["remaining_seconds"] <= 5
    closed = restarted.voting.current("123", now=NOW + 16)
    assert closed["state"] == "Closed" and closed["winner"] == 1
    with pytest.raises(ValueError):
        restarted.voting.transition(
            "123", row["id"], "start", closed["version"], str(uuid4()), now=NOW + 16
        )


def test_missing_or_replaced_privacy_key_fails_closed(tmp_path):
    path = tmp_path / "intake.sqlite3"
    Store(path)
    key = path.with_suffix(".voting.key")
    key.unlink()
    with pytest.raises(ValueError, match="KEY_MISSING"):
        Store(path)
    key.write_bytes(b"x" * 32)
    with pytest.raises(ValueError, match="KEY_CHANGED"):
        Store(path)


def test_cross_channel_unknown_source_rate_and_clock_rollback(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    row = opened(store)
    assert ingest(store, 10, "!vote 1", channel="321", now=NOW + 1) == "VOTING_CLOSED"
    assert store.voting.current("123", now=NOW + 1)["total_votes"] == 0
    with pytest.raises(ValueError, match="ROUND_NOT_FOUND"):
        store.voting.transition("321", row["id"], "close", 2, str(uuid4()), now=NOW + 1)
    with closing(store.connect()) as db:
        for n in range(60):
            db.execute(
                "INSERT INTO crowd_votes VALUES(?,?,1,?)", (row["id"], f"fixture-{n}", NOW + 1)
            )
        db.commit()
    assert ingest(store, 11, "!vote 1", now=NOW + 1) == "VOTE_CHANNEL_RATE_LIMIT"
    assert store.voting.current("123", now=NOW - 10)["reason"] == "CLOCK_UNCERTAIN"


def test_write_contention_rolls_back_event_then_explicit_delivery_can_be_processed(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    opened(store)
    with closing(store.connect()) as blocker:
        blocker.execute("BEGIN IMMEDIATE")
        with pytest.raises(sqlite3.OperationalError, match="locked"):
            ingest(store, 10, "!vote 1", now=NOW + 1)
        blocker.rollback()
    assert ingest(store, 10, "!vote 1", now=NOW + 1) == "VOTE_ACCEPTED"
    assert store.voting.current("123", now=NOW + 1)["total_votes"] == 1


@pytest.mark.parametrize("point,expected", [("before", 0), ("after", 1)])
def test_actual_process_interruption_preserves_atomic_vote_and_dedup(tmp_path, point, expected):
    now = time.time()
    store = Store(tmp_path / "intake.sqlite3")
    opened(store, now=now)
    envelope = notification(
        delivery="crash-vote", message="crash-chat", viewer="888", text="!vote 1"
    )
    (tmp_path / "fixture-event.json").write_text(json.dumps(envelope), encoding="utf-8")
    process = subprocess.run(
        [sys.executable, "-m", "tests.voting_crash", str(tmp_path), point],
        capture_output=True,
        check=False,
        timeout=10,
        creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0,
    )
    assert process.returncode == (94 if point == "before" else 95), process.stderr.decode()
    restarted = Store(tmp_path / "intake.sqlite3")
    assert restarted.voting.current("123")["total_votes"] == expected
    with closing(restarted.connect()) as db:
        assert db.execute("PRAGMA integrity_check").fetchall()[0][0] == "ok"
        assert (
            db.execute("SELECT count(*) FROM deliveries WHERE id='crash-vote'").fetchone()[0]
            == expected
        )
    result = restarted.ingest(
        envelope,
        owner_id="123",
        session_id="session-1",
        subscription_id="sub-1",
        source="synthetic",
    )
    assert result == ("DUPLICATE" if expected else "VOTE_ACCEPTED")
    assert restarted.voting.current("123")["total_votes"] == 1


def test_winner_snapshot_tampering_and_cross_channel_audit(tmp_path):
    store = Store(tmp_path / "intake.sqlite3")
    row = opened(store)
    ingest(store, 10, "!vote 1", now=NOW + 1)
    closed = store.voting.transition("123", row["id"], "close", 2, str(uuid4()), now=NOW + 2)
    winner = closed["choices"][0]["candidate_id"]
    with closing(store.connect()) as db:
        db.execute("UPDATE candidates SET suggestion='fixture corruption' WHERE id=?", (winner,))
        db.commit()
    with pytest.raises(ValueError, match="WINNER_BINDING_CHANGED"):
        store.voting.bind_winner("123", row["id"], closed["version"], now=NOW + 3)
    assert store.voting.audit("123") and store.voting.audit("999") == []
