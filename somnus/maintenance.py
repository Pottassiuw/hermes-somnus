"""Zero-token, conservative maintenance for the Somnus SQLite ledger."""
from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
from pathlib import Path


@dataclass(frozen=True)
class MaintenanceReport:
    database: str
    volatile_removed: int
    checkpoint: str
    vacuum_requested: bool
    vacuum_completed: bool
    backup: str
    size_before: int
    size_after: int
    errors: tuple[str, ...] = ()

    def to_dict(self) -> dict:
        return asdict(self)


def _stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _ensure_volatile_table(db: sqlite3.Connection) -> None:
    db.executescript("""
    CREATE TABLE IF NOT EXISTS volatile_records (
        id TEXT PRIMARY KEY,
        kind TEXT NOT NULL,
        payload TEXT NOT NULL,
        expires_at TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    CREATE INDEX IF NOT EXISTS idx_volatile_expires ON volatile_records(expires_at);
    """)


def backup_database(path: Path) -> Path:
    backup_dir = path.parent / "backups"
    backup_dir.mkdir(parents=True, exist_ok=True)
    target = backup_dir / f"{path.name}.{_stamp()}.bak"
    source = sqlite3.connect(path, timeout=30)
    destination = sqlite3.connect(target)
    try:
        source.backup(destination)
    finally:
        destination.close()
        source.close()
    os.chmod(target, 0o600)
    return target


def run_maintenance(path: str | os.PathLike, *, vacuum: bool = False) -> MaintenanceReport:
    db_path = Path(path).expanduser()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    if not db_path.exists():
        db = sqlite3.connect(db_path)
        db.close()
    size_before = db_path.stat().st_size
    errors: list[str] = []
    removed = 0
    checkpoint = "not-run"
    backup = ""
    vacuum_completed = False
    db = sqlite3.connect(db_path, timeout=30, isolation_level=None)
    try:
        db.execute("PRAGMA busy_timeout=30000")
        db.execute("PRAGMA journal_mode=WAL")
        _ensure_volatile_table(db)
        db.execute("BEGIN IMMEDIATE")
        try:
            cursor = db.execute("DELETE FROM volatile_records WHERE datetime(expires_at) <= datetime('now')")
            removed = max(0, cursor.rowcount)
            db.execute("COMMIT")
        except Exception:
            db.execute("ROLLBACK")
            raise
        try:
            db.execute("PRAGMA optimize")
            result = db.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
            checkpoint = ",".join(str(value) for value in result) if result else "ok"
        except sqlite3.DatabaseError as exc:
            errors.append(f"checkpoint: {type(exc).__name__}")
        if vacuum:
            try:
                backup = str(backup_database(db_path))
                db.execute("VACUUM")
                vacuum_completed = True
            except (sqlite3.DatabaseError, OSError) as exc:
                errors.append(f"vacuum: {type(exc).__name__}")
    except (sqlite3.DatabaseError, OSError) as exc:
        errors.append(f"transaction: {type(exc).__name__}")
    finally:
        db.close()
    size_after = db_path.stat().st_size if db_path.exists() else 0
    return MaintenanceReport(str(db_path), removed, checkpoint, vacuum, vacuum_completed, backup, size_before, size_after, tuple(errors))


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--db", default=os.environ.get("SOMNUS_DB", "~/.hermes/somnus/somnus.db"))
    parser.add_argument("--vacuum", action="store_true")
    args = parser.parse_args()
    report = run_maintenance(args.db, vacuum=args.vacuum)
    print(json.dumps(report.to_dict(), sort_keys=True))
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
