# Per-service ENV pages: recorded values and code defaults

Use when updating a service's ENV table from a dated release, comparing PROD with
develop, or filling missing recorded values from code. This is a documentation
update; deployment configs, Jira metadata and the source release page are separate
write scopes. Use the existing table, not the API/design-page template.

## Pin source and destination

1. Resolve the requested service page. Record ID, title, space, ancestor chain,
   version and storage-body hash. Read the existing headers, rows and source note.
2. Resolve the requested release date in the correct environment/hierarchy. For
   relative dates, record the absolute date from the session clock; do not select
   by page modification time or the greatest tag. Record the release ID, version,
   body hash, exact service row, tag/image, ENV cell and status.
3. Verify repository identity and resolve the tag to a commit. Compare with a
   freshly fetched develop ref without switching or modifying the user's branch.
   Inspect a clean tag snapshot, including config, Java consumers and changed
   dependencies, following the release owner's
   [env verification](../../9to5-release-confluence-sync/references/env-var-verification.md).
   Tag equals develop does not skip inventory; config-only equality does not prove
   no Java ENV delta. Unreleased branch keys do not belong in the release inventory.
4. Pin historical release-repo/config evidence by commit and path, not a mutable
   branch link. If comment lines mean previously promoted values, establish that
   repository convention first. Conflicting duplicate keys are unresolved evidence,
   not permission to silently choose the last occurrence.

A row marked Pending remains a pending **release record**. A page tag/image and
historical note-env values do not prove what PROD is running. A blank release ENV
cell means no override is recorded there; it is neither a complete ENV inventory
nor evidence that every value equals develop. Preserve known PROD values unless
new source evidence and the requested scope authorize changes.

## Value selection

Keep provenance visible in column labels, per-row annotations or a concise source
note. Distinguish **recorded PROD value**, **code fallback** and **runtime verified**.
For mixed recorded/default values, a label such as
`Giá trị PROD (release repo / default code)` must explain that defaults are not
verified PROD configuration. The develop column remains a separate comparison.

| Existing cell / request | Action |
| --- | --- |
| Recorded non-secret PROD override | Preserve; do not overwrite with develop/tag defaults merely because they differ |
| Exact `Không ghi trong note-env`, user requests code defaults | Fill only these cells from the pinned release tag's explicit default; record source path/line/profile |
| Key not recorded, no fallback requested | Retain the evidence limit; any fallback proposal belongs in the review |
| `Không ghi giá trị`, secret/hidden cell or `Chưa xác minh` | Do not sweep into the missing-note replacement; keep unchanged unless separately scoped |
| No explicit default or conflicting defaults | Retain an unresolved status with the reason; never invent an empty, false or framework default |

Inspect values privately. Never publish secret defaults, resolved credentials or
credential-bearing URLs, even for a missing-note cell. Treat inferred Spring ENV
names as candidates until their binding is traced.

Resolve active profiles, imports, property precedence and consumers before calling
a value **effective**. If the requested key has a default only in a local/inactive
profile, it can be documented as a **source-only default** when explicitly requested,
but flag its profile next to the row or in a note naming that key. Do not claim it
applies to PROD, infer a JVM timezone, or copy the develop display text without
checking the tag. Unknown profile/override/dependency evidence remains a limit.

For a tag-only change, count and report changed tag cells separately from changed
ENV values: `81 tag cells changed; 0 ENV value changes` is not “81 ENV updated”.
Preserve names, order, other columns and values. Remove/keep the updater column as
requested; do not replace it with author details in a note. System-attributed
Confluence version history is not an editable updater column.

## Review, apply and verify

- Reuse `scripts/storage_tables.py` for supported table edits. Save the full body,
  compact before/after values, source evidence and reviewed body hash in a private
  request directory. Exclude secrets from reviews; keep raw snapshots private.
- List value changes, additions/removals, tag changes, header/source-note changes
  and protected fields. Validate the candidate and verifier before the first write.
- A later fallback request produces a **new** body/review; prior approval does not
  carry over. A contextual `push` after the current Confluence review approves that
  unchanged page plan, not git publication. Skill commit/push is a separate scope.
- Re-check source/destination versions and hashes; publish the saved body once with
  the reviewed `--expected-version --apply --approved`. On conflict or changed source
  evidence, re-read and re-review rather than attach a fresh version to stale content.
- Save the acknowledged version before verification. Follow
  [publication recovery](publication-verification.md): check identity/hierarchy,
  storage, table counts, exact requested values and all protected cells. Compare
  rendered flat table text with `scripts/publication_checks.py::html_tables`;
  `body.view` is HTML and must not go through the storage XHTML parser.
- A failed verifier is not permission to repeat PUT. Re-read and repair only the
  verifier when the saved page already matches. Report storage/server-view/browser
  coverage separately, saved version and the full Confluence URL. Publication is
  not proof of deployment.
