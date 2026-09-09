"""
End-to-end cycle tests with a fake Runtime.

These are the tests that let you sleep while the agent does. They assert the
things that must hold even when every model in the loop misbehaves:

  * a cycle that would touch the identity manifest aborts and rolls back
  * a consolidation that grows the bank is rejected
  * a candidate that trades a guard fixture for score never gets staged
  * budgets are hard ceilings, not suggestions
"""

from __future__ import annotations

import json

import pytest

from somnus.bench import CaseResult
from somnus.config import SomnusConfig
from somnus.consolidate import (
    ConsolidationBatch, MemoryEntry, SchemaRejection, build_batch,
    token_estimate, utility_ok, validate_entry,
)
from somnus.daemon import Abort, Budget, CycleReport, dream_cycle
from somnus.guards import FakeHost
from somnus.report import render
from somnus.state import Store
from somnus.triage import Turn


# --------------------------------------------------------------------------- #
# Budget
# --------------------------------------------------------------------------- #

def test_budget_stops_at_the_call_ceiling():
    b = Budget(wall_deadline=1e18, llm_calls_left=2, usd_left=100.0)
    b.spend(calls=1)
    b.spend(calls=1)
    with pytest.raises(Abort, match="llm_call_budget_exceeded"):
        b.spend(calls=1)


def test_budget_stops_at_the_money_ceiling():
    b = Budget(wall_deadline=1e18, llm_calls_left=999, usd_left=0.05)
    with pytest.raises(Abort, match="usd_budget_exceeded"):
        b.spend(usd=0.10)


def test_budget_stops_at_the_wall_clock():
    b = Budget(wall_deadline=0.0, llm_calls_left=999, usd_left=999.0)
    with pytest.raises(Abort, match="wall_clock_exceeded"):
        b.spend(calls=1, now=1.0)


# --------------------------------------------------------------------------- #
# Consolidation semantics
# --------------------------------------------------------------------------- #

def _entry(content="a fact", tier="tool_observed", prov=("ev1",)):
    return {"type": "semantic", "content": content, "provenance": list(prov),
            "confidence_tier": tier}


def test_entry_without_provenance_is_rejected():
    bad = _entry()
    bad["provenance"] = []
    with pytest.raises(SchemaRejection, match="provenance"):
        validate_entry(bad)


def test_entry_with_unknown_confidence_tier_is_rejected():
    bad = _entry(tier="vibes")
    with pytest.raises(SchemaRejection, match="confidence_tier"):
        validate_entry(bad)


def test_empty_content_is_rejected():
    with pytest.raises(SchemaRejection):
        validate_entry(_entry(content="   "))


def test_build_batch_counts_rejects_and_aborts_above_the_health_floor():
    region = [MemoryEntry("semantic", "old fact", ["ev1"], "tool_observed")]
    garbage = json.dumps({"replacement_set": [
        _entry("good"), {"type": "semantic", "content": "no provenance",
                         "provenance": [], "confidence_tier": "tool_observed"},
        {"type": "nonsense", "content": "x", "provenance": ["e"],
         "confidence_tier": "tool_observed"},
    ]})
    with pytest.raises(SchemaRejection, match="reject rate"):
        build_batch(region, "traj", lambda _p: garbage, max_reject_rate=0.10)


def test_build_batch_accepts_a_clean_shrinking_rewrite():
    region = [MemoryEntry("semantic", "x" * 400, ["ev1"], "tool_observed"),
              MemoryEntry("semantic", "y" * 400, ["ev2"], "tool_observed")]
    payload = json.dumps({
        "replacement_set": [_entry("one merged fact", prov=["ev1", "ev2"])],
        "omitted": [{"id": "old", "reason": "redundant"}],
        "contradictions": [],
    })
    batch = build_batch(region, "traj", lambda _p: payload)
    assert len(batch.replacement_set) == 1
    assert batch.tokens_after < batch.tokens_before
    assert batch.reject_rate == 0.0
    assert batch.to_dict()["size_delta"]["entries_after"] == 1


def test_build_batch_rejects_non_json():
    with pytest.raises(SchemaRejection, match="non-JSON"):
        build_batch([], "traj", lambda _p: "I think the memory looks fine!")


def test_utility_rejects_a_replacement_that_grew():
    region = [MemoryEntry("semantic", "x" * 100, ["e"], "tool_observed")]
    bigger = [MemoryEntry("semantic", "x" * 900, ["e"], "tool_observed")]
    batch = ConsolidationBatch(region=region, replacement_set=bigger)
    ok, why = utility_ok(batch, score_with=0.8, score_without=0.5, score_replacement=0.8)
    assert not ok and "replacement_grew" in why


