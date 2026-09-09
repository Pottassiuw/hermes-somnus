#!/usr/bin/env bash
set -euo pipefail
HERMES_HOME="${HERMES_HOME:-$HOME}"
SOMNUS_ROOT="${SOMNUS_ROOT:-$HERMES_HOME/hermes-somnus}"
export PYTHONPATH="$SOMNUS_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "$SOMNUS_ROOT/scripts/somnus-maintenance.py" --db "${SOMNUS_DB:-$HOME/.hermes/somnus/somnus.db}"
