---
name: 9to5-github-settings
description: Change explicitly requested GitHub repository visibility or description with a concrete plan, scoped authorization and read-back verification. Use for make public/private, keep selected repos public and privatize the rest, publish a repo's visibility, or update its About description. Distinguish visibility from git push, deployment, archival and deletion.
license: MIT
metadata:
  version: "1.0.0"
---

# Scoped GitHub Settings

## Example output

Illustrative, not an executed account change:

```text
Public: example/tools, example/site
Other visible repos: 3 private (2 changed, 1 already private)
Verified: exact target set matches read-back
No commits, deployments, archives or deletions performed
```

## 1. Resolve intent and targets

Use exact `OWNER/REPO` identifiers and the user's latest correction. Distinguish:

- **Keep these; make the rest private**: preserve selected repos' current visibility.
- **Make these public; the rest private**: assign PUBLIC to the named set and PRIVATE
  to the remaining repos in the agreed inventory.
- **Publish code**: use `9to5-git-publish`; visibility is a separate operation.
- **Change description**: edit only the About description unless README edits were
  also requested. Report contradictions in README instead of silently broadening.

Use `9to5-github-audit` to obtain the visible inventory for a bulk operation. Every
named exception must resolve exactly once; missing names or ambiguous owners stop
the bulk write. Do not treat a new repo created after the inventory as authorized.

## 2. Bind the plan to authorization

Build a snapshot of each target's current visibility/description and proposed
values. Separate changed targets, already-correct targets and preserved exceptions.
Describe the exact set and consequences before writing. An explicit request that
fully specifies this plan authorizes it; a read-only check or vague "publish" in
an unclear context does not. If scope or desired value is missing, report the
blocker and perform no writes.

Public exposure includes committed files, history and potentially Actions logs
and artifacts. Inspect the proposed public repo and unpublished changes for
credentials/private data; for skill exports also run `9to5-skill-sync` leak checks.
A clean hostname scan is not a full history/security audit. Stop on known sensitive
content; do not rewrite history or delete evidence as an implicit cleanup step.
Privatizing can affect Pages, forks, stars and integrations. Follow the CLI/API's
current consequences; do not assert a public fork can or cannot be converted until
the operation's actual result is known.

## 3. Apply only the requested fields

Before each write, re-read current fields and compare them with the snapshot.
If another writer changed a relevant field, stop that target and report the
conflict instead of overwriting it. GitHub's settings commands are not an atomic
compare-and-swap; record a successful write only after read-back verification.

For approved visibility changes, use the explicit repository:

```bash
gh repo edit "$REPO" --visibility "$VISIBILITY" \
  --accept-visibility-change-consequences
```

For an approved About-description change:

```bash
gh repo edit "$REPO" --description "$DESCRIPTION"
gh repo view "$REPO" --json nameWithOwner,description,visibility,url
```

Prefer a factual, personal description for daily developer skills. Removing
company branding does not prove that existing code/configuration has no company
references. Describe what changed without inventing an affiliation disclaimer.
README edits, skill rewrites, commits and pushes require their own requested scope.

Record each result independently. Failure on one repo is a partial operation, not
permission to delete/recreate it, detach a fork or change ownership. Preserve
already-successful changes; report failures without an unrequested rollback.

## 4. Verify the entire plan

Re-read all targets, including exceptions and already-correct repos. Recompute
counts from this read-back and list mismatches. For bulk plans, compare the original
target set; report newly observed repos separately rather than editing them.

Finish with verified values, changed/already-correct counts, preserved exceptions
and any failures. Visibility changes do not archive or delete repositories.

## Offline review cases

[`evals/evals.json`](evals/evals.json) covers keep-versus-public and field-only edits.
These simulated cases do not authorize real GitHub writes.
