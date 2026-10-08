# Release review and publication

## Release Note: new ENV only

For a new daily release page, clear inherited `Release Note` content on every
service row, including unnumbered service rows. Preserve header/section content.
For an existing page, identify inherited notes from the previous page and clear
the reviewed scope; preserve source-verified ENV notes already added for today.
An explicit user request to clear every row overrides the inherited-only scope.

Populate a note only with an ENV key newly introduced between that service's
previous recorded release and the target version actually approved for this run.
Verify the addition in that repository's version diff or environment-config diff
and cite the path/commit. Uppercase permission names or SQL identifiers are not
ENV evidence. A renamed key, changed existing value, old ENV mention or a newer
Git-only tag not being promoted is not automatically a new ENV addition.

Use `KEY — purpose — required/default — source` when supported by the evidence.
Withhold secrets and sensitive values; never copy complete `.env` or credential
config into review output. If no new ENV additions are verified, leave the note
blank and state that evidence limit rather than claiming no additions exist.

For the separate `Cấu hình biến môi trường` column, follow the explicit-cleanup
branch below. Release Note cleanup alone preserves that column. Report the number
of service rows reviewed and non-empty inherited notes removed.

To verify or complete a service's env vars against its release tag, follow
[env-var verification](env-var-verification.md).

## Cấu hình biến môi trường: clear only on request

Preserve this column by default. When the user explicitly requests clearing its
data, include that operation in the proposed page update; a conditional instruction
such as “clear nếu có yêu cầu” defines future behavior, not an immediate page write.

- Resolve the column by its actual header, not a fixed numeric index. A missing or
  ambiguous header blocks this operation rather than targeting another column.
- Clear all content inside the selected service-row cells, including text, links,
  lists and macros. Keep the column header, cell structure, formatting/highlights
  and section/header rows. Include unnumbered service rows in an all-row request;
  if specific services are requested, preserve all other rows.
- Show the affected services and counts of selected cells and non-empty cells
  cleared in the review. Adding this operation to an already approved plan changes
  its scope and requires approval of the revised body before publication.
- Clear only page data. Preserve Release Note, tags, images and other fields unless
  separately included in the plan; keep source `.env`, configuration repositories
  and deployed environment variables untouched. Keep cleared cells blank instead
  of repopulating them from Release Note or environment files.
- Read back after publication: every approved target cell is empty, while ENV cells
  outside the selected scope and all other protected fields match the source.

## Build a reviewable artifact

Save the full proposed storage body plus a compact field-level diff under the
working repository's `.kit/releases/<request>/` (gitignored), or under
`~/.local/state/opencode/requests/<request>/` when no working repository applies.
Record project/date, page or parent, source ID/version, source-body hash,
reviewed-body hash and exact row/field changes. Engine creation previews
stop before per-service tag discovery; finish that evidence check before approval.

A review artifact should show:

- Release Note cleanup and any source-backed new ENV additions.
- Separately requested `Cấu hình biến môi trường` cleanup, its row scope/counts,
  or an explicit statement that the column is preserved.
- Before/after `current version` values, preserving the corresponding tag links.
- Exact tag/image changes, or an explicit statement that they are preserved.
- Highlight changes and protected same-day highlights.
- Unverified or conflicting repository/tag/image evidence.
- `Review ready — not applied` and the separate current Confluence page link.

When asked for `link review`, return a clickable local/file/HTTP review link, not
only the current Confluence page. For local HTTP, bind to loopback, serve only a
dedicated sanitized review directory, and verify its content once. Keep original
page snapshots, auth/config, private values and receipts out of the served directory.
Do not include private page data merely to make a preview look complete.

## Approval and concurrent edits

Approval is tied to the displayed plan and body hash in the active release-page
workflow. After reviewing that exact draft, `ok push` or `update Confluence`
authorizes its write; `link review` and
`are you done?` only request information. If approval and source still match,
apply without repeating the approval loop. Git repository publication is a separate
task: do not interpret a later skill-repository push as Confluence approval.
Re-read immediately before writing.

For creation, verify the reviewed parent, template version/hash and target-date
absence. If the target appears while waiting:

- An already matching approved body is a verified no-op, not another create.
- A different body requires reading the new page and preparing a rebased diff.
  Preserve concurrent tag/image/current-version changes and their highlights.
  Do not replace the new body with the old clone or attach a fresh version to it.
  Show the revised destination/version/body scope and obtain new approval.

For a baseline rollover on an existing page, copy the previous daily page's
recorded Release Tag into `current version` only for the reviewed still-pending
cells. A same-day new Release Tag belongs to the new release; do not roll it into
current version just because it now differs. Match by service/repository/series,
not row number alone. If a current value differs from both reviewed before and
after values, treat it as a conflict rather than substituting it silently.

Publish only the approved saved body. Custom note/ENV-column edits or a narrow rebased update
use the generic Confluence REST helper's storage-body/version gate, not a fresh
automatic scan that may discover and apply unreviewed tags. Leave unrelated page
cells and user work unchanged. After an uncertain request failure, read the target
before retrying; do not create a duplicate or blindly repeat a write.

## Read-back and completion

After POST/PUT, GET the page by the returned ID. Verify title, space, parent, saved
version, service identities/count, approved notes, rollover values/links and
highlights and any explicitly cleared ENV-column cells. Compare protected
tag/image/ENV fields outside the approved changes to the reviewed source. Check
the saved body against the approved body, allowing only storage serialization
normalization. Report mismatches without retrying or reverting concurrent edits.

Use accurate status:

- `Review ready — not applied`: only local artifacts exist.
- `Blocked`: auth, version/hash, destination or verification prevents completion.
- `Applied — verified`: write succeeded and the approved/preserved fields match.

Mark the review artifact with the saved version after success so its status does
not still say pending. Report changed-row counts and a full Confluence URL on its
own line, using the configured base plus returned page ID. Do not replace that
with a local review URL or infer deployment from publication.
