#!/usr/bin/env bash
# Read-only post-merge smoke. Mutating sync is opt-in and never default.
set -u
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
REPO="${HELIOS_REPO:-$HERMES_HOME/helios-audit-cron}"
REPORT_DIR="${SOMNUS_REPORT_DIR:-$HOME/.hermes/somnus/reports}"
BASE_URL="${HELIOS_BASE_URL:-}"
mkdir -p "$REPORT_DIR"
REPORT="$REPORT_DIR/helios-smoke-$(date -u +%Y%m%dT%H%M%SZ).log"
umask 077
touch "$REPORT"
fail=0
run_logged() {
  name="$1"; shift
  "$@" >"$REPORT.$name" 2>&1
  rc=$?
  printf '%s exit=%s log=%s\n' "$name" "$rc" "$REPORT.$name"
  [ "$rc" -eq 0 ] || fail=1
}
if [ ! -d "$REPO/.git" ]; then
  printf 'smoke repository=unavailable\n'
  exit 2
fi
PYTHON="${HELIOS_PYTHON:-python3}"
if command -v "$PYTHON" >/dev/null 2>&1 && "$PYTHON" -c 'import pytest' >/dev/null 2>&1; then
  run_logged backend "$PYTHON" -m pytest -q "$REPO/backend"
else
  printf 'backend exit=skipped reason=pytest_unavailable python=%s\n' "$PYTHON"
  fail=1
fi
if [ -f "$REPO/frontend/package.json" ]; then
  NPM="${HELIOS_NPM:-npm}"
  if command -v "$NPM" >/dev/null 2>&1; then
    run_logged frontend "$NPM" --prefix "$REPO/frontend" run build
  else
    printf 'frontend exit=skipped reason=npm_unavailable executable=%s\n' "$NPM"
    fail=1
  fi
else
  printf 'frontend exit=skipped reason=package_json_missing\n'
fi
if [ -z "$BASE_URL" ]; then
  printf 'api=skipped reason=HELIOS_BASE_URL_unset\n'
  [ "${HELIOS_REQUIRE_API:-0}" = 1 ] && fail=1
else
  for path in /api/carteira/plano/status /api/carteira/dashboard; do
    code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 20 "$BASE_URL$path" 2>/dev/null || printf '000')"
    printf 'api_get path=%s status=%s\n' "$path" "$code"
    case "$code" in 2*) ;; *) fail=1 ;; esac
  done
  if [ "${HELIOS_SMOKE_ALLOW_MUTATION:-0}" = 1 ]; then
    payload="${HELIOS_SYNC_PAYLOAD:-{}}"
    code="$(curl -fsS -o /dev/null -w '%{http_code}' --max-time 60 -X POST -H 'Content-Type: application/json' --data "$payload" "$BASE_URL/api/carteira/plano/sincronizar" 2>/dev/null || printf '000')"
    printf 'api_post path=/api/carteira/plano/sincronizar status=%s\n' "$code"
    case "$code" in 2*) ;; *) fail=1 ;; esac
  else
    printf 'api_post path=/api/carteira/plano/sincronizar status=skipped reason=mutation_not_allowed\n'
  fi
fi
printf 'report=%s\n' "$REPORT"
exit "$fail"
