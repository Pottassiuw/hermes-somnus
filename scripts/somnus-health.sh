#!/usr/bin/env bash
#
# somnus-health.sh — the deterministic probe suite.
#
#   hermes cron create "*/15 * * * *" --no-agent \
#     --script somnus-health.sh --deliver telegram --name somnus-health
#
# Silent (and free) when everything is green: emits {"wakeAgent": false} with no
# body. Speaks up only when something is actually wrong — which is the only way
# a 15-minute probe stays readable over months.
#
set -uo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SOMNUS_HOME="$HERMES_HOME/somnus"

# Load local environment overrides if present
if [ -f "$SOMNUS_HOME/.env" ]; then
  # shellcheck disable=SC1090,SC1091
  . "$SOMNUS_HOME/.env"
fi

HINDSIGHT_URL="${HINDSIGHT_URL:-http://127.0.0.1:8888}"
BANK="${HINDSIGHT_BANK:-agent-hermes}"
HINDSIGHT_API_KEY="${HINDSIGHT_API_KEY:-}"
REPO="${SOMNUS_REPO:-$HERMES_HOME/hermes-agent}"

red=()
warn=()

probe() {  # probe <name> <command...>
  local name="$1"; shift
  if ! "$@" >/dev/null 2>&1; then
    red+=("$name")
  fi
}

# ------------------------------------------------------------- host ---------
load1="$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo 0)"
temp=$(( $(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0) / 1000 ))
free_mb="$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 0)"
used_pct="$(df --output=pcent "$HOME" 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0)"

[ "$temp" -ge 75 ] && red+=("thermal:${temp}C")
[ "$free_mb" -le 400 ] && red+=("memory:${free_mb}MB")
[ "$(( 100 - ${used_pct:-0} ))" -le 10 ] && red+=("disk:$(( 100 - used_pct ))%free")
awk -v l="$load1" 'BEGIN{exit !(l > 3.0)}' && warn+=("load1:$load1")

# -------------------------------------------------------- dependencies ------
probe "hindsight:health" curl -fsS --max-time 5 "$HINDSIGHT_URL/health"
if [ -n "$HINDSIGHT_API_KEY" ]; then
  probe "hindsight:stats" curl -fsS --max-time 5 -H "Authorization: Bearer $HINDSIGHT_API_KEY" "$HINDSIGHT_URL/v1/default/banks/$BANK/stats"
else
  probe "hindsight:stats" curl -fsS --max-time 5 "$HINDSIGHT_URL/v1/default/banks/$BANK/stats"
fi
probe "docker"          docker info

# --------------------------------------------------------------- git --------
if [ -d "$REPO/.git" ]; then
  if [ -n "$(git -C "$REPO" status --porcelain 2>/dev/null)" ]; then
    warn+=("repo:dirty")
  fi
  stale="$(git -C "$REPO" worktree list 2>/dev/null | grep -c 'dream-' || true)"
  [ "${stale:-0}" -gt 3 ] && warn+=("worktrees:${stale}_stale")
fi

# ------------------------------------------------------------ fixtures ------
# Tamper evidence: the recorded tree hash must still match (IR-2).
if [ -f "$SOMNUS_HOME/fixtures.sha256" ] && command -v sha256sum >/dev/null; then
  recorded="$(cat "$SOMNUS_HOME/fixtures.sha256")"
  actual="$(find "$SOMNUS_HOME/fixtures" -type f -print0 2>/dev/null \
            | sort -z | xargs -0 sha256sum 2>/dev/null | sha256sum | cut -d' ' -f1)"
  [ "$recorded" = "$actual" ] || red+=("fixtures:TAMPERED")
fi

# ------------------------------------------------------------- report -------
if [ "${#red[@]}" -eq 0 ] && [ "${#warn[@]}" -eq 0 ]; then
  printf '{"wakeAgent": false}\n'
  exit 0
fi

printf 'somnus health\n'
[ "${#red[@]}"  -gt 0 ] && printf '  RED  : %s\n' "${red[*]}"
[ "${#warn[@]}" -gt 0 ] && printf '  WARN : %s\n' "${warn[*]}"
printf '  host : load=%s temp=%sC free=%sMB\n' "$load1" "$temp" "$free_mb"
printf '{"wakeAgent": false}\n'
