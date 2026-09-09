#!/usr/bin/env bash
set -u
HERMES_HOME="${HERMES_HOME:-$HOME}"
SOMNUS_ROOT="${SOMNUS_ROOT:-$HERMES_HOME/hermes-somnus}"
exec "$SOMNUS_ROOT/scripts/coffee-healthcheck.sh"
