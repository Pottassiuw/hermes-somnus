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
export PYTHONPATH="$SOMNUS_ROOT${PYTHONPATH:+:$PYTHONPATH}"
QUERY="${HINDSIGHT_REFLECT_QUERY:-Generate a concise weekly digest of verified technical facts and unresolved contradictions. Do not invent facts. Return structured output and require human review for contradictions.}"
exec python3 "$SOMNUS_ROOT/scripts/somnus-reflect.py" --bank "${HINDSIGHT_BANK:-repo-edp-helios}" "$QUERY"
