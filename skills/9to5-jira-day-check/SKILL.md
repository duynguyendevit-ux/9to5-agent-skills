---
name: 9to5-jira-day-check
description: "Perform a daily Jira and workflow status check — sprint issues currently in progress or assigned, missing worklogs for the current week, and pending release tag synchronizations. Use for morning standups, daily summaries, checking weekly worklog status, or when the user says 'hôm nay còn gì', 'check sprint', 'standup', 'tóm tắt đầu ngày', 'kiểm tra công tuần này', 'sáng nay làm gì'."
license: MIT
metadata:
  version: "1.0.3"
---
# Jira Day Check

## Example output

Illustrative daily summary; a skipped source is not an empty result.

```markdown
## Sprint
| Key | Summary | Status |
|---|---|---|
| DEMO-123 | Retry report exports | In Progress |

## Worklogs (week of 2026-09-21)
| Day | Logged | Missing |
|---|---|---|
| Monday | 8h | 0h |
| Tuesday | 6h | 2h |
| Wednesday | 8h | 0h |
| Thursday | 4h | 4h |
| Friday | 0h | Future day |

## Releases pending
Skipped: release endpoint unavailable; pending status is unknown.
```

Read-only summary. Do not log work, transition issues, or write Confluence from this skill.

## Steps

1. Auth sanity:
   ```bash
   ZJIRA=$(command -v zjira || echo "$HOME/.local/bin/zjira")
   "$ZJIRA" whoami --json | head -5
   ```
   On 401/error: stop and ask the user to run `zjira whoami`.

2. Assigned sprint issues:
   ```bash
   $ZJIRA issue list --jql "sprint in openSprints() AND assignee = currentUser() ORDER BY updated DESC" --limit 20 --json
   ```
   Render `| Key | Summary | Status |`. If the JQL fails (no Agile boards), fall back to
   `$ZJIRA issue list --days 7 --limit 20 --json` and say so.

3. Worklogs for the week:
   ```bash
   $ZJIRA weekstatus
   ```
   Extract per-day logged hours vs the 8h target; list missing days.

4. Pending releases (dry run only):
   ```bash
   S=~/.config/opencode/skills/9to5-release-confluence-sync/scripts/sync_release_tags.py
   python3 "$S" --project dev-product
   python3 "$S" --project dev-user
   ```
   Collect rows with `update:` status. Skip this step if the tooling or project
   configs are unavailable, and note the skip.

## Output

```
## Sprint
| Key | Summary | Status |

## Worklogs (week of <date>)
| Day | Logged | Missing |

## Releases pending
| Project | No | Service | Tag |
```

Keep it to the three sections; no preamble, no suggestions.
