# Plan Templates

Read this file in Step 5. Pick the template matching `TASK_TYPE`:

- `Bug` → Bug template
- `Story` / `Task` / `Sub-task` → Story template

Substitute every `{placeholder}` and keep the section headings exactly as written.

## Bug template

```markdown
# {KEY}: {Summary}

> Source: {Jira URL} {Confluence URL if fetched}
> Date: {YYYY-MM-DD}
> Type: Bug
> Branch: `fix/{KEY}-{slug}`

## Context

{2-4 sentences: what broke, who is affected, when it started occurring.
Write from the bug's perspective — not "the ticket says" but the actual impact.}

## Requirements

{Bullet list of concrete requirements from description + comments.
Use the exact language from acceptance criteria if present.
If comments contradict the description, note the conflict explicitly.}

## Reproduction Steps

{Numbered steps to reproduce the bug exactly.
End with: "Expected: X / Actual: Y"}

## Root Cause

{Your hypothesis on what is wrong, based on the description and codebase exploration.
Mark as "(hypothesis)" if not confirmed by reading the code.}

## Technical Constraints

{Any constraints found in comments, Confluence, or inferred from the codebase.
Omit this section if empty.}

## Implementation Plan

{Numbered steps. Each step must be:
- Concrete: names a specific file, function, or operation
- Verifiable: has a clear done state
- Ordered: each step can start after the previous one finishes}

## Files to Touch

| File | Change |
|------|--------|
| `path/to/file.go` | Add X / Modify Y / Create new |

## Out of Scope

{Explicit list of what this fix does NOT cover.}

## Verification

{How to confirm the bug is fixed:
- Build command
- Manual test steps that reproduce the bug, now passing
- Regression: what other behavior must not break}
```

## Story / Task / Sub-task template

```markdown
# {KEY}: {Summary}

> Source: {Jira URL} {Confluence URL if fetched}
> Date: {YYYY-MM-DD}
> Type: {TASK_TYPE}
> Branch: `feat/{KEY}-{slug}`

## Context

{2-4 sentences: what this ticket is about, why it exists, what user/system problem it solves.
Write from the ticket's perspective — not "the ticket says" but the actual context.}

## Requirements

{Bullet list of concrete requirements extracted from description + comments.
Use the exact language from acceptance criteria if present.
If comments contradict the description, note the conflict explicitly.}

## API / Interface Contract

{Only include if the ticket adds or changes a public API, CLI command, HTTP endpoint, or shared type.
List: method signature, input/output shape, error cases.
Omit this section if not applicable.}

## Technical Constraints

{Any constraints found in comments, Confluence, or inferred from the codebase:
architecture decisions, API contracts, performance requirements, backward compatibility needs.
Omit this section if empty.}

## Implementation Plan

{Numbered steps. Each step must be:
- Concrete: names a specific file, function, or operation
- Verifiable: has a clear done state
- Ordered: each step can start after the previous one finishes

Bad: "Update the service layer"
Good: "1. Add `GetFoo(ctx, id string) (*Foo, error)` to `internal/jira/service.go`"}

## Files to Touch

| File | Change |
|------|--------|
| `path/to/file.go` | Add X / Modify Y / Create new |

List only files you are confident will change. Flag uncertain ones with "(likely)".

## Out of Scope

{Explicit list of things the ticket does NOT ask for, based on description + comments.
At minimum: what the ticket explicitly deferred or excluded.}

## Verification

{How to confirm the implementation is correct:
- Build command: `make build`
- Manual test steps against a live Jira/Confluence instance
- Edge cases to check (e.g. missing field, auth failure, empty list)}
```
