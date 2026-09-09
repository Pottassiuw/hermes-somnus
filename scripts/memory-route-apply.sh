#!/usr/bin/env bash
set -euo pipefail
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
for ENV_FILE in "$HERMES_HOME/.env" "$HERMES_HOME/somnus/.env"; do
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090,SC1091
    . "$ENV_FILE"
  fi
done
export SOMNUS_ROUTER_APPLY=1
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/..${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "$SCRIPT_DIR/memory-route.py" --apply --batch-size "${SOMNUS_ROUTER_BATCH_SIZE:-25}" --quiet "$@"
