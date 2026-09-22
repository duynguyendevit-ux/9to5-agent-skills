---
name: 9to5-confluence-doc
description: Draft and publish Vietnamese technical design pages on Confluence with the OTS structure (bối cảnh, phạm vi, thiết kế, mô hình dữ liệu, API, rollout) using the zjira CLI. Use when the user asks to write or update a Confluence design/spec page (viết tài liệu, tạo page, cập nhật spec), document a feature for review, or pastes content to add to a Confluence page — always dry-run and get explicit approval before writing. Not for release tables — use 9to5-release-confluence-sync for those.
license: MIT
metadata:
  version: "1.0.0"
---

# Confluence Design Doc

## Page structure

Use these headings, in Vietnamese, unless the user asks otherwise:

```markdown
# <Tên tính năng>

## Bối cảnh
## Phạm vi
## Thiết kế / Kiến trúc
## Mô hình dữ liệu
## API
## Xử lý lỗi
## Rollout / Vận hành
## Kiểm thử
```

Rules: read the existing page before editing, keep untouched sections byte-identical,
do not fabricate — mark unknowns as `Cần xác nhận`.

## Read and search

```bash
ZJIRA=$(command -v zjira || echo "$HOME/.local/bin/zjira")
$ZJIRA whoami --json                       # auth check
$ZJIRA confluence get <pageId|url> --md
$ZJIRA confluence search "<title>" --json  # title URLs without a page ID
```

## Write safety

Every write is dry-run first, approval second, verify last:

1. Resolve exactly one page; GET `body.storage`, `version`, `title`, `space`.
2. Compose the new storage body, preserving everything not being changed.
3. Show the diff/summary to the user and ask for explicit approval.
4. PUT once with version `current + 1` — never retry against stale content.
5. GET the page again and verify the new version and content.

Secrets: read `confluence_url` / `confluence_token` from
`~/.config/zjira/config.yaml` (or the overlay `~/.config/opencode/release-sync.json`);
never print or hardcode the token. For release-table edits prefer the
`9to5-jira` release script and its `--dry-run` / `--approved` flow.
