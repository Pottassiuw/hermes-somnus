"""
somnus.report — the morning digest.

One file you read with coffee. The section that teaches you the most is
REJECTED: it tells you what your agent tried and exactly which gate stopped it.
A digest that only lists wins is a digest that is hiding a broken harness.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .daemon import CycleReport

__all__ = ["render", "write"]

_STATUS_MARK = {"ok": "✅", "skipped": "💤", "aborted": "🛑", "disabled": "⏸️", "unknown": "❔"}


def render(report: CycleReport, cfg=None) -> str:
    mark = _STATUS_MARK.get(report.status, "❔")
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    lines: list[str] = [
        f"# Somnus digest — {date}",
        "",
        f"{mark} **{report.status}**" + (f" — {report.reason}" if report.reason else ""),
        "",
        f"- run: `{report.run_id or '—'}`",
        f"- triggers: {', '.join(report.triggers) or '—'}",
        f"- cost: {report.llm_calls} LLM calls, ${report.usd:.2f}",
        "",
    ]

    if report.status in {"skipped", "disabled"}:
        lines += ["_Nothing ran. This is a normal outcome and costs nothing._", ""]
        return "\n".join(lines)

    lines += ["## Phases", "", "| phase | ok | items | detail |", "|---|---|---|---|"]
    for p in report.phases:
        lines.append(f"| {p.name} | {'✅' if p.ok else '❌'} | {p.items} | {p.detail} |")
    lines.append("")

    lines += [
        "## Memory",
        "",
        f"- failure signatures found: **{report.failures_found}**",
        f"- consolidation batches accepted / rejected: **{report.batches_accepted}** / "
        f"{report.batches_rejected}",
        f"- tokens reclaimed: **{report.tokens_saved}**"
        + ("  ← this should trend positive; a growing bank means the consolidator is "
           "archiving rather than compressing" if report.tokens_saved == 0 else ""),
        "",
    ]

    lines += ["## Accepted", ""]
    if report.accepted:
        lines += ["| hypothesis | effect | p | staged at |", "|---|---|---|---|"]
        for a in report.accepted:
            lines.append(f"| `{a['id']}` | {a.get('effect', 0):+.4f} | "
                         f"{a.get('p', 1):.4g} | `{a.get('ref', '—')}` |")
    else:
        lines.append("_Nothing accepted. Zero is a perfectly good night._")
    lines.append("")

    lines += ["## Rejected — read this section first", ""]
    if report.rejected:
        lines += ["| hypothesis | gate |", "|---|---|"]
        for r in report.rejected:
            lines.append(f"| `{r['id']}` | {r['reason']} |")
        lines += [
            "",
            "> Repeated `unfalsifiable_fixture` means ideation is producing prose, not "
            "tests. Repeated `insufficient_pairs` means the fixture suite is too small "
            "to conclude anything. Repeated `guard_regression` means something is trying "
            "to trade safety for score — investigate that one by hand.",
        ]
    else:
        lines.append("_Nothing rejected._")
    lines.append("")

    return "\n".join(lines)


def write(report: CycleReport, cfg) -> Path:
    date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    out_dir = cfg.home_path / "reports" / date
    out_dir.mkdir(parents=True, exist_ok=True)

    (out_dir / "run.json").write_text(
        json.dumps({
            "run_id": report.run_id,
            "status": report.status,
            "reason": report.reason,
            "triggers": list(report.triggers),
            "failures_found": report.failures_found,
            "batches_accepted": report.batches_accepted,
            "batches_rejected": report.batches_rejected,
            "hypotheses_queued": report.hypotheses_queued,
            "accepted": report.accepted,
            "rejected": report.rejected,
            "tokens_saved": report.tokens_saved,
            "llm_calls": report.llm_calls,
            "usd": report.usd,
            "phases": [p.__dict__ for p in report.phases],
        }, indent=2, sort_keys=True),
        encoding="utf-8",
    )

    digest = out_dir / "DIGEST.md"
    digest.write_text(render(report, cfg), encoding="utf-8")
    return digest
