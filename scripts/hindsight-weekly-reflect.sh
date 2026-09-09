#!/usr/bin/env bash
set -euo pipefail
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
for ENV_FILE in "$HERMES_HOME/.env" "$HERMES_HOME/somnus/.env"; do
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090,SC1091
    . "$ENV_FILE"
  fi
done
QUERY="${HINDSIGHT_REFLECT_QUERY:-Generate a concise weekly digest of verified technical facts and unresolved contradictions. Do not invent facts. Return structured output and require human review for contradictions.}"
BANK="${HINDSIGHT_BANK:-repo-edp-helios}"
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
export PYTHONPATH="$SCRIPT_DIR/..${PYTHONPATH:+:$PYTHONPATH}"
exec python3 "$SCRIPT_DIR/somnus-reflect.py" --bank "$BANK" "$QUERY"
