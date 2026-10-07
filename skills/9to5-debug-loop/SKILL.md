---
name: 9to5-debug-loop
description: Diagnose a reported bug or performance regression with a symptom-specific reproduction loop, falsifiable hypotheses and measured verification. Use for debug this, diagnose a failure, wrong output, flaky behavior or a performance regression. Keep diagnosis separate from authorization to modify code, production systems or permanent tests.
license: MIT
metadata:
  version: "1.0.0"
---

# Evidence-Driven Debug Loop

## Example output

Illustrative, not an executed diagnosis:

```text
Symptom: duplicate item after retry
Repro: replay.py fixture.json — failed before the change, passed after
Cause: retry reuses the request but generates a different deduplication key
Checks: original replay passed; wider integration suite not run
Remaining: cross-process retry behavior unverified
```

## 1. Define the signal

Read the target repo's instructions, glossary and relevant decision records.
Record the user's exact symptom, expected behavior, affected version/environment
and whether the request permits a fix or diagnosis only.

Find a narrow observation that can fail on this symptom: an existing test, fixture
replay, CLI invocation, HTTP request or browser interaction. Run it and save the
command, exit status and redacted result. A compile error, missing tool or unrelated
exception does not reproduce the reported bug.

Prefer existing checks. Use temporary harnesses only within authorized local scope;
create permanent test files only when requested or permitted by repo instructions.
For runtime values/call flow, use the debugger when available; load `ij-debugger`
when its runtime-evidence conditions apply. Remote diagnosis remains read-only
unless the user explicitly approves instrumentation or load generation.

**Gate:** proceed when evidence exercises the relevant path and detects the exact
symptom. If access or data is missing, report attempts and the missing prerequisite;
label any static explanation as a candidate, not a confirmed root cause.

## 2. Minimize and test predictions

Reduce inputs, config and caller steps one at a time, rerunning after each change.
Keep the smallest observed scenario that still fails; do not claim exhaustive
minimality without trying those reductions.

List a few plausible causes and the observation that would distinguish each.
Inspect the relevant source to design probes, then vary one factor per experiment.
Use targeted breakpoints/logs; redact credentials and avoid capturing full private
payloads. Mark temporary instrumentation so only your own additions are removed.

For flaky bugs, record trials, seed/input, failure rate and conditions. One passing
run is not resolution. For slowness, measure the same workload before and after;
capture latency/distribution and resource evidence instead of guessing from code.

**Gate:** identify evidence that distinguishes the confirmed cause from alternatives,
or report which hypotheses remain unresolved.

## 3. Fix and verify within scope

When a fix is authorized, make the smallest change addressing the demonstrated
cause. If tests are allowed, assert behavior at the real public boundary, watch
the regression fail first, then pass after the change. Avoid assertions that merely
recompute the implementation or mock away the failing interaction.

Rerun both the minimized case and original scenario, then the repo's relevant
checks. Compare the same performance/flakiness conditions; record limitations.
Remove only instrumentation/artifacts you created, preserving user work.

Finish with symptom, reproduction evidence, cause/confidence, changes, checks and
unresolved conditions. A diagnosis-only task ends with evidence, not a patch.
Commit/push and deployment are separate publication decisions.

## References

Inspired by Matt Pocock's
[diagnosing-bugs](https://github.com/mattpocock/skills/blob/6fd947921b935b7e1e69293a200400f0fdd5c15f/skills/engineering/diagnosing-bugs/SKILL.md)
and [tdd](https://github.com/mattpocock/skills/blob/6fd947921b935b7e1e69293a200400f0fdd5c15f/skills/engineering/tdd/SKILL.md).
This adaptation respects local edit/test authorization rather than assuming it.
Offline cases: [`evals/evals.json`](evals/evals.json).
