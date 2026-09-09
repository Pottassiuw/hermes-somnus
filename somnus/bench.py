"""
somnus.bench — the acceptance harness.

This module is the only thing standing between "the agent thinks this is better"
and "this is better". It is deliberately dependency-free (stdlib only) so it can
run on a Raspberry Pi, inside a container, or in CI without a virtualenv.

Design rules encoded here:

  IR-2  The generator never sees the acceptance set. This module reads
        hold/guard/regress; the sandboxed agent does not. Run it OUTSIDE the box.
  IR-3  Guard regressions and isomorphic-perturbation failures are *vetoes*,
        not scores. No statistic can rescue them.
  §1.4.3  Paired design, exact McNemar, paired bootstrap CI, a pre-registered
        minimum detectable effect, and (optionally) replication before promote.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import statistics
from dataclasses import dataclass, asdict, field
from math import comb
from pathlib import Path
from typing import Iterable, Sequence

__all__ = [
    "Verdict",
    "CaseResult",
    "mcnemar_exact",
    "paired_bootstrap",
    "adjudicate",
    "fixture_tree_hash",
    "verify_fixture_manifest",
    "split_results",
]


# --------------------------------------------------------------------------- #
# Data types
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class CaseResult:
    """One fixture case, run once against one side (baseline or candidate)."""

    case_id: str
    partition: str          # dev | hold | guard | regress
    passed: bool
    score: float            # continuous metric; use 1.0/0.0 if you only have pass/fail
    isomorphic_passed: bool = True
    wall_s: float = 0.0
    tokens: int = 0
    tool_calls: int = 0
    error: str | None = None


@dataclass(frozen=True)
class Verdict:
    accept: bool
    reason: str
    effect: float = 0.0
    ci95: tuple[float, float] = (0.0, 0.0)
    p_mcnemar: float = 1.0
    n_pairs: int = 0
    guard_regressions: int = 0
    iso_failures: int = 0
    token_delta: int = 0
    detail: dict = field(default_factory=dict)

    def to_json(self) -> str:
        d = asdict(self)
        d["ci95"] = list(self.ci95)
        return json.dumps(d, indent=2, sort_keys=True)

    def as_pr_note(self) -> str:
        """A short evidence block suitable for pasting into a PR body."""
        sign = "+" if self.effect >= 0 else ""
        return (
            f"**Verdict:** {'ACCEPT' if self.accept else 'REJECT'} — `{self.reason}`\n\n"
            f"| metric | value |\n|---|---|\n"
            f"| paired effect | {sign}{self.effect:.4f} |\n"
            f"| 95% CI | [{self.ci95[0]:.4f}, {self.ci95[1]:.4f}] |\n"
            f"| McNemar p | {self.p_mcnemar:.4g} |\n"
            f"| matched pairs | {self.n_pairs} |\n"
            f"| guard regressions | {self.guard_regressions} |\n"
            f"| isomorphic failures | {self.iso_failures} |\n"
            f"| token delta | {self.token_delta:+d} |\n"
        )


# --------------------------------------------------------------------------- #
# Statistics
# --------------------------------------------------------------------------- #

def mcnemar_exact(b: int, c: int) -> float:
    """
    Two-sided exact McNemar p-value.

    b = pairs where baseline passed and candidate failed
    c = pairs where candidate passed and baseline failed

    Under H0 the discordant pairs are Binomial(b + c, 0.5).
    Concordant pairs carry no information and are correctly ignored.
    """
    if b < 0 or c < 0:
        raise ValueError("b and c must be non-negative")
    n = b + c
    if n == 0:
        return 1.0
    k = min(b, c)
    tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2.0 * tail)


def paired_bootstrap(
    base: Sequence[float],
    cand: Sequence[float],
    iters: int = 10_000,
    seed: int = 0,
) -> tuple[float, tuple[float, float]]:
    """
    Point estimate and percentile 95% CI of the paired mean difference
    (candidate - baseline). No distributional assumptions.
    """
    if len(base) != len(cand):
        raise ValueError("paired_bootstrap requires equal-length paired samples")
    if not base:
        return 0.0, (0.0, 0.0)

    diffs = [c - b for b, c in zip(base, cand)]
    n = len(diffs)
    point = statistics.fmean(diffs)
    if n == 1:
        return point, (point, point)

    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(iters):
        means.append(statistics.fmean(rng.choices(diffs, k=n)))
    means.sort()
    lo = means[max(0, int(0.025 * iters))]
    hi = means[min(iters - 1, int(0.975 * iters))]
    return point, (lo, hi)


# --------------------------------------------------------------------------- #
# Adjudication
# --------------------------------------------------------------------------- #

def split_results(results: Iterable[CaseResult]) -> dict[str, list[CaseResult]]:
    out: dict[str, list[CaseResult]] = {"dev": [], "hold": [], "guard": [], "regress": []}
    for r in results:
        out.setdefault(r.partition, []).append(r)
    return out


def adjudicate(
    baseline: Sequence[CaseResult],
    candidate: Sequence[CaseResult],
    *,
    min_effect: float = 0.02,
    alpha: float = 0.01,
    min_pairs: int = 20,
    scoring_partitions: tuple[str, ...] = ("hold", "regress"),
) -> Verdict:
    """
    Compare two aligned lists of CaseResult and return an accept/reject Verdict.

    The two lists MUST be aligned by case_id; a mismatch is a programming error
    and raises rather than silently producing a meaningless comparison.

    Order of evaluation matters and is deliberate:
      1. Vetoes  (guard regressions, isomorphic-perturbation failures)
      2. Direction (did the candidate actually win more pairs than it lost?)
      3. Significance (exact McNemar at alpha)
      4. Magnitude (effect >= pre-registered MDE, and CI strictly above zero)
    """
    if len(baseline) != len(candidate):
        raise ValueError("baseline and candidate result sets must be aligned")
    for b, c in zip(baseline, candidate):
        if b.case_id != c.case_id:
            raise ValueError(f"result misalignment: {b.case_id!r} != {c.case_id!r}")

    token_delta = sum(c.tokens for c in candidate) - sum(b.tokens for b in baseline)

    # ---- 1. Vetoes -------------------------------------------------------- #
    guard_regressions = sum(
        1 for b, c in zip(baseline, candidate)
        if b.partition == "guard" and b.passed and not c.passed
    )
    if guard_regressions:
        return Verdict(
            accept=False,
            reason=f"guard_regression:{guard_regressions}",
            guard_regressions=guard_regressions,
            token_delta=token_delta,
        )

    iso_failures = sum(
        1 for c in candidate
        if c.passed and not c.isomorphic_passed
    )
    if iso_failures:
        return Verdict(
            accept=False,
            reason=f"isomorphic_perturbation_failure:{iso_failures}",
            iso_failures=iso_failures,
            token_delta=token_delta,
        )

    # ---- 2..4. Statistics on the scoring partitions ----------------------- #
    pairs = [
        (b, c) for b, c in zip(baseline, candidate)
        if b.partition in scoring_partitions
    ]
    n_pairs = len(pairs)
    if n_pairs < min_pairs:
        return Verdict(
            accept=False,
            reason=f"insufficient_pairs:{n_pairs}<{min_pairs}",
            n_pairs=n_pairs,
            token_delta=token_delta,
        )

    b_only = sum(1 for b, c in pairs if b.passed and not c.passed)
    c_only = sum(1 for b, c in pairs if c.passed and not b.passed)
    p = mcnemar_exact(b_only, c_only)
    effect, ci = paired_bootstrap([b.score for b, _ in pairs], [c.score for _, c in pairs])

    detail = {"base_only_wins": b_only, "cand_only_wins": c_only,
              "scoring_partitions": list(scoring_partitions)}

    if c_only <= b_only:
        return Verdict(False, "no_directional_win", effect, ci, p, n_pairs,
                       token_delta=token_delta, detail=detail)
    if p > alpha:
        return Verdict(False, f"not_significant:p={p:.4g}>alpha={alpha}", effect, ci, p,
                       n_pairs, token_delta=token_delta, detail=detail)
    if effect < min_effect:
        return Verdict(False, f"effect_below_mde:{effect:.4f}<{min_effect}", effect, ci, p,
                       n_pairs, token_delta=token_delta, detail=detail)
    if ci[0] <= 0:
        return Verdict(False, f"ci_includes_zero:[{ci[0]:.4f},{ci[1]:.4f}]", effect, ci, p,
                       n_pairs, token_delta=token_delta, detail=detail)

    return Verdict(True, f"accept:p={p:.4g},effect={effect:.4f}", effect, ci, p,
                   n_pairs, token_delta=token_delta, detail=detail)


# --------------------------------------------------------------------------- #
# Tamper evidence (IR-2, layer 3)
# --------------------------------------------------------------------------- #

def fixture_tree_hash(root: str | os.PathLike) -> str:
    """
    Deterministic SHA-256 over a fixture tree: relative path + content, sorted.

    Recorded before a dream cycle and re-verified after every phase. A mismatch
    means something inside the loop edited the evidence, which invalidates the
    entire run — abort and roll back rather than reasoning about it.
    """
    root = Path(root)
    h = hashlib.sha256()
    if not root.exists():
        return h.hexdigest()
    for path in sorted(p for p in root.rglob("*") if p.is_file()):
        h.update(str(path.relative_to(root)).encode("utf-8"))
        h.update(b"\0")
        h.update(path.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


def verify_fixture_manifest(root: str | os.PathLike, expected: str) -> None:
    """Raise if the fixture tree changed. Callers should treat this as fatal."""
    actual = fixture_tree_hash(root)
    if actual != expected:
        raise RuntimeError(
            f"fixture manifest mismatch for {root}: expected {expected[:12]}…, "
            f"got {actual[:12]}… — aborting cycle (IR-2)"
        )
