#!/usr/bin/env bash
set -euo pipefail
HERMES_HOME="${HERMES_HOME:-$HOME}"
SOMNUS_ROOT="${SOMNUS_ROOT:-$HERMES_HOME/hermes-somnus}"
exec "$SOMNUS_ROOT/scripts/hindsight-routing-precheck.sh"
