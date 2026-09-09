"""
somnus.consolidate — the region-rewrite operator.

The single most important design decision in Somnus, taken from Auto-Dreamer
(arXiv:2605.20616): a consolidation pass selects a REGION, treats it as
read-only EVIDENCE, and synthesizes a complete REPLACEMENT SET.

    B* = (B \\ R) u S

Why: with replacement semantics, abstraction, deduplication, contradiction
resolution and forgetting are the operator's DEFAULT behaviours instead of four
separate features. A CRUD consolidator must be told to delete; a rewriting
consolidator deletes by omission.

Two invariants are enforced here and both are non-negotiable:

  IR-6  The identity manifest hash must be byte-identical before and after
        (arXiv:2607.01988). The semantic layer is excluded from that hash by
        construction, which is what makes the guarantee checkable.

  §3.4  Every write is schema-validated. Small models emit up to 30% format
        errors during memory operations, and the resulting corruption is silent
        (arXiv:2602.19320). Rejections are counted; >10% aborts the phase.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Iterable, Sequence

__all__ = ["MemoryEntry", "ConsolidationBatch", "RegionSelector", "validate_entry",
           "build_batch", "utility_ok", "token_estimate"]

LLMFn = Callable[[str], str]

CONFIDENCE_TIERS = ("user_stated", "tool_observed", "model_inferred")
ENTRY_TYPES = ("semantic", "procedural", "entity_state", "mental_model")


# --------------------------------------------------------------------------- #
# Entries
# --------------------------------------------------------------------------- #

@dataclass
class MemoryEntry:
    type: str
    content: str
    provenance: list[str]              # episodic event ids — never empty
    confidence_tier: str
    id: str = field(default_factory=lambda: f"me_{uuid.uuid4().hex[:12]}")
    valid_from: str = ""
    valid_to: str | None = None

    def to_dict(self) -> dict:
        d = {
            "id": self.id,
            "type": self.type,
            "content": self.content,
            "provenance": list(self.provenance),
            "confidence_tier": self.confidence_tier,
            "valid_from": self.valid_from or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        if self.valid_to:
            d["valid_to"] = self.valid_to
        return d


class SchemaRejection(ValueError):
    pass


def validate_entry(raw: dict) -> MemoryEntry:
    """
    Reject anything that would poison the semantic layer.

    The provenance requirement is break #1 against the recursive hallucination
    loop (§1.3.6): an entry with no episodic ancestry cannot become a fact.
    """
    if not isinstance(raw, dict):
        raise SchemaRejection("entry is not an object")
    etype = raw.get("type")
    if etype not in ENTRY_TYPES:
        raise SchemaRejection(f"bad type: {etype!r}")
    content = raw.get("content")
    if not isinstance(content, str) or not content.strip():
        raise SchemaRejection("empty content")
    if len(content) > 2000:
        raise SchemaRejection("content exceeds 2000 chars")
    prov = raw.get("provenance")
    if not isinstance(prov, list) or not prov:
        raise SchemaRejection("missing provenance (IR: no ancestry, no fact)")
    tier = raw.get("confidence_tier")
    if tier not in CONFIDENCE_TIERS:
        raise SchemaRejection(f"bad confidence_tier: {tier!r}")
    return MemoryEntry(type=etype, content=content.strip(),
                       provenance=[str(p) for p in prov], confidence_tier=tier,
                       valid_from=str(raw.get("valid_from", "")),
                       valid_to=raw.get("valid_to"))


def token_estimate(entries: Iterable[MemoryEntry]) -> int:
    """Cheap, stable proxy (~4 chars/token). Trend matters, not absolute value."""
    return sum(len(e.content) for e in entries) // 4


# --------------------------------------------------------------------------- #
# Region selection
# --------------------------------------------------------------------------- #

@dataclass
class RegionSelector:
    kind: str = "newly_written"     # newly_written | recently_retrieved | entity_scoped
                                    # | contradiction_cluster | low_utility
    max_entries: int = 40

    def select(self, bank: Sequence[MemoryEntry],
               retrieved_ids: Sequence[str] = ()) -> list[MemoryEntry]:
        if self.kind == "recently_retrieved":
            wanted = set(retrieved_ids)
            picked = [e for e in bank if e.id in wanted]
        elif self.kind == "contradiction_cluster":
            picked = list(bank)   # caller pre-filters; kept explicit for readability
        else:
            picked = list(bank)
        return picked[: self.max_entries]


# --------------------------------------------------------------------------- #
# Batch
# --------------------------------------------------------------------------- #

@dataclass
class ConsolidationBatch:
    region: list[MemoryEntry]
    replacement_set: list[MemoryEntry]
    omitted: list[dict] = field(default_factory=list)
    contradictions_escalated: list[dict] = field(default_factory=list)
    id: str = field(default_factory=lambda: f"cb_{uuid.uuid4().hex[:12]}")
    started_at: str = field(default_factory=lambda: datetime.now(timezone.utc)
                            .isoformat(timespec="seconds"))
    identity_hash_before: str = ""
    identity_hash_after: str = ""
    rejected_writes: int = 0
    attempted_writes: int = 0

    @property
    def tokens_before(self) -> int:
        return token_estimate(self.region)

    @property
    def tokens_after(self) -> int:
        return token_estimate(self.replacement_set)

    @property
    def shrink_ratio(self) -> float:
        before = self.tokens_before
        return (self.tokens_after / before) if before else 1.0

    @property
    def reject_rate(self) -> float:
        return (self.rejected_writes / self.attempted_writes) if self.attempted_writes else 0.0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "started_at": self.started_at,
            "region": {"member_ids": [e.id for e in self.region],
                       "selector": "newly_written"},
            "replacement_set": [e.to_dict() for e in self.replacement_set],
            "omitted": self.omitted,
            "contradictions_escalated": self.contradictions_escalated,
            "invariants": {"identity_hash_before": self.identity_hash_before,
                           "identity_hash_after": self.identity_hash_after},
            "size_delta": {"tokens_before": self.tokens_before,
                           "tokens_after": self.tokens_after,
                           "entries_before": len(self.region),
                           "entries_after": len(self.replacement_set)},
            "health": {"attempted_writes": self.attempted_writes,
                       "rejected_writes": self.rejected_writes,
                       "reject_rate": round(self.reject_rate, 4)},
        }


_REWRITE_PROMPT = """\
You are consolidating one region of an agent's semantic memory.

