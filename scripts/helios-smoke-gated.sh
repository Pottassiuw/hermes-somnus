#!/usr/bin/env bash
# Run the smoke suite only after the deterministic SHA gate changes.
set -u
SCRIPT_DIR="$(CDPATH='' cd -- "$(dirname -- "$0")" && pwd)"
precheck="$("$SCRIPT_DIR"/helios-precheck.sh)"
case "$precheck" in
  *'"wakeAgent": true'*)
    exec "$SCRIPT_DIR/helios-smoke.sh"
    ;;
  *)
    exit 0
    ;;
esac
