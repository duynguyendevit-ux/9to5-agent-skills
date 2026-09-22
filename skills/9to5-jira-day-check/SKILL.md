---
name: 9to5-jira-day-check
description: Daily Jira check — current sprint issues assigned to me, worklogs missing this week (zjira weekstatus), and release rows still pending tag sync. Use when the user asks "what's left today", "check my sprint", "weekly status", "morning summary", "standup", or wants a combined view of tickets, hours, and releases.
license: MIT
metadata:
  version: "1.0.0"
---

# Jira Day Check

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
   python3 "$S" --project dev-c7
   python3 "$S" --project dev-c7-ttdvkh
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
