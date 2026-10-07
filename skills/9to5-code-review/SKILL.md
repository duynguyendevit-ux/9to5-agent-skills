---
name: 9to5-code-review
description: Review a pinned diff along separate Standards and Spec axes, with concrete correctness/security findings and explicit coverage limits. Use for review this change, review a branch or PR, inspect a work-in-progress diff, or compare changes since a commit. Review is read-only; fixes and publication require separate authorization.
license: MIT
metadata:
  version: "1.0.0"
---

# Two-Axis Code Review

## Example output

Illustrative, not a completed review:

```text
Scope: base abc1234 → HEAD def5678; working-tree changes excluded
Standards: no actionable violations found in inspected scope
Spec: [P1] src/cache.py:48 — invalidates before commit; rollback leaves stale reads
Coverage: unit suite passed; multi-replica behavior not exercised
```

## 1. Freeze the comparison

Resolve the intended repository and read its `AGENTS.md` and coding standards.
Record HEAD SHA, base SHA and the requested scope: committed branch, direct
snapshot comparison, staged changes or full work in progress.

For a branch/PR review, use the resolved merge-base as the diff base. For an exact
before/after snapshot, compare the two supplied SHAs directly. Record that choice;
three-dot comparison and direct comparison answer different questions. If the
requested ref is invalid or the base cannot be resolved, stop with the blocker.

Include staged, unstaged and untracked content only when the requested scope
includes it. Inspect each part without staging or changing files. An empty diff
is a no-op review, not evidence that the whole codebase is correct.

**Gate:** every included file/hunk has a known comparison boundary. Report scope
changes if HEAD or working-tree content changes during the review.

## 2. Establish the two independent axes

**Standards:** use documented repository conventions and relevant language rules.
For Java/Spring, consult `9to5-spring-conventions`. Separate documented violations
from design heuristics such as duplication, unclear naming or needless indirection;
repo conventions take precedence. Avoid repeating automated formatting warnings
as high-impact correctness findings.

**Spec:** use the user's requirements, supplied issue/plan or referenced spec.
Compare actual behavior against required behavior, missing cases and unauthorized
scope expansion. Resolve issue-tracker references with the repo's configured tools;
do not assume GitHub or require a particular setup file. If no spec is available,
report that axis as unverified rather than deriving the intended spec from the code.

Keep the axes separate so clean style cannot hide wrong behavior. Work inline by
default; delegate independent reviews only when the user or applicable instructions
authorize agents. Read-only review permission does not authorize fixes or new tests.

## 3. Follow the changed behavior

Trace changed entry points through callers, validation, persistence and side effects.
Inspect error paths, null/empty inputs, authorization, compatibility, transactions,
concurrency and retries when relevant. Focus on regressions introduced by this diff;
label pre-existing problems separately.

For each finding, give severity, changed file/line, failing condition, mechanism
and impact. Cite the relevant spec/standard for that axis and distinguish observed
failure from a source-backed risk. Run authorized, non-destructive existing checks
when useful; state missing environment/dependency coverage accurately.

**Gate:** each reported issue has a concrete consequence and source/evidence support.
Drop generic warnings and unsupported claims of failure.

## 4. Report without mutating

Use separate **Standards** and **Spec** sections, severity-ordering within each.
Add scope/SHA, checks run and unknowns. If neither axis has actionable findings,
say so for the inspected scope; missing tests/spec remain limits, not automatic
approval. Successful tests alone do not prove correctness.

Leave code, index, commits, branches, PR state and remote settings untouched.

## References

Inspired by Matt Pocock's
[code-review](https://github.com/mattpocock/skills/blob/6fd947921b935b7e1e69293a200400f0fdd5c15f/skills/engineering/code-review/SKILL.md).
This adaptation makes comparison semantics explicit and delegation conditional.
Offline cases: [`evals/evals.json`](evals/evals.json).
