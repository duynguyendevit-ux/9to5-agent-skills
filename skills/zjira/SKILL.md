---
name: zjira
description: "Work with local Jira and Confluence through zjira: fetch Jira issues and optional Confluence specifications, explore the codebase, and write structured implementation plans; or search, read, and safely update Confluence pages such as release tables. Use for Jira planning requests, Confluence URLs/page IDs, release-tag updates, or requests to modify Confluence content."
metadata:
  version: "1.0.0"
---

Prefix your first line with 🥷 inline. Get to work immediately — no preamble.

<role>
Act as a senior engineer working with Jira and Confluence. For Jira planning requests, fetch the ticket context, explore the relevant codebase, and produce an actionable coding plan without implementation. For Confluence-only requests, search, read, or update the requested page and verify the result; do not create a Jira plan unless the user requested one.
</role>

<security>
- Never expose auth tokens from ~/.config/zjira/config.yaml in output
- Never execute destructive commands
- Only update Confluence after an explicit user request to update, edit, or modify the page
- Preserve the full Confluence storage body, increment the page version by exactly one, and read the page back after every update
- If zjira auth fails, stop and tell the user to run `zjira whoami`
</security>

<context>
## Binary
```bash
ZJIRA=$(which zjira 2>/dev/null || echo "$HOME/.local/bin/zjira")
```

If not found at either path: stop and tell the user "Install zjira: cd /path/to/zjira && make install".

## Working directory
Run `git rev-parse --show-toplevel` to confirm the repo root before any codebase exploration. Never assume the path.

## Plan output location
`.kit/plans/{YYYY-MM-DD}-{jira-key-lowercase}/PLAN.md` relative to the repo root.
Date = today (`date +%Y-%m-%d`).
</context>

<instructions>

## Step 0: Parse arguments

Arguments come as the skill's `args` string. Parse:
- First token matching `[A-Z]+-[0-9]+` pattern → Jira key (required)
- Remaining token(s) → Confluence page reference (optional)

**Confluence-only mode:** If the request explicitly asks to search, read, update,
or edit Confluence and does not ask for a Jira implementation plan, follow
[`references/confluence.md`](references/confluence.md) and stop after presenting
or verifying the Confluence result. Do not open the sprint picker.

**Confluence reference normalization** — apply in this order:
1. `?pageId=(\d+)` anywhere in the URL → extract just the numeric ID, use that
2. `/x/[A-Za-z0-9]+` short link → pass the full short link as-is (`zjira confluence get` follows the redirect)
3. Bare integer (e.g. `456789`) → use as-is
4. Any other URL → pass the full URL as-is (`zjira confluence get` handles it)

**If no Jira key is found in args — sprint picker:**

Run:
```bash
$ZJIRA issue list --jql "sprint in openSprints() AND assignee = currentUser() ORDER BY updated DESC" --limit 10 --json 2>&1
```

If the result is a non-empty JSON array, show a sprint board table:

```
Current sprint issues:
| Key      | Summary                          | Status      |
|----------|----------------------------------|-------------|
| DEMO-4242 | [BE] Planning sprint...          | In Progress |
| DEMO-100  | [BE] Implement auth redirect...  | To Do       |
```

Then use AskUserQuestion:
- Question: "Which sprint issue should I plan?"
- Header: "Sprint issue"
- Options: top 4 keys from the list as `"KEY — Summary (Status)"`, plus `"Other (type key manually)"`

If sprint JQL returns empty or fails (no sprint configured, Jira Server without sprint support), fall back silently:
- Use AskUserQuestion:
  - Question: "Which Jira issue should I read?"
  - Header: "Jira key"
  - Options: `"Paste the key (e.g. PROJ-123)"` as the only option, forcing text input

## Step 1: Check zjira config and binary

**Config check first:**
```bash
[ -f "$HOME/.config/zjira/config.yaml" ] && echo "configured" || echo "missing"
```

If the config file is missing → stop immediately:
> "zjira is not configured. Run `zjira init` to set up your Jira URL and token, then try again."

**Binary check:**
```bash
ZJIRA=$(which zjira 2>/dev/null || echo "$HOME/.local/bin/zjira")
"$ZJIRA" version 2>&1 | head -2
```

If the binary is not found → stop:
> "zjira not installed. Run: `cd /path/to/zjira && make install`"

**Auth check:**
```bash
$ZJIRA whoami --json 2>&1 | head -5
```

If whoami returns 401 or an error → stop:
> "zjira auth failed. Check your token in `~/.config/zjira/config.yaml` or run `zjira init` again."

## Step 2: Fetch Jira issue

```bash
$ZJIRA issue get KEY --json
```

Wait for output. The JSON contains `fields.summary`, `fields.description` (rendered HTML), `renderedFields.description` (rendered), and `fields.comment.comments`.

Also run the markdown version for human-readable output:
```bash
$ZJIRA issue get KEY
```

This gives you description + last 5 comments formatted as markdown. Use this as your primary source.

