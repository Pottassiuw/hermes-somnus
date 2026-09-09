"""
somnus.state — the night ledger.

Everything a dream cycle does is recorded here, content-addressed and
append-only, so that any change can be explained and reversed the next morning
(IR-4). The design deliberately mirrors Hermes's own Curator ledger
(~/.hermes/skills/.curator_ledger.jsonl) so the two read alike.

Also home to the identity-manifest hash (IR-6): the invariant that proves a
night of autonomous work did not change who the agent is.
"""

from __future__ import annotations

import hashlib
import json
import os
import sqlite3
import tarfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator, Sequence

SCHEMA = """
CREATE TABLE IF NOT EXISTS runs (
    id           TEXT PRIMARY KEY,
    started_at   TEXT NOT NULL,
    finished_at  TEXT,
    status       TEXT NOT NULL DEFAULT 'running',
    reason       TEXT,
    trigger      TEXT,
    usd          REAL NOT NULL DEFAULT 0.0,
    llm_calls    INTEGER NOT NULL DEFAULT 0,
    identity_before TEXT,
    identity_after  TEXT
);

CREATE TABLE IF NOT EXISTS activity (
    ts         TEXT NOT NULL,
    session_id TEXT,
    kind       TEXT NOT NULL          -- session_start | session_end | tool_call | compress
);
CREATE INDEX IF NOT EXISTS idx_activity_ts ON activity(ts);

CREATE TABLE IF NOT EXISTS turns (
    session_id   TEXT NOT NULL,
    turn_index   INTEGER NOT NULL,
    ts           TEXT NOT NULL,
    consolidated INTEGER NOT NULL DEFAULT 0,
    PRIMARY KEY (session_id, turn_index)
);
CREATE INDEX IF NOT EXISTS idx_turns_unconsolidated ON turns(consolidated);

CREATE TABLE IF NOT EXISTS failures (
    id          TEXT PRIMARY KEY,
    signature   TEXT NOT NULL,
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL,
    occurrences INTEGER NOT NULL DEFAULT 1,
    severity    TEXT NOT NULL DEFAULT 'degraded',
    task_class  TEXT,
    trigger     TEXT,
    error       TEXT,
    consequence TEXT,
    defense     TEXT,
    status      TEXT NOT NULL DEFAULT 'open',
    payload     TEXT NOT NULL          -- full FailureRecord JSON
);
CREATE INDEX IF NOT EXISTS idx_failures_sig    ON failures(signature);
CREATE INDEX IF NOT EXISTS idx_failures_status ON failures(status);

CREATE TABLE IF NOT EXISTS hypotheses (
    id         TEXT PRIMARY KEY,
    run_id     TEXT,
    created_at TEXT NOT NULL,
    source     TEXT NOT NULL,
    target     TEXT,
    status     TEXT NOT NULL DEFAULT 'queued',
    reason     TEXT,
    verdict    TEXT,                   -- Verdict JSON
    payload    TEXT NOT NULL           -- full DreamHypothesis JSON
);
CREATE INDEX IF NOT EXISTS idx_hyp_status ON hypotheses(status);

CREATE TABLE IF NOT EXISTS batches (
    id         TEXT PRIMARY KEY,
    run_id     TEXT,
    started_at TEXT NOT NULL,
    accepted   INTEGER NOT NULL DEFAULT 0,
    reason     TEXT,
    tokens_before INTEGER,
    tokens_after  INTEGER,
    payload    TEXT NOT NULL           -- full ConsolidationBatch JSON
);

CREATE TABLE IF NOT EXISTS volatile_records (
    id         TEXT PRIMARY KEY,
    kind       TEXT NOT NULL,
    payload    TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    created_at TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_volatile_expires ON volatile_records(expires_at);
"""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _sid(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def _parse_ts(raw: str) -> datetime:
    """
    Parse a timestamp that may be tz-aware (ours) or naive (SQLite's
    `datetime('now')`, which is UTC but unlabelled). Mixing the two is a classic
    source of `can't subtract offset-naive and offset-aware datetimes` at 3 a.m.
    """
    text = raw.strip().replace(" ", "T", 1)
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    dt = datetime.fromisoformat(text)
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


# --------------------------------------------------------------------------- #
# Store
# --------------------------------------------------------------------------- #

class Store:
    """Thin SQLite wrapper. WAL mode so the gate script can read while we write."""

    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(self.path, isolation_level=None)
        self.db.row_factory = sqlite3.Row
        self.db.execute("PRAGMA journal_mode=WAL;")
        self.db.execute("PRAGMA synchronous=NORMAL;")
        self.db.executescript(SCHEMA)

    def close(self) -> None:
        self.db.close()

    # -- runs ------------------------------------------------------------- #

    def begin_run(self, trigger: str, identity_before: str) -> str:
        run_id = _sid("run")
        self.db.execute(
            "INSERT INTO runs (id, started_at, trigger, identity_before) VALUES (?,?,?,?)",
            (run_id, _now(), trigger, identity_before),
        )
        return run_id

    def finish_run(self, run_id: str, status: str, reason: str = "",
                   identity_after: str = "", usd: float = 0.0, llm_calls: int = 0) -> None:
        self.db.execute(
            "UPDATE runs SET finished_at=?, status=?, reason=?, identity_after=?, "
            "usd=?, llm_calls=? WHERE id=?",
            (_now(), status, reason, identity_after, usd, llm_calls, run_id),
        )

    def spend_today(self) -> float:
        row = self.db.execute(
            "SELECT COALESCE(SUM(usd), 0.0) AS s FROM runs "
            "WHERE started_at > datetime('now', '-1 day')"
        ).fetchone()
        return float(row["s"])

    # -- activity / backlog ------------------------------------------------ #

    def note_activity(self, kind: str, session_id: str = "") -> None:
        self.db.execute("INSERT INTO activity (ts, session_id, kind) VALUES (?,?,?)",
                        (_now(), session_id, kind))

    def idle_minutes(self) -> float:
        row = self.db.execute("SELECT MAX(ts) AS t FROM activity").fetchone()
        if not row or not row["t"]:
            return float("inf")
        return (datetime.now(timezone.utc) - _parse_ts(row["t"])).total_seconds() / 60.0

    def unconsolidated_turns(self) -> int:
        row = self.db.execute("SELECT COUNT(*) AS n FROM turns WHERE consolidated=0").fetchone()
        return int(row["n"])

    def mark_consolidated(self, session_ids: Sequence[str]) -> None:
        self.db.executemany("UPDATE turns SET consolidated=1 WHERE session_id=?",
                            [(s,) for s in session_ids])

    # -- failures ---------------------------------------------------------- #

    def upsert_failure(self, record: dict[str, Any]) -> str:
        """Insert, or bump occurrences if the signature already exists."""
        sig = record["signature"]
        existing = self.db.execute(
            "SELECT id, occurrences FROM failures WHERE signature=?", (sig,)
        ).fetchone()
        if existing:
            self.db.execute(
                "UPDATE failures SET occurrences=occurrences+1, last_seen=?, payload=? WHERE id=?",
                (_now(), json.dumps(record, sort_keys=True), existing["id"]),
            )
            return existing["id"]

        fid = record.get("id") or _sid("fr")
        record["id"] = fid
        self.db.execute(
            "INSERT INTO failures (id, signature, first_seen, last_seen, occurrences, "
            "severity, task_class, trigger, error, consequence, defense, status, payload) "
            "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (fid, sig, record.get("first_seen", _now()), _now(), 1,
             record.get("severity", "degraded"), record.get("task_class"),
             record.get("trigger"), record.get("error"), record.get("consequence"),
             record.get("defense"), record.get("status", "open"),
             json.dumps(record, sort_keys=True)),
        )
        return fid

    def open_failure_signatures(self) -> int:
        row = self.db.execute(
            "SELECT COUNT(DISTINCT signature) AS n FROM failures WHERE status='open'"
        ).fetchone()
        return int(row["n"])

    def open_failures(self, limit: int = 50) -> list[dict[str, Any]]:
        rows = self.db.execute(
            "SELECT payload FROM failures WHERE status='open' "
            "ORDER BY occurrences DESC, last_seen DESC LIMIT ?", (limit,)
        ).fetchall()
        return [json.loads(r["payload"]) for r in rows]

    # -- hypotheses -------------------------------------------------------- #

    def enqueue_hypothesis(self, h: dict[str, Any], run_id: str = "") -> str:
        hid = h.get("id") or _sid("dh")
        h["id"] = hid
        self.db.execute(
            "INSERT OR REPLACE INTO hypotheses (id, run_id, created_at, source, target, "
            "status, payload) VALUES (?,?,?,?,?,?,?)",
            (hid, run_id, h.get("created_at", _now()),
             json.dumps(h.get("source", {}), sort_keys=True),
             json.dumps(h.get("target", {}), sort_keys=True),
             h.get("status", "queued"), json.dumps(h, sort_keys=True)),
        )
        return hid

    def settle_hypothesis(self, hid: str, status: str, reason: str = "",
                          verdict_json: str = "") -> None:
        self.db.execute(
            "UPDATE hypotheses SET status=?, reason=?, verdict=? WHERE id=?",
            (status, reason, verdict_json, hid),
        )


