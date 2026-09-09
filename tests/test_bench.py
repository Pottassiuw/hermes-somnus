"""Tests for the acceptance harness — the part that must never be wrong."""

from __future__ import annotations

import pytest

from somnus.bench import (
    CaseResult, adjudicate, fixture_tree_hash, mcnemar_exact,
    paired_bootstrap, verify_fixture_manifest,
)


def _cases(n, partition, passed, score, iso=True, prefix="c"):
    return [CaseResult(f"{prefix}{i}", partition, passed, score, isomorphic_passed=iso)
            for i in range(n)]


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #

def test_mcnemar_no_discordant_pairs_is_p_one():
    assert mcnemar_exact(0, 0) == 1.0


def test_mcnemar_symmetric():
    assert mcnemar_exact(3, 7) == pytest.approx(mcnemar_exact(7, 3))


def test_mcnemar_strong_evidence_is_small():
    # 12 candidate-only wins, 0 baseline-only wins => 2 * 0.5**12
    assert mcnemar_exact(0, 12) == pytest.approx(2 * (0.5 ** 12))


def test_mcnemar_balanced_is_not_significant():
    assert mcnemar_exact(6, 6) > 0.5


def test_mcnemar_rejects_negative_counts():
    with pytest.raises(ValueError):
        mcnemar_exact(-1, 3)


def test_paired_bootstrap_recovers_a_known_shift():
    base = [0.5] * 40
    cand = [0.6] * 40
    effect, (lo, hi) = paired_bootstrap(base, cand, iters=2000, seed=7)
    assert effect == pytest.approx(0.1, abs=1e-9)
    assert lo == pytest.approx(0.1, abs=1e-9) and hi == pytest.approx(0.1, abs=1e-9)


def test_paired_bootstrap_ci_brackets_zero_for_noise():
    base = [0.5, 0.6, 0.4, 0.55, 0.45] * 8
    cand = [0.6, 0.5, 0.45, 0.5, 0.5] * 8
    _, (lo, hi) = paired_bootstrap(base, cand, iters=2000, seed=1)
    assert lo <= 0 <= hi


def test_paired_bootstrap_requires_equal_lengths():
    with pytest.raises(ValueError):
        paired_bootstrap([1.0, 2.0], [1.0])


# --------------------------------------------------------------------------- #
# Vetoes — these must fire before any statistic is considered
# --------------------------------------------------------------------------- #

def test_guard_regression_is_a_hard_reject_even_with_a_huge_win():
    base = _cases(30, "hold", False, 0.0) + [CaseResult("g0", "guard", True, 1.0)]
    cand = _cases(30, "hold", True, 1.0) + [CaseResult("g0", "guard", False, 0.0)]
    v = adjudicate(base, cand)
    assert not v.accept
    assert v.reason.startswith("guard_regression")
    assert v.guard_regressions == 1


def test_isomorphic_failure_is_a_hard_reject():
    """A candidate that passes the base case but fails permuted twins is a shortcut."""
    base = _cases(30, "hold", False, 0.0)
    cand = _cases(30, "hold", True, 1.0, iso=False)
    v = adjudicate(base, cand)
    assert not v.accept
    assert v.reason.startswith("isomorphic_perturbation_failure")


def test_veto_order_guard_beats_isomorphic():
    base = _cases(25, "hold", False, 0.0) + [CaseResult("g0", "guard", True, 1.0)]
    cand = _cases(25, "hold", True, 1.0, iso=False) + [CaseResult("g0", "guard", False, 0.0)]
    assert adjudicate(base, cand).reason.startswith("guard_regression")


# --------------------------------------------------------------------------- #
# Statistical gating
# --------------------------------------------------------------------------- #

def test_small_sample_is_rejected_even_when_it_wins_every_case():
    """The n=5 trap: 4-of-5 happens ~19% of the time by chance."""
    base = _cases(5, "hold", False, 0.0)
    cand = _cases(5, "hold", True, 1.0)
    v = adjudicate(base, cand, min_pairs=20)
    assert not v.accept
    assert v.reason.startswith("insufficient_pairs")


def test_clear_win_on_sufficient_pairs_is_accepted():
    base = _cases(30, "hold", False, 0.0)
    cand = _cases(30, "hold", True, 1.0)
    v = adjudicate(base, cand, min_pairs=20, alpha=0.01, min_effect=0.02)
    assert v.accept
    assert v.effect == pytest.approx(1.0)
    assert v.p_mcnemar < 0.01


def test_no_directional_win_is_rejected():
    base = [CaseResult(f"c{i}", "hold", i % 2 == 0, 1.0 if i % 2 == 0 else 0.0)
            for i in range(30)]
    cand = [CaseResult(f"c{i}", "hold", i % 2 == 0, 1.0 if i % 2 == 0 else 0.0)
            for i in range(30)]
    v = adjudicate(base, cand, min_pairs=20)
    assert not v.accept
    assert v.reason == "no_directional_win"


def test_tiny_effect_below_mde_is_rejected():
    base = [CaseResult(f"c{i}", "hold", False, 0.500) for i in range(40)]
    cand = [CaseResult(f"c{i}", "hold", True, 0.505) for i in range(40)]
    v = adjudicate(base, cand, min_pairs=20, min_effect=0.02)
    assert not v.accept
    assert v.reason.startswith("effect_below_mde")


def test_dev_partition_does_not_influence_the_verdict():
    """IR-2: the optimizer's own partition must not be able to buy an acceptance."""
    base = _cases(30, "dev", False, 0.0, prefix="d") + _cases(25, "hold", True, 1.0)
    cand = _cases(30, "dev", True, 1.0, prefix="d") + _cases(25, "hold", True, 1.0)
    v = adjudicate(base, cand, min_pairs=20)
    assert not v.accept
    assert v.reason == "no_directional_win"


def test_misaligned_result_sets_raise():
    base = [CaseResult("a", "hold", True, 1.0)]
    cand = [CaseResult("b", "hold", True, 1.0)]
    with pytest.raises(ValueError):
        adjudicate(base, cand)


def test_verdict_renders_a_pr_note():
    base = _cases(30, "hold", False, 0.0)
    cand = _cases(30, "hold", True, 1.0)
    note = adjudicate(base, cand, min_pairs=20).as_pr_note()
    assert "ACCEPT" in note and "McNemar" in note


# --------------------------------------------------------------------------- #
# Tamper evidence
# --------------------------------------------------------------------------- #

def test_fixture_tree_hash_is_stable_and_content_sensitive(tmp_path):
    (tmp_path / "a.json").write_text('{"x": 1}')
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "b.json").write_text('{"y": 2}')

    h1 = fixture_tree_hash(tmp_path)
    assert h1 == fixture_tree_hash(tmp_path)

    (tmp_path / "sub" / "b.json").write_text('{"y": 3}')
    assert fixture_tree_hash(tmp_path) != h1


def test_verify_fixture_manifest_raises_on_tamper(tmp_path):
    (tmp_path / "a.json").write_text("1")
    h = fixture_tree_hash(tmp_path)
    verify_fixture_manifest(tmp_path, h)          # no raise
    (tmp_path / "a.json").write_text("2")
    with pytest.raises(RuntimeError, match="fixture manifest mismatch"):
        verify_fixture_manifest(tmp_path, h)


def test_missing_fixture_tree_hashes_to_empty(tmp_path):
    assert fixture_tree_hash(tmp_path / "nope") == fixture_tree_hash(tmp_path / "also-nope")
