import json
import subprocess
import sys

from crowdquest.evidence import inspect_store
from crowdquest.intake import Store
from tests.support import notification


def test_fresh_python_process_preserves_dedup_and_redacts_evidence(tmp_path):
    path = tmp_path / "intake.sqlite3"
    store = Store(path)
    now = 1_800_000_000.0
    raw = notification(now=now)
    assert (
        store.ingest(
            raw,
            owner_id="123",
            session_id="session-1",
            subscription_id="sub-1",
            now=now,
            source="synthetic",
        )
        == "ACCEPTED"
    )
    script = """
import json,sys
from pathlib import Path
from crowdquest.intake import Store
from tests.support import notification
print(Store(Path(sys.argv[1])).ingest(notification(now=1800000000),owner_id='123',
    session_id='session-1',subscription_id='sub-1',now=1800000000,source='synthetic'))
"""
    assert (
        subprocess.check_output([sys.executable, "-c", script, str(path)], text=True).strip()
        == "DUPLICATE"
    )
    evidence = inspect_store(path)
    assert evidence["counts"] == {"deliveries": 1, "messages": 1, "candidates": 1}
    assert evidence["reason_counts"] == {"ACCEPTED": 1, "DUPLICATE": 1}
    rendered = json.dumps(evidence)
    assert "Survive" not in rendered and "delivery-1" not in rendered and "chat-1" not in rendered
