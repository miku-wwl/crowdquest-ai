"""Candidate-to-Run provenance and current-review fencing, outside the AIG ledger."""

import hashlib
import json
import sqlite3
import threading
import time
from contextlib import closing

from agentic_intent_gate.runtime import Intent

from .challenges import Challenge
from .providers import TRACE


def short(value):
    return hashlib.sha256(value.encode()).hexdigest()[:12]


class GenerationBusy(ValueError):
    pass


class ProductStore:
    def __init__(self, path):
        self.path = path

    @staticmethod
    def provision(path):
        path.touch(exist_ok=False)
        with closing(sqlite3.connect(path)) as db:
            db.executescript("""
                CREATE TABLE candidates(candidate_id TEXT PRIMARY KEY, current_run TEXT,
                    revision INTEGER NOT NULL, status TEXT NOT NULL) STRICT;
                CREATE TABLE proposals(run_id TEXT PRIMARY KEY, candidate_id TEXT NOT NULL,
                    revision INTEGER NOT NULL, provenance TEXT NOT NULL,
                    UNIQUE(candidate_id,revision)) STRICT;
                CREATE TABLE audit(sequence INTEGER PRIMARY KEY, at REAL NOT NULL,
                    kind TEXT NOT NULL, correlation TEXT NOT NULL) STRICT;
            """)

    def connect(self):
        return sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=0.2)

    def recover(self):
        with closing(self.connect()) as db:
            db.execute(
                "UPDATE candidates SET status='FAILED' WHERE status IN ('GENERATING','EDITING')"
            )
            db.commit()

    def item(self, candidate_id):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT current_run,revision,status FROM candidates WHERE candidate_id=?",
                (candidate_id,),
            ).fetchone()
            return {"run_id": row[0], "revision": row[1], "status": row[2]} if row else None

    def reserve(self, candidate_id):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute("SELECT count(*) FROM candidates").fetchone()[0] >= 500:
                raise ValueError("PROPOSAL_CAPACITY")
            db.execute("INSERT INTO candidates VALUES(?,NULL,1,'GENERATING')", (candidate_id,))
            db.commit()

    def editing(self, candidate_id):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            if (
                db.execute(
                    "UPDATE candidates SET status='EDITING',revision=revision+1 "
                    "WHERE candidate_id=? AND status IN ('READY','FAILED')",
                    (candidate_id,),
                ).rowcount
                != 1
            ):
                raise ValueError("PROPOSAL_BUSY")
            db.commit()

    def finish(self, candidate_id, run, trace):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            revision = db.execute(
                "SELECT revision FROM candidates WHERE candidate_id=?", (candidate_id,)
            ).fetchone()[0]
            db.execute(
                "INSERT INTO proposals VALUES(?,?,?,?)",
                (
                    run.run_id,
                    candidate_id,
                    revision,
                    json.dumps(trace, sort_keys=True),
                ),
            )
            db.execute(
                "UPDATE candidates SET current_run=?,status='READY' WHERE candidate_id=?",
                (run.run_id, candidate_id),
            )
            db.commit()

    def failed(self, candidate_id):
        with closing(self.connect()) as db:
            db.execute(
                "UPDATE candidates SET status='FAILED' WHERE candidate_id=?", (candidate_id,)
            )
            db.commit()

    def metadata(self, run_id):
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT candidate_id,provenance FROM proposals WHERE run_id=?", (run_id,)
            ).fetchone()
            if not row:
                raise ValueError("PROPOSAL_NOT_FOUND")
            return row[0], json.loads(row[1])

    def runs_for(self, candidate_id):
        with closing(self.connect()) as db:
            return [
                r[0]
                for r in db.execute(
                    "SELECT run_id FROM proposals WHERE candidate_id=?", (candidate_id,)
                )
            ]

    def record(self, kind, correlation):
        with closing(self.connect()) as db:
            db.execute(
                "INSERT INTO audit(at,kind,correlation) VALUES(?,?,?)",
                (time.time(), kind, short(correlation)),
            )
            db.commit()

    def audit(self):
        with closing(self.connect()) as db:
            return [
                {"at": at, "kind": kind, "correlation": key}
                for at, kind, key in db.execute(
                    "SELECT at,kind,correlation FROM audit ORDER BY sequence DESC LIMIT 12"
                )
            ]


