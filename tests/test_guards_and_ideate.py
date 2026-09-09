"""Guards, triggers, triage normalization, hypothesis ranking, sandbox policy."""

from __future__ import annotations

import pytest

from somnus.config import SomnusConfig
from somnus.guards import FakeHost, evaluate, triggers_fired
from somnus.ideate import (
    Hypothesis, cross_domain_pairs, crystallize_score, rank, score, should_crystallize,
)
from somnus.sandbox import SandboxSpec, docker_argv
from somnus.triage import Turn, extract, normalize_error, signature_of


@pytest.fixture
def cfg():
    return SomnusConfig(enabled=True)


# --------------------------------------------------------------------------- #
# Guards
# --------------------------------------------------------------------------- #

def test_all_guards_pass_on_a_healthy_idle_host(cfg, tmp_path):
    gr = evaluate(cfg, FakeHost(), idle_minutes=120, spend_today_usd=0.0,
                  lock_free=True, health_ok=True, somnus_home=tmp_path)
    assert gr.ok and gr.reason() == "ok"


def test_user_activity_vetoes_the_cycle(cfg, tmp_path):
    gr = evaluate(cfg, FakeHost(), idle_minutes=5, spend_today_usd=0.0,
                  lock_free=True, health_ok=True, somnus_home=tmp_path)
    assert not gr.ok
    assert any("user_active" in f for f in gr.failures)


def test_budget_exhaustion_vetoes(cfg, tmp_path):
    gr = evaluate(cfg, FakeHost(), idle_minutes=200, spend_today_usd=5.0,
                  lock_free=True, health_ok=True, somnus_home=tmp_path)
    assert not gr.ok
    assert any("budget_exhausted" in f for f in gr.failures)


def test_thermal_and_memory_pressure_veto(cfg, tmp_path):
    host = FakeHost(_temp_c=85.0, _free_mem_mb=300)
    gr = evaluate(cfg, host, idle_minutes=200, spend_today_usd=0.0,
                  lock_free=True, health_ok=True, somnus_home=tmp_path)
    assert not gr.ok
    assert any("temp=" in f for f in gr.failures)
    assert any("free_mem=" in f for f in gr.failures)


def test_guards_report_every_failure_not_just_the_first(cfg, tmp_path):
    host = FakeHost(_load1=9.0, _temp_c=90.0, _free_mem_mb=10, _free_disk_pct=1.0)
    gr = evaluate(cfg, host, idle_minutes=0, spend_today_usd=99.0,
                  lock_free=False, health_ok=False, somnus_home=tmp_path)
    assert len(gr.failures) >= 6


def test_lock_held_vetoes(cfg, tmp_path):
    gr = evaluate(cfg, FakeHost(), idle_minutes=200, spend_today_usd=0.0,
                  lock_free=False, health_ok=True, somnus_home=tmp_path)
    assert "lock_held" in gr.failures


# --------------------------------------------------------------------------- #
# Triggers
# --------------------------------------------------------------------------- #

def test_scheduled_window_requires_idleness(cfg):
    assert triggers_fired(cfg, hour=3, idle_minutes=10, backlog_turns=0,
                          open_failure_signatures=0) == ()
    assert "scheduled_window" in triggers_fired(
        cfg, hour=3, idle_minutes=200, backlog_turns=0, open_failure_signatures=0)


def test_backlog_and_open_failures_fire_independently(cfg):
    fired = triggers_fired(cfg, hour=14, idle_minutes=200, backlog_turns=500,
                           open_failure_signatures=9)
    assert any(f.startswith("episodic_backlog") for f in fired)
    assert any(f.startswith("open_failures") for f in fired)


def test_no_trigger_on_a_quiet_healthy_day(cfg):
    assert triggers_fired(cfg, hour=14, idle_minutes=200, backlog_turns=3,
                          open_failure_signatures=0) == ()


# --------------------------------------------------------------------------- #
# Triage normalization
# --------------------------------------------------------------------------- #

def test_normalization_collapses_variable_parts():
    a = "TimeoutError at 2026-09-01T03:14:15Z in /home/pi/.hermes/tools/x.py line 42"
    b = "TimeoutError at 2026-09-04T22:01:09Z in /home/pi/.hermes/tools/x.py line 91"
    assert normalize_error(a) == normalize_error(b)


def test_same_bug_gets_one_signature_different_bugs_do_not():
    a = signature_of("ConnectionError: refused (0x7f2a)", "terminal", "api")
    b = signature_of("ConnectionError: refused (0x91bb)", "terminal", "api")
    c = signature_of("ValueError: bad schema", "terminal", "api")
    assert a == b and a != c


def test_task_class_separates_otherwise_identical_errors():
    assert signature_of("boom", "terminal", "api") != signature_of("boom", "terminal", "etl")


def test_extract_clusters_failures_and_counts_occurrences():
    turns = [
        Turn("s1", 1, "2026-09-01T03:00:00Z", "tool", "terminal",
             "TimeoutError after 30s", ok=False, task_class="api"),
        Turn("s2", 4, "2026-09-02T03:00:00Z", "tool", "terminal",
             "TimeoutError after 45s", ok=False, task_class="api"),
        Turn("s3", 2, "2026-09-03T03:00:00Z", "tool", "terminal",
             "ValueError: bad schema", ok=False, task_class="api"),
        Turn("s3", 3, "2026-09-03T03:01:00Z", "assistant", "", "all good", ok=True),
    ]
    records = extract(turns, llm=None)
    assert len(records) == 2
    top = records[0]
    assert top.occurrences == 2
    assert len(top.evidence) == 2
    assert top.status == "open"


