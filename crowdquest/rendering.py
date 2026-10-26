"""Consumer rendering ledger and fenced publication; never an AIG state machine."""

import json
import re
import secrets
import sqlite3
import time
from contextlib import closing
from uuid import uuid4

from .admission import canonical, uuid4_string
from .challenges import Challenge

ACTIVE = ("CLAIMED", "SENT", "RENDERED")


class RenderStore:
    def __init__(self, path, binding, *, monotonic=time.monotonic, clock=time.time):
        self.path, self.binding, self.monotonic, self.clock = path, binding, monotonic, clock

    @staticmethod
    def provision(path, binding):
        path.touch(exist_ok=False)
        with closing(sqlite3.connect(path)) as db:
            db.executescript("""
                CREATE TABLE identity(singleton INTEGER PRIMARY KEY, binding TEXT NOT NULL) STRICT;
                CREATE TABLE leader(singleton INTEGER PRIMARY KEY, worker TEXT NOT NULL,
                    epoch INTEGER NOT NULL, deadline REAL NOT NULL, boot TEXT NOT NULL) STRICT;
                CREATE TABLE renders(effect_key TEXT PRIMARY KEY, render_id TEXT UNIQUE NOT NULL,
                    job_id TEXT UNIQUE NOT NULL, receipt TEXT NOT NULL, payload TEXT NOT NULL,
                    state TEXT NOT NULL, worker TEXT NOT NULL, epoch INTEGER NOT NULL,
                    boot TEXT NOT NULL, started REAL, deadline REAL, expires_at REAL) STRICT;
                CREATE UNIQUE INDEX one_active_channel ON renders((1))
                    WHERE state IN ('CLAIMED','SENT','RENDERED');
                CREATE TABLE observations(render_id TEXT NOT NULL, overlay_key TEXT NOT NULL,
                    view_id TEXT NOT NULL, delivery_id TEXT UNIQUE NOT NULL, issued REAL NOT NULL,
                    status TEXT NOT NULL, PRIMARY KEY(render_id,overlay_key)) STRICT;
            """)
            db.execute("INSERT INTO identity VALUES(1,?)", (canonical(vars(binding)),))
            db.execute("INSERT INTO leader VALUES(1,'',0,0,'')")
            db.commit()

    def connect(self):
        db = sqlite3.connect(self.path.resolve().as_uri() + "?mode=rw", uri=True, timeout=0.2)
        db.row_factory = sqlite3.Row
        if db.execute("SELECT binding FROM identity WHERE singleton=1").fetchone()[0] != canonical(
            vars(self.binding)
        ):
            db.close()
            raise ValueError("RENDER_IDENTITY")
        return db

    def recover(self, boot):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            db.execute(
                "UPDATE renders SET state=CASE WHEN state='CLAIMED' THEN 'RENDER_FAILED' "
                "ELSE 'UNKNOWN' END WHERE state IN ('CLAIMED','SENT','RENDERED')"
            )
            db.execute("UPDATE observations SET status='UNKNOWN' WHERE status='ISSUED'")
            db.execute("UPDATE leader SET worker='',epoch=epoch+1,deadline=0,boot=?", (boot,))
            db.commit()

    def _maintain(self, db, now):
        leader = db.execute("SELECT * FROM leader").fetchone()
        if leader["deadline"] <= now:
            db.execute(
                "UPDATE renders SET state=CASE WHEN state='CLAIMED' THEN 'RENDER_FAILED' "
                "ELSE 'UNKNOWN' END WHERE state IN ('CLAIMED','SENT','RENDERED')"
            )
        db.execute(
            "UPDATE observations SET status='UNKNOWN' WHERE status='ISSUED' AND issued<?",
            (now - 5,),
        )
        db.execute(
            "UPDATE renders SET state='UNKNOWN' WHERE state='SENT' AND "
            "EXISTS(SELECT 1 FROM observations o WHERE o.render_id=renders.render_id) AND "
            "NOT EXISTS(SELECT 1 FROM observations o WHERE o.render_id=renders.render_id "
            "AND o.status IN ('ISSUED','ACKNOWLEDGED'))"
        )
        db.execute(
            "UPDATE renders SET state='EXPIRED' WHERE state IN ('SENT','RENDERED') AND deadline<=?",
            (now,),
        )

    def maintain(self):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self._maintain(db, self.monotonic())
            db.commit()

    def take_leadership(self, worker, boot):
        now = self.monotonic()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self._maintain(db, now)
            leader = db.execute("SELECT * FROM leader").fetchone()
            if leader["boot"] != boot or (leader["deadline"] > now and leader["worker"] != worker):
                raise ValueError("WORKER_FENCED")
            epoch = leader["epoch"] + (leader["worker"] != worker or leader["deadline"] <= now)
            db.execute(
                "UPDATE leader SET worker=?,epoch=?,deadline=? WHERE singleton=1",
                (worker, epoch, now + 5),
            )
            db.commit()
            return epoch

    def claim(self, job, worker, epoch, boot):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self._fence(db, worker, epoch, boot)
            if db.execute(
                "SELECT 1 FROM renders WHERE state IN ('CLAIMED','SENT','RENDERED')"
            ).fetchone():
                return None
            if db.execute(
                "SELECT 1 FROM renders WHERE effect_key=?", (job["effect_key"],)
            ).fetchone():
                return None
            render_id = str(uuid4())
            db.execute(
                "INSERT INTO renders VALUES(?,?,?,?,?,'CLAIMED',?,?,?,NULL,NULL,NULL)",
                (
                    job["effect_key"],
                    render_id,
                    job["job_id"],
                    job["receipt"],
                    job["arguments"],
                    worker,
                    epoch,
                    boot,
                ),
            )
            db.commit()
            return render_id

    def _fence(self, db, worker, epoch, boot):
        leader = db.execute("SELECT * FROM leader").fetchone()
        if (leader["worker"], leader["epoch"], leader["boot"]) != (worker, epoch, boot) or leader[
            "deadline"
        ] <= self.monotonic():
            raise ValueError("WORKER_FENCED")

    def publish(self, render_id, worker, epoch, boot):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self._fence(db, worker, epoch, boot)
            row = db.execute("SELECT * FROM renders WHERE render_id=?", (render_id,)).fetchone()
            if (
                not row
                or row["state"] != "CLAIMED"
                or (row["worker"], row["epoch"], row["boot"]) != (worker, epoch, boot)
            ):
                raise ValueError("RENDER_NOT_CLAIMED")
            challenge = Challenge.model_validate(json.loads(row["payload"]))
            now = self.monotonic()
            db.execute(
                "UPDATE renders SET state='SENT',started=?,deadline=?,expires_at=? WHERE render_id=?",
                (
                    now,
                    now + challenge.duration_seconds,
                    self.clock() + challenge.duration_seconds,
                    render_id,
                ),
            )
            db.commit()  # Durable marker BEFORE any overlay receives content.

    def has_effect(self, effect_key):
        with closing(self.connect()) as db:
            return bool(
                db.execute("SELECT 1 FROM renders WHERE effect_key=?", (effect_key,)).fetchone()
            )

    def summary(self, effect_key):
        self.maintain()
        with closing(self.connect()) as db:
            row = db.execute(
                "SELECT render_id,state FROM renders WHERE effect_key=?", (effect_key,)
            ).fetchone()
            if row is None:
                return {"state": "Waiting", "acknowledgements": 0}
            count = db.execute(
                "SELECT count(*) FROM observations WHERE render_id=? AND status='ACKNOWLEDGED'",
                (row["render_id"],),
            ).fetchone()[0]
            return {
                "state": row["state"],
                "render_id": row["render_id"],
                "acknowledgements": count,
                "evidence": "BROWSER_ACK_ONLY" if count else "NO_RENDER_ACK",
            }

    def current(self, overlay_key, view_id):
        now = self.monotonic()
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self._maintain(db, now)
            row = db.execute("SELECT * FROM renders ORDER BY rowid DESC LIMIT 1").fetchone()
            if not row or row["state"] not in ("SENT", "RENDERED"):
                state = (
                    "expired"
                    if row and row["state"] == "EXPIRED"
                    else "unknown"
                    if row and row["state"] == "UNKNOWN"
                    else "waiting"
                )
                db.commit()
                return {"mode": "production", "state": state}
            observation = db.execute(
                "SELECT * FROM observations WHERE render_id=? AND overlay_key=?",
                (row["render_id"], overlay_key),
            ).fetchone()
            if observation:
                if observation["view_id"] != view_id or observation["status"] == "UNKNOWN":
                    db.commit()
                    return {"mode": "production", "state": "waiting", "reason": "NO_REPLAY"}
                if observation["status"] == "ISSUED":
                    db.commit()
                    return {"mode": "production", "state": "waiting", "reason": "ACK_PENDING"}
                delivery = observation["delivery_id"]
            else:
                delivery = str(uuid4())
                db.execute(
                    "INSERT INTO observations VALUES(?,?,?,?,?,'ISSUED')",
                    (row["render_id"], overlay_key, view_id, delivery, now),
                )
            db.commit()
            return {
                "mode": "production",
                "state": "challenge",
                "render_id": row["render_id"],
                "delivery_id": delivery,
                "challenge": json.loads(row["payload"]),
                "remaining_seconds": max(0, row["deadline"] - now),
                "expires_at": row["expires_at"],
            }

    def acknowledge(self, overlay_key, view_id, render_id, delivery_id):
        with closing(self.connect()) as db:
            db.execute("BEGIN IMMEDIATE")
            self._maintain(db, self.monotonic())
            row = db.execute(
                "SELECT o.status,r.state FROM observations o JOIN renders r USING(render_id) "
                "WHERE o.render_id=? AND o.overlay_key=? AND o.view_id=? AND o.delivery_id=?",
                (render_id, overlay_key, view_id, delivery_id),
            ).fetchone()
            if not row or row[0] == "UNKNOWN" or row[1] not in ("SENT", "RENDERED"):
                raise ValueError("RENDER_ACK_REJECTED")
            db.execute(
                "UPDATE observations SET status='ACKNOWLEDGED' WHERE delivery_id=?", (delivery_id,)
            )
            db.execute("UPDATE renders SET state='RENDERED' WHERE render_id=?", (render_id,))
            db.commit()


