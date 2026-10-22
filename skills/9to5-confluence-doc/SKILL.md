---
name: 9to5-confluence-doc
description: "Draft, structure, and publish source-backed technical documentation and system design pages on Confluence in Vietnamese following standard architecture templates. Loads private per-project style profiles and lesson logs so every agent reuses the user's structure and wording and avoids corrected mistakes. Use when writing or editing any documentation page, documenting features or services, writing technical specs, drafting architecture pages, or when the user says 'viết tài liệu confluence', 'tạo doc kỹ thuật', 'soạn thảo tài liệu thiết kế', 'viết spec', 'tài liệu hóa luồng'."
license: MIT
metadata:
  version: "1.4.0"
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

## Profiles and lessons (always first)

Applies to every document: Confluence pages, repo Markdown mirrors, handover
checklists, READMEs written as documentation. Before drafting or editing, follow
[`references/doc-memory.md`](references/doc-memory.md): resolve the private
profile index, load repo `AGENTS.md`/`CLAUDE.md`, the matched project profile and
its lessons, and the cross-project lessons. Their structure and vocabulary
override the default template below.

When the user corrects wording, structure, scope or a fact, or a linter rejects
agent-written text, append a lesson in that file's format before continuing, and
run every lesson's check before presenting a draft or dry run. When a repository
keeps a Markdown file and a storage-format file per page, edit both together and
run the repo linter before any dry run.

## Page structure

Per-service ENV tables use
[Confluence service ENV pages](../9to5-confluence/references/service-env-pages.md),
not the design template below. Preserve the table and requested removals.

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

### Focused flow notes

Write business notes in direct, ordinary Vietnamese: what happens, which records
are handled, the eligibility conditions, and the configuration needed. Use the
user's latest refined page as the vocabulary/structure reference; preserve their
manual wording and removed rows. Describe the business effect, not merely a worker
or method name. Check behavior against source; raise contradictions separately.

For milestone notes, use **milestone summary → one section per milestone → shared
configuration**, unless the user requests a condensed table. Each milestone covers
**xử lý gì, tin nào, điều kiện nào, ENV nào**. In a short business note, list only
variables that change eligibility, routing, processing mode or recovery, using
**variable → effect**. Include defaults only for a requested ENV reference or when
explicitly requested; preserve existing ENV tables outside the refinement scope.
Distinguish delay from polling interval and configurable source filters from fixed
eligibility rules. A cache source-type ENV does not automatically filter DB polling.

When refining a verbose note, retain business actions, eligibility, service handoffs
and requested links. Condense repeated prose and omit implementation inventories,
binding tuning and numbered diagram legends unless needed by the requested audience.
Changing diagram placement/references belongs in the preview; preserve attachments.
For a database note, include only the tables/views used by that feature and explain
what each is used for. For a cache, state the decision or query it serves and why
caching helps; a label such as “cache alarm data” is not a purpose. Related repositories
or an audit of the page tree do not expand the user's business scope.

Keep review/publication status and verification caveats in the conversation or
evidence bundle, not boilerplate “Lưu ý”/“Cần xác nhận” sections in a short business
note. When defaults are requested, label them as defaults rather than deployed values. A full
technical document can still include explicitly requested operational limits.

Keep source provenance in the private review/evidence bundle by default. Add a
page section **Tham chiếu**, **Source code**, or an equivalent reference list only
when the user requests it; renaming the heading does not satisfy an omission.
Preserve explicitly requested inline source links and existing content outside
the authorized edit scope.

For a business-flow note, default to **Tổng quan** and **Luồng cơ bản**,
with only the limits needed to interpret the flow. Set the audience, detail level,
diagram placement and intended page hierarchy before drawing. A full design/API
request still uses its requested structure, not this short-note default.

When asked to match an existing overview, read that reference and the target's latest
content. Reuse its structure, not unrelated business rules: summarize service roles,
communication direction/protocol/purpose, main flow and links to feature notes.
Keep existing diagrams, topic tables and hierarchy outside the approved edit intact.

Put detailed sequences, class-level gates, persistence contracts and source evidence
in a shared technical page; link to it from the business note and back to the note.
For a requested collapsible group, plan a separate sequence parent/container with
the technical pages below it. An explicit request for inline diagrams overrides
this default. Grouping, moving existing pages and replacing a detailed note with
a shorter one all belong in the content-bound dry run; approval of a prior publish
does not authorize these new operations.

## Source-backed notes and local review

For documentation derived from code, follow
[`references/source-backed-review.md`](references/source-backed-review.md).
It covers observable API behavior, asynchronous handoffs, cache/Web configuration,
safe config inspection, and diagrams at the agreed documentation layer.

When a review folder is requested, save the Markdown there before presenting the
review link. That file becomes the publication source; temporary storage HTML and
rendered images are derived artifacts. Further edits belong in the review file,
not in a second draft. Local edits do not authorize remote writes.

For small revisions, reuse existing conversion/publication helpers and keep the
review URL stable when practical. Refresh the latest review from the Markdown;
preserve approval-bound snapshots and checkpoints instead of rewriting evidence.
For a scoped edit to an existing page, use the sibling's
[scoped update tool](../9to5-confluence/references/scoped-updates.md) for text,
sections or table cells; its reviewed patch and derived storage are the source
for that narrow operation. A new/full document still uses the Markdown workflow.

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
    additions using the sibling's
    [publication verification guide](../9to5-confluence/references/publication-verification.md).
    Storage checks establish saved content, not live browser rendering.

Secrets: read `confluence_url` / `confluence_token` from
`~/.config/zjira/config.yaml` (or the overlay `~/.config/opencode/release-sync.json`);
the shared auth skill owns precedence and missing-login behavior. Never print or
hardcode the token. For release-table edits use `9to5-release-confluence-sync`
to prepare the plan and `9to5-confluence` to publish custom approved bodies with
the original `--expected-version --apply --approved` gate.
