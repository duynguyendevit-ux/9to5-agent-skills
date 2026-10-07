---
name: 9to5-github-audit
description: Read-only GitHub repository inventory and workflow audit, with paginated counts and commit-specific CI evidence. Use when asked to check GitHub repos, list public/private projects, find failing Actions, or verify CI for a pushed commit. Route requested visibility or description changes to 9to5-github-settings; code publication belongs to 9to5-git-publish.
license: MIT
metadata:
  version: "1.0.0"
---

# GitHub Repository Audit

## Example output

Illustrative, not a live account audit:

```text
Visible inventory: 4 repos — 2 public, 2 private
example/tools: main at abc1234; Test failed, Deploy pending for that SHA
example/site: latest Pages run succeeded for an older SHA; current HEAD unverified
Scope: metadata and Actions evidence, not a source/security review
```

## 1. Establish read scope

Resolve the requested owner or explicit `OWNER/REPO` set from the active task.
Use `gh auth status` to confirm available access without printing tokens. If the
owner is unspecified and cannot be resolved, stop with that missing input rather
than auditing whichever account happens to be logged in.

Keep the audit read-only: no settings edits, commits, workflow reruns, issue
creation or repairs. Local checkout discovery is outside an account inventory.

## 2. Enumerate visible repositories

For an account-wide inventory, page through the connection rather than assuming
the first 100 repos are the whole account:

```bash
gh api graphql --paginate -F owner="$OWNER" -f query='
query($owner: String!, $endCursor: String) {
  repositoryOwner(login: $owner) {
    repositories(first: 100, after: $endCursor, orderBy: {field: NAME, direction: ASC}) {
      nodes {
        nameWithOwner url visibility isArchived isFork description pushedAt
        defaultBranchRef { name target { oid } }
      }
      pageInfo { hasNextPage endCursor }
    }
  }
}' --jq '.data.repositoryOwner.repositories.nodes[]'
```

Check command success and pagination completion before computing counts. Deduplicate
by `nameWithOwner`; derive visibility totals and exceptions from the same snapshot.
Distinguish INTERNAL from PRIVATE. Call this a visible inventory: permissions can
hide private repos, so enumeration does not prove access to every account repo.
Record timestamp, owner and scope. `pushedAt` is repository-wide activity, not
necessarily the last commit date of the default branch.

A missing default branch suggests an empty/uninitialized repo; verify with repo
metadata before calling it empty. API/auth failures remain unknown, not zero repos
or no workflow runs.

## 3. Inspect workflow evidence

For each requested repo with a default branch, list Actions runs on that branch:

```bash
gh run list --repo "$REPO" --branch "$BRANCH" --limit 100 \
  --json databaseId,workflowName,status,conclusion,headSha,createdAt,url,event
```

If the limit is reached or older runs are needed, paginate the Actions REST API.
Select the latest run per workflow and compare its `headSha` to default-branch
HEAD, or to the pushed SHA supplied by the user. A successful Dependabot job or
an older deployment run does not establish that current code passes CI. Report
failed, cancelled, skipped and in-progress workflows independently; do not let
one successful run hide another failed workflow for the same commit.

No matching runs means **no observed runs in this scope**, not no configured CI.
Avoid inferring that a deployed site is healthy from an Actions conclusion alone.
For failed runs, inspect `gh run view <id> --repo "$REPO" --log-failed`; extract
the failing step and concise error evidence, redacting sensitive log values.

## 4. Report

Return verified totals, notable repositories, failing workflow links and exact
file/line evidence when available. State whether results cover latest-per-workflow
history or current/pushed SHA. Separate absent evidence from verified failure and
state that metadata/Actions inspection is not a full source or security review.

## Offline review cases

[`evals/evals.json`](evals/evals.json) covers partial enumeration and misleading CI.
Evaluate supplied fixtures without contacting a live GitHub account.
