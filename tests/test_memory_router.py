from __future__ import annotations

from pathlib import Path

from somnus.memory_router import (
    BankRoute, Fact, MemoryRouter, RouteLedger, classify_fact, make_decisions,
    redact_sensitive,
)


def test_redaction_never_preserves_secret_value():
    raw = "API_KEY=super-secret password: hunter2 postgres://user:pw@db/main"
    result = redact_sensitive(raw)
    assert "super-secret" not in result
    assert "hunter2" not in result
    assert "user:pw@" not in result
    assert "[REDACTED]" in result


def test_classification_routes_helios_and_infra():
    assert classify_fact("EDP-Helios PR 137 backend CI passou").bank_id == "repo-edp-helios"
    assert classify_fact("Docker no Raspberry Pi com Cloudflare Tunnel").bank_id == "ops-infra"


def test_ambiguous_or_unknown_is_not_guessed():
    decision = classify_fact("fato genérico sem domínio")
    assert decision.bank_id == "agent-hermes"
    assert decision.needs_review is True


def test_observations_and_invalid_facts_are_not_routed():
    facts = [
        Fact("world-1", "EDP-Helios PR 137", fact_type="world"),
        Fact("obs-1", "EDP-Helios observation", fact_type="observation"),
        Fact("bad-1", "EDP-Helios invalid", state="invalidated"),
    ]
    decisions = make_decisions("agent-hermes", facts)
    assert [item.source_memory_id for item in decisions] == ["world-1"]


class FakeClient:
    def __init__(self, *, readback=True):
        self.readback = readback
        self.retains = []
        self.invalidations = []
        self.last_document_id = ""

    def retain_digest(self, bank_id, content, *, context, document_id, timestamp=""):
        self.retains.append((bank_id, content, context, document_id))
        self.last_document_id = document_id
        return {"success": True, "items_count": 1}

    def list_memories(self, bank_id, *, limit=100, offset=0):
        if self.readback:
            return [Fact("target-1", "synthesized", document_id=self.last_document_id)]
        return []

    def invalidate(self, bank_id, memory_id, *, reason):
        self.invalidations.append((bank_id, memory_id, reason))
        return {"state": "invalidated"}


def _fact():
    return Fact("source-1", "EDP-Helios PR 137 foi validado", fact_type="world")


def test_dry_run_never_calls_external_writes(tmp_path: Path):
    client = FakeClient()
    ledger = RouteLedger(tmp_path / "somnus.db")
    try:
        report = MemoryRouter(client, ledger, apply=False).route("agent-hermes", [_fact()])
    finally:
        ledger.close()
    assert report["dry_run"] is True
    assert report["planned"] == 1
    assert client.retains == []
    assert client.invalidations == []


def test_apply_requires_readback_before_invalidation(tmp_path: Path):
    client = FakeClient(readback=True)
    ledger = RouteLedger(tmp_path / "somnus.db")
    try:
        report = MemoryRouter(client, ledger, apply=True).route("agent-hermes", [_fact()])
        assert report["verified"] == 1
        assert report["invalidated"] == 1
        assert len(client.retains) == 1
        assert len(client.invalidations) == 1
        second = MemoryRouter(client, ledger, apply=True).route("agent-hermes", [_fact()])
        assert second["verified"] == 0
        assert len(client.invalidations) == 1
    finally:
        ledger.close()


def test_apply_fail_closed_when_target_readback_missing(tmp_path: Path):
    client = FakeClient(readback=False)
    ledger = RouteLedger(tmp_path / "somnus.db")
    try:
        report = MemoryRouter(client, ledger, apply=True).route("agent-hermes", [_fact()])
    finally:
        ledger.close()
    assert report["verified"] == 0
    assert report["invalidated"] == 0
    assert report["errors"]
    assert client.invalidations == []
