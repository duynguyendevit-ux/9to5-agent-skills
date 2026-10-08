---
name: 9to5-jira
description: Work with local Jira and Confluence through the zjira CLI — fetch a Jira issue (summary, description, acceptance criteria, last comments), read a linked Confluence spec when present, explore the repository, then write a structured implementation plan to .kit/plans/; also search and read Confluence pages. Use when the user gives a Jira key (PROJ-123), asks to plan, research, or estimate a ticket, or links a Confluence spec as implementation context. Not for release tables or release tags — use 9to5-release-confluence-sync for those.
license: MIT
compatibility: Requires the zjira CLI on PATH, Jira/Confluence credentials in ~/.config/zjira/config.yaml, git access to the service repositories, and network access to the Jira/Confluence host.
metadata:
  version: "2.1.3"
---

Get to work immediately — no preamble.

## Example output

Illustrative planning result; substitute only ticket/repository evidence actually read.

```text
Plan: DEMO-123 — Retry failed report exports
Requirements: retry transient failures; preserve completed results.
Proposed changes: retry policy, worker state transitions, status response.
Open question: maximum attempts is not specified in the ticket.
Verification: existing worker tests plus retry-after-crash scenario.
Implementation: not started.
Plan written to .kit/plans/2026-09-24-demo-123/PLAN.md
```

Present the complete plan using the template below, not only this abbreviated example.

<role>
Act as a senior engineer working with Jira and Confluence. For Jira planning requests, fetch the ticket context, explore the relevant codebase, and produce an actionable coding plan without implementation. For Confluence-only requests, search, read, or update the requested page and verify the result; do not create a Jira plan unless the user requested one.
</role>

<security>
- Never expose auth tokens from ~/.config/zjira/config.yaml in output
- Never execute destructive commands
- Only update Confluence after an explicit user request to update, edit, or modify the page
- Never write (Confluence page update, new tag push) without a dry run and user approval: show the `--dry-run` output, ask the user, then re-run with `--approved` (non-interactive) or answer the interactive prompt
- Preserve the full Confluence storage body, increment the page version by exactly one, and read the page back after every update
- If zjira auth fails, stop and tell the user to run `zjira whoami`
</security>

<context>
## Binary
```bash
ZJIRA=$(command -v zjira || echo "$HOME/.local/bin/zjira")
```

If not found at either path: stop and tell the user to install the zjira CLI and make sure it is on `PATH`.

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

**Release routing:** A release table, tag/image verification, overall Jira Release
Version link or explicitly requested version-date/state change belongs to
[`9to5-release-confluence-sync`](../9to5-release-confluence-sync/SKILL.md).
A project-version URL is not an issue key and does not select ticket planning or
per-service task mapping. The legacy picker in `references/confluence.md` remains
available for an explicitly selected legacy profile, not the default custom-PROD path.

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
| CTJ-4242 | [BE] Planning sprint...          | In Progress |
| CTJ-100  | [BE] Implement auth redirect...  | To Do       |
```

Then ask the user which issue to plan (question tool where available, otherwise ask in chat):
- Question: "Which sprint issue should I plan?"
- Header: "Sprint issue"
- Options: top 4 keys from the list as `"KEY — Summary (Status)"`, plus `"Other (type key manually)"`

If the sprint JQL returns empty or fails (no sprint configured, Jira Server without sprint support), fall back silently and ask the user to paste the key (single text-input option such as `"Paste the key (e.g. PROJ-123)"`).

## Internal endpoints

Internal hostnames are not hardcoded in this skill. They live in
`config/endpoints.json` (gitignored; version control ships only
`config/endpoints.example.json`).

Resolution order: CLI flag -> environment variable (`CONFLUENCE_URL`,
`GITLAB_URL`) -> `config/endpoints.json` -> fail with instructions. There is no
hardcoded fallback.

When a script reports a missing endpoint, ask the user for the internal URL,
confirm it, then persist it:

```bash
python3 scripts/update_confluence_release.py --set-endpoint confluence_url=<url>
python3 scripts/update_confluence_release.py --set-endpoint gitlab_url=<url>
```

Keys: `confluence_url`, `jira_url`, `gitlab_url`, `git_ssh_base`. Do this also
when the user says an environment changed or a URL is wrong.

## Step 1: Check zjira config and binary

**Config check first:**
```bash
[ -f "$HOME/.config/zjira/config.yaml" ] && echo "configured" || echo "missing"
```

If the config file is missing → stop immediately:
> "zjira is not configured. Run `zjira init` to set up your Jira URL and token, then try again."

**Binary check:**
```bash
ZJIRA=$(command -v zjira || echo "$HOME/.local/bin/zjira")
"$ZJIRA" --help >/dev/null
```

If the binary is not found → stop:
> "zjira not installed. Install the zjira CLI and make sure it is on `PATH`."

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
   rg -l "KEYWORD" --type java | head -20
   ```
   Use 2-3 keywords extracted from the ticket summary/description.

2. **Existing patterns**: read 1-2 representative files to understand code style, naming, and structure relevant to the change.

3. **Types/interfaces**: if the ticket involves a new entity or modifies an existing one, find where related types are defined.
   ```bash
   rg -n "class RelatedType|interface RelatedType|record RelatedType" --type java | head -10
   ```

4. **Test patterns**: find 1 existing test file in the relevant package to understand how tests are written.

Limit exploration to 5-8 targeted searches. Do not read the entire codebase. Stop when you have enough to identify which files will likely change.

## Step 5: Synthesize and write plan

Derive the git branch name from KEY and Summary:
- `TASK_TYPE == Bug` → prefix `fix/`
- `TASK_TYPE == Story` or `Task` or `Sub-task` → prefix `feat/`
- Slug: lowercase the first 4-5 meaningful words of Summary, replace spaces with `-`, strip special chars
- Example: `KEY=CTJ-4242`, Summary="[BE] Add OAuth redirect handler" → `feat/CTJ-4242-add-oauth-redirect-handler`

Read [`references/plan-templates.md`](references/plan-templates.md) and use the template that matches `TASK_TYPE`.

Create the directory and write the file:
```bash
mkdir -p .kit/plans/{date}-{key-lowercase}
```
Then write `PLAN.md` with the Write tool.

## Step 6: Present the plan

After writing the file, print the full plan content in chat so the user can read it without opening the file.

Then add exactly this footer — no more:

```
Plan written to .kit/plans/{date}-{key-lowercase}/PLAN.md

To implement: say "implement this plan". After implementation, run `/check` before merging.
When done coding: `/9to5-logwork day` to log your hours.
```

Do not ask for approval — the user will indicate readiness by saying "implement this plan" or equivalent.

## Error handling

| Error | Action |
|-------|--------|
| Config missing (`~/.config/zjira/config.yaml`) | Stop: "Run `zjira init` to configure zjira" |
| zjira not found | Stop: "Install the zjira CLI and make sure it is on `PATH`" |
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
