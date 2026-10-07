# Daily coding skill design

Reference: [mattpocock/skills](https://github.com/mattpocock/skills), inspected
2026-10-07 at commit `6fd947921b935b7e1e69293a200400f0fdd5c15f` (MIT).
These skills are independently worded adaptations of workflow ideas, not an
installation of upstream skills and not a claim of affiliation.

## Selected patterns

| Source | Local skill | Adopted pattern | Local boundary |
| --- | --- | --- | --- |
| [diagnosing-bugs](https://github.com/mattpocock/skills/blob/6fd947921b935b7e1e69293a200400f0fdd5c15f/skills/engineering/diagnosing-bugs/SKILL.md) | `9to5-debug-loop` | Detect the exact symptom before claiming a cause; minimize, probe predictions, verify original behavior. | Diagnosis permission is not fix/production permission; missing repro remains explicit. |
| [tdd](https://github.com/mattpocock/skills/blob/6fd947921b935b7e1e69293a200400f0fdd5c15f/skills/engineering/tdd/SKILL.md) | `9to5-debug-loop` | Behavior at a public boundary; independent expected results; red before green when permanent tests are allowed. | Repository rules determine whether new test files are authorized. |
| [code-review](https://github.com/mattpocock/skills/blob/6fd947921b935b7e1e69293a200400f0fdd5c15f/skills/engineering/code-review/SKILL.md) | `9to5-code-review` | Pin the diff and keep Standards/Spec as independent axes. | Direct snapshot vs merge-base semantics are explicit; delegation requires authorization; no mandatory tracker setup. |
| [handoff](https://github.com/mattpocock/skills/blob/6fd947921b935b7e1e69293a200400f0fdd5c15f/skills/productivity/handoff/SKILL.md) | `9to5-handoff` | User-invoked temporary note; link durable artifacts rather than duplicate them. | Carry publication/test status and authorization limits; installed skill availability must be verified. |

The earlier `9to5-git-publish`, `9to5-github-audit` and `9to5-github-settings`
capture repository-management mistakes from the local workflow. They complement
the coding skills rather than claiming to be Matt Pocock's implementations.

## Composition

- Diagnose the relevant symptom with `9to5-debug-loop`.
- Review an authorized change with `9to5-code-review` before publication.
- Publish only the named repository with `9to5-git-publish` when requested.
- Audit remote workflow evidence with `9to5-github-audit` when requested.
- Save a continuation note with `9to5-handoff` when the user invokes it.

Each step requires its own task scope; this is a composition map, not an automatic
pipeline that grants permission for the next operation. The GitHub settings skill
is a separate administrative workflow, not a coding/deployment step.

`9to5-handoff` uses `metadata.opencode/autoinvoke: false`, as documented in
[OpenCode V2 skills](https://opencode.ai/v2/docs/skills), to keep it out of the
model's advertised list. Explicit loading still works; the setting is not an
authorization guard and does not promise the same discovery behavior in other agents.

## Validation limits

Contract tests verify metadata, local links and offline fixtures. Agent simulations
check action plans, not live Git/GitHub execution or successful reproduction of a
real application bug. Results should retain that distinction.
