#!/usr/bin/env python3
"""Run deterministic Python static checks for a Helios checkout."""
from __future__ import annotations
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from somnus.code_audit import main
raise SystemExit(main())
