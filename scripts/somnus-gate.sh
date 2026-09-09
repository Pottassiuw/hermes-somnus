#!/usr/bin/env bash
#
# somnus-gate.sh — the zero-token idle gate.
#
# Registered as a Hermes script-only cron job:
#
#   hermes cron create "*/15 * * * *" --no-agent \
#     --script somnus-gate.sh --deliver local --name somnus-gate
#
# Hermes runs a job's --script BEFORE the agent. If the last line of stdout is
# {"wakeAgent": false} the LLM is never invoked, so polling costs nothing at all.
# Guards are a conjunction; triggers are a disjunction. Both must be satisfied.
#
set -euo pipefail

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SOMNUS_HOME="$HERMES_HOME/somnus"
LOCK="$SOMNUS_HOME/dream.lock"
STATE="$SOMNUS_HOME/somnus.db"

# Thresholds (keep in sync with config.yaml `somnus:`)
MIN_IDLE_MIN="${SOMNUS_MIN_IDLE_MIN:-90}"
MAX_LOAD1="${SOMNUS_MAX_LOAD1:-2.0}"
MAX_TEMP_C="${SOMNUS_MAX_TEMP_C:-70}"
MIN_FREE_MB="${SOMNUS_MIN_FREE_MB:-700}"
MIN_FREE_DISK_PCT="${SOMNUS_MIN_FREE_DISK_PCT:-15}"
DAILY_CAP_USD="${SOMNUS_DAILY_CAP_USD:-5.0}"
BACKLOG_TURNS="${SOMNUS_BACKLOG_TURNS:-200}"
OPEN_FAILURES="${SOMNUS_OPEN_FAILURES:-3}"
SCHEDULED_HOUR="${SOMNUS_SCHEDULED_HOUR:-3}"

mkdir -p "$SOMNUS_HOME"

no_wake() {
  printf 'somnus: %s\n' "$1"
  printf '{"wakeAgent": false}\n'
  exit 0
}

q() {  # query somnus.db, tolerating a missing DB on first run
  sqlite3 "$STATE" "$1" 2>/dev/null || printf '%s' "$2"
}

# ---------------------------------------------------------------- guards ----
if [ -e "$LOCK" ]; then
  pid="$(cat "$LOCK" 2>/dev/null || echo 0)"
  if [ "$pid" -gt 0 ] 2>/dev/null && kill -0 "$pid" 2>/dev/null; then
    no_wake "lock held by pid $pid (curator or another dream is running)"
  fi
  rm -f "$LOCK"   # stale lock from a crashed run
fi

load1="$(awk '{print $1}' /proc/loadavg 2>/dev/null || echo 0)"
awk -v l="$load1" -v m="$MAX_LOAD1" 'BEGIN{exit !(l < m)}' \
  || no_wake "load1=$load1 >= $MAX_LOAD1"

temp_raw="$(cat /sys/class/thermal/thermal_zone0/temp 2>/dev/null || echo 0)"
temp=$(( temp_raw / 1000 ))
[ "$temp" -lt "$MAX_TEMP_C" ] || no_wake "temp=${temp}C >= ${MAX_TEMP_C}C (Pi is throttling)"

free_mb="$(awk '/MemAvailable/{print int($2/1024)}' /proc/meminfo 2>/dev/null || echo 99999)"
[ "$free_mb" -gt "$MIN_FREE_MB" ] || no_wake "free_mem=${free_mb}MB <= ${MIN_FREE_MB}MB"

used_pct="$(df --output=pcent "$SOMNUS_HOME" 2>/dev/null | tail -1 | tr -dc '0-9' || echo 0)"
free_pct=$(( 100 - ${used_pct:-0} ))
[ "$free_pct" -gt "$MIN_FREE_DISK_PCT" ] || no_wake "free_disk=${free_pct}% <= ${MIN_FREE_DISK_PCT}%"

spent="$(q "SELECT COALESCE(SUM(usd),0) FROM runs WHERE started_at > datetime('now','-1 day');" 0)"
awk -v s="${spent:-0}" -v c="$DAILY_CAP_USD" 'BEGIN{exit !(s < c)}' \
  || no_wake "daily budget exhausted (\$$spent >= \$$DAILY_CAP_USD)"

idle_min="$(q "SELECT CAST((julianday('now') - julianday(MAX(ts))) * 1440 AS INT) FROM activity;" 9999)"
idle_min="${idle_min:-9999}"
[ "$idle_min" -ge "$MIN_IDLE_MIN" ] || no_wake "user active ${idle_min}m ago (< ${MIN_IDLE_MIN}m)"

# -------------------------------------------------------------- triggers ----
backlog="$(q "SELECT COUNT(*) FROM turns WHERE consolidated = 0;" 0)"
open_fail="$(q "SELECT COUNT(DISTINCT signature) FROM failures WHERE status = 'open';" 0)"
hour="$(date +%-H)"

reason=""
[ "$hour" -eq "$SCHEDULED_HOUR" ] && reason="scheduled_window"
[ "${backlog:-0}"   -ge "$BACKLOG_TURNS"  ] && reason="${reason:+$reason,}episodic_backlog=$backlog"
[ "${open_fail:-0}" -ge "$OPEN_FAILURES"  ] && reason="${reason:+$reason,}open_failures=$open_fail"

[ -n "$reason" ] || no_wake "no trigger (backlog=$backlog open_failures=$open_fail hour=$hour)"

# ------------------------------------------------------------------ wake ----
cat <<EOF
somnus: dream cycle authorized
  triggers : $reason
  backlog  : $backlog unconsolidated turns
  failures : $open_fail open signatures
  host     : idle=${idle_min}m load=$load1 temp=${temp}C free=${free_mb}MB disk=${free_pct}%
  budget   : \$$spent spent in the last 24h (cap \$$DAILY_CAP_USD)
EOF
printf '{"wakeAgent": true}\n'
