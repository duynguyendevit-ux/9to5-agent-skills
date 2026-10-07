---
name: 9to5-git-publish
description: Commit and push changes in the exact repository requested, with scoped staging, repository checks and remote verification. Use for push changes, publish code, commit and push, or checking whether a named checkout has unpublished commits. A clean target stays a no-op; it does not authorize publishing another repository.
license: MIT
metadata:
  version: "1.0.0"
---

# Scoped Git Publish

## Example output

Illustrative, not an executed push:

```text
Repo: example/daily-tools; branch: main
Pushed: abc1234; remote main matches local HEAD
Checks: unit tests passed; CI pending for abc1234
Remaining local changes: notes/draft.md (excluded from this publish)
```

## 1. Resolve the target

Use the repository named in the latest request; otherwise use the active task's
repository. Read its applicable `AGENTS.md`, then inspect from that directory:

```bash
git rev-parse --show-toplevel
git remote -v
git status --short --branch
git branch --show-current
```

Record the root, intended remote URL, branch and publication scope. Credentials
embedded in a remote URL belong in redacted output. For competing clones, compare
remotes rather than choosing the checkout with the most recent edits.

A clean checkout with no unpublished commits is a completed no-op. Stop there;
an unrelated dirty repository is not an alternative target. Repository discovery
beyond the target requires a separate request. Detached HEAD, ambiguous remotes
or an unspecified destination branch are blockers, not permission to invent one.

## 2. Inspect the publication boundary

Fetch the intended remote without modifying the working tree. Compare HEAD with
the actual destination ref, not just a stale tracking branch. If the destination
does not exist, require an explicit new-branch publication target.

Inspect every commit to be pushed, not only the latest commit. For uncommitted
work, read the tracked diff, untracked files, staged diff and `git diff --check`.
Stage only files or hunks covered by the request; preserve unrelated user work
and existing staged changes outside that scope. An existing mixed staged set is
a blocker unless the user explicitly includes it. Use explicit paths rather
than `git add -A` for a partial task.

Check staged content and unpublished history for credentials, private configs,
logs and generated artifacts. A pattern scan is screening, not proof of absence.
If skill exports are involved, use `9to5-skill-sync` for canonical parity and its
leak check before staging generated copies.

## 3. Validate and commit

Run the repository's documented check command. Preserve its exit status:

```bash
set -o pipefail
# Run the repository's actual check command here, optionally piped to tee.
```

Report skipped checks and failures accurately. A missing browser or tool means
the check did not complete; a build passing does not establish tests passed.
Inspect `git diff --cached` and commit with the repository's message convention.
If only existing commits need publication, skip creating a new commit.

## 4. Push and verify

Push the explicit remote and destination branch. A rejection stops publication;
do not force-push, reset, stash, rebase or overwrite history to make it succeed.
When remote history advanced, report the conflict for a separately authorized
integration decision.

Compare `git rev-parse HEAD` with `git ls-remote <remote> refs/heads/<branch>`.
Report residual working-tree changes separately from remote success. On GitHub,
use `9to5-github-audit` to check workflow runs for the pushed SHA if requested;
pending CI is not success and absence of a run is not validation.

Finish with repo/branch, pushed SHA or no-op, check results, and any blockers.
Publishing one repo never authorizes creating releases, changing visibility,
deploying services or pushing other repos.

## Offline review cases

[`evals/evals.json`](evals/evals.json) covers clean-target scope and mixed staging.
Use simulated evidence; these cases do not authorize live Git writes.
