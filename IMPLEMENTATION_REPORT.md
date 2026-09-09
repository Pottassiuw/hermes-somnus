# Somnus memory automation — implementation report

## Scope

This branch implements deterministic multi-bank routing, conservative SQLite maintenance, structured read-only Reflect, Helios health/smoke gates, and scheduler wrappers.

## Routing policy

- `repo-edp-helios`: Helios code, PRs, CI, bugs, validation and decisions.
- `ops-infra`: Docker, Raspberry Pi, network, tunnels, Hindsight/Somnus operations.
- `agent-hermes`: governance, profiles and general Hermes context.

The router defaults to dry-run. Production routing requires the explicit `--apply` flag and `SOMNUS_ROUTER_APPLY=1`. It writes to the target, reads the target back, records an SQLite ledger, and only then invalidates the source.

## Verified evidence

- Local Somnus suite: 97 passed.
- Local Python compilation: passed.
- Local Bash syntax: passed.
- Local ShellCheck: clean.
- Container compilation and Bash syntax as user `hermes`: passed.
- Container Hindsight dry-run: 710 facts scanned, 262 planned, 0 writes, 0 errors, batch size 25.
- Container stats monitor: two consecutive outputs byte-identical.
- Container Reflect: real read-only structured response, IDs omitted, mental models empty, no write.
- Container maintenance: temporary SQLite run completed with zero volatile records removed and no errors.
- COFFEE healthcheck: explicit `skipped` when endpoint is not configured; never reports false health.

## Scheduler jobs

Existing job preserved:

- `helios-auditoria-noturna` (`0f5031105309`)

New jobs verified by scheduler read-back:

- `hindsight-memory-route` (`fedf6a98da66`) — every 30m.
- `somnus-memory-maintenance` (`3e679be6fe31`) — daily 03:30.
- `hindsight-stats-health` (`92ea8f7985bf`) — every 15m.
- `coffee-healthcheck` (`7ff67c5664c2`) — every 6h.
- `helios-smoke-pos-merge` (`572982d014a2`) — every 15m, SHA-gated.
- `hindsight-weekly-reflect` (`01411427fd8f`) — Mondays 04:00.

All new jobs use `no_agent=true`; success delivery is local and failure delivery is Telegram. The dual-write job is the only scheduled job with intentional memory mutation, and it is bounded to batches of 25 with read-back verification.

## Known blockers

- The scaffold arrived without a Git remote, so this branch can be committed locally but cannot be pushed or opened as a PR until an upstream repository/remote is supplied.
- Node/npm are unavailable in the current host/container, so the Helios frontend build cannot be independently executed here.
- The COFFEE endpoint is not configured in the container profile; the healthcheck reports this explicitly.


## Scheduler path correction

The scheduler resolves relative script names under `/opt/data/scripts`, not `/opt/data/.hermes/scripts`. The first manual fires exposed this with `Script not found`; deployment wrappers were then copied to `/opt/data/scripts`, syntax-checked, and the same jobs were fired again for verification. No job definition was recreated or duplicated.
