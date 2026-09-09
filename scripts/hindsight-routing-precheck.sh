#!/usr/bin/env bash
# Stable Hindsight stats fingerprint for a zero-token cron monitor.
set -euo pipefail
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
for ENV_FILE in "$HERMES_HOME/.env" "$HERMES_HOME/somnus/.env"; do
  if [ -f "$ENV_FILE" ]; then
    # shellcheck disable=SC1090,SC1091
    . "$ENV_FILE"
  fi
done
URL="${HINDSIGHT_API_URL:-${HINDSIGHT_URL:-http://127.0.0.1:8888}}"
BANK="${HINDSIGHT_SOURCE_BANK:-${HINDSIGHT_BANK_ID:-agent-hermes}}"
TMP="$(mktemp)"
trap 'rm -f "$TMP"' EXIT
if [ -n "${HINDSIGHT_API_KEY:-}" ]; then
  code="$(curl -sS -o "$TMP" -w '%{http_code}' --max-time 10 -H "Authorization: Bearer ${HINDSIGHT_API_KEY}" "$URL/v1/default/banks/$BANK/stats" 2>/dev/null || printf '000')"
else
  code="$(curl -sS -o "$TMP" -w '%{http_code}' --max-time 10 "$URL/v1/default/banks/$BANK/stats" 2>/dev/null || printf '000')"
fi
if [ "$code" != 200 ]; then
  printf 'hindsight routing monitor bank=%s status=%s\n' "$BANK" "$code"
  exit 1
fi
python3 - "$BANK" "$TMP" <<'PY'
import json, sys
bank, path = sys.argv[1:]
try:
    data = json.loads(open(path, encoding="utf-8").read())
except Exception:
    print(f"hindsight routing monitor bank={bank} status=invalid_json")
    raise SystemExit(1)
keys = ("total_nodes", "total_links", "total_documents", "total_observations", "pending_operations", "failed_operations", "pending_consolidation", "failed_consolidation")
counts = {key: data.get(key) for key in keys if key in data}
by_type = data.get("nodes_by_fact_type")
if isinstance(by_type, dict):
    counts["nodes_by_fact_type"] = {str(key): by_type[key] for key in sorted(by_type)}
print(json.dumps({"bank": bank, "status": "ok", "counts": counts}, sort_keys=True))
PY
