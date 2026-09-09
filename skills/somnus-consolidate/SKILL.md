---
name: somnus-consolidate
description: Rewrite a region of semantic memory as a complete replacement set — abstracting, deduplicating, resolving contradictions and forgetting by omission — while proving the agent's identity manifest is byte-identical before and after.
version: 1.0.0
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Somnus, Memory]
    category: self-improvement
    requires_toolsets: [terminal, memory]
---

# Somnus — Memory Consolidation

## When to Use

- Phase 2 of a dream cycle, after triage.
- When `somnus(action="status")` shows the bank growing week over week while
  fixture scores stay flat — that is an archivist, not a consolidator.
- After a large import or a long project push, when the semantic layer has
  accumulated many near-duplicate facts about one entity.

## The one idea that matters

**You are not editing entries. You are replacing a region.**

```
B* = (B \ R) ∪ S
```

Select a region `R`, treat it as **read-only evidence**, and emit a complete
replacement set `S`. Anything you do not carry forward is deleted — and that is
the point. With replacement semantics, abstraction, deduplication, contradiction
resolution and forgetting are all *default behaviours of the operator* rather
than four separate features you have to build and sequence.

The published result for this operator is higher task success with a **12–400×
smaller** memory bank. If your rewrite makes the bank bigger, you have not
consolidated; you have transcribed.

## Quick Reference

| Step | Call |
|---|---|
| Bank stats | `GET /v1/default/banks/<bank>/stats` |
| List region | `GET /v1/default/banks/<bank>/memories?...` |
| Synthesize | `POST /v1/default/banks/<bank>/reflect` |
| Curate a unit | `PATCH /v1/default/banks/<bank>/memories/<id>` |
| Reset derived knowledge | `DELETE /v1/default/banks/<bank>/observations` |
| Identity hash | `python3 -c "from somnus.state import identity_hash; ..."` |

## Procedure

1. **Record the identity hash first.** Hash the manifest paths before touching
   anything. If it differs at the end of the phase, abort and roll back — no
   exceptions, no "probably fine".

2. **Select a region.** `newly_written`, `recently_retrieved`,
   `entity_scoped`, or `contradiction_cluster`. Cap at
   `memory.region_max_entries` (default 40). A region larger than the model can
   hold in working context produces a rewrite that quietly drops things at random.

3. **Pull the provenance trajectories** for the region's entries. The
   consolidator must be able to fact-check its own region against source events,
   not just re-read the region's prose.

4. **Emit the replacement set.** Requirements, all non-negotiable:
   - Every entry cites `provenance` ids drawn from the evidence. **No ancestry,
     no fact.**
   - Never merge across `confidence_tier` (`user_stated` / `tool_observed` /
     `model_inferred`). If you must combine, keep the weakest tier.
   - Two `user_stated` facts in direct contradiction go to `contradictions` for a
     human. **Do not choose.** An agent silently picking one is how you get
     confidently wrong.
   - Record every omission with a reason: `redundant | superseded | contradicted |
     low_utility | noise`.

5. **Write to the shadow bank**, never to the live bank.

6. **Run the utility check.** Score a small fixture set three ways: with the
   original region, with the region masked, and with the replacement in place.
   - Replacement scores below "with region" → reject.
   - Replacement is larger than the region → reject.
   - Masking costs nothing → the region was dead weight; an *empty* replacement
     is the correct answer.

7. **Promote shadow → live**, then re-verify the identity hash.

8. **Stage anything bound for `MEMORY.md`.** That file is 2,200 characters and
   frozen into the system prompt at session start. It is the highest-leverage
   800 tokens in the system; earning a slot there should be hard. Use
   `memory.write_approval` and let a human approve.

## Pitfalls

- **Never run this phase on a small local model.** Backbones in the 3B class emit
  up to 30% format errors on memory operations, and the corruption is *silent* —
  it surfaces months later as an agent that confidently knows wrong things.
  Abort the phase if the schema-reject rate exceeds 10%.
- **Do not delete the episodic log.** It is append-only. If the semantic layer is
  ever poisoned, the fix is `DELETE /observations` and re-derive, which is a
  five-minute operation only if the episodic layer is intact.
- **Do not "helpfully" tidy the identity manifest.** Bundled skills, the prompt
  core and tool allowlists are outside your write-set by construction.
- **Do not consolidate during active use.** The guard exists because a rewrite
  racing a live session produces a memory neither of them agrees with.

## Verification

```bash
# Identity is byte-identical across the pass
python3 - <<'PY'
from somnus.config import load
from somnus.state import identity_hash
cfg = load()
print(identity_hash(cfg.identity.manifest_paths))
PY

# The bank got smaller, not bigger
curl -fsS localhost:8888/v1/default/banks/hermes/stats | python3 -m json.tool

# Contradictions were escalated, not silently resolved
somnus(action="digest")   # look for "contradictions_escalated"
```
