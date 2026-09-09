#!/usr/bin/env bash
# Deterministic gate for the Helios audit. No LLM is invoked here.
set -euo pipefail
HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
REPO="${HELIOS_REPO:-$HERMES_HOME/helios-audit-cron}"
STATE="${HELIOS_PRECHECK_STATE:-$HERMES_HOME/somnus/helios-precheck.state}"
mkdir -p "$(dirname "$STATE")"
if [ ! -d "$REPO/.git" ]; then
  printf 'helios precheck: repository unavailable\n'
  printf '{"wakeAgent": false, "reason": "repo_unavailable"}\n'
  exit 1
fi
sha="$(git -C "$REPO" rev-parse origin/develop 2>/dev/null || git -C "$REPO" rev-parse HEAD)"
branch="$(git -C "$REPO" branch --show-current 2>/dev/null || printf 'unknown')"
status_count="$(git -C "$REPO" status --porcelain 2>/dev/null | wc -l | tr -d ' ')"
fingerprint="${sha}|${branch}|${status_count}"
previous=""
[ -f "$STATE" ] && previous="$(tr -d '\n' < "$STATE")"
printf '%s' "$fingerprint" > "$STATE"
if [ "$fingerprint" = "$previous" ]; then
  printf '{"wakeAgent": false, "reason": "unchanged"}\n'
else
  printf 'helios precheck: change detected sha=%s branch=%s dirty_files=%s\n' "$sha" "$branch" "$status_count"
  printf '{"wakeAgent": true, "sha": "%s", "branch": "%s"}\n' "$sha" "$branch"
fi