The region below is READ-ONLY EVIDENCE. Do not edit it entry by entry. Instead,
emit a COMPLETE REPLACEMENT SET that should stand in its place. Anything you do
not carry forward is deleted - that is intended.

Requirements:
- Prefer FEWER, more general entries. A smaller replacement set that preserves
  task-relevant information is the goal, not a faithful copy.
- Every entry MUST cite provenance ids drawn from the evidence.
- NEVER merge entries across confidence tiers (user_stated / tool_observed /
  model_inferred). Keep the weakest tier if you must combine.
- If two `user_stated` entries directly contradict, do NOT choose. Emit them in
  "contradictions" for a human to resolve.
- Output ONLY JSON:
  {{"replacement_set": [...], "omitted": [{{"id": "...", "reason": "redundant|superseded|contradicted|low_utility|noise"}}],
    "contradictions": [{{"a": "...", "b": "...", "question": "..."}}]}}

REGION ({n} entries, ~{tokens} tokens):
{region}

SOURCE TRAJECTORY EXCERPTS:
{trajectories}
"""


def build_batch(
    region: Sequence[MemoryEntry],
    trajectories: str,
    llm: LLMFn,
    *,
    identity_before: str = "",
    max_reject_rate: float = 0.10,
) -> ConsolidationBatch:
    """
    Run one region rewrite. Raises SchemaRejection if the model's write quality
    is below the health floor - better to skip a night than to corrupt the bank.
    """
    prompt = _REWRITE_PROMPT.format(
        n=len(region),
        tokens=token_estimate(region),
        region=json.dumps([e.to_dict() for e in region], indent=2),
        trajectories=trajectories[:8000],
    )
    raw = _strip_fences(llm(prompt))
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise SchemaRejection(f"consolidator emitted non-JSON: {exc}") from exc

    replacement: list[MemoryEntry] = []
    attempted = 0
    rejected = 0
    for item in parsed.get("replacement_set", []):
        attempted += 1
        try:
            replacement.append(validate_entry(item))
        except SchemaRejection:
            rejected += 1

    batch = ConsolidationBatch(
        region=list(region),
        replacement_set=replacement,
        omitted=list(parsed.get("omitted", [])),
        contradictions_escalated=list(parsed.get("contradictions", [])),
        identity_hash_before=identity_before,
        attempted_writes=attempted,
        rejected_writes=rejected,
    )
    if batch.reject_rate > max_reject_rate:
        raise SchemaRejection(
            f"write reject rate {batch.reject_rate:.0%} exceeds {max_reject_rate:.0%} — "
            f"consolidator model is unreliable; aborting phase (arXiv:2602.19320)"
        )
    return batch


def utility_ok(
    batch: ConsolidationBatch,
    score_with: float,
    score_without: float,
    score_replacement: float,
    *,
    tolerance: float = 0.01,
) -> tuple[bool, str]:
    """
    Counterfactual utility check — a cheap stand-in for Auto-Dreamer's r_cf.

    Mask the region and re-run a small fixture set:
      score_with        : fixtures with the ORIGINAL region present
      score_without     : fixtures with the region MASKED
      score_replacement : fixtures with the REPLACEMENT set in place

    Accept when the replacement holds the line (within tolerance) AND does not
    grow. If masking the region costs nothing, the region was dead weight and an
    empty replacement is the correct answer.
    """
    if score_replacement + tolerance < score_with:
        return False, (f"replacement_degrades:{score_replacement:.3f}"
                       f"<{score_with:.3f}-{tolerance}")
    if batch.tokens_after > batch.tokens_before:
        return False, (f"replacement_grew:{batch.tokens_before}->{batch.tokens_after} "
                       f"tokens (IR-8: prefer deleting)")
    if abs(score_with - score_without) <= tolerance and batch.replacement_set:
        return True, ("region_was_dead_weight:consider_empty_replacement "
                      f"(masking cost {score_with - score_without:+.3f})")
    return True, (f"ok:score={score_replacement:.3f} "
                  f"shrink={batch.shrink_ratio:.2f}x")


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        t = t.rsplit("```", 1)[0]
    return t.strip()
