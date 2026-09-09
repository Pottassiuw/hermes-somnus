#!/usr/bin/env python3
"""Run a read-only, budgeted, structured Hindsight Reflect query."""
from __future__ import annotations

import sys
from pathlib import Path as _ScriptPath
_SCRIPT_ROOT = _ScriptPath(__file__).resolve().parents[1]
if str(_SCRIPT_ROOT) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_ROOT))

import argparse
import json
import os

from somnus.memory_router import env_client, redact_sensitive
from somnus.reflect import ReflectRequest, Reflector


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query")
    parser.add_argument("--bank", default=os.environ.get("HINDSIGHT_BANK", "repo-edp-helios"))
    parser.add_argument("--budget", choices=["low", "mid", "high"], default="low")
    parser.add_argument("--max-tokens", type=int, default=1200)
    args = parser.parse_args()
    try:
        result = Reflector(env_client()).run(args.bank, ReflectRequest(args.query, budget=args.budget, max_tokens=args.max_tokens))
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except Exception as exc:
        print(json.dumps({"error": redact_sensitive(str(exc))[:500], "bank": args.bank}, ensure_ascii=False, sort_keys=True))
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
