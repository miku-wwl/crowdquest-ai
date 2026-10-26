"""Private child process for actual pre/post-COMMIT interruption of synthetic votes."""

import json
import os
import sys
from pathlib import Path

from crowdquest.intake import Store

directory = Path(sys.argv[1])
store = Store(directory / "intake.sqlite3")
envelope = json.loads((directory / "fixture-event.json").read_text("utf-8"))
if sys.argv[2] == "before":
    original = store._reason

    def interrupted(db, reason, now):
        value = original(db, reason, now)
        if reason == "VOTE_ACCEPTED":
            os._exit(94)
        return value

    store._reason = interrupted
result = store.ingest(
    envelope, owner_id="123", session_id="session-1", subscription_id="sub-1", source="synthetic"
)
assert result == "VOTE_ACCEPTED"
os._exit(95)