class ProductService:
    def __init__(self, base, proposals, renderer):
        self.base, self.proposals, self.renderer = base, proposals, renderer
        self.owner_id = base.owner_id
        self.lock = threading.RLock()
        self.model_active = False

    def require_current(self, run_id):
        candidate, _ = self.proposals.metadata(run_id)
        current = self.proposals.item(candidate)
        if current["run_id"] != run_id or current["status"] != "READY":
            raise ValueError("STALE_PROPOSAL")
        return candidate

    async def _generate(self, candidate_id, envelope):
        trace = {}
        context = TRACE.set(trace)
        try:
            run = await self.base.runtime.run_service.create(Intent(json.dumps(envelope)))
            self.proposals.finish(candidate_id, run, trace)
            self.proposals.record("PLAN_" + run.state.value.upper(), run.run_id)
            return self.view(candidate_id)
        except BaseException:
            self.proposals.failed(candidate_id)
            raise
        finally:
            TRACE.reset(context)

    async def generate(self, candidate):
        with self.lock:
            if self.model_active:
                raise GenerationBusy("GENERATION_BUSY")
            self.proposals.reserve(candidate["id"])
            self.model_active = True
        try:
            return await self._generate(candidate["id"], {"suggestion": candidate["suggestion"]})
        finally:
            with self.lock:
                self.model_active = False

    async def manual(self, candidate_id, challenge, expected_version):
        challenge = Challenge.model_validate(challenge)
        with self.lock:
            current = self.proposals.item(candidate_id)
            if current is None:
                if expected_version != 0:
                    raise ValueError("STALE_PROPOSAL")
                self.proposals.reserve(candidate_id)
            else:
                for run_id in self.proposals.runs_for(candidate_id):
                    if self.base.actions_for_run(run_id):
                        raise ValueError("ACTION_ALREADY_ADMITTED_NO_REPLACEMENT")
                run = self.base.run(current["run_id"]) if current["run_id"] else None
                if (run.version if run else 0) != expected_version:
                    raise ValueError("STALE_PROPOSAL")
                self.proposals.editing(candidate_id)
        return await self._generate(candidate_id, {"manual": challenge.model_dump()})

    def view(self, candidate_id):
        current = self.proposals.item(candidate_id)
        if current is None or current["run_id"] is None:
            return {
                "candidate_id": candidate_id,
                "status": current["status"] if current else "Candidate",
                "run": None,
                "action": None,
                "provenance": None,
            }
        run = self.base.run(current["run_id"])
        _, trace = self.proposals.metadata(run.run_id)
        actions = self.base.actions_for_run(run.run_id)
        return {
            "candidate_id": candidate_id,
            "status": current["status"],
            "run": run.to_dict(),
            "provenance": trace,
            "action": self.snapshot(actions[0]) if actions else None,
        }

    def decide(self, run_id, version, decision, reviewer):
        with self.lock:
            self.require_current(run_id)
            run = self.base.decide(run_id, version, decision, reviewer_id=reviewer)
            self.proposals.record(decision, run_id)
            return run

    def admit(self, run_id, version, key):
        with self.lock:
            self.require_current(run_id)
            action = self.base.admit(run_id, version, key)
            self.proposals.record("ADMITTED", action.action_id)
            return action

    def authorize(self, action_id, version, key):
        with self.lock:
            action = self.base.refresh(action_id)
            self.require_current(action.spec.run_id)
            result = self.base.authorize(action_id, version, key)
            self.proposals.record("AUTHORIZED", action_id)
            return result

    async def execute(self, action_id, version, key):
        action = self.base.refresh(action_id)
        self.require_current(action.spec.run_id)
        result = await self.base.execute(action_id, version, key)
        self.proposals.record(result.state.value.upper(), action_id)
        return result

    def snapshot(self, action):
        action = self.base.refresh(action.action_id)
        job = self.base.store.job(action.effect_key)
        return {
            "action_id": action.action_id,
            "state": action.state.value,
            "version": action.version,
            "admission": None
            if not job
            else {"state": job["state"], "receipt_hash": short(job["receipt"])},
            "rendering": self.renderer.summary(action.effect_key),
        }
