#!/usr/bin/env python3
"""Run the explicit Hindsight bank router with safe aggregate output."""
from __future__ import annotations

import sys
from pathlib import Path as _ScriptPath
_SCRIPT_ROOT = _ScriptPath(__file__).resolve().parents[1]
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

import argparse
import json
import os
from pathlib import Path

from somnus.memory_router import MemoryRouter, RouteLedger, classify_fact, env_client, redact_sensitive


def truthy(value: str) -> bool:
    return value.casefold() in {"1", "true", "yes", "on"}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="request writes; still requires SOMNUS_ROUTER_APPLY=1")
    parser.add_argument("--source-bank", default=os.environ.get("HINDSIGHT_SOURCE_BANK", "agent-hermes"))
    parser.add_argument("--page-size", type=int, default=100)
    parser.add_argument("--max-pages", type=int, default=20)
    parser.add_argument("--db", default=os.environ.get("SOMNUS_DB", "~/.hermes/somnus/somnus.db"))
    parser.add_argument("--contains", default="", help="select a bounded case-insensitive text match")
    parser.add_argument("--max-facts", type=int, default=0, help="cap selected facts; intended for canaries")
    parser.add_argument("--target-bank", default="", help="select only facts classified for this bank")
    parser.add_argument("--batch-size", type=int, default=int(os.environ.get("SOMNUS_ROUTER_BATCH_SIZE", "25")))
    parser.add_argument("--quiet", action="store_true", help="suppress a clean no-work report")
    args = parser.parse_args()
    apply = args.apply and truthy(os.environ.get("SOMNUS_ROUTER_APPLY", ""))
    if args.page_size < 1 or args.page_size > 500 or args.max_pages < 1 or not 1 <= args.batch_size <= 50:
        print(json.dumps({"error": "invalid pagination bounds", "apply_enabled": apply}))
        return 2
    try:
        facts = []
        client = env_client()
        for page in range(args.max_pages):
            page_items = client.list_memories(args.source_bank, limit=args.page_size, offset=page * args.page_size)
            facts.extend(page_items)
            if len(page_items) < args.page_size:
                break
        else:
            print(json.dumps({"error": "pagination limit reached; refusing partial migration", "apply_enabled": apply}))
            return 2
        if args.max_facts < 0:
            print(json.dumps({"error": "max-facts cannot be negative", "apply_enabled": apply}))
            return 2
        if args.contains:
            needle = args.contains.casefold()
            facts = [fact for fact in facts if needle in fact.text.casefold()]
        if args.target_bank:
            facts = [fact for fact in facts if fact.fact_type != "observation" and fact.state == "valid" and classify_fact(fact.text).bank_id == args.target_bank]
        if args.max_facts:
            facts = facts[:args.max_facts]
        ledger = RouteLedger(Path(os.path.expanduser(args.db)))
        try:
            report = MemoryRouter(client, ledger, apply=apply, max_batch=args.batch_size).route(args.source_bank, facts)
        finally:
            ledger.close()
        report["facts_scanned"] = len(facts)
        report["selection_contains"] = bool(args.contains)
        report["selection_capped"] = bool(args.max_facts)
        report["selection_target_bank"] = args.target_bank or None
        report["apply_requested"] = bool(args.apply)
        report["apply_enabled"] = apply
        if not (args.quiet and not report["errors"] and report["planned"] == 0):
            print(json.dumps(report, ensure_ascii=False, sort_keys=True))
        return 1 if report["errors"] else 0
    except Exception as exc:
        print(json.dumps({"error": redact_sensitive(str(exc))[:500], "source_bank": args.source_bank, "apply_enabled": apply}, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
