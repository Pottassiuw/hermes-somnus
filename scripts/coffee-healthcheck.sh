#!/usr/bin/env bash
# Deterministic COFFEE connectivity probe. Never prints credentials or body data.
set -u
URL="${COFFEE_HEALTH_URL:-${COFFEE_URL:-}}"
if [ -z "$URL" ]; then
  printf 'coffee status=SKIPPED reason=COFFEE_HEALTH_URL_unset
'
  exit 0
fi

# Use HTTP/1.1 and standard User-Agent to avoid HTTP/2 stream negotiation hangs on enterprise proxies
result="$(curl -sS -o /dev/null -w '%{http_code}|%{content_type}|%{time_total}' --http1.1 -A 'Mozilla/5.0' --max-time 15 "$URL" 2>/dev/null || printf '000||0')"
IFS='|' read -r code content_type latency <<<"$result"
printf 'coffee status=%s content_type=%s latency_s=%s
' "$code" "${content_type:-unknown}" "${latency:-unknown}"

case "$code" in
  2*|3*) exit 0 ;;
  *) exit 1 ;;
esac
