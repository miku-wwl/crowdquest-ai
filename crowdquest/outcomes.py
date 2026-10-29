"""Immutable owner reports and bounded presentation, independent of AIG execution."""

from contextlib import closing
from uuid import uuid4

from .admission import uuid4_string

OUTCOMES = ("Completed", "Failed", "Skipped")


class OutcomePresentation:
    def ensure_presentation_schema(self):
        with closing(self.connect()) as db:
            db.executescript("""
                CREATE TABLE IF NOT EXISTS render_origins(effect_key TEXT PRIMARY KEY,
                    audience_selected INTEGER NOT NULL CHECK(audience_selected IN (0,1))) STRICT;
                CREATE TABLE IF NOT EXISTS challenge_outcomes(effect_key TEXT PRIMARY KEY,
                    action_id TEXT UNIQUE NOT NULL, render_id TEXT UNIQUE NOT NULL,
                    receipt TEXT NOT NULL, kind TEXT NOT NULL
                    CHECK(kind IN ('Completed','Failed','Skipped')), command_key TEXT UNIQUE NOT NULL,
                    presentation_id TEXT UNIQUE NOT NULL, recorded REAL NOT NULL,
                    deadline REAL NOT NULL, boot TEXT NOT NULL, state TEXT NOT NULL
                    CHECK(state IN ('PRESENTING','ENDED'))) STRICT;
                CREATE TABLE IF NOT EXISTS outcome_issues(presentation_id TEXT NOT NULL,
                    overlay_key TEXT NOT NULL, view_id TEXT NOT NULL,
                    PRIMARY KEY(presentation_id,overlay_key)) STRICT;
            """)

    def outcome(self, effect_key):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT kind,recorded,state FROM challenge_outcomes WHERE effect_key=?",
                (effect_key,),
            ).fetchone()
            return dict(row) if row else None

    def record_outcome(self, action, job, kind, key):
        if kind not in OUTCOMES or not uuid4_string(key):
            raise ValueError("OUTCOME_INPUT")
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self._maintain(db, self.monotonic())
            previous = db.execute(
                "SELECT * FROM challenge_outcomes WHERE command_key=? OR effect_key=?",
                (key, action.effect_key),
            ).fetchall()
            if previous:
                if len(previous) == 1 and (
                    previous[0]["effect_key"],
                    previous[0]["action_id"],
                    previous[0]["kind"],
                    previous[0]["command_key"],
                    previous[0]["receipt"],
                ) == (action.effect_key, action.action_id, kind, key, job["receipt"]):
                    db.commit()
                    return {
                        "kind": kind,
                        "source": "OWNER_REPORTED",
                        "recorded": previous[0]["recorded"],
                    }
                raise ValueError("OUTCOME_ALREADY_TERMINAL")
            row = db.execute(
                "SELECT * FROM renders WHERE effect_key=?", (action.effect_key,)
            ).fetchone()
            if (
                not row
                or row["state"] not in ("RENDERED", "EXPIRED")
                or row["receipt"] != job["receipt"]
                or row["job_id"] != job["job_id"]
                or row["payload"] != job["arguments"]
                or not db.execute(
                    "SELECT 1 FROM observations WHERE render_id=? AND status='ACKNOWLEDGED'",
                    (row["render_id"],),
                ).fetchone()
            ):
                raise ValueError("OUTCOME_REQUIRES_ACKNOWLEDGED_RENDER")
            now = self.clock()
            db.execute(
                "INSERT INTO challenge_outcomes VALUES(?,?,?,?,?,?,?,?,?,?,'PRESENTING')",
                (
                    action.effect_key,
                    action.action_id,
                    row["render_id"],
                    job["receipt"],
                    kind,
                    key,
                    str(uuid4()),
                    now,
                    self.monotonic() + 8,
                    self.boot,
                ),
            )
            # End the display only. The AIG Succeeded result and receipt are immutable.
            db.execute(
                "UPDATE renders SET state='ENDED' WHERE effect_key=? AND state='RENDERED'",
                (action.effect_key,),
            )
            db.commit()
            return {"kind": kind, "source": "OWNER_REPORTED", "recorded": now}

    def current_outcome(self, db, overlay_key, view_id, now, *, consume=True, expected_id=None):
        db.execute(
            "UPDATE challenge_outcomes SET state='ENDED' WHERE state='PRESENTING' AND (deadline<=? OR boot!=?)",
            (now, self.boot),
        )
        row = db.execute(
            "SELECT * FROM challenge_outcomes WHERE state='PRESENTING' ORDER BY rowid DESC LIMIT 1"
        ).fetchone()
        if row is None:
            return None
        if expected_id is not None and expected_id != row["presentation_id"]:
            return {"mode": "production", "state": "waiting", "reason": "STALE_DELIVERY"}
        issued = db.execute(
            "SELECT view_id FROM outcome_issues WHERE presentation_id=? AND overlay_key=?",
            (row["presentation_id"], overlay_key),
        ).fetchone()
        if issued and issued[0] != view_id:
            return None
        if issued and expected_id is not None:
            return {"mode": "production", "state": "waiting", "reason": "NO_REPLAY"}
        if issued and not consume:
            return {
                "mode": "production",
                "state": "outcome_claimed",
                "presentation_id": row["presentation_id"],
            }
        if not issued:
            if not consume:
                return {
                    "mode": "production",
                    "state": "outcome_pending",
                    "presentation_id": row["presentation_id"],
                }
            db.execute(
                "INSERT INTO outcome_issues VALUES(?,?,?)",
                (row["presentation_id"], overlay_key, view_id),
            )
        return {
            "mode": "production",
            "state": "outcome",
            "presentation_id": row["presentation_id"],
            "outcome": row["kind"],
            "source": "OWNER_REPORTED",
            "remaining_seconds": max(0, row["deadline"] - now),
        }