def test_utility_rejects_a_replacement_that_degrades_scores():
    region = [MemoryEntry("semantic", "x" * 400, ["e"], "tool_observed")]
    smaller = [MemoryEntry("semantic", "x" * 40, ["e"], "tool_observed")]
    batch = ConsolidationBatch(region=region, replacement_set=smaller)
    ok, why = utility_ok(batch, score_with=0.80, score_without=0.50, score_replacement=0.60)
    assert not ok and "replacement_degrades" in why


def test_utility_flags_a_dead_weight_region():
    """If masking the region costs nothing, the region was never load-bearing."""
    region = [MemoryEntry("semantic", "x" * 400, ["e"], "tool_observed")]
    smaller = [MemoryEntry("semantic", "x" * 40, ["e"], "tool_observed")]
    batch = ConsolidationBatch(region=region, replacement_set=smaller)
    ok, why = utility_ok(batch, score_with=0.80, score_without=0.80, score_replacement=0.80)
    assert ok and "dead_weight" in why


def test_token_estimate_is_monotonic():
    small = [MemoryEntry("semantic", "a" * 40, ["e"], "tool_observed")]
    big = [MemoryEntry("semantic", "a" * 4000, ["e"], "tool_observed")]
    assert token_estimate(big) > token_estimate(small)


# --------------------------------------------------------------------------- #
# Fake runtime
# --------------------------------------------------------------------------- #

class FakeRuntime:
    def __init__(self, *, guard_trap=False, scores=(0.8, 0.5, 0.8),
                 triage_json=None, consolidate_json=None, n_cases=30):
        self.guard_trap = guard_trap
        self.scores = scores
        self.n_cases = n_cases
        self.calls = 0
        self._triage = triage_json or json.dumps(
            {"trigger": "called before auth", "consequence": "batch lost",
             "defense": "assert token present", "severity": "blocking"})
        self._consolidate = consolidate_json or json.dumps(
            {"replacement_set": [{"type": "semantic", "content": "merged",
                                  "provenance": ["ev1"], "confidence_tier": "tool_observed"}],
             "omitted": [], "contradictions": []})

    # -- injected surface -------------------------------------------------- #
    def llm(self, prompt: str, *, tier: str = "aux") -> str:
        self.calls += 1
        return self._consolidate if "consolidating one region" in prompt else self._triage

    def recent_turns(self):
        return [
            Turn("s1", 1, "2026-09-01T03:00:00Z", "tool", "terminal",
                 "TimeoutError after 30s", ok=False, task_class="api"),
            Turn("s2", 2, "2026-09-02T03:00:00Z", "tool", "terminal",
                 "TimeoutError after 45s", ok=False, task_class="api"),
        ]

    def memory_region(self):
        return [MemoryEntry("semantic", "z" * 800, ["ev1"], "tool_observed")]

    def trajectory_excerpts(self):
        return "…trajectory…"

    def fixture_scores(self, variant: str) -> float:
        return {"with_region": self.scores[0], "without_region": self.scores[1],
                "replacement": self.scores[2]}[variant]

    def baseline_reproduces(self, hypothesis) -> bool:
        return True

    def build_candidate(self, hypothesis):
        return {"id": hypothesis.id}

    def gate_a(self, candidate):
        return True, "ok"

    def run_fixtures(self, side: str, candidate):
        cand = side == "candidate"
        out = [CaseResult(f"c{i}", "hold", cand, 1.0 if cand else 0.0)
               for i in range(self.n_cases)]
        if self.guard_trap:
            out.append(CaseResult("g0", "guard", not cand, 0.0 if cand else 1.0))
        return out

    def stage(self, hypothesis, candidate, verdict) -> str:
        return f"staging/{hypothesis.id}"


def _cfg(tmp_path) -> SomnusConfig:
    cfg = SomnusConfig(enabled=True, home=str(tmp_path / "somnus"))
    cfg.identity.manifest_paths = [str(tmp_path / "core.md")]
    cfg.promote.repo = str(tmp_path / "repo")
    (tmp_path / "core.md").write_text("identity")
    cfg.home_path.mkdir(parents=True, exist_ok=True)
    (cfg.home_path / "staging").mkdir(parents=True, exist_ok=True)
    return cfg


def _primed_store(cfg) -> Store:
    """Idle host, plenty of backlog: triggers fire, guards pass."""
    store = Store(cfg.db_path)
    store.db.execute("INSERT INTO activity (ts, session_id, kind) "
                     "VALUES (datetime('now','-1 day'), 's0', 'session_end')")
    for i in range(250):
        store.db.execute("INSERT INTO turns (session_id, turn_index, ts) "
                         "VALUES ('s1', ?, datetime('now'))", (i,))
    return store


