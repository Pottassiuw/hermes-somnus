"""
Schema tests.

The schemas are contracts between phases; if they drift from the dataclasses
that produce them, a night's output becomes unreadable by the next night's
tooling. These tests keep the two honest.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from somnus.consolidate import ConsolidationBatch, MemoryEntry
from somnus.ideate import Hypothesis
from somnus.triage import FailureRecord

SCHEMA_DIR = Path(__file__).resolve().parents[1] / "somnus" / "schemas"

jsonschema = pytest.importorskip("jsonschema", reason="jsonschema is optional at runtime")


def _schema(name: str) -> dict:
    return json.loads((SCHEMA_DIR / name).read_text(encoding="utf-8"))


def test_every_schema_is_valid_json_schema():
    for path in sorted(SCHEMA_DIR.glob("*.json")):
        schema = json.loads(path.read_text(encoding="utf-8"))
        jsonschema.Draft202012Validator.check_schema(schema)


def test_failure_record_dataclass_matches_its_schema():
    rec = FailureRecord(
        signature="abc123", trigger="called before auth", error="401 Unauthorized",
        consequence="batch import lost", id="fr_0123456789ab",
        first_seen="2026-09-01T03:00:00+00:00", last_seen="2026-09-02T03:00:00+00:00",
        occurrences=4, severity="blocking", task_class="api",
        defense="assert token present before batch call",
        evidence=[{"session_id": "s1", "turn_range": [3, 5], "excerpt": "…"}],
    )
    jsonschema.validate(rec.to_dict(), _schema("failure_record.schema.json"))


def test_dream_hypothesis_dataclass_matches_its_schema():
    h = Hypothesis(
        intent="Stop the recurring 401 in api tasks",
        hypothesis="IF the procedure asserts a token THEN pass_rate improves BECAUSE …",
        source_kind="open_failure", target_kind="skill_patch",
        target_path="skills/api/SKILL.md", fixture_ids=["fx_0123456789ab"],
        success_metrics=[{"name": "pass_rate", "direction": "increase", "min_effect": 0.02}],
        write_set=["skills/api/SKILL.md"],
    )
    jsonschema.validate(h.to_dict(), _schema("dream_hypothesis.schema.json"))


def test_consolidation_batch_matches_its_schema():
    batch = ConsolidationBatch(
        region=[MemoryEntry("semantic", "old", ["ev1"], "tool_observed")],
        replacement_set=[MemoryEntry("semantic", "merged", ["ev1"], "tool_observed")],
        identity_hash_before="a" * 64, identity_hash_after="a" * 64,
        attempted_writes=1, rejected_writes=0,
    )
    jsonschema.validate(batch.to_dict(), _schema("consolidation_batch.schema.json"))


def test_falsifiability_is_enforced_at_both_layers():
    """
    Defence in depth: the SCHEMA refuses a hypothesis with no fixture, and the
    RANKER independently drives its score toward zero. Either layer alone would
    eventually be bypassed by a clever generator; both together will not.
    """
    from somnus.ideate import score

    h = Hypothesis(
        intent="x", hypothesis="y", source_kind="freeform",
        target_kind="skill", target_path="skills/x", fixture_ids=[],
        success_metrics=[{"name": "pass_rate", "direction": "increase", "min_effect": 0.02}],
    )

    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate(h.to_dict(), _schema("dream_hypothesis.schema.json"))

    assert score(h) < 0.1

    h.fixture_ids = ["fx_0123456789ab"]
    jsonschema.validate(h.to_dict(), _schema("dream_hypothesis.schema.json"))


def test_baseline_must_fail_is_pinned_to_true_in_the_schema():
    """The falsifiability gate is a const, not a default anyone can flip."""
    schema = _schema("dream_hypothesis.schema.json")
    assert schema["properties"]["test_scenario"]["properties"]["baseline_must_fail"]["const"] is True


def test_guard_partition_is_a_legal_fixture_partition():
    schema = _schema("fixture_case.schema.json")
    assert "guard" in schema["properties"]["partition"]["enum"]


def test_replacement_entry_requires_provenance_in_the_schema():
    schema = _schema("consolidation_batch.schema.json")
    item = schema["properties"]["replacement_set"]["items"]
    assert "provenance" in item["required"]
    assert item["properties"]["provenance"]["minItems"] == 1
