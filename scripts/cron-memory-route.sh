#!/usr/bin/env bash
set -euo pipefail
HERMES_HOME="${HERMES_HOME:-/opt/data}"
SOMNUS_ROOT="${SOMNUS_ROOT:-/opt/data/hermes-somnus}"

for ENV_FILE in "/opt/data/.env" "$HOME/.env" "$HOME/somnus/.env"; do
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090,SC1091
    set -a
    . "$ENV_FILE"
    set +a
  fi
done

if [ -z "${HINDSIGHT_URL:-}" ] || [ "$HINDSIGHT_URL" = "http://127.0.0.1:8888" ] || [ "$HINDSIGHT_URL" = "http://localhost:8888" ]; then
  export HINDSIGHT_URL="http://hindsight-app:8888"
fi
if [ -z "${HINDSIGHT_API_URL:-}" ] || [ "$HINDSIGHT_API_URL" = "http://127.0.0.1:8888" ] || [ "$HINDSIGHT_API_URL" = "http://localhost:8888" ]; then
  export HINDSIGHT_API_URL="http://hindsight-app:8888"
fi

export HINDSIGHT_TIMEOUT_S=90
export SOMNUS_ROUTER_APPLY=1
export PYTHONPATH="$SOMNUS_ROOT${PYTHONPATH:+:$PYTHONPATH}"

# Controlled batch size (5) and max-facts (10) per run to keep Pi latency and memory safe
BATCH_SIZE="${SOMNUS_ROUTER_BATCH_SIZE:-5}"
MAX_FACTS="${SOMNUS_ROUTER_MAX_FACTS:-10}"

exec python3 "$SOMNUS_ROOT/scripts/memory-route.py" --apply --batch-size "$BATCH_SIZE" --max-facts "$MAX_FACTS" --quiet
