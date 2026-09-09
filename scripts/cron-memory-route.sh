#!/usr/bin/env bash
set -euo pipefail
HERMES_HOME="${HERMES_HOME:-$HOME}"
SOMNUS_ROOT="${SOMNUS_ROOT:-$HERMES_HOME/hermes-somnus}"
for ENV_FILE in "$HERMES_HOME/.env" "$HERMES_HOME/somnus/.env"; do
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090,SC1091
    . "$ENV_FILE"
  fi
done
export SOMNUS_ROUTER_APPLY=1
export PYTHONPATH="$SOMNUS_ROOT${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "$SOMNUS_ROOT/scripts/memory-route.py" --apply --batch-size "${SOMNUS_ROUTER_BATCH_SIZE:-25}" --quiet
