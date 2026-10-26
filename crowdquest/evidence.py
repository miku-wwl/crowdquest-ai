"""Read-only, redacted intake evidence. Does not connect to Twitch or replay events."""

import hashlib
import json
import sqlite3
from contextlib import closing
from datetime import UTC, datetime

from .config import Settings


def redacted(value):
    return hashlib.sha256(value.encode()).hexdigest()[:12]


def inspect_store(path):
    with closing(sqlite3.connect(path.resolve().as_uri() + "?mode=ro", uri=True)) as db:
        db.row_factory = sqlite3.Row
        counts = {
            table: db.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
            for table in ("deliveries", "messages", "candidates")
        }
        rows = db.execute(
            "SELECT channel,chat_id,delivery_id,event_time,state,source "
            "FROM candidates ORDER BY received DESC LIMIT 5"
        ).fetchall()
        return {
            "counts": counts,
            "recent_candidates": [
                {
                    "channel_hash": redacted(row["channel"]),
                    "chat_id_hash": redacted(row["chat_id"]),
                    "delivery_id_hash": redacted(row["delivery_id"]),
                    "event_timestamp": datetime.fromtimestamp(row["event_time"], UTC).isoformat(),
                    "state": row["state"],
                    "source": row["source"],
                }
                for row in rows
            ],
            "reason_counts": dict(db.execute("SELECT code,count FROM reasons")),
            "scope": "Persisted intake only; not OAuth/browser/OBS verification",
        }


if __name__ == "__main__":
    path = Settings.load().state_dir / "intake.sqlite3"
    if not path.exists():
        print(json.dumps({"status": "NOT_RUN", "reason": "NO_INTAKE_DATABASE"}))
    else:
        print(json.dumps(inspect_store(path), indent=2))
