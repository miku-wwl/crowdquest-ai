"""Consumer-owned durable queue admission and receipts, never AIG lifecycle state."""

import json
import sqlite3
from contextlib import closing
from pathlib import Path
from uuid import UUID, uuid4

from agentic_intent_gate.runtime import EXTERNAL_PAYLOAD_REVISION, Outcome, ToolOutcome

from .challenges import Challenge


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def uuid4_string(value):
    try:
        parsed = UUID(value)
        return parsed.version == 4 and str(parsed) == value
    except (ValueError, TypeError, AttributeError):
        return False


class AdmissionStore:
    def __init__(self, path, binding):
        self.path, self.binding = Path(path), binding

    @classmethod
    def provision(cls, path, binding):
        Path(path).touch(exist_ok=False)
        with closing(sqlite3.connect(path)) as db:
            db.executescript("""
                PRAGMA journal_mode=WAL;
                CREATE TABLE identity (singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                    binding TEXT NOT NULL) STRICT;
                CREATE TABLE reviews (run_id TEXT PRIMARY KEY, version INTEGER NOT NULL,
                    owner_id TEXT NOT NULL, plan TEXT NOT NULL, decision TEXT NOT NULL) STRICT;
                CREATE TABLE links (action_id TEXT PRIMARY KEY, effect_key TEXT UNIQUE NOT NULL,
                    payload_digest TEXT NOT NULL) STRICT;
                CREATE TABLE jobs (effect_key TEXT PRIMARY KEY,
                    payload_digest TEXT NOT NULL, binding TEXT NOT NULL,
                    arguments TEXT NOT NULL, job_id TEXT UNIQUE NOT NULL,
                    receipt TEXT UNIQUE NOT NULL, state TEXT NOT NULL
                    CHECK(state IN ('PENDING_CONFIRMATION','ELIGIBLE','QUARANTINED'))) STRICT;
            """)
            db.execute("INSERT INTO identity VALUES(1,?)", (canonical(vars(binding)),))
            db.commit()

    def connect(self):
        return sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=0.1)

    def check_identity(self, db):
        if db.execute("SELECT binding FROM identity WHERE singleton=1").fetchall() != [
            (canonical(vars(self.binding)),)
        ]:
            raise ValueError("STORE_IDENTITY_MISMATCH")

    def record_review(self, run, owner_id, decision):
        with closing(self.connect()) as db:
            self.check_identity(db)
            db.execute(
                "INSERT INTO reviews VALUES(?,?,?,?,?)",
                (
                    run.run_id,
                    run.version,
                    owner_id,
                    canonical(run.plan.to_dict()),
                    decision,
                ),
            )
            db.commit()

    def require_review(self, run, owner_id):
        with closing(self.connect()) as db:
            self.check_identity(db)
            row = db.execute(
                "SELECT version,owner_id,plan,decision FROM reviews WHERE run_id=?", (run.run_id,)
            ).fetchone()
        if run.state.value != "Approved" or row != (
            run.version,
            owner_id,
            canonical(run.plan.to_dict()),
            "APPROVE",
        ):
            raise ValueError("EXACT_OWNER_REVIEW_REQUIRED")

    def link(self, action, spec):
        with closing(self.connect()) as db:
            self.check_identity(db)
            expected = (action.action_id, action.effect_key, spec.payload_digest())
            db.execute("INSERT OR IGNORE INTO links VALUES(?,?,?)", expected)
            if (
                db.execute("SELECT * FROM links WHERE action_id=?", (action.action_id,)).fetchone()
                != expected
            ):
                raise ValueError("ACTION_LINK_CONFLICT")
            db.commit()

    def action_ids(self):
        with closing(self.connect()) as db:
            self.check_identity(db)
            return [row[0] for row in db.execute("SELECT action_id FROM links")]

    def job(self, effect_key):
        with closing(self.connect()) as db:
            self.check_identity(db)
            db.row_factory = sqlite3.Row
            row = db.execute("SELECT * FROM jobs WHERE effect_key=?", (effect_key,)).fetchone()
            return dict(row) if row else None

    def confirm(self, action, spec):
        """Called only with a fresh public gateway read; never infer AIG success from a job."""
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self.check_identity(db)
            row = db.execute(
                "SELECT payload_digest,binding,arguments,receipt,state FROM jobs "
                "WHERE effect_key=?",
                (action.effect_key,),
            ).fetchone()
            if row is None:
                return
            receipt = action.result.get("receipt_reference") if action.result else None
            link = db.execute(
                "SELECT action_id,effect_key,payload_digest FROM links WHERE action_id=?",
                (action.action_id,),
            ).fetchone()
            matched = (
                self.binding.matches(spec)
                and link == (action.action_id, action.effect_key, spec.payload_digest())
                and action.state.value == "Succeeded"
                and row[:4]
                == (
                    spec.payload_digest(),
                    canonical(vars(self.binding)),
                    canonical(dict(spec.arguments)),
                    receipt,
                )
                and uuid4_string(receipt)
            )
            if (
                not matched
                and action.state.value in {"Pending", "Authorized", "Executing"}
                and row[4] == "PENDING_CONFIRMATION"
            ):
                # An active, unconfirmed attempt stays ineligible. Polling must not turn
                # normal in-flight work into a permanent terminal quarantine. Startup
                # recovery converts interrupted execution to Unknown before this read.
                return
            state = "ELIGIBLE" if matched and row[4] != "QUARANTINED" else "QUARANTINED"
            db.execute("UPDATE jobs SET state=? WHERE effect_key=?", (state, action.effect_key))
            db.commit()


