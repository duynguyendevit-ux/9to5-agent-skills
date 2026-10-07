---
name: 9to5-handoff
description: Save a concise, source-linked handoff so another coding session can continue from verified state.
license: MIT
metadata:
  version: "1.0.0"
  opencode/autoinvoke: false
---

# Coding Session Handoff

Run on an explicit user request. OpenCode V2 hides this skill from automatic
advertising through `metadata.opencode/autoinvoke: false`; other agents may use
different discovery rules. This flag is not a permission boundary.

## Example output

Illustrative, not a saved handoff:

```text
Saved: <temp>/daily-tools-handoff.md
Focus: finish cache review
Includes: repo/branch/SHA, verified changes, check results, unresolved decision
No commit or remote write performed
```

## Capture only continuation context

Use the user's stated next-session focus and latest corrections. Resolve the
active repo, branch and HEAD if available. Inspect its current status before
describing local changes; distinguish agent edits, existing user work and work
whose provenance is unknown.

Prefer links to existing specs, plans, ADRs, issues, commits and diffs over copied
content. Record important conversation decisions not already captured elsewhere.
Separate verified outcomes from attempted steps, hypotheses and pending work.
State whether a commit exists, whether it was pushed, and which SHA checks cover.
A local commit is not proof of remote publication or deployment.

Save a new Markdown file in the approved temporary directory (`/tmp/opencode` in
this workspace), or a user-requested destination. Use a unique filename; preserve
existing notes. If no filesystem tools are available, provide the handoff in the
reply and label it unsaved. The destination is not the current repo by default.

## Document structure

```markdown
# Handoff: <focus>
## Goal and latest constraints
## Repository and state
## Completed work and evidence
## Checks and limitations
## Pending decisions and next authorized action
## Source pointers
## Suggested skills
```

Under repository state, include the checkout path, branch/HEAD, publication state
and residual changes. Quote only sanitized excerpts of commands/logs. Exclude
credentials, tokens, auth headers, private payloads and unnecessary personal data;
refer to configuration locations without copying their contents.

Under next action, identify the smallest continuation step inside current scope.
Carry forward authorization limits: pending decisions remain pending, missing
checks remain missing, unrelated dirty repos remain unrelated. Handoff itself
does not authorize a future fix, push, visibility change or deployment.

Name relevant **installed** skills and why the next agent would use them; label
unverified availability instead of claiming an upstream skill is installed. A
user-invoked skill is a pointer for the user, not an automatic agent dependency.

Finish only when the handoff file exists with the latest state and resolvable local
pointers, or when an unsaved fallback is clearly reported. Return its path and
focus. Creating a handoff does not stage, commit or publish repository content.

## References

Inspired by Matt Pocock's
[handoff](https://github.com/mattpocock/skills/blob/6fd947921b935b7e1e69293a200400f0fdd5c15f/skills/productivity/handoff/SKILL.md).
Offline cases: [`evals/evals.json`](evals/evals.json).
