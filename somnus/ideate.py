"""
somnus.ideate — hypothesis generation and ranking.

Ordered by expected value, not by how interesting a hypothesis sounds (§2.4.1).
Two rules do most of the work here:

  * Every hypothesis must be FALSIFIABLE: it carries a fixture spec that is
    asserted to fail on the current baseline. If it cannot fail today, it cannot
    prove anything tomorrow, and it is dropped before a single build token.

  * Cross-domain pairing must be DISTANT. Within-domain consolidation measures
    null (-1.8 +/- 4.4 pp); cross-domain recombination measures +5.64 pp, and the
    effect lives at large embedding distance (arXiv:2607.16256). Sampling pairs
    by similarity destroys the only ideation mode with positive evidence.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Sequence

__all__ = ["Hypothesis", "SOURCE_PRIOR", "score", "rank", "from_failure",
           "cross_domain_pairs", "crystallize_score"]

#: Prior expected value per source kind. Derived from §2.4.1's ranking, and
#: deliberately harsh on `freeform`, which otherwise floods the queue with
#: plausible, unfalsifiable prose.
SOURCE_PRIOR: dict[str, float] = {
    "open_failure":          1.00,
    "counterfactual_repair": 0.85,
    "contract_drift":        0.80,
    "repetition_pattern":    0.70,
    "cross_domain":          0.55,
    "efficiency_delta":      0.45,
    "freeform":              0.15,
}


@dataclass
class Hypothesis:
    intent: str
    hypothesis: str
    source_kind: str
    target_kind: str                       # skill | skill_patch | prompt_section | ...
    target_path: str
    id: str = field(default_factory=lambda: f"dh_{uuid.uuid4().hex[:12]}")
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc)
                            .isoformat(timespec="seconds"))
    failure_ids: list[str] = field(default_factory=list)
    regions: list[str] = field(default_factory=list)
    region_distance: float = 0.0
    fixture_ids: list[str] = field(default_factory=list)
    baseline_must_fail: bool = True
    repeats: int = 3
    isomorphic_variants: int = 2
    success_metrics: list[dict] = field(default_factory=list)
    occurrences: int = 1
    severity: str = "degraded"
    risk_level: str = "low"
    write_set: list[str] = field(default_factory=list)
    network: str = "none"
    status: str = "queued"

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "source": {"kind": self.source_kind, "failure_ids": self.failure_ids,
                       "regions": self.regions, "distance": self.region_distance},
            "intent": self.intent,
            "hypothesis": self.hypothesis,
            "target": {"kind": self.target_kind, "path": self.target_path},
            "test_scenario": {"fixture_ids": self.fixture_ids,
                              "baseline_must_fail": self.baseline_must_fail,
                              "repeats": self.repeats,
                              "isomorphic_variants": self.isomorphic_variants},
            "success_metrics": self.success_metrics,
            "risk": {"level": self.risk_level, "write_set": self.write_set,
                     "network": self.network},
            "status": self.status,
        }


SEVERITY_WEIGHT = {"cosmetic": 0.4, "degraded": 1.0, "blocking": 1.6, "unsafe": 2.2}


def score(h: Hypothesis) -> float:
    """
    Expected value of attempting this hypothesis tonight.

    prior x severity x log-ish recurrence, penalised for missing falsifiability
    and for risk that will need human approval anyway.
    """
    prior = SOURCE_PRIOR.get(h.source_kind, 0.2)
    sev = SEVERITY_WEIGHT.get(h.severity, 1.0)
    recurrence = 1.0 + min(h.occurrences, 20) ** 0.5 / 4.0
    falsifiable = 1.0 if h.fixture_ids else 0.25
    risk_penalty = {"low": 1.0, "medium": 0.85, "high": 0.6}.get(h.risk_level, 0.6)

    # A cross-domain hypothesis whose regions are close together is exactly the
    # configuration that measured null. Collapse its score rather than run it.
    if h.source_kind == "cross_domain" and h.region_distance < 0.55:
        return 0.0

    return prior * sev * recurrence * falsifiable * risk_penalty


def rank(hypotheses: Sequence[Hypothesis], top_k: int | None = None) -> list[Hypothesis]:
    ordered = sorted(hypotheses, key=score, reverse=True)
    ordered = [h for h in ordered if score(h) > 0.0]
    return ordered[:top_k] if top_k else ordered


def from_failure(record: dict, target_path: str) -> Hypothesis:
    """Build the highest-EV hypothesis kind directly from a FailureRecord."""
    return Hypothesis(
        intent=f"Stop recurring failure {record['signature'][:8]} in "
               f"{record.get('task_class') or 'unknown'} tasks",
        hypothesis=(f"IF the procedure adds the check '{record.get('defense') or 'TBD'}' "
                    f"THEN the failure '{record.get('error', '')[:120]}' stops recurring "
                    f"BECAUSE the trigger '{record.get('trigger', '')[:120]}' is caught "
                    f"before the failing call."),
        source_kind="open_failure",
        target_kind="skill_patch",
        target_path=target_path,
        failure_ids=[record.get("id", "")],
        occurrences=int(record.get("occurrences", 1)),
        severity=str(record.get("severity", "degraded")),
        success_metrics=[{"name": "pass_rate", "direction": "increase", "min_effect": 0.02}],
        write_set=[target_path],
    )


def cross_domain_pairs(
    region_ids: Sequence[str],
    distance: Callable[[str, str], float],
    *,
    min_distance: float = 0.55,
    limit: int = 3,
) -> list[tuple[str, str, float]]:
    """
    Force-pair the MOST DISTANT memory regions, not the most similar ones.

    This inverts the usual retrieval instinct on purpose. Similarity-based
    pairing reproduces the within-domain null result; the measured gain lives at
    the far end of the distribution (arXiv:2607.16256, rho=0.54 between novelty
    and embedding distance).
    """
    pairs: list[tuple[str, str, float]] = []
    for i, a in enumerate(region_ids):
        for b in region_ids[i + 1:]:
            d = distance(a, b)
            if d >= min_distance:
                pairs.append((a, b, d))
    pairs.sort(key=lambda t: t[2], reverse=True)
    return pairs[:limit]


def crystallize_score(
    *,
    repetition: int,
    complexity: int,
    friction: int,
    stability: float,
    value_tokens_saved: int,
    overlap: float,
    generality_risk: float,
    weights: dict[str, float] | None = None,
) -> float:
    """
    Should this pattern become a skill? (§4.2.1)

    `overlap` is the load-bearing term. Retrieval precision falls from 29.6% at
    pool size 5 to 3.3% at pool size 100 (arXiv:2608.14036), so a new skill that
    is 80% similar to an existing one has NEGATIVE expected value: the right move
    is a patch to the existing skill, which is a different hypothesis kind.
    """
    w = {"r": 1.0, "c": 0.6, "f": 0.8, "s": 0.7, "v": 0.5, "o": 2.0, "g": 1.0}
    if weights:
        w.update(weights)
    import math
    return (
        w["r"] * math.log1p(max(repetition, 0))
        + w["c"] * min(complexity, 15) / 15.0
        + w["f"] * min(friction, 10) / 10.0
        + w["s"] * max(0.0, min(stability, 1.0))
        + w["v"] * min(max(value_tokens_saved, 0), 20_000) / 20_000.0
        - w["o"] * max(0.0, min(overlap, 1.0))
        - w["g"] * max(0.0, min(generality_risk, 1.0))
    )


def should_crystallize(score_value: float, repetition: int, overlap: float,
                       *, threshold: float = 1.2) -> tuple[bool, str]:
    if repetition < 3:
        return False, "insufficient_repetition:<3_distinct_sessions"
    if overlap >= 0.75:
        return False, f"overlap_too_high:{overlap:.2f}>=0.75 -> emit skill_patch instead"
    if score_value <= threshold:
        return False, f"score_below_threshold:{score_value:.2f}<={threshold}"
    return True, "crystallize"
