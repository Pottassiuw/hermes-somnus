#!/usr/bin/env bash
#
# somnus-sandbox.sh <hypothesis_id> <command...>
#
# Layer 2 (git worktree) + Layer 1 (ephemeral container). Every terminal command
# issued during a dream cycle is rewritten through this wrapper by the plugin's
# pre_tool_call hook, so there is no unsandboxed path out of a dream.
#
# What is deliberately NOT mounted: fixtures/{hold,guard,regress}. That absence
# is IR-2's cheapest and most reliable layer — the agent cannot overfit to
# evidence it cannot read.
#
set -euo pipefail

if [ "$#" -lt 2 ]; then
  echo "usage: somnus-sandbox.sh <hypothesis_id> <command...>" >&2
  exit 64
fi

HID="$1"; shift

HERMES_HOME="${HERMES_HOME:-$HOME/.hermes}"
SOMNUS_HOME="$HERMES_HOME/somnus"
REPO="${SOMNUS_REPO:-$HERMES_HOME/hermes-agent}"
WT="$SOMNUS_HOME/worktrees/dream-$HID"
IMAGE="${SOMNUS_IMAGE:-python:3.11-slim}"
MEM_MB="${SOMNUS_MEM_MB:-512}"
CPUS="${SOMNUS_CPUS:-1.0}"
PIDS="${SOMNUS_PIDS:-256}"
TIMEOUT_S="${SOMNUS_TIMEOUT_S:-900}"
NETWORK="${SOMNUS_NETWORK:-none}"     # none | somnus-egress (LLM endpoint only)

mkdir -p "$SOMNUS_HOME/worktrees" "$SOMNUS_HOME/fixtures/dev"

# ------------------------------------------------ layer 2: git worktree ----
if [ ! -d "$WT" ]; then
  if [ ! -d "$REPO/.git" ]; then
    echo "somnus-sandbox: $REPO is not a git repository" >&2
    exit 65
  fi
  git -C "$REPO" worktree add -b "somnus/dream-$HID" "$WT" HEAD >&2
fi

# ------------------------------------------- layer 1: ephemeral container ----
exec docker run --rm \
  --name "somnus-$HID" \
  --network "$NETWORK" \
  --cap-drop ALL \
  --security-opt no-new-privileges \
  --read-only \
  --tmpfs /tmp:rw,noexec,nosuid,size=128m \
  --pids-limit "$PIDS" \
  --memory "${MEM_MB}m" \
  --memory-swap "${MEM_MB}m" \
  --cpus "$CPUS" \
  --user "$(id -u):$(id -g)" \
  -v "$WT:/work:rw" \
  -v "$SOMNUS_HOME/fixtures/dev:/fixtures/dev:ro" \
  -w /work \
  -e HOME=/tmp \
  -e SOMNUS_HYPOTHESIS="$HID" \
  "$IMAGE" \
  timeout "$TIMEOUT_S" "$@"
