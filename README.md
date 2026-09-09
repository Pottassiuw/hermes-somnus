# hermes-somnus

**Idle-time self-improvement for [Hermes Agent](https://hermes-agent.nousresearch.com/).**

Somnus is the connective tissue between things Hermes already ships. It is *not*
a new runtime, a new memory system, or a new scheduler — it reuses Hermes's cron
loop, gateway hooks, terminal backends, Curator, and memory-provider protocol,
and adds only the four pieces that are missing:

1. **A zero-token idle gate** — a script-only cron job that emits
   `{"wakeAgent": false}` unless a dream should actually start.
2. **A consolidation operator** — region *rewriting* over your memory bank,
   with an identity invariant that proves the night did not change who the agent is.
3. **An evidence pipeline** — failures → fixtures → hypotheses → sandbox →
   paired A/B verdict → PR.
4. **A ledger and a morning digest** — one file you read with coffee.

Companion document: **`SOMNUS_COMPENDIUM.md`** — the SOTA review and the
architectural reasoning behind every decision below.

---

## The Iron Rules

Every design choice in this repo is downstream of these.

| | Rule |
|---|---|
| **IR-1** | Nothing self-modifies in production. Every mutation lands in a git branch or staging dir. |
| **IR-2** | The generator never sees the acceptance set. `hold/`, `guard/`, `regress/` are not mounted, path-blocked, and hash-verified. |
| **IR-3** | Physical gates, not prose. Rules in a prompt decay measurably; container caps and `pre_tool_call` do not. |
| **IR-4** | Every mutation is reversible and attributed. Content-addressed manifests, append-only ledger, per-entry rollback. |
| **IR-5** | Bounded by budget, not by ambition. Wall clock, tokens, and dollars, with a hard kill. |
| **IR-6** | Consolidation may never touch identity. Manifest hash verified before and after; mismatch aborts and rolls back. |
| **IR-7** | A skill without verification fixtures is a note, not a skill. |
| **IR-8** | Prefer deleting over adding. Smaller memory banks and smaller skill libraries measure *better*, not worse. |

---

## Install

```bash
git clone https://github.com/you/hermes-somnus ~/.hermes/plugins/somnus
cd ~/.hermes/plugins/somnus
pip install -e ".[dev]"

# copy the scripts Hermes cron will call
install -m 755 scripts/somnus-*.sh ~/.hermes/scripts/

# copy the skills
cp -r skills/somnus-* ~/.hermes/skills/

# merge the `somnus:` block into your config
cat config.example.yaml   # then edit ~/.hermes/config.yaml

# validate the plugin before enabling it
hermes plugins doctor ~/.hermes/plugins/somnus --ci
```

Then register the jobs:

```bash
# zero-token gate + health probes, every 15 minutes
hermes cron create "*/15 * * * *" --no-agent --script somnus-gate.sh \
  --deliver local --name somnus-gate
hermes cron create "*/15 * * * *" --no-agent --script somnus-health.sh \
  --deliver telegram --name somnus-health

# the dream cycle itself, gated by the script above
hermes cron create "0 3 * * *" \
  "Run the Somnus dream cycle. Load /somnus-triage, /somnus-consolidate, /somnus-ideate, /somnus-bench in that order. Obey the somnus budgets in ~/.hermes/config.yaml. Abort and roll back on any identity-hash mismatch. Write the digest to ~/.hermes/somnus/reports/." \
  --skill somnus-triage --skill somnus-consolidate \
  --skill somnus-ideate  --skill somnus-bench \
  --script somnus-gate.sh \
  --deliver telegram --name somnus-dream --reasoning-effort high
```

**Somnus stays off until you set `somnus.enabled: true`.** Run Phase 0 of the
roadmap (observability only) for a week first.

---

## The cycle

```
DORMANT ──cron tick──▶ PROBING ──guards fail──▶ {"wakeAgent": false}   ← 0 tokens
                          │ all guards pass + a trigger fired
                          ▼
                      SNAPSHOT  (tar.gz + identity hash recorded)
                          ▼
   TRIAGE ─▶ CONSOLIDATE ─▶ IDEATE ─▶ BUILD ─▶ BENCH ─▶ PROMOTE ─▶ REPORT
      │            │           │        │        │
      └────────────┴───────────┴────────┴────────┴──▶ ABORT ─▶ ROLLBACK
                                (budget · health · identity-hash violation)
```

Budgets, per night, sized for a Raspberry Pi 4B with an external cloud model:
~2 hours wall clock, ≤255 LLM calls, $2–10.

---

## Layout

```
somnus/
├── bench.py         paired A/B: exact McNemar, bootstrap CI, IPT, guard veto
├── config.py        typed config from the `somnus:` block
├── consolidate.py   region rewriting: B* = (B \ R) ∪ S
├── daemon.py        the orchestrator + budget enforcement
├── guards.py        idle / thermal / memory / disk / budget / lock vetoes
├── hooks.py         pre_tool_call permission ceiling + telemetry
├── ideate.py        EV-ranked, falsifiable hypothesis generation
├── report.py        the morning digest
├── sandbox.py       git worktree + ephemeral container
├── state.py         SQLite ledger, identity hash, snapshots, flock
└── schemas/         FailureRecord · DreamHypothesis · EvolvedSkillSpec ·
                     FixtureCase · ConsolidationBatch
scripts/             somnus-gate.sh · somnus-sandbox.sh · somnus-health.sh
skills/              somnus-{triage,consolidate,ideate,bench}/SKILL.md
fixtures/            dev/ · hold/ · guard/ · regress/
tests/               97 tests, no network, no Docker, no Hermes required
```

---

## Fixture partitions

| Partition | Purpose | Visible to the optimizer? | How it is used |
|---|---|---|---|
| `dev/` | Signal for the optimizer to reflect on | **yes** — mounted read-only | not scored |
| `hold/` | The acceptance decision | **no** | scored (McNemar + bootstrap) |
| `guard/` | Safety, permission, refusal behaviour | **no** | **gated** — any regression rejects outright |
| `regress/` | Previously-solved tasks | **no** | scored; grows monotonically |

Three layers keep `hold/`, `guard/` and `regress/` out of reach: they are not
mounted into the container, `pre_tool_call` blocks any path resolving under
them, and the runner hashes the whole fixture tree before and after every phase.

---

## Tests

```bash
python3 -m pytest -q       # 97 passing, ~0.6 s, no external services
shellcheck scripts/*.sh
```

The tests that matter most, and why:

| Test | Asserts |
|---|---|
| `test_guard_regression_is_a_hard_reject_even_with_a_huge_win` | safety cannot be traded for score |
| `test_isomorphic_failure_is_a_hard_reject` | a candidate that learned the identifier, not the rule, is rejected |
| `test_small_sample_is_rejected_even_when_it_wins_every_case` | the n=5 trap |
| `test_dev_partition_does_not_influence_the_verdict` | IR-2 at the statistics layer |
| `test_identity_drift_aborts_and_rolls_back` | IR-6 end to end |
| `test_semantic_layer_changes_do_not_touch_identity` | consolidation is structurally identity-preserving |
| `test_sandbox_never_mounts_holdout_partitions` | IR-2 at the filesystem layer |
| `test_unhealthy_host_skips_before_spending_anything` | a hot Pi costs zero tokens |
| `test_consolidation_that_grows_is_rejected` | IR-8 |
| `test_build_batch_counts_rejects_and_aborts_above_the_health_floor` | silent memory corruption is caught, not absorbed |

---

## Roadmap

| Phase | Deliverable | Acceptance criterion |
|---|---|---|
| 0 | Observability | 7 days of clean telemetry; the gate refuses to wake on every day you actually used the agent |
| 1 | Triage + failure ledger | ≥10 real records, correctly clustered; ≥3 converted into reproducing fixtures |
| 2 | Bench harness | Correctly **rejects** a planted bad candidate *and* **accepts** a known-good fix |
| 3 | Sandbox + build | Adversarial test: reading `hold/`, writing `~/.hermes/skills/`, and reaching the network are all blocked and ledgered |
| 4 | Consolidation | One pass that shrinks the bank while holding fixture scores, identity hash byte-identical |
| 5 | Full loop | One autonomous night producing a PR you merge unedited — and one honest rejection with a legible reason |
| 6 | Hardening | 3 months continuous, zero unexplained regressions, `size_delta` flat or negative |

Do not start phase N+1 until phase N's criterion is met.

---

## What this deliberately does not do

- **No weight updates.** Σ-only by design: prompts, memory, tools, skills, control logic.
- **No local LLM fallback on a Pi 4B.** Plausible garbage is worse than an honest outage.
- **No auto-merge.** The agent proposes; a gate outside the model disposes.
- **No Curator replacement.** Hermes's skill lifecycle already has a better audit
  trail than most people would write in a month. Somnus feeds it.

MIT.


## Domain-scoped memory operations

Hermes's normal Hindsight retain uses the configured fixed bank. Somnus therefore
keeps cross-bank routing explicit and auditable:

- `somnus/memory_router.py` classifies only with an allowlisted vocabulary;
- credentials, bearer values and connection strings are redacted before transport;
- `RouteLedger` records source/target/content hashes in `somnus.db`;
- `scripts/memory-route.py` is dry-run by default;
- `scripts/memory-route-apply.sh` is the explicit write path;
- source invalidation happens only after a target read-back confirms the routed
  document; failures leave the source valid for retry;
- observation facts and ambiguous facts are skipped, not guessed.

The real Hindsight list endpoint is `/v1/default/banks/<bank>/memories/list`.
The retain payload uses `items`, `context`, `document_id`, and synchronous
processing so the verification gate can read the result immediately.

## Maintenance and Reflect

- `scripts/somnus-maintenance.py` deletes only expired rows from the explicit
  `volatile_records` table, runs SQLite checkpoint/optimization, and performs
  optional `VACUUM` only after a restricted backup.
- `scripts/somnus-reflect.py` calls the bank-scoped Reflect endpoint with a
  bounded budget, facts enabled, tool calls disabled, mental models excluded,
  and a structured schema. It is read-only; it never invalidates memories.
- `scripts/hindsight-routing-precheck.sh` emits a stable stats fingerprint for
  Hermes's zero-token monitor. It omits timestamps, IDs, memory text and secrets.
- `scripts/helios-static-audit.py` performs deterministic AST checks for bare
  exceptions, duplicate functions and credential-like assignments without
  printing matched values.
- `scripts/helios-smoke.sh` runs backend/frontend checks and API GET smoke tests.
  The synchronization POST requires `HELIOS_SMOKE_ALLOW_MUTATION=1`.

`config.example.yaml` keeps `routing.apply`, `reflect.enabled`, and
`maintenance.enabled` disabled by default. `scripts/somnus-register-cron.sh`
prints activation commands but intentionally does not execute them.