class AdmissionExecutor:
    """Only short transactional admission; no owner credentials, rendering or remote calls."""

    def __init__(self, store):
        self.store = store

    async def execute(self, spec, effect_key, context):
        def evidence(category, receipt=None, reason=None):
            return ToolOutcome(
                category,
                effect_key,
                spec.execution_scope,
                spec.target,
                spec.payload_digest(),
                receipt,
                reason,
            )

        if (
            not self.store.binding.matches(spec)
            or spec.identity_revision != EXTERNAL_PAYLOAD_REVISION
            or not uuid4_string(effect_key)
            or not uuid4_string(context.attempt_id)
        ):
            return evidence(Outcome.CONFIRMED_FAILURE, reason="INPUT_REJECTED")
        try:
            challenge = Challenge.model_validate(dict(spec.arguments))
        except ValueError:
            return evidence(Outcome.CONFIRMED_FAILURE, reason="INPUT_REJECTED")
        if context.expired():
            return ToolOutcome(Outcome.UNKNOWN_OUTCOME)
        try:
            with closing(self.store.connect()) as db:
                db.execute("BEGIN IMMEDIATE")
                try:
                    self.store.check_identity(db)
                except ValueError:
                    return evidence(Outcome.CONFIRMED_FAILURE, reason="STORE_IDENTITY_MISMATCH")
                row = db.execute(
                    "SELECT payload_digest,binding,arguments,receipt FROM jobs WHERE effect_key=?",
                    (effect_key,),
                ).fetchone()
                expected = (
                    spec.payload_digest(),
                    canonical(vars(self.store.binding)),
                    canonical(challenge.model_dump()),
                )
                if row:
                    if row[0] != expected[0]:
                        return evidence(Outcome.CONFIRMED_FAILURE, reason="PAYLOAD_CONFLICT")
                    if row[:3] != expected or not uuid4_string(row[3]):
                        return ToolOutcome(Outcome.UNKNOWN_OUTCOME)
                    return evidence(Outcome.SUCCESS, receipt=row[3])
                receipt, job_id = str(uuid4()), str(uuid4())
                db.execute(
                    "INSERT INTO jobs VALUES(?,?,?,?,?,?,?)",
                    (
                        effect_key,
                        *expected,
                        job_id,
                        receipt,
                        "PENDING_CONFIRMATION",
                    ),
                )
                if context.expired():
                    return ToolOutcome(Outcome.UNKNOWN_OUTCOME)
                db.commit()
            # Independent readback is still inside the adapter budget.
            stored = self.store.job(effect_key)
            if (
                context.expired()
                or not stored
                or (
                    stored["payload_digest"],
                    stored["binding"],
                    stored["arguments"],
                    stored["receipt"],
                )
                != (*expected, receipt)
            ):
                return ToolOutcome(Outcome.UNKNOWN_OUTCOME)
            return evidence(Outcome.SUCCESS, receipt=receipt)
        except Exception:  # noqa: BLE001 -- uncertain writes never become no-effect proof
            return ToolOutcome(Outcome.UNKNOWN_OUTCOME)
