---
name: somnus-bench
description: Decide whether a candidate change is actually better, using paired fixtures, exact McNemar, bootstrap confidence intervals, isomorphic perturbation testing, and a zero-tolerance guardrail veto. Use before promoting any skill, prompt or tool change.
version: 1.0.0
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Somnus, Testing]
    category: self-improvement
    requires_toolsets: [terminal, code_execution]
---

# Somnus — Acceptance Harness

## When to Use

- Before promoting **any** self-authored change: skill, skill patch, prompt
  section, tool description, script.
- When you want to know whether last week's "improvement" actually helped.
- **Not** for exploratory measurement. This skill produces a verdict, and a
  verdict you did not intend to honour is worse than no verdict.

## The claim you are entitled to make

| Claim | Evidence needed | Realistic? |
|---|---|---|
| "Better on this fixture suite" | Gates A+B | ✅ this is what you get |
| "Better on this task distribution" | fixtures sampled from real sessions | ✅ with discipline |
| "Better in general" | — | ❌ never write this |
| **"Not worse on things I care about"** | `guard/` + `regress/` partitions | ✅ **the most valuable claim, and the cheapest** |

Optimize for the fourth row before the first.

## Procedure

1. **Confirm falsifiability.** Run the candidate's fixtures against the current
   baseline. If they do not fail, the hypothesis is unfalsifiable — reject it
   now, before spending build tokens. This step kills most freeform hypotheses,
   which is exactly what it is for.

2. **Gate A — deterministic, no LLM, no network.** Schema valid; size caps
   (SKILL.md ≤ 15 KB, tool descriptions ≤ 500 chars); lint; security scan; the
   diff touches only paths in the declared write-set; **identity manifest hash
   unchanged**. 80% of candidates die here at zero cost. Order matters: never
   spend an LLM call on a candidate that fails a size check.

3. **Gate B — paired A/B on the hold-out partitions.**
   - Same fixture, same seed, baseline vs candidate. Pairing removes most
     variance and buys enormous power at the same n.
   - `repeats ≥ 3` per case; `min_pairs ≥ 20`.
   - **Vetoes first, before any statistic:**
     - any `guard/` regression → hard reject
     - any isomorphic-variant failure on a passing base case → hard reject
       (the candidate learned the identifier, not the rule)
   - Then: directional win → exact McNemar at α=0.01 → effect ≥ pre-registered
     MDE → bootstrap CI strictly above zero.

4. **Verify the fixture manifest.** Re-hash the fixture tree. A mismatch means
   something inside the loop edited the evidence, which invalidates the entire
   run — abort, do not reason about it.

5. **Require replication.** An accepted candidate re-runs on a second
   independent night before promotion. Testing 12 candidates a night at α=0.05
   gives a **~46% chance of at least one false acceptance every night**
   (1 − 0.95¹²); replication is cheaper to implement and far more legible in a
   PR body than FDR bookkeeping.

6. **Bundle the evidence.** Diff, verdict JSON, effect + CI + p, token delta,
   and the failing-baseline trace. This is the PR body.

## Pitfalls

- **Never accept on n=5.** Four-of-five happens ~19% of the time by chance —
  roughly 69 spurious "improvements" a year if you run nightly, each one
  permanently degrading your scaffold.
- **Never let an LLM judge be the sole gate.** Reference-free judges are hackable
  by the system they score: optimization drifts toward persuasiveness, not
  correctness. A judge may rank and explain; something deterministic must decide.
- **Never score the `dev/` partition into the verdict.** It is the optimizer's
  own playground. If it counts, it stops being evidence.
- **Never grant the sandbox read access to `hold/`, `guard/` or `regress/`.**
  Three layers: don't mount them, block the path in `pre_tool_call`, and hash the
  tree before and after.
- **Beware silent provider drift.** A vendor swapping weights behind a stable
  model name will move your baseline underneath you. Pin the model string, and
  run a fixed canary set daily so you can see the step change.

## Verification

```bash
# The harness must reject a deliberately-bad candidate...
python3 -m pytest tests/test_bench.py::test_guard_regression_is_a_hard_reject_even_with_a_huge_win -q

# ...and accept a known-good one. Test BOTH directions: a harness that only
# ever accepts is indistinguishable from having no harness at all.
python3 -m pytest tests/test_bench.py::test_clear_win_on_sufficient_pairs_is_accepted -q

# Fixture tamper evidence is live
python3 -c "
from somnus.bench import fixture_tree_hash
print(fixture_tree_hash('$HOME/.hermes/somnus/fixtures'))"
```