# --------------------------------------------------------------------------- #
# Cycle behaviour
# --------------------------------------------------------------------------- #

def test_disabled_config_does_nothing(tmp_path):
    cfg = _cfg(tmp_path)
    cfg.enabled = False
    r = dream_cycle(cfg, FakeRuntime(), host=FakeHost(), store=_primed_store(cfg))
    assert r.status == "disabled"


def test_cycle_skips_when_the_user_was_recently_active(tmp_path):
    cfg = _cfg(tmp_path)
    store = _primed_store(cfg)
    store.note_activity("tool_call", "now")     # user is here
    r = dream_cycle(cfg, FakeRuntime(), host=FakeHost(), store=store, now_hour=3)
    assert r.status == "skipped"
    assert "user_active" in r.reason


def test_cycle_skips_when_no_trigger_fires(tmp_path):
    cfg = _cfg(tmp_path)
    store = Store(cfg.db_path)
    store.db.execute("INSERT INTO activity (ts, session_id, kind) "
                     "VALUES (datetime('now','-1 day'), 's0', 'session_end')")
    r = dream_cycle(cfg, FakeRuntime(), host=FakeHost(), store=store, now_hour=14)
    assert r.status == "skipped" and r.reason == "no_trigger"


def test_happy_path_stages_an_accepted_candidate(tmp_path):
    cfg = _cfg(tmp_path)
    r = dream_cycle(cfg, FakeRuntime(), host=FakeHost(),
                    store=_primed_store(cfg), now_hour=3)
    assert r.status == "ok"
    assert r.failures_found == 1
    assert r.batches_accepted == 1
    assert r.tokens_saved > 0
    assert len(r.accepted) == 1
    assert r.rejected == []


def test_guard_regression_prevents_staging(tmp_path):
    """The single most important assertion in this file."""
    cfg = _cfg(tmp_path)
    r = dream_cycle(cfg, FakeRuntime(guard_trap=True), host=FakeHost(),
                    store=_primed_store(cfg), now_hour=3)
    assert r.status == "ok"
    assert r.accepted == []
    assert any("guard_regression" in x["reason"] for x in r.rejected)


def test_identity_drift_aborts_and_rolls_back(tmp_path):
    cfg = _cfg(tmp_path)
    store = _primed_store(cfg)

    class Tamperer(FakeRuntime):
        def memory_region(self):
            # simulate something in the loop editing the identity manifest
            (tmp_path / "core.md").write_text("TAMPERED")
            return super().memory_region()

    r = dream_cycle(cfg, Tamperer(), host=FakeHost(), store=store, now_hour=3)
    assert r.status == "aborted"
    assert "identity manifest changed" in r.reason
    assert any(p.name == "rollback" and p.ok for p in r.phases)


def test_unhealthy_host_skips_before_spending_anything(tmp_path):
    cfg = _cfg(tmp_path)
    rt = FakeRuntime()
    r = dream_cycle(cfg, rt, host=FakeHost(_temp_c=95.0),
                    store=_primed_store(cfg), now_hour=3)
    assert r.status == "skipped"
    assert rt.calls == 0          # zero tokens spent on a hot Pi


def test_consolidation_that_grows_is_rejected_but_the_cycle_continues(tmp_path):
    cfg = _cfg(tmp_path)
    grow = json.dumps({"replacement_set": [
        {"type": "semantic", "content": "q" * 4000, "provenance": ["ev1"],
         "confidence_tier": "tool_observed"}], "omitted": [], "contradictions": []})
    r = dream_cycle(cfg, FakeRuntime(consolidate_json=grow), host=FakeHost(),
                    store=_primed_store(cfg), now_hour=3)
    assert r.status == "ok"
    assert r.batches_rejected == 1
    assert len(r.accepted) == 1          # the build/bench phase still ran


def test_report_renders_and_names_the_rejections(tmp_path):
    cfg = _cfg(tmp_path)
    r = dream_cycle(cfg, FakeRuntime(guard_trap=True), host=FakeHost(),
                    store=_primed_store(cfg), now_hour=3)
    md = render(r)
    assert "Somnus digest" in md
    assert "Rejected" in md
    assert "guard_regression" in md


def test_report_handles_a_skipped_night(tmp_path):
    md = render(CycleReport(status="skipped", reason="user_active_5m_ago<60"))
    assert "Nothing ran" in md
