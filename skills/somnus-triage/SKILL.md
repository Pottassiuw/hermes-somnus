---
name: somnus-triage
description: Turn recent Hermes sessions into structured, clustered FailureRecords with a mechanical defense for each. Use at the start of a dream cycle, or on demand after a bad day.
version: 1.0.0
license: MIT
platforms: [linux, macos]
metadata:
  hermes:
    tags: [Somnus, Diagnostics]
    category: self-improvement
    requires_toolsets: [terminal, session_search]
    requires_tools: [terminal]
---

# Somnus — Log Triage

## When to Use

- The first phase of every dream cycle (`somnus-dream` cron job).
- On demand after a day where something repeatedly went wrong and you want the
  failures *counted* rather than remembered.
- Before writing any fixture: a fixture without a FailureRecord behind it is a
  guess.

Do **not** use this to diagnose a single one-off error. That is `log-autopsy`.
This skill exists to find *patterns across sessions*.

## Quick Reference

| Step | Command |
|---|---|
| Recent failing turns | `sqlite3 ~/.hermes/somnus/somnus.db "SELECT * FROM turns WHERE consolidated=0 LIMIT 50;"` |
| Existing open failures | `somnus(action="failures")` |
| Session full-text search | `session_search` tool |
| Write records | `python3 -m somnus.cli triage --since '24 hours ago'` |

## Procedure

1. **Collect.** Pull turns since the last consolidation checkpoint from the
   sessions DB. Include tool results and errors, not just assistant text.

2. **Normalize before clustering.** Strip the parts that vary between
   occurrences of the same bug: timestamps, UUIDs, hex addresses, absolute
   paths, and *all* digit runs (note: `30s` and `45s` have no word boundary
   before the unit, so a naive `\b\d+\b` leaves them distinct and every timeout
   gets its own signature).

3. **Cluster by signature** = `sha256(task_class | tool | normalized_error)[:16]`.
   Count occurrences and distinct sessions. Most failures are one bug wearing
   many hats.

4. **Fill the interpretive fields** for the top clusters only:
   - `trigger` — the state or action immediately *before* the error, concretely.
   - `consequence` — what the **user** actually lost. Not what the stack trace said.
   - `defense` — one mechanical check that would have prevented it. It must be
     something a script can assert. If no such check exists, write `null` — an
     honest null is worth more than an aspirational sentence.
   - `severity` — `cosmetic | degraded | blocking | unsafe`.

5. **Localize** (only for clusters with ≥3 occurrences): find the last step
   whose intervention could still have changed the outcome. Start with the
   cheap methods — the raising step, or the first divergence from a successful
   sibling trajectory — and escalate to resampling only if the cheap ones are
   ambiguous.

6. **Persist.** Upsert by signature so recurrences bump `occurrences` instead of
   creating duplicates.

7. **Emit guard fixtures.** Every `defense` on an `unsafe` or `blocking` record
   becomes a case in `fixtures/guard/`. These are permanent and never scored —
   they are gated.

## Pitfalls

- **Do not interpret every cluster.** Interpreting 40 clusters burns the phase
  budget on noise. Take the top ~20 by occurrence count.
- **Do not invent a cause you cannot see in the evidence.** A confident wrong
  `trigger` produces a confident wrong fixture, which then "passes" forever.
- **Do not let a parse failure lose the record.** The deterministic fields
  (signature, occurrences, evidence) must survive a malformed model response.
  Mark the record `<triage-parse-failed>` and move on.
- **Do not mark a record `fixed` here.** Only a merged PR with a passing fixture
  closes a failure.

## Verification

```bash
# Clusters exist and none are singletons-only
sqlite3 ~/.hermes/somnus/somnus.db \
  "SELECT signature, occurrences FROM failures ORDER BY occurrences DESC LIMIT 10;"

# Every blocking/unsafe record has a defense
sqlite3 ~/.hermes/somnus/somnus.db \
  "SELECT COUNT(*) FROM failures WHERE severity IN ('blocking','unsafe') AND defense IS NULL;"
# expect: 0

# Records validate against the schema
python3 -c "
import json,sqlite3,jsonschema,pathlib
s=json.loads(pathlib.Path('${HERMES_SKILL_DIR}/../../somnus/schemas/failure_record.schema.json').read_text())
db=sqlite3.connect('$HOME/.hermes/somnus/somnus.db')
for (p,) in db.execute('SELECT payload FROM failures'):
    jsonschema.validate(json.loads(p), s)
print('all failure records valid')"
```