# --------------------------------------------------------------------------- #
# Append-only ledger (IR-4)
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class LedgerEntry:
    id: str
    ts: str
    actor: str          # somnus | agent | user | curator
    action: str         # propose | stage | promote | reject | rollback | consolidate
    target: str
    before: dict[str, str]     # relpath -> sha256
    after: dict[str, str]
    evidence: dict


class Ledger:
    def __init__(self, path: str | os.PathLike) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def append(self, actor: str, action: str, target: str,
               before: dict[str, str] | None = None,
               after: dict[str, str] | None = None,
               evidence: dict | None = None) -> str:
        entry = LedgerEntry(
            id=_sid("le"), ts=_now(), actor=actor, action=action, target=target,
            before=before or {}, after=after or {}, evidence=evidence or {},
        )
        with self.path.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry.__dict__, sort_keys=True) + "\n")
        return entry.id

    def read(self, limit: int = 100) -> list[dict]:
        if not self.path.exists():
            return []
        lines = self.path.read_text(encoding="utf-8").splitlines()
        return [json.loads(ln) for ln in lines[-limit:] if ln.strip()]


def manifest_of(root: str | os.PathLike) -> dict[str, str]:
    """relpath -> sha256 for every file under root. Used for before/after diffs."""
    root = Path(root)
    out: dict[str, str] = {}
    if not root.exists():
        return out
    for p in sorted(x for x in root.rglob("*") if x.is_file()):
        out[str(p.relative_to(root))] = hashlib.sha256(p.read_bytes()).hexdigest()
    return out


