#!/usr/bin/env bash
# Deterministic COFFEE connectivity probe. Never prints credentials or body data.
set -u
URL="${COFFEE_HEALTH_URL:-${COFFEE_URL:-}}"
if [ -z "$URL" ]; then
  printf 'coffee status=skipped reason=COFFEE_HEALTH_URL_unset\n'
  exit 2
fi
headers=()
if [ -n "${COFFEE_API_KEY:-}" ]; then
  headers=(-H "Authorization: Bearer ${COFFEE_API_KEY}")
fi
result="$(curl -sS -o /dev/null -w '%{http_code}|%{content_type}|%{time_total}' --max-time 20 "${headers[@]}" "$URL" 2>/dev/null || printf '000||0')"
IFS='|' read -r code content_type latency <<<"$result"
printf 'coffee status=%s content_type=%s latency_s=%s\n' "$code" "${content_type:-unknown}" "${latency:-unknown}"
case "$code" in 2*|3*) exit 0 ;; *) exit 1 ;; esac