class RenderCoordinator:
    def __init__(self, base, store, token):
        self.base, self.store, self.token = base, store, token
        self.boot = str(uuid4())
        store.recover(self.boot)

    def require_worker(self, header):
        if (
            type(header) is not str
            or not re.fullmatch(r"Bearer [0-9a-f]{64}", header)
            or not secrets.compare_digest(header, "Bearer " + self.token)
        ):
            raise ValueError("WORKER_AUTH_REQUIRED")

    def tick(self, worker_id, boot):
        if boot != self.boot or not uuid4_string(worker_id):
            raise ValueError("WORKER_FENCED")
        epoch = self.store.take_leadership(worker_id, boot)
        with closing(self.base.store.connect()) as db:
            rows = db.execute(
                "SELECT l.action_id,j.effect_key FROM jobs j JOIN links l USING(effect_key) "
                "WHERE j.state='ELIGIBLE' ORDER BY j.rowid"
            ).fetchall()
        for action_id, effect_key in rows:
            if self.store.has_effect(effect_key):
                continue
            action = self.base.refresh(action_id)
            job = self.base.store.job(effect_key)
            if action.state.value != "Succeeded" or not job or job["state"] != "ELIGIBLE":
                continue
            render_id = self.store.claim(job, worker_id, epoch, boot)
            if render_id:
                # A second durable public read closes the claim-to-publish boundary.
                checked = self.base.refresh(action_id)
                if checked.state.value != "Succeeded" or self.base.store.job(effect_key) != job:
                    raise ValueError("RENDER_RECEIPT_UNCONFIRMED")
                self.store.publish(render_id, worker_id, epoch, boot)
            break
        return {"worker_epoch": epoch}

    def summary(self, effect_key):
        return self.store.summary(effect_key)
