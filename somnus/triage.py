"""
somnus.triage — turn last night's sessions into FailureRecords.

The atom of the whole system. Nothing improves without evidence, and evidence
starts as a normalized error signature that lets you tell "this happened 14
times" from "this happened once".

Shape borrowed from Hermes issue #41963 (Reflexion-style structured failure
learning): [trigger] -> [error] -> [consequence] -> [defense], where `defense`
is the check that would have prevented it and therefore becomes a permanent
guard fixture (§3.3.4).

The LLM is injected as a callable so this module is testable offline and so you
can route it to a cheap auxiliary model (Hermes: `auxiliary.*`).
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, asdict, field
from datetime import datetime, timezone
from typing import Callable, Iterable, Sequence

__all__ = ["Turn", "FailureRecord", "normalize_error", "signature_of", "cluster", "extract"]

LLMFn = Callable[[str], str]   # prompt -> completion


# --------------------------------------------------------------------------- #
# Inputs
# --------------------------------------------------------------------------- #

@dataclass(frozen=True)
class Turn:
    session_id: str
    index: int
    ts: str
    role: str                 # user | assistant | tool
    tool_name: str = ""
    content: str = ""
    ok: bool = True
    task_class: str = ""


# --------------------------------------------------------------------------- #
# Normalization — the part that makes clustering work
# --------------------------------------------------------------------------- #

_SUBS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"0x[0-9a-fA-F]+"), "<ADDR>"),
    (re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
                r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"), "<UUID>"),
    (re.compile(r"\b\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}:\d{2}\S*"), "<TS>"),
    (re.compile(r"(/[\w.\-]+){2,}"), "<PATH>"),
    # NOTE: no \b anchors. "30s" and "45s" have no word boundary between the
    # digits and the unit, so \b\d+\b would leave them distinct and every
    # occurrence of the same timeout bug would get its own signature.
    (re.compile(r"\d+"), "<N>"),
    (re.compile(r"\s+"), " "),
)


def normalize_error(text: str) -> str:
    """
    Strip the parts of an error that vary between occurrences of the same bug.

    Without this every failure looks unique, `occurrences` is always 1, and the
    "recurring failure" trigger never fires. Most failures are one bug wearing
    many hats (§3.3.3, tier 0).
    """
    out = text.strip()
    for pattern, repl in _SUBS:
        out = pattern.sub(repl, out)
    return out.strip()[:400]


def signature_of(error: str, tool: str = "", task_class: str = "") -> str:
    norm = normalize_error(error)
    raw = f"{task_class}|{tool}|{norm}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]


# --------------------------------------------------------------------------- #
# FailureRecord
# --------------------------------------------------------------------------- #

@dataclass
class FailureRecord:
    signature: str
    trigger: str
    error: str
    consequence: str
    id: str = ""
    first_seen: str = ""
    last_seen: str = ""
    occurrences: int = 1
    severity: str = "degraded"          # cosmetic | degraded | blocking | unsafe
    task_class: str = ""
    defense: str | None = None
    locus: dict = field(default_factory=dict)
    environment: dict = field(default_factory=dict)
    evidence: list = field(default_factory=list)
    status: str = "open"

    def to_dict(self) -> dict:
        d = asdict(self)
        d["first_seen"] = d["first_seen"] or datetime.now(timezone.utc).isoformat(timespec="seconds")
        d["last_seen"] = d["last_seen"] or d["first_seen"]
        return d


# --------------------------------------------------------------------------- #
# Clustering + extraction
# --------------------------------------------------------------------------- #

def cluster(turns: Sequence[Turn]) -> dict[str, list[Turn]]:
    """Group failing turns by normalized signature."""
    groups: dict[str, list[Turn]] = {}
    for t in turns:
        if t.ok:
            continue
        sig = signature_of(t.content, t.tool_name, t.task_class)
        groups.setdefault(sig, []).append(t)
    return groups


_PROMPT = """\
You are triaging one recurring agent failure. Answer ONLY with JSON matching:

{{"trigger": "...", "consequence": "...", "defense": "...", "severity": "cosmetic|degraded|blocking|unsafe"}}

Rules:
- "trigger" is the state or action immediately BEFORE the error, stated concretely.
- "consequence" is what the USER actually lost. Not what the stack trace said.
- "defense" is a single mechanical check that would have prevented this. It must
  be something a script can assert. If no such check exists, use null.
- Do not speculate about causes you cannot see in the evidence.

Task class: {task_class}
Tool: {tool}
Occurrences: {occurrences}

Evidence (most recent {n} excerpts):
{evidence}
"""


def extract(
    turns: Iterable[Turn],
    llm: LLMFn | None = None,
    *,
    max_records: int = 20,
    max_excerpts: int = 3,
) -> list[FailureRecord]:
    """
    Sessions -> FailureRecords.

    Deterministic without an LLM (signature, occurrences, evidence); the LLM
    only fills the interpretive fields. That split matters: if the model is
    unavailable or emits garbage, you still get a usable, countable failure
    ledger rather than nothing.
    """
    turns = list(turns)
    groups = cluster(turns)
    records: list[FailureRecord] = []

    for sig, members in sorted(groups.items(), key=lambda kv: -len(kv[1]))[:max_records]:
        members.sort(key=lambda t: t.ts)
        head, tail = members[0], members[-1]
        rec = FailureRecord(
            signature=sig,
            trigger="",
            error=normalize_error(tail.content),
            consequence="",
            first_seen=head.ts,
            last_seen=tail.ts,
            occurrences=len(members),
            task_class=tail.task_class,
            evidence=[{"session_id": m.session_id,
                       "turn_range": [m.index, m.index],
                       "excerpt": m.content[:2000]} for m in members[-max_excerpts:]],
        )

        if llm is not None:
            prompt = _PROMPT.format(
                task_class=tail.task_class or "unknown",
                tool=tail.tool_name or "unknown",
                occurrences=len(members),
                n=min(max_excerpts, len(members)),
                evidence="\n---\n".join(e["excerpt"] for e in rec.evidence),
            )
            try:
                parsed = json.loads(_strip_fences(llm(prompt)))
                rec.trigger = str(parsed.get("trigger", ""))[:500]
                rec.consequence = str(parsed.get("consequence", ""))[:500]
                defense = parsed.get("defense")
                rec.defense = None if defense in (None, "", "null") else str(defense)[:500]
                sev = str(parsed.get("severity", "degraded"))
                if sev in {"cosmetic", "degraded", "blocking", "unsafe"}:
                    rec.severity = sev
            except Exception:
                # A parse failure is data, not a crash: count it and move on.
                rec.trigger = rec.trigger or "<triage-parse-failed>"

        records.append(rec)

    return records


def _strip_fences(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = t.split("\n", 1)[-1]
        t = t.rsplit("```", 1)[0]
    return t.strip()
