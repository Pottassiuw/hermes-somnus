"""Tests for the ledger, the identity invariant, and snapshots."""

from __future__ import annotations

import json

import pytest

from somnus.state import (
    IdentityDrift, Ledger, Store, assert_identity, identity_hash,
    manifest_of, prune_snapshots, restore, snapshot,
)


# --------------------------------------------------------------------------- #
# Store
# --------------------------------------------------------------------------- #

def test_failure_upsert_bumps_occurrences_instead_of_duplicating(tmp_path):
    store = Store(tmp_path / "s.db")
    rec = {"signature": "abc123", "error": "boom", "trigger": "t", "consequence": "c"}
    first = store.upsert_failure(dict(rec))
    second = store.upsert_failure(dict(rec))
    assert first == second

    rows = store.db.execute("SELECT occurrences FROM failures").fetchall()
    assert len(rows) == 1 and rows[0]["occurrences"] == 2
    assert store.open_failure_signatures() == 1


def test_distinct_signatures_are_separate_records(tmp_path):
    store = Store(tmp_path / "s.db")
    store.upsert_failure({"signature": "a", "error": "x", "trigger": "", "consequence": ""})
    store.upsert_failure({"signature": "b", "error": "y", "trigger": "", "consequence": ""})
    assert store.open_failure_signatures() == 2


def test_idle_minutes_is_infinite_with_no_activity(tmp_path):
    store = Store(tmp_path / "s.db")
    assert store.idle_minutes() == float("inf")


def test_idle_minutes_drops_after_activity(tmp_path):
    store = Store(tmp_path / "s.db")
    store.note_activity("session_end", "sess-1")
    assert store.idle_minutes() < 1.0


def test_unconsolidated_backlog_and_marking(tmp_path):
    store = Store(tmp_path / "s.db")
    for i in range(5):
        store.db.execute(
            "INSERT INTO turns (session_id, turn_index, ts) VALUES (?,?,datetime('now'))",
            ("sess-1", i),
        )
    assert store.unconsolidated_turns() == 5
    store.mark_consolidated(["sess-1"])
    assert store.unconsolidated_turns() == 0


def test_run_lifecycle_and_spend(tmp_path):
    store = Store(tmp_path / "s.db")
    run_id = store.begin_run("scheduled_window", "hash-before")
    store.finish_run(run_id, "ok", "", "hash-after", usd=2.5, llm_calls=42)
    assert store.spend_today() == pytest.approx(2.5)


def test_hypothesis_enqueue_and_settle(tmp_path):
    store = Store(tmp_path / "s.db")
    hid = store.enqueue_hypothesis({"intent": "x", "source": {"kind": "open_failure"}})
    store.settle_hypothesis(hid, "rejected", "gate_a:size")
    row = store.db.execute("SELECT status, reason FROM hypotheses WHERE id=?", (hid,)).fetchone()
    assert row["status"] == "rejected" and row["reason"] == "gate_a:size"


# --------------------------------------------------------------------------- #
# Identity invariant (IR-6)
# --------------------------------------------------------------------------- #

def test_identity_hash_is_stable_for_unchanged_inputs(tmp_path):
    manifest = tmp_path / "core.md"
    manifest.write_text("you are hermes")
    assert identity_hash([manifest]) == identity_hash([manifest])


def test_identity_hash_changes_when_a_manifest_file_changes(tmp_path):
    manifest = tmp_path / "core.md"
    manifest.write_text("you are hermes")
    before = identity_hash([manifest])
    manifest.write_text("you are hermes, but different")
    assert identity_hash([manifest]) != before


def test_identity_hash_detects_deletion(tmp_path):
    manifest = tmp_path / "core.md"
    manifest.write_text("x")
    before = identity_hash([manifest])
    manifest.unlink()
    assert identity_hash([manifest]) != before


def test_semantic_layer_changes_do_not_touch_identity(tmp_path):
    """
    The whole point of arXiv:2607.01988: consolidation writes to the semantic
    store, which is excluded from the manifest's input set BY CONSTRUCTION.
    """
    manifest = tmp_path / "core.md"
    manifest.write_text("identity")
    semantic = tmp_path / "semantic.jsonl"
    semantic.write_text('{"fact": "old"}\n')

    before = identity_hash([manifest])
    semantic.write_text('{"fact": "new"}\n{"fact": "another"}\n')
    assert_identity(before, [manifest])       # must not raise


def test_assert_identity_raises_on_drift(tmp_path):
    manifest = tmp_path / "core.md"
    manifest.write_text("identity")
    before = identity_hash([manifest])
    manifest.write_text("tampered")
    with pytest.raises(IdentityDrift):
        assert_identity(before, [manifest])


# --------------------------------------------------------------------------- #
# Ledger
# --------------------------------------------------------------------------- #

def test_ledger_is_append_only_and_readable(tmp_path):
    ledger = Ledger(tmp_path / "ledger.jsonl")
    a = ledger.append("somnus", "stage", "dh_1", evidence={"why": "test"})
    b = ledger.append("somnus", "reject", "dh_2", evidence={"why": "gate_a"})
    entries = ledger.read()
    assert [e["id"] for e in entries] == [a, b]
    assert entries[0]["actor"] == "somnus"
    assert json.loads(json.dumps(entries))  # round-trips


def test_manifest_of_captures_content_hashes(tmp_path):
    (tmp_path / "one.txt").write_text("a")
    (tmp_path / "two.txt").write_text("b")
    m = manifest_of(tmp_path)
    assert set(m) == {"one.txt", "two.txt"}
    assert m["one.txt"] != m["two.txt"]


# --------------------------------------------------------------------------- #
# Snapshots
# --------------------------------------------------------------------------- #

def test_snapshot_and_restore_round_trip(tmp_path):
    src = tmp_path / "staging"
    src.mkdir()
    (src / "skill.md").write_text("original")

    archive = snapshot(src, tmp_path / "snaps", reason="pre-dream")
    (src / "skill.md").write_text("mutated by a bad night")

    restore(archive, tmp_path)
    assert (src / "skill.md").read_text() == "original"


def test_prune_snapshots_keeps_the_newest(tmp_path):
    src = tmp_path / "staging"
    src.mkdir()
    (src / "f").write_text("x")
    snaps = tmp_path / "snaps"
    for i in range(4):
        d = snaps / f"2026090{i}T000000Z"
        d.mkdir(parents=True)
        (d / "snapshot.tar.gz").write_text("fake")
    removed = prune_snapshots(snaps, keep=2)
    assert len(removed) == 2
    assert len(list(snaps.iterdir())) == 2
