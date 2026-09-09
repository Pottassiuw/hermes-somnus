from __future__ import annotations

import sqlite3
from pathlib import Path

from somnus.maintenance import run_maintenance
from somnus.state import Store


def test_maintenance_removes_only_expired_volatile_rows(tmp_path: Path):
    db_path = tmp_path / "somnus.db"
    store = Store(db_path)
    store.db.execute("INSERT INTO volatile_records VALUES (?,?,?,?,?)", ("old", "tmp", "{}", "2000-01-01T00:00:00+00:00", "2000-01-01T00:00:00+00:00"))
    store.db.execute("INSERT INTO volatile_records VALUES (?,?,?,?,?)", ("new", "tmp", "{}", "2999-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"))
    store.db.execute("INSERT INTO failures (id,signature,first_seen,last_seen,payload) VALUES (?,?,?,?,?)", ("f", "sig", "2026-01-01", "2026-01-01", "{}"))
    store.close()
    report = run_maintenance(db_path)
    assert report.volatile_removed == 1
    check = sqlite3.connect(db_path)
    assert check.execute("SELECT count(*) FROM volatile_records").fetchone()[0] == 1
    assert check.execute("SELECT count(*) FROM failures").fetchone()[0] == 1
    check.close()


def test_vacuum_creates_restricted_backup(tmp_path: Path):
    db_path = tmp_path / "somnus.db"
    Store(db_path).close()
    report = run_maintenance(db_path, vacuum=True)
    assert report.vacuum_completed is True
    assert report.backup
    assert Path(report.backup).stat().st_mode & 0o777 == 0o600
