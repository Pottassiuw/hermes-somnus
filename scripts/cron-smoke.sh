#!/usr/bin/env bash
set -u
HERMES_HOME="${HERMES_HOME:-$HOME}"
SOMNUS_ROOT="${SOMNUS_ROOT:-$HERMES_HOME/hermes-somnus}"
export HELIOS_REPO="${HELIOS_REPO:-$HERMES_HOME/helios-audit-cron}"
exec "$SOMNUS_ROOT/scripts/helios-smoke-gated.sh"