# --------------------------------------------------------------------------- #
# Identity invariant (IR-6) — arXiv:2607.01988
# --------------------------------------------------------------------------- #

def identity_hash(paths: Sequence[str | os.PathLike]) -> str:
    """
    SHA-256 over the ordered contents of the identity manifest paths.

    The semantic memory layer is deliberately NOT in this input set. That
    exclusion is structural, which is what makes "consolidation cannot change
    identity" a property you can verify rather than a promise you make.

    Missing paths hash as an explicit absence marker so that deleting a manifest
    file is detected as a change rather than silently ignored.
    """
    h = hashlib.sha256()
    for raw in paths:
        p = Path(os.path.expanduser(str(raw).split("#", 1)[0]))
        h.update(str(raw).encode("utf-8"))
        h.update(b"\0")
        if p.is_file():
            h.update(p.read_bytes())
        elif p.is_dir():
            for f in sorted(x for x in p.rglob("*") if x.is_file()):
                h.update(str(f.relative_to(p)).encode("utf-8"))
                h.update(f.read_bytes())
        else:
            h.update(b"<ABSENT>")
        h.update(b"\0")
    return h.hexdigest()


class IdentityDrift(RuntimeError):
    """Raised when the identity manifest changed during a dream cycle."""


def assert_identity(expected: str, paths: Sequence[str | os.PathLike]) -> None:
    actual = identity_hash(paths)
    if actual != expected:
        raise IdentityDrift(
            f"identity manifest changed during cycle: {expected[:12]}… -> {actual[:12]}… "
            f"(IR-6) — aborting and rolling back"
        )


# --------------------------------------------------------------------------- #
# Snapshots
# --------------------------------------------------------------------------- #

def snapshot(src: str | os.PathLike, dest_dir: str | os.PathLike, reason: str = "") -> Path:
    """tar.gz a directory before mutating it. Mirrors Curator's backup shape."""
    src, dest_dir = Path(src), Path(dest_dir)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = dest_dir / stamp
    out_dir.mkdir(parents=True, exist_ok=True)
    archive = out_dir / "snapshot.tar.gz"
    with tarfile.open(archive, "w:gz") as tf:
        if src.exists():
            tf.add(src, arcname=src.name)
    (out_dir / "manifest.json").write_text(
        json.dumps({"reason": reason, "src": str(src), "created_at": _now(),
                    "files": manifest_of(src)}, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return archive


def restore(archive: str | os.PathLike, dest_parent: str | os.PathLike) -> None:
    """Restore a snapshot. Called only from the abort path."""
    with tarfile.open(archive, "r:gz") as tf:
        tf.extractall(dest_parent, filter="data")


def prune_snapshots(dest_dir: str | os.PathLike, keep: int = 5) -> list[Path]:
    """Keep the newest `keep` snapshots; return what was removed."""
    dest_dir = Path(dest_dir)
    if not dest_dir.exists():
        return []
    stamps = sorted((d for d in dest_dir.iterdir() if d.is_dir()), reverse=True)
    removed: list[Path] = []
    for old in stamps[keep:]:
        for f in sorted(old.rglob("*"), reverse=True):
            f.unlink() if f.is_file() else f.rmdir()
        old.rmdir()
        removed.append(old)
    return removed


# --------------------------------------------------------------------------- #
# Cross-process lock (shared with Curator / self-evolution)
# --------------------------------------------------------------------------- #

@contextmanager
def flock(path: str | os.PathLike) -> Iterator[None]:
    """
    Advisory exclusive lock. Two processes rewriting ~/.hermes/skills/ at once is
    a corruption you do not want to debug at 4 a.m.
    """
    import fcntl

    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    fh = p.open("w")
    try:
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError as exc:  # pragma: no cover - timing dependent
        fh.close()
        raise RuntimeError(f"somnus lock held by another process: {p}") from exc
    fh.write(str(os.getpid()))
    fh.flush()
    try:
        yield
    finally:
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()
            try:
                p.unlink()
            except FileNotFoundError:
                pass
