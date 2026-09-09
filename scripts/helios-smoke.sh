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
has_fail=0
has_blocked=0

run_logged() {
  name="$1"; shift
  "$@" >"$REPORT.$name" 2>&1
  rc=$?
  if [ "$rc" -eq 0 ]; then
    printf "%s status=PASS exit=0 log=%s
" "$name" "$REPORT.$name"
  else
    printf "%s status=FAIL exit=%s log=%s
" "$name" "$rc" "$REPORT.$name"
    has_fail=1
  fi
}

if [ ! -d "$REPO/.git" ]; then
  printf "smoke repository=unavailable status=BLOCKED
"
  exit 3
fi

PYTHON="${HELIOS_PYTHON:-python3}"
if command -v "$PYTHON" >/dev/null 2>&1 && "$PYTHON" -c "import pytest" >/dev/null 2>&1; then
  run_logged backend "$PYTHON" -m pytest -q "$REPO/backend"
else
  printf "backend status=BLOCKED reason=pytest_unavailable python=%s
" "$PYTHON"
  has_blocked=1
fi

if [ -f "$REPO/frontend/package.json" ]; then
  NPM="${HELIOS_NPM:-npm}"
  if command -v "$NPM" >/dev/null 2>&1; then
    run_logged frontend "$NPM" --prefix "$REPO/frontend" run build
  else
    printf "frontend status=BLOCKED reason=npm_unavailable executable=%s
" "$NPM"
    has_blocked=1
  fi
else
  printf "frontend status=SKIPPED reason=package_json_missing
"
fi

if [ -z "$BASE_URL" ]; then
  printf "api status=SKIPPED reason=HELIOS_BASE_URL_unset
"
  if [ "${HELIOS_REQUIRE_API:-0}" = 1 ]; then has_blocked=1; fi
else
  for path in /api/carteira/plano/status /api/carteira/dashboard; do
    code="$(curl -fsS -o /dev/null -w "%{http_code}" --max-time 20 "$BASE_URL$path" 2>/dev/null || printf 000)"
    printf "api_get path=%s status=%s
" "$path" "$code"
    case "$code" in 2*) ;; *) has_fail=1 ;; esac
  done
fi

printf "report=%s
" "$REPORT"
if [ "$has_fail" -eq 1 ]; then
  printf "overall_status=FAIL
"
  exit 1
elif [ "$has_blocked" -eq 1 ]; then
  printf "overall_status=BLOCKED
"
  exit 3
else
  printf "overall_status=PASS
"
  exit 0
fi
