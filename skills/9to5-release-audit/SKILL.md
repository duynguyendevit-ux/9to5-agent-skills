---
name: 9to5-release-audit
description: Read-only audit of a Confluence release page. Save a traceable snapshot of recorded service versions and release tags, compare a later page reading with the snapshot, and report recorded release differences without claiming that production is actually running the release. Use when checking what a Confluence release page records, comparing release snapshots, or auditing a production release record.
license: MIT
compatibility: Requires Python 3 and Confluence credentials in ~/.config/zjira/config.yaml or ~/.config/opencode/release-sync.json. Reads non-secret endpoints from config/endpoints.json. Does not require Kubernetes access and never writes Confluence.
metadata:
  version: "1.0.0"
---

# Release Audit

This skill audits the **release record** in Confluence. It does not prove that an
artifact is running in production. A successful result means that the page records
the expected version; runtime deployment requires a separate read-only cluster check.

## Commands

```bash
S=~/.config/opencode/skills/9to5-release-audit/scripts/release_audit.py

# Save the current page record
python3 "$S" snapshot --page '<Confluence page URL or ID>' \
  --output /tmp/prod-release-before.json

# Read the page again and compare it with the saved record
python3 "$S" compare --page '<Confluence page URL or ID>' \
  --before /tmp/prod-release-before.json
```

`--project` is optional metadata and is read from the adjacent `projects.json`
registry. `--page` is required so the audit never guesses between similarly named
release pages. The script accepts a numeric page ID, a `pageId` URL, or a
Confluence `/display/<SPACE>/<TITLE>` URL.

## Snapshot contents

Each snapshot records:

- page ID, title, URL, space, and Confluence page version;
- capture time in UTC;
- service rows and the values found under `Version`, `Current version`, `Release Tag`,
  and `Docker image` columns;
- the source page, so the result remains traceable after later edits.

The snapshot is local evidence. Do not commit it when it contains internal URLs or
production service information.

## Result meanings

| Result | Meaning |
|---|---|
| `RECORDED_RELEASE` | The current page records the expected release tag/version. |
| `RECORDED_CHANGE` | The current page differs from the saved snapshot. |
| `UNCHANGED_RECORD` | The page version and service values are unchanged. |
| `MISSING_SERVICE` | A service existed in the baseline but is absent now. |
| `NEW_SERVICE` | A service appears in the current page but not the baseline. |
| `UNKNOWN` | The relevant cells are empty or the page does not identify an expected value. |

The report must use the wording **recorded in Confluence**. It must not say
`deployed`, `running`, or `production verified` based only on this audit.

## Safety

- All operations are GET/read-only operations.
- There is no `--apply` mode.
- Never print the Confluence token.
- Never treat a Git tag, Docker image cell, or Confluence page edit as independent
  proof that the image is running.

## Endpoint configuration

Resolution order is CLI flag, environment variable, `config/endpoints.json`, then
an actionable error:

```bash
python3 "$S" --set-endpoint confluence_url=<url>
```

The token is read from `~/.config/zjira/config.yaml` or the existing
`~/.config/opencode/release-sync.json` overlay. Real endpoints are local-only;
the repository contains only `endpoints.example.json`.
