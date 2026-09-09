---
name: somnus-ideate
description: Generate falsifiable improvement hypotheses ranked by expected value, sourcing from open failures, counterfactual repairs, repetition patterns and forced cross-domain recombination. Use as phase 3 of a dream cycle.
version: 1.0.0
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Somnus, Planning]
    category: self-improvement
    requires_toolsets: [terminal, memory]
---

# Somnus — Ideation

## When to Use

Phase 3 of a dream cycle, after triage and consolidation. Also useful on demand
when you have a backlog of open failures and want them turned into a queue of
things a sandbox can actually attempt.

## Sources, ranked by measured expected value

| # | Source | Why it ranks here |
|---|---|---|
| 1 | **Open failures** | Concrete reproduction, known-bad outcome, the fixture writes itself |
| 2 | **Counterfactual repairs** | A localized causal answer becomes a targeted patch |
| 3 | **Contract drift** | An external dependency changed shape; the repair is mechanical |
| 4 | **Repetition patterns** | A ≥5-call sequence recurring across sessions is a skill waiting to exist |
| 5 | **Cross-domain recombination** | The *only* ideation mode with a positive measured effect — but only when the paired regions are genuinely distant |
| 6 | **Efficiency deltas** | Outlier token/latency cost versus that task's own historical median |
| 7 | **Freeform** | Lowest EV. **Cap at 1 per night** or it floods the queue with plausible, unfalsifiable prose |

## The counter-intuitive rule

For cross-domain hypotheses, **pair the most distant memory regions, not the
most similar ones.** This inverts the usual retrieval instinct on purpose:

- Within-domain consolidation measures **null** (−1.8 ± 4.4 pp across three base
  models). Paraphrasing yesterday's logs back at yourself buys nothing.
- Cross-domain recombination measures **+5.64 ± 2.31 pp** (p=0.0055), and the
  novel bridges sit at *greater* embedding distance than within-domain pairs.

So: sample pairs from the far tail. A cross-domain hypothesis whose regions are
close together scores zero and is dropped before it costs anything.

## Procedure

1. **Dequeue open failures** with `occurrences ≥ 2`, newest first.
2. **For each**, write the hypothesis in the mandatory form:
   `IF <change> THEN <metric> improves BECAUSE <mechanism>`.
   A hypothesis without a `BECAUSE` is a wish.
3. **Attach a fixture spec** — at least one case, with `baseline_must_fail: true`
   and ≥2 isomorphic variants. No fixture, no hypothesis.
4. **Declare the write-set.** Enumerate the paths the change may touch. A
   denylist is a losing game; an allowlist is a solved one. Anything outside it
   is a hard reject at Gate A.
5. **Decide skill vs. patch.** Compute the crystallization score. If
   `overlap ≥ 0.75` against an existing skill description, emit a **skill_patch**
   hypothesis instead of a new skill — retrieval precision falls from 29.6% at
   pool size 5 to 3.3% at pool size 100, so a near-duplicate skill has negative
   expected value.
6. **Rank and truncate** to `ideate_top_k`. A night that attempts five
   hypotheses well beats one that attempts twenty badly.
7. **Set risk.** `high` (new skill, new tool, config, network, credentials)
   always requires human approval before build. There is no auto-promote path
   for `high`.

## Pitfalls

- **Do not generate hypotheses for failures you cannot reproduce.** Reproduction
  is the ticket price.
- **Do not let one failure spawn five hypotheses.** Pick the one with the
  clearest mechanism; if it fails, the others are still in the ledger tomorrow.
- **Do not propose changes to the identity manifest.** Out of scope, by
  construction, permanently.
- **Do not use similarity search to build cross-domain pairs.** It reproduces
  the null result exactly.

## Verification

```bash
# Every queued hypothesis validates, which enforces >=1 fixture and
# baseline_must_fail: true
python3 - <<'PY'
import json, sqlite3, jsonschema, importlib.resources as res
from somnus.config import load

cfg = load()
schema = json.loads(res.files("somnus").joinpath(
    "schemas/dream_hypothesis.schema.json").read_text())
db = sqlite3.connect(cfg.db_path)
rows = db.execute("SELECT payload FROM hypotheses WHERE status='queued'").fetchall()
for (payload,) in rows:
    jsonschema.validate(json.loads(payload), schema)
print(f"{len(rows)} queued hypotheses, all valid")
PY

# The ranker drops near cross-domain pairs before they cost anything
python3 -m pytest \
  tests/test_guards_and_ideate.py::test_near_cross_domain_pairs_score_zero_and_are_dropped -q
```
