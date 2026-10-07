---
name: 9to5-confluence-doc
description: Draft source-backed Vietnamese API/flow notes and technical pages for local review and approved Confluence publication, with dotfile auth preflight and missing-login handling. Use when asked to document a feature/flow, write or update a Confluence page, or publish reviewed Markdown. Authentication and drafting do not authorize remote writes; release tables belong to 9to5-release-confluence-sync.
license: MIT
metadata:
  version: "1.2.0"
---

# Confluence Documentation Workflow

## Example output

Illustrative draft summary; include the actual proposed storage diff for approval.

```text
Trang: Thiết kế export báo cáo (ID 12345, phiên bản 7)
Trạng thái: Bản nháp — chưa ghi Confluence
Bối cảnh: Export lớn cần xử lý nền và theo dõi tiến độ.
Phạm vi: Tạo job, xem trạng thái, tải kết quả.
Thiết kế: API đăng ký job; worker xử lý và cập nhật trạng thái.
Cần xác nhận: Thời gian giữ file và giới hạn số job mỗi khách hàng.
Thay đổi dự kiến: Bổ sung mục Xử lý lỗi và Rollout; giữ nguyên phần API.
```

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

The user's requested sections and removals take precedence over this template. Keep
API references and focused flow notes focused; do not restore deleted examples,
scope, rollout or processing prose just because the default template lists them.

## Source-backed notes and local review

For documentation derived from code, follow
[`references/source-backed-review.md`](references/source-backed-review.md).
It covers observable API behavior, asynchronous handoffs, cache/Web configuration,
safe config inspection, and inline diagrams.

When a review folder is requested, save the Markdown there before presenting the
review link. That file becomes the publication source; temporary storage HTML and
rendered images are derived artifacts. Further edits belong in the review file,
not in a second draft. Local edits do not authorize remote writes.

## Read and search

Resolve/check credentials with `9to5-confluence-auth` before fetching existing
pages or planning publication. Its helper loads dotfiles and checks Confluence,
not merely Jira. If the user authorized login when auth is missing, use its
`--check --login-if-needed` path; non-interactive shells report the verified
`zjira init` command instead of prompting for a PAT in chat. Valid auth stays intact.

```bash
ZJIRA=$(command -v zjira || echo "$HOME/.local/bin/zjira")
$ZJIRA whoami --json                       # Jira auth only; not Confluence proof
$ZJIRA confluence get <pageId|url> --md
$ZJIRA confluence search "<title>" --json  # title URLs without a page ID
```

## Write safety

Use `9to5-confluence` for REST commands, attachments and concurrency handling.
Every remote write uses a dry-run plan, content-bound approval, and verification:

1. Resolve exactly one page; GET `body.storage`, `version`, `title`, `space`.
2. Generate storage from the latest review file, preserving untouched page sections.
   Record the source/body/attachment hashes and original page version. Validate
   XHTML and inline diagram references before generating the dry run.
3. Show the proposed content/diff and attachment plan; get explicit approval.
   Approval of an older draft does not cover edits made afterward. If the user
   reviews the latest local file and says `ok push`, regenerate the transport
   dry run from that exact file and show its summary; reuse that approval only
   when conversion preserves the reviewed content and the previously reviewed
   attachment scope, destination and base version are unchanged.
4. Check the hashes and original page version again. Upload approved attachments,
   then PUT once using `--expected-version <original-version> --apply --approved`.
   On a conflict, re-read, rebase and review; never substitute a fresh version
   onto a stale body. Report partial uploads if publication stops.
5. GET the page again. Verify version, title/parent, normalized text, table counts,
   image references and attachment names; explicitly check the last user-requested
   additions. Storage checks establish saved content, not live browser rendering.

Secrets: read `confluence_url` / `confluence_token` from
`~/.config/zjira/config.yaml` (or the overlay `~/.config/opencode/release-sync.json`);
the shared auth skill owns precedence and missing-login behavior. Never print or
hardcode the token. For release-table edits prefer the
`9to5-jira` release script and its `--dry-run` / `--approved` flow.
