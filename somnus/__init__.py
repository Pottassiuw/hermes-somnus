"""
hermes-somnus — idle-time self-improvement for Hermes Agent.

Somnus is a Hermes *plugin*, not a daemon. It reuses Hermes's cron scheduler,
gateway hooks, terminal backends, Curator and memory-provider protocol, and adds
only the connective tissue: an idle gate, a consolidation operator, an evidence
pipeline, and a ledger.

Entry point: `register(ctx)`, called once at startup by Hermes's plugin loader.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["register", "__version__"]

from . import bench, config, consolidate, daemon, guards, hooks, ideate, report, sandbox, state


def register(ctx) -> None:  # pragma: no cover - exercised by Hermes at runtime
    """
    Wire Somnus into a running Hermes.

    Registers, in order:
      * the permission ceiling (`pre_tool_call`) — the physical gate of IR-3
      * session telemetry, which feeds the zero-token cron gate
      * a `somnus` tool so the agent can inspect (never bypass) its own state
      * a `/somnus` slash command and a `hermes somnus` CLI group
    """
    cfg = config.load(ctx.get_config("config_path", default="~/.hermes/config.yaml"))

    ctx.register_hook("pre_tool_call", hooks.make_pre_tool_call(cfg))

    on_start, on_end, post_tool = hooks.make_session_hooks(cfg)
    ctx.register_hook("on_session_start", on_start)
    ctx.register_hook("on_session_end", on_end)
    ctx.register_hook("post_tool_call", post_tool)

    ctx.register_tool(
        name="somnus",
        toolset="somnus",
        schema={
            "type": "object",
            "properties": {
                "action": {
                    "type": "string",
                    "enum": ["status", "failures", "hypotheses", "digest", "ledger"],
                    "description": "Read-only introspection of the dream ledger.",
                },
                "limit": {"type": "integer", "default": 20},
            },
            "required": ["action"],
        },
        handler=_make_tool(cfg),
    )

    ctx.register_command("somnus", _make_command(cfg),
                         description="Inspect Somnus state, or run a dream cycle manually.")


def _make_tool(cfg):
    import json

    def handler(args: dict, **_kw) -> str:
        action = args.get("action", "status")
        limit = int(args.get("limit", 20))
        try:
            store = state.Store(cfg.db_path)
            if action == "failures":
                return json.dumps(store.open_failures(limit), indent=2)
            if action == "ledger":
                return json.dumps(state.Ledger(cfg.ledger_path).read(limit), indent=2)
            if action == "digest":
                latest = sorted((cfg.home_path / "reports").glob("*/DIGEST.md"))
                return latest[-1].read_text(encoding="utf-8") if latest else "no digest yet"
            return json.dumps({
                "enabled": cfg.enabled,
                "idle_minutes": round(store.idle_minutes(), 1),
                "unconsolidated_turns": store.unconsolidated_turns(),
                "open_failure_signatures": store.open_failure_signatures(),
                "spend_today_usd": round(store.spend_today(), 2),
                "lock_held": cfg.lock_path.exists(),
            }, indent=2)
        except Exception as exc:
            return json.dumps({"error": str(exc)})

    return handler


def _make_command(cfg):
    def command(args: str = "", **_kw) -> str:
        return (
            "Somnus commands:\n"
            "  /somnus status      — idle time, backlog, open failures, budget\n"
            "  /somnus failures    — open failure records\n"
            "  /somnus digest      — last night's report\n"
            "  /somnus ledger      — recent mutations\n"
            "\n"
            "Dream cycles are started by the cron job `somnus-dream`, gated by\n"
            "`somnus-gate.sh`. Run one now with: hermes cron run somnus-dream"
        )

    return command