def test_extract_survives_a_broken_llm_response():
    turns = [Turn("s1", 1, "2026-09-01T03:00:00Z", "tool", "terminal",
                  "boom", ok=False, task_class="api")]
    records = extract(turns, llm=lambda _p: "not json at all")
    assert len(records) == 1
    assert records[0].trigger == "<triage-parse-failed>"
    assert records[0].occurrences == 1     # the deterministic parts still work


def test_extract_uses_llm_fields_when_valid():
    turns = [Turn("s1", 1, "2026-09-01T03:00:00Z", "tool", "terminal",
                  "boom", ok=False, task_class="api")]
    payload = ('```json\n{"trigger":"called before auth","consequence":"user lost the batch",'
               '"defense":"assert token present","severity":"blocking"}\n```')
    rec = extract(turns, llm=lambda _p: payload)[0]
    assert rec.severity == "blocking"
    assert rec.defense == "assert token present"


# --------------------------------------------------------------------------- #
# Ideation
# --------------------------------------------------------------------------- #

def _h(**kw):
    base = dict(intent="i", hypothesis="h", source_kind="open_failure",
                target_kind="skill_patch", target_path="skills/x", fixture_ids=["fx_1"])
    base.update(kw)
    return Hypothesis(**base)


def test_open_failures_outrank_freeform():
    assert score(_h(source_kind="open_failure")) > score(_h(source_kind="freeform"))


def test_unfalsifiable_hypotheses_are_heavily_penalised():
    assert score(_h(fixture_ids=[])) < score(_h()) / 3


def test_severity_and_recurrence_raise_the_score():
    assert score(_h(severity="unsafe", occurrences=10)) > score(_h(severity="cosmetic",
                                                                  occurrences=1))


def test_near_cross_domain_pairs_score_zero_and_are_dropped():
    """Within-domain recombination measured null; do not spend a night on it."""
    near = _h(source_kind="cross_domain", region_distance=0.2)
    far = _h(source_kind="cross_domain", region_distance=0.9)
    assert score(near) == 0.0
    assert score(far) > 0.0
    assert rank([near, far]) == [far]


def test_rank_truncates_to_top_k():
    hs = [_h(occurrences=i) for i in range(1, 11)]
    assert len(rank(hs, top_k=3)) == 3


def test_cross_domain_pairs_prefers_the_most_distant():
    regions = ["a", "b", "c"]
    dist = {("a", "b"): 0.9, ("a", "c"): 0.6, ("b", "c"): 0.2}

    def d(x, y):
        return dist.get((x, y)) or dist.get((y, x)) or 0.0

    pairs = cross_domain_pairs(regions, d, min_distance=0.55, limit=5)
    assert [(p[0], p[1]) for p in pairs] == [("a", "b"), ("a", "c")]
    assert pairs[0][2] == 0.9


# --------------------------------------------------------------------------- #
# Crystallization
# --------------------------------------------------------------------------- #

def test_overlap_penalty_dominates_the_crystallize_score():
    kw = dict(repetition=6, complexity=8, friction=4, stability=0.9,
              value_tokens_saved=5000, generality_risk=0.1)
    assert crystallize_score(overlap=0.0, **kw) > crystallize_score(overlap=0.9, **kw)


def test_should_crystallize_requires_three_distinct_sessions():
    ok, why = should_crystallize(5.0, repetition=2, overlap=0.1)
    assert not ok and "insufficient_repetition" in why


def test_high_overlap_redirects_to_a_patch():
    ok, why = should_crystallize(5.0, repetition=9, overlap=0.8)
    assert not ok and "skill_patch" in why


def test_clean_candidate_crystallizes():
    s = crystallize_score(repetition=8, complexity=10, friction=5, stability=0.95,
                          value_tokens_saved=9000, overlap=0.1, generality_risk=0.05)
    ok, why = should_crystallize(s, repetition=8, overlap=0.1)
    assert ok and why == "crystallize"


# --------------------------------------------------------------------------- #
# Sandbox policy — the adversarial surface
# --------------------------------------------------------------------------- #

def _spec(tmp_path):
    return SandboxSpec(hypothesis_id="dh_abc", worktree=tmp_path / "wt",
                       fixtures_dev=tmp_path / "fx" / "dev")


def test_sandbox_drops_capabilities_and_network(tmp_path):
    argv = docker_argv(_spec(tmp_path), ["pytest", "-q"])
    assert "--rm" in argv
    assert argv[argv.index("--network") + 1] == "none"
    assert argv[argv.index("--cap-drop") + 1] == "ALL"
    assert "--read-only" in argv
    assert argv[argv.index("--security-opt") + 1] == "no-new-privileges"


def test_sandbox_never_mounts_holdout_partitions(tmp_path):
    argv = docker_argv(_spec(tmp_path), ["true"])
    mounts = [argv[i + 1] for i, a in enumerate(argv) if a == "-v"]
    joined = " ".join(mounts)
    assert "fixtures/dev" in joined
    for forbidden in ("fixtures/hold", "fixtures/guard", "fixtures/regress"):
        assert forbidden not in joined


def test_sandbox_caps_memory_cpu_and_pids(tmp_path):
    argv = docker_argv(_spec(tmp_path), ["true"])
    assert argv[argv.index("--memory") + 1] == "512m"
    assert argv[argv.index("--memory-swap") + 1] == "512m"
    assert argv[argv.index("--pids-limit") + 1] == "256"
    assert argv[argv.index("--cpus") + 1] == "1.0"


def test_sandbox_wraps_the_command_in_a_timeout(tmp_path):
    argv = docker_argv(_spec(tmp_path), ["pytest", "-q"])
    assert argv[-3:] == ["900", "pytest", "-q"] or "timeout" in argv
