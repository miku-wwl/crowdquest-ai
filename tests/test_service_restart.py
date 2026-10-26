from crowdquest.intake import Store
from tests.process_helpers import start_fixture, stop_fixture


def test_temporary_service_restart_preserves_rows_without_real_oauth(tmp_path):
    """Actual subprocess/SQLite lifecycle, with explicit synthetic Twitch dependencies."""
    first, _ = start_fixture(tmp_path)
    try:
        before = Store(tmp_path / "intake.sqlite3").candidates("123")
        assert len(before) == 2
    finally:
        stop_fixture(first, tmp_path)
    second, _ = start_fixture(tmp_path)
    try:
        after = Store(tmp_path / "intake.sqlite3").candidates("123")
        assert {r["id"]: r["suggestion"] for r in after} == {
            r["id"]: r["suggestion"] for r in before
        }
    finally:
        stop_fixture(second, tmp_path)
