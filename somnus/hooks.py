"""
somnus.hooks — the permission ceiling and the telemetry tap.

Two responsibilities:

  1. `pre_tool_call` is the PHYSICAL gate (IR-3). Prompt rules decay measurably
     (rule adherence 94% -> 61% across sessions, arXiv:2606.08162); a hook that
     Hermes fails CLOSED on timeout does not.
  2. `on_session_end` / `post_tool_call` feed the activity and turn tables that
     the zero-token cron gate reads to decide whether to dream tonight.

Registered from `somnus/__init__.py::register(ctx)` via `ctx.register_hook(...)`.
"""

from __future__ import annotations

import os
import shlex
from pathlib import Path

from . import config as _config
from . import state as _state

# --------------------------------------------------------------------------- #
# Policy tables
# --------------------------------------------------------------------------- #

#: Reading any of these from inside a dream session breaks IR-2.
FORBIDDEN_READ_FRAGMENTS = (
    "somnus/fixtures/hold",
    "somnus/fixtures/guard",
    "somnus/fixtures/regress",
)

#: Writing any of these from inside a dream session breaks IR-1.
FORBIDDEN_WRITE_PREFIXES = (
    "~/.hermes/skills/",
    "~/.hermes/memories/",
    "~/.hermes/config.yaml",
    "~/.hermes/cron/",
    "~/.hermes/hooks/",
    "~/.hermes/plugins/",
)

#: Commands that are never appropriate inside a sandboxed experiment.
FORBIDDEN_COMMAND_FRAGMENTS = (
    "git push",
    "git remote add",
    "crontab",
    "systemctl",
    "docker rm",
    "docker kill",
    "rm -rf /",
    "curl http",       # network egress belongs to the sandbox policy, not ad-hoc calls
    "wget http",
    "ssh ",
    "scp ",
)

WRITE_TOOLS = {"patch", "write_file", "skill_manage", "memory"}


def _expand(p: str) -> str:
    return os.path.realpath(os.path.expanduser(p)) if p else ""


def _is_dream_session(task_id: str, marker_dir: Path) -> bool:
    """
    A dream session is marked by a sentinel file written by the orchestrator.

    A file rather than an env var, deliberately: the gate must hold for tools
    dispatched from hooks and subagents that do not inherit the environment.
    """
    if not task_id:
        return False
    return (marker_dir / f"{task_id}.dream").exists()


# --------------------------------------------------------------------------- #
# The ceiling
# --------------------------------------------------------------------------- #

def make_pre_tool_call(cfg: _config.SomnusConfig):
    marker_dir = cfg.home_path / "sessions"

    def pre_tool_call(tool_name: str, args: dict, task_id: str = "", **_kw):
        if not _is_dream_session(task_id, marker_dir):
            return None  # outside a dream cycle Somnus does not constrain anything

        path = args.get("path") or args.get("file_path") or args.get("target") or ""
        real = _expand(str(path))

        if real and any(frag in real for frag in FORBIDDEN_READ_FRAGMENTS):
            return {
                "action": "block",
                "message": ("Hold-out, guard and regression fixtures are not readable "
                            "during a dream cycle (IR-2). The bench runner evaluates "
                            "them outside the sandbox and returns only a verdict."),
                "rule_key": "somnus.ir2.holdout",
            }

        if tool_name in WRITE_TOOLS and real:
            for prefix in FORBIDDEN_WRITE_PREFIXES:
                if real.startswith(_expand(prefix)):
                    return {
                        "action": "block",
                        "message": ("Production paths are read-only during a dream cycle "
                                    "(IR-1). Write into the worktree; promotion happens "
                                    "at Gate C, outside this session."),
                        "rule_key": "somnus.ir1.production",
                    }

        if tool_name == "terminal":
            cmd = str(args.get("command", ""))
            low = cmd.lower()
            for frag in FORBIDDEN_COMMAND_FRAGMENTS:
                if frag in low:
                    return {
                        "action": "block",
                        "message": f"Blocked in dream sandbox: {frag!r}",
                        "rule_key": "somnus.ir3.command",
                    }
            wrapper = _expand("~/.hermes/scripts/somnus-sandbox.sh")
            if not cmd.startswith(wrapper) and "somnus-sandbox.sh" not in cmd:
                return {
                    "action": "modify",
                    "args": {"command": f"{wrapper} {shlex.quote(task_id)} bash -lc {shlex.quote(cmd)}"},
                }
        return None

    return pre_tool_call


# --------------------------------------------------------------------------- #
# Telemetry
# --------------------------------------------------------------------------- #

def make_session_hooks(cfg: _config.SomnusConfig):
    """
    Returns (on_session_start, on_session_end, post_tool_call).

    These write only to somnus.db. They must be cheap and must never raise —
    Hermes catches hook errors, but a hook that throws on every turn is noise
    that will train you to ignore your own logs.
    """
    store = _state.Store(cfg.db_path)

    def on_session_start(session_id: str = "", **_kw):
        try:
            store.note_activity("session_start", session_id)
        except Exception:
            pass

    def on_session_end(session_id: str = "", **_kw):
        try:
            store.note_activity("session_end", session_id)
        except Exception:
            pass

    def post_tool_call(tool_name: str = "", **_kw):
        try:
            store.note_activity("tool_call")
        except Exception:
            pass

    return on_session_start, on_session_end, post_tool_call
