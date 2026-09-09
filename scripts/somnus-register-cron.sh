#!/usr/bin/env bash
# Print the approved scheduler commands; do not execute automatically.
set -euo pipefail
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
printf '%s
'   "hermes cron create '*/15 * * * *' --no-agent --script $SCRIPT_DIR/somnus-gate.sh --deliver local --name somnus-gate"   "hermes cron create '*/15 * * * *' --no-agent --script $SCRIPT_DIR/somnus-health.sh --deliver local --name somnus-health"   "hermes cron create '*/30 * * * *' --no-agent --script $SCRIPT_DIR/memory-route-apply.sh --deliver local --name hindsight-memory-route"   "hermes cron create '0 3 * * *' --no-agent --script $SCRIPT_DIR/somnus-maintenance.py --deliver local --name somnus-maintenance"   "hermes cron create '0 4 * * 1' --script $SCRIPT_DIR/hindsight-weekly-reflect.sh --deliver local --name hindsight-weekly-reflect"   "hermes cron create '0 */6 * * *' --no-agent --script $SCRIPT_DIR/coffee-healthcheck.sh --deliver telegram --name coffee-healthcheck"
printf '%s
' 'Activation is intentionally separate and requires the reviewed PR to be merged.'
