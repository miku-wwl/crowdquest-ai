"""Consumer-only crowd voting; no runtime, grant, executor or model authority."""

import hashlib
import hmac
import json
import os
import secrets
import time
from contextlib import closing
from uuid import uuid4

from filelock import FileLock


def parse_vote(text):
    if type(text) is not str or len(text) > 1120:
        return None, "MESSAGE_SIZE"
    if not text.startswith("!vote") or (len(text) > 5 and not text[5].isspace()):
        return None, "NOT_VOTE"
    if text not in ("!vote 1", "!vote 2"):
        return None, "INVALID_VOTE"
    return int(text[-1]), "VOTE_ACCEPTED"


class VotingStore:
    def __init__(self, intake, *, clock=time.time, monotonic=time.monotonic):
        self.intake, self.clock, self.monotonic = intake, clock, monotonic
        self.anchors = {}
        with closing(intake.connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS voting_identity(singleton INTEGER PRIMARY KEY,
                    key_digest TEXT NOT NULL) STRICT;
                CREATE TABLE IF NOT EXISTS voting_rounds(
                    id TEXT PRIMARY KEY, channel TEXT NOT NULL, state TEXT NOT NULL
                        CHECK(state IN ('Draft','Open','Closed','Cancelled')),
                    version INTEGER NOT NULL, candidate1 TEXT NOT NULL REFERENCES candidates(id),
                    candidate2 TEXT NOT NULL REFERENCES candidates(id), text1 TEXT NOT NULL,
                    text2 TEXT NOT NULL, duration INTEGER NOT NULL CHECK(duration IN (15,30,60)),
                    created REAL NOT NULL, opened REAL, deadline REAL, last_seen REAL,
                    closed REAL, winner INTEGER CHECK(winner IN (1,2)), reason TEXT,
                    CHECK(candidate1!=candidate2)) STRICT;
                CREATE UNIQUE INDEX IF NOT EXISTS one_open_vote_per_channel
                    ON voting_rounds(channel) WHERE state IN ('Draft','Open');
                CREATE TABLE IF NOT EXISTS crowd_votes(round_id TEXT NOT NULL
                    REFERENCES voting_rounds(id), voter TEXT NOT NULL, choice INTEGER NOT NULL
                    CHECK(choice IN (1,2)), received REAL NOT NULL,
                    PRIMARY KEY(round_id,voter)) STRICT;
                CREATE INDEX IF NOT EXISTS voting_rate ON crowd_votes(received);
                CREATE TABLE IF NOT EXISTS voting_commands(key TEXT PRIMARY KEY,
                    channel TEXT NOT NULL, digest TEXT NOT NULL, round_id TEXT NOT NULL) STRICT;
                CREATE TABLE IF NOT EXISTS voting_origins(candidate_id TEXT PRIMARY KEY
                    REFERENCES candidates(id), round_id TEXT UNIQUE NOT NULL
                    REFERENCES voting_rounds(id)) STRICT;
                CREATE TABLE IF NOT EXISTS voting_audit(sequence INTEGER PRIMARY KEY,
                    channel TEXT NOT NULL, at REAL NOT NULL, kind TEXT NOT NULL, correlation TEXT NOT NULL) STRICT;
            """)
        # The key is never regenerated for an existing voting identity. An interrupted
        # first creation can leave the private key, which is reused, never overwritten.
        key_path = intake.path.with_suffix(".voting.key")
        with FileLock(str(key_path) + ".lock"), closing(intake.connect()) as db:
            identity = db.execute("SELECT key_digest FROM voting_identity").fetchone()
            if identity and not key_path.is_file():
                raise ValueError("VOTER_KEY_MISSING")
            if not key_path.exists():
                with os.fdopen(
                    os.open(key_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600), "wb"
                ) as stream:
                    stream.write(secrets.token_bytes(32))
            self.key = key_path.read_bytes()
            if len(self.key) != 32:
                raise ValueError("VOTER_KEY_INVALID")
            digest = hashlib.sha256(self.key).hexdigest()
            if identity and not hmac.compare_digest(identity[0], digest):
                raise ValueError("VOTER_KEY_CHANGED")
            db.execute("INSERT OR IGNORE INTO voting_identity VALUES(1,?)", (digest,))
            db.commit()

    @staticmethod
    def _audit(db, kind, identity, now, channel):
        db.execute(
            "INSERT INTO voting_audit(channel,at,kind,correlation) VALUES(?,?,?,?)",
            (channel, now, kind, hashlib.sha256(identity.encode()).hexdigest()[:12]),
        )

    @staticmethod
    def _totals(db, round_id):
        values = dict(
            db.execute(
                "SELECT choice,count(*) FROM crowd_votes WHERE round_id=? GROUP BY choice",
                (round_id,),
            )
        )
        return [values.get(1, 0), values.get(2, 0)]

    def _remaining(self, row, now):
        if row["id"] not in self.anchors:
            self.anchors[row["id"]] = self.monotonic() + max(
                0, min(row["duration"], row["deadline"] - now)
            )
        return max(0, min(row["deadline"] - now, self.anchors[row["id"]] - self.monotonic()))

    def _close(self, db, row, now, reason):
        a, b = self._totals(db, row["id"])
        winner = 1 if a > b else 2 if b > a else None
        db.execute(
            "UPDATE voting_rounds SET state='Closed',closed=?,winner=?,reason=?,version=version+1 WHERE id=? AND state='Open'",
            (now, winner, reason, row["id"]),
        )
        self._audit(db, "ROUND_" + reason, row["id"], now, row["channel"])

    def _expire(self, db, channel, now):
        for row in db.execute(
            "SELECT * FROM voting_rounds WHERE channel=? AND state='Open'", (channel,)
        ).fetchall():
            if now < row["last_seen"] - 2:
                self._close(db, row, now, "CLOCK_UNCERTAIN")
            elif self._remaining(row, now) <= 0:
                self._close(db, row, min(now, row["deadline"]), "EXPIRED")
            else:
                db.execute(
                    "UPDATE voting_rounds SET last_seen=MAX(last_seen,?) WHERE id=?",
                    (now, row["id"]),
                )

    def _snapshot(self, db, row, now):
        if row is None:
            return None
        totals = self._totals(db, row["id"])
        return {
            "id": row["id"],
            "state": row["state"],
            "version": row["version"],
            "choices": [
                {
                    "number": n,
                    "candidate_id": row[f"candidate{n}"],
                    "text": row[f"text{n}"],
                    "votes": totals[n - 1],
                    "percentage": round(totals[n - 1] * 100 / sum(totals), 1) if sum(totals) else 0,
                }
                for n in (1, 2)
            ],
            "total_votes": sum(totals),
            "evidence": "SYNTHETIC_TEST"
            if db.execute(
                "SELECT 1 FROM candidates WHERE id IN (?,?) AND source='synthetic'",
                (row["candidate1"], row["candidate2"]),
            ).fetchone()
            else "REAL_TWITCH",
            "duration_seconds": row["duration"],
            "remaining_seconds": self._remaining(row, now) if row["state"] == "Open" else 0,
            "winner": row["winner"],
            "reason": row["reason"],
            "plan_bound": bool(
                db.execute("SELECT 1 FROM voting_origins WHERE round_id=?", (row["id"],)).fetchone()
            ),
        }

    def current(self, channel, *, now=None):
        now = self.clock() if now is None else now
        with closing(self.intake.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._expire(db, channel, now)
            row = db.execute(
                "SELECT * FROM voting_rounds WHERE channel=? ORDER BY rowid DESC LIMIT 1",
                (channel,),
            ).fetchone()
            return self._snapshot(db, row, now)

    def _command(self, db, channel, key, value):
        from .admission import uuid4_string

        if not uuid4_string(key):
            raise ValueError("VOTING_COMMAND_ID")
        digest = hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()
        old = db.execute(
            "SELECT channel,digest,round_id FROM voting_commands WHERE key=?", (key,)
        ).fetchone()
        if old and (old[0], old[1]) != (channel, digest):
            raise ValueError("VOTING_COMMAND_CONFLICT")
        return digest, old[2] if old else None

    def create(self, channel, candidates, duration, key, *, now=None):
        now = self.clock() if now is None else now
        if (
            len(candidates) != 2
            or len(set(candidates)) != 2
            or type(duration) is not int
            or duration not in (15, 30, 60)
        ):
            raise ValueError("SHORTLIST_EXACTLY_TWO")
        with closing(self.intake.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            digest, old = self._command(db, channel, key, ["create", candidates, duration])
            self._expire(db, channel, now)
            if old:
                return self._snapshot(
                    db, db.execute("SELECT * FROM voting_rounds WHERE id=?", (old,)).fetchone(), now
                )
            if db.execute("SELECT count(*) FROM voting_rounds").fetchone()[0] >= 500:
                raise ValueError("ROUND_CAPACITY")
            if (
                db.execute(
                    "SELECT count(*) FROM voting_rounds WHERE channel=? AND created>?",
                    (channel, now - 60),
                ).fetchone()[0]
                >= 6
            ):
                raise ValueError("ROUND_RATE_LIMIT")
            choices = []
            for candidate in candidates:
                row = db.execute(
                    "SELECT suggestion FROM candidates WHERE id=? AND channel=?",
                    (candidate, channel),
                ).fetchone()
                if (
                    row is None
                    or db.execute(
                        "SELECT 1 FROM voting_origins WHERE candidate_id=?", (candidate,)
                    ).fetchone()
                ):
                    raise ValueError("CANDIDATE_UNAVAILABLE")
                choices.append(row[0])
            identity = str(uuid4())
            db.execute(
                "INSERT INTO voting_rounds VALUES(?,?,'Draft',1,?,?,?,?,?,?,NULL,NULL,NULL,NULL,NULL,NULL)",
                (identity, channel, *candidates, *choices, duration, now),
            )
            db.execute(
                "INSERT INTO voting_commands VALUES(?,?,?,?)", (key, channel, digest, identity)
            )
            self._audit(db, "ROUND_CREATED", identity, now, channel)
            return self._snapshot(
                db,
                db.execute("SELECT * FROM voting_rounds WHERE id=?", (identity,)).fetchone(),
                now,
            )

    def transition(self, channel, identity, operation, version, key, *, choice=None, now=None):
        now = self.clock() if now is None else now
        with closing(self.intake.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            digest, old = self._command(db, channel, key, [identity, operation, version, choice])
            self._expire(db, channel, now)
            row = db.execute(
                "SELECT * FROM voting_rounds WHERE id=? AND channel=?", (identity, channel)
            ).fetchone()
            if row is None:
                raise ValueError("ROUND_NOT_FOUND")
            if old:
                return self._snapshot(db, row, now)
            if row["version"] != version:
                raise ValueError("STALE_ROUND")
            if operation == "start" and row["state"] == "Draft":
                self.anchors[identity] = self.monotonic() + row["duration"]
                db.execute(
                    "UPDATE voting_rounds SET state='Open',version=version+1,opened=?,deadline=?,last_seen=? WHERE id=?",
                    (now, now + row["duration"], now, identity),
                )
            elif operation == "close" and row["state"] == "Open":
                self._close(db, row, now, "OWNER_CLOSED")
            elif operation == "cancel" and row["state"] in ("Draft", "Open"):
                db.execute(
                    "UPDATE voting_rounds SET state='Cancelled',version=version+1,closed=? WHERE id=?",
                    (now, identity),
                )
            elif (
                operation == "winner"
                and row["state"] == "Closed"
                and row["winner"] is None
                and type(choice) is int
                and choice in (1, 2)
            ):
                db.execute(
                    "UPDATE voting_rounds SET winner=?,reason='TIE_OWNER_CHOICE',version=version+1 WHERE id=?",
                    (choice, identity),
                )
            else:
                raise ValueError("ROUND_TRANSITION_DENIED")
            db.execute(
                "INSERT INTO voting_commands VALUES(?,?,?,?)", (key, channel, digest, identity)
            )
            self._audit(db, "ROUND_" + operation.upper(), identity, now, channel)
            return self._snapshot(
                db,
                db.execute("SELECT * FROM voting_rounds WHERE id=?", (identity,)).fetchone(),
                now,
            )

    def accept(self, db, channel, viewer, choice, now, event_time):
        self._expire(db, channel, now)
        row = db.execute(
            "SELECT * FROM voting_rounds WHERE channel=? AND state='Open'", (channel,)
        ).fetchone()
        if row is None:
            return "VOTING_CLOSED"
        if event_time < row["opened"]:
            return "VOTE_BEFORE_OPEN"
        voter = hmac.new(
            self.key, f"{channel}:{row['id']}:{viewer}".encode(), hashlib.sha256
        ).hexdigest()
        if db.execute(
            "SELECT 1 FROM crowd_votes WHERE round_id=? AND voter=?", (row["id"], voter)
        ).fetchone():
            return "DUPLICATE_VOTE"
        if db.execute("SELECT count(*) FROM crowd_votes").fetchone()[0] >= 20000:
            return "VOTE_CAPACITY"
        if (
            db.execute("SELECT count(*) FROM crowd_votes WHERE received>?", (now - 1,)).fetchone()[
                0
            ]
            >= 120
        ):
            return "VOTE_GLOBAL_RATE_LIMIT"
        if (
            db.execute(
                "SELECT count(*) FROM crowd_votes WHERE round_id=? AND received>?",
                (row["id"], now - 1),
            ).fetchone()[0]
            >= 60
        ):
            return "VOTE_CHANNEL_RATE_LIMIT"
        db.execute("INSERT INTO crowd_votes VALUES(?,?,?,?)", (row["id"], voter, choice, now))
        return "VOTE_ACCEPTED"

    def bind_winner(self, channel, identity, version, *, now=None):
        now = self.clock() if now is None else now
        with closing(self.intake.connect()) as db, db:
            db.execute("BEGIN IMMEDIATE")
            self._expire(db, channel, now)
            row = db.execute(
                "SELECT * FROM voting_rounds WHERE id=? AND channel=?", (identity, channel)
            ).fetchone()
            if (
                row is None
                or row["state"] != "Closed"
                or row["version"] != version
                or row["winner"] is None
            ):
                raise ValueError("WINNER_NOT_READY")
            candidate_id = row[f"candidate{row['winner']}"]
            candidate = db.execute(
                "SELECT id,suggestion FROM candidates WHERE id=? AND channel=?",
                (candidate_id, channel),
            ).fetchone()
            if not candidate or candidate["suggestion"] != row[f"text{row['winner']}"]:
                raise ValueError("WINNER_BINDING_CHANGED")
            db.execute("INSERT INTO voting_origins VALUES(?,?)", (candidate_id, identity))
            self._audit(db, "WINNER_BOUND", identity, now, channel)
            return dict(candidate)

    def require_plannable(self, channel, candidate_id):
        with closing(self.intake.connect()) as db:
            if db.execute(
                "SELECT 1 FROM voting_rounds WHERE channel=? AND state IN ('Draft','Open') AND (candidate1=? OR candidate2=?)",
                (channel, candidate_id, candidate_id),
            ).fetchone():
                raise ValueError("VOTE_IN_PROGRESS")

    def audit(self, channel):
        with closing(self.intake.connect()) as db:
            return [
                dict(row)
                for row in db.execute(
                    "SELECT at,kind,correlation FROM voting_audit WHERE channel=? ORDER BY sequence DESC LIMIT 12",
                    (channel,),
                )
            ]