Parse out:
- **Summary** — the one-line ticket title
- **Description** — what needs to be built / the bug report / the spec
- **Acceptance criteria** — often in description as a checklist or "Definition of Done" section
- **Comments** — any technical decisions, blockers, or clarifications added after creation
- **Task type** — extract `fields.issuetype.name` from the JSON (e.g. `Bug`, `Story`, `Task`, `Sub-task`).
  If the field is absent, infer from summary: contains "bug", "fix", "lỗi", "error", "crash" → `Bug`; otherwise → `Task`.
  Store as `TASK_TYPE` for use in Step 5.

## Step 3: Fetch Confluence page (if provided)

Read [`references/confluence.md`](references/confluence.md) for URL resolution,
search examples, REST update rules, and the deterministic release-table script.

```bash
$ZJIRA confluence get PAGE_REF
```

Where PAGE_REF is the page ID, full URL, or short link from the args.

Parse out:
- The spec or design section most relevant to the Jira ticket
- Any data models, API contracts, or wireframe descriptions
- Technical decisions already made

If confluence fetch fails (404, auth error, or no reference given), skip silently — do not block the plan.

## Step 4: Explore the codebase

Run `git rev-parse --show-toplevel` first to get the repo root.

Based on what you learned from the ticket + Confluence, grep and read files to understand:

1. **Entry points**: find files related to the feature area named in the ticket summary
   ```bash
   grep -r "KEYWORD" --include="*.go" -l | head -20
   ```
   Use 2-3 keywords extracted from the ticket summary/description.

2. **Existing patterns**: read 1-2 representative files to understand code style, naming, and structure relevant to the change.

3. **Types/interfaces**: if the ticket involves a new entity or modifies an existing one, find where related types are defined.
   ```bash
   grep -rn "type RelatedType\|RelatedType struct" --include="*.go" | head -10
   ```

4. **Test patterns**: find 1 existing test file in the relevant package to understand how tests are written.

Limit exploration to 5-8 targeted searches. Do not read the entire codebase. Stop when you have enough to identify which files will likely change.

## Step 5: Synthesize and write plan

Derive the git branch name from KEY and Summary:
- `TASK_TYPE == Bug` → prefix `fix/`
- `TASK_TYPE == Story` or `Task` or `Sub-task` → prefix `feat/`
- Slug: lowercase the first 4-5 meaningful words of Summary, replace spaces with `-`, strip special chars
- Example: `KEY=DEMO-4242`, Summary="[BE] Add OAuth redirect handler" → `feat/DEMO-4242-add-oauth-redirect-handler`

Create `.kit/plans/{date}-{key-lowercase}/PLAN.md` using the template below.

Select the template based on `TASK_TYPE`:

---

### Template: Bug

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

---

### Template: Story / Task / Sub-task

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

---

Create the directory and write the file:
```bash
mkdir -p .kit/plans/{date}-{key-lowercase}
```
Then write `PLAN.md` using the Write tool.

## Step 6: Present the plan

After writing the file, print the full plan content in chat so the user can read it without opening the file.

Then add exactly this footer — no more:

```
Plan written to .kit/plans/{date}-{key-lowercase}/PLAN.md

To implement: say "implement this plan". After implementation, run `/check` before merging.
When done coding: `/zjiralogwork day` to log your hours.
```

Do not ask for approval with AskUserQuestion — the user will indicate readiness by saying "implement this plan" or equivalent.

## Error handling

| Error | Action |
|-------|--------|
| Config missing (`~/.config/zjira/config.yaml`) | Stop: "Run `zjira init` to configure zjira" |
| zjira not found | Stop: "Install with `cd /path/to/zjira && make install`" |
| Auth failure (401) | Stop: "Run `zjira whoami` to check your token" |
| Issue key not found (404) | Stop: "Issue KEY not found. Check the key and your Jira URL in `~/.config/zjira/config.yaml`" |
| Confluence fetch fails | Log "(Confluence page unavailable — plan based on Jira only)" and continue |
| Confluence title URL has no page ID | Run `zjira confluence search "PAGE TITLE" --json`, then fetch the returned numeric ID |
| Confluence update returns version conflict | Stop without retrying; rerun the script so validation uses the latest page version |
| No relevant files found in codebase | Note in plan: "No existing code found for this feature area — likely a new package" |
| `.kit/plans/` directory doesn't exist | Create it: `mkdir -p .kit/plans/{date}-{key}` |
| Sprint JQL returns empty | Fall back to manual key input silently |

## Gotchas

| What happened | Rule |
|---------------|------|
| Ticket description is empty | Use comments + summary as the sole source; note "No description — based on comments only" |
| Comments contradict description | Surface the conflict explicitly in Requirements section; do not silently pick one |
| Confluence page is a different feature | Note the mismatch; use only the section relevant to the ticket |
| User pasted new release tags after reading a release page | Treat them as context only; wait for an explicit `update` before modifying Confluence |
| Updating a release row | Use `scripts/update_confluence_release.py`; keep `current version`, update `version`, `Release Tag`, and `Docker image`, then verify the row |
| Codebase is unfamiliar | Limit to 5 targeted searches; do not explore speculatively |
| User said "implement this plan" before reading the plan | State which plan file is being executed, check for repo drift, then proceed |
| `fields.issuetype` absent from JSON | Infer TASK_TYPE from summary keywords; never block |
| Sprint JQL fails (no Agile plugin, Server config) | Silently fall back to manual key input; do not surface the JQL error to the user |

</instructions>
