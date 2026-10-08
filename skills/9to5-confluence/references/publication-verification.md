# Publication verification and recovery

Use for publishing pages/images, moving pages, or investigating a check that failed
after a remote write. Verification is read-only; a failed check is not permission
to repeat a create, upload or PUT.

## Pin the contract before writing

Record the approved local Markdown, storage bodies and attachments with hashes;
pin the page ID, title, space, original version and parent chain. Validate all
check inputs locally before the first write. A creation plan may use a placeholder
for a new ID; resolving that placeholder does not authorize changing content or
using a newer version for an existing page.

Keep a checkpoint after each acknowledged write: action, returned page/attachment
ID, resulting version and status (`created`, `uploaded`, `updated-unverified`,
`moved-unverified`, `verified`). Persist the acknowledgement before the next check
so a verification failure cannot hide a completed write. Distinguish a rejected
write from a transport timeout with an unknown outcome; re-read before retrying.

## Verify at the right layer

| Contract | Evidence |
| --- | --- |
| Page identity | GET the known ID; check title, space, expected resulting version and ancestor chain. |
| Saved prose | Compare normalized storage text, headings, tables, source links and macros with the approved body. |
| Unchanged content on a move | Compare the saved storage body hash with the original snapshot; investigate a mismatch instead of silently rewriting it. |
| Rendered diagram labels | Check the reviewed Mermaid/source label, its render-manifest hash and the downloaded PNG hash. Labels in a raster image are not storage prose. |
| Images | Match storage attachment references to approved filenames and attachment IDs; check downloaded bytes/size/hash and server-view image URLs. |
| Page links | Check the link's actual target using page ID or same-origin page URL; optional HTML attributes are supplementary evidence. |
| Collapsible group | Check the parent container's direct children and each moved child's ancestors; business notes stay outside when requested. |

`body.view` is server-generated HTML, not a live browser. Report storage, server-view,
attachment and live-browser verification as distinct coverage levels. A missing
optional view attribute does not invalidate otherwise verified saved content;
missing/wrong targets, broken image references or hash mismatches do.

For table transformations and narrow numeric col-width normalization, reuse
[offline storage-table helpers](storage-tables.md). Compare the whole body;
keep field values, hrefs, macro parameters and geometry significant. The bounded
width tolerance handles formatting/rounding, not an actual column-layout change.

## Page links without brittle HTML assumptions

Reuse `scripts/publication_checks.py::has_page_link` to match anchors in a saved view.
It accepts a same-origin `pageId` URL even when `data-linked-resource-id` is absent.
Friendly `/display/<space>/<title>` routes can be matched using the known page's
space/title or its resource ID. Treat explicit conflicting IDs, wrong origins,
attachment resource types and unresolved links as failures. Link text alone does
not establish the target. GET the target ID separately to verify that it exists
and has the expected identity; matching the HTML anchor does not perform that GET.

For rasterized labels, reuse `verify_diagram_label` with the source and image hashes
from the approved render manifest. The helper only checks a label against unchanged
source and bytes; the prior render check establishes the source/image relationship.
If the diagram was approved for placement on a shared page, check its label there,
not in the short business note that contains only the page link.

## Recovery after a failed check

1. Stop further writes. Save which operations were acknowledged and which outcomes
   are unknown; report partial publication when it remains unresolved.
2. Re-read those exact IDs, versions, bodies, parents and attachment metadata. For
   an unknown create outcome, search the approved title in the approved space and
   read the result instead of creating a duplicate.
3. Compare remote state with the unchanged approved plan. If the write succeeded
   and the check incorrectly assumed a raster label was prose or required optional
   HTML markup, fix only the verifier and repeat the read-only verification.
4. Resume only pending, originally approved operations after all their base versions,
   hashes and destination scope still match. Keep completed operations skipped.
   Concurrent edits, changed content or a different hierarchy require re-read,
   rebase and a new dry run/approval; do not roll back someone else's work.
5. Mark complete only when every approved destination, link and attachment has
   passed its applicable checks. A grouping/move-only operation keeps the page ID,
   title and attachments so existing note links remain valid.
