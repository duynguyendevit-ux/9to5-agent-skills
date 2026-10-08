# PROD: compare each service's previous and target version

Run this branch for every PROD creation or version promotion, including an explicit
image list. Formatting-only corrections retain the comparison already approved.
The result is a source-backed old/new table plus a pinned local evidence manifest.

## 1. Resolve the baseline per service

1. Identify the actual PROD root and variant (project, region/device generation when
   applicable). Paginate its release history, including direct daily children and
   monthly descendants. Order by release date/explicit release sequence, not last
   modified time or the numerically greatest tag. Exclude the active draft and
   future releases. Record same-day ordering when needed; unresolved ties are conflicts.
2. Match by project + repository + deployed service/image identity + tag series.
   Resolve aliases from repository/CI evidence. `No` and `Order` are display fields;
   a plain `Branch = develop` is not repository evidence. A repository may produce
   multiple migration images; keep each image/service identity separate.
3. Walk backward for each requested service until its latest eligible prior record
   is found. A sparse release page that omits a service does not erase its last
   known version. Preserve rollback history: a later v8 supersedes an earlier v9.
4. Use that record's **Release Tag**, not its `current version` (which describes an
   even older baseline) or an arbitrary tag from the row. Resolve columns by header.
   Save the tag's link and repository, plus the separate Docker image value.
   Cross-check visible tag text against the link target; conflicts remain unresolved.
5. Capture source page ID/title/version, release date, body hash and row identity.
   Empty/conflicting fields on the latest matching row are `Unknown`/`Conflict`:
   an older known row may be shown as historical evidence, but is not silently
   promoted over a newer ambiguous release. If no row exists in the searched
   history, classify `New service` only with explicit first-release evidence;
   otherwise use `Unknown baseline` and report the history search coverage.

The baseline is **previous recorded PROD release**, not proof of deployment.
`Pending`, cancelled or failed records do not establish successful deployment.
Report their status in local review evidence. When the user asks for the actually
running baseline, use timestamped read-only runtime image/digest evidence separately;
reconcile any difference before calling it the deployed version. Never substitute
STG, a local checkout, newest Git tag or today's target for missing PROD history.

## 2. Pin exact targets and compare source

- Preserve the user's exact image path/tag. Resolve the Git release tag independently
  from repository/CI evidence; Git and image tags can differ. Verify requested Nexus
  images and both old/new Git refs, peeling annotated tags to commit SHAs. Capture
  image digests when available. A digest mismatch on an unchanged tag is a distinct
  artifact change, not `Unchanged`; unavailable digest evidence remains unverified.
- Classify `Unchanged`, `Upgrade`, `Rollback`, `Diverged`, `New service`,
  `Unknown baseline`, or `Conflict`. Commit ancestry determines forward/backward
  direction; tag-number ordering alone does not. Different tags at the same commit
  are a retag, with image comparison still required. Missing history/refs means
  direction and source diff remain unverified; do not turn a Git error into no change.
- Use a read-only temporary clone/object store when commits are absent locally;
  preserve user worktrees and branches. Resolve refs to SHAs before passing them
  to Git. With both SHAs present, inspect:

  ```bash
  git merge-base --is-ancestor OLD_SHA NEW_SHA
  git merge-base --is-ancestor NEW_SHA OLD_SHA
  git rev-list --left-right --count OLD_SHA...NEW_SHA
  git log --oneline OLD_SHA..NEW_SHA
  git diff --stat OLD_SHA NEW_SHA
  git diff --name-status OLD_SHA NEW_SHA
  ```

  For rollback/divergence also inspect `NEW_SHA..OLD_SHA` for removed commits.
  Use the two-endpoint diff `OLD_SHA NEW_SHA` for released-tree changes; a three-dot
  diff only describes changes since merge base and can omit removed behavior.
- Inspect relevant changed API/proto contracts, config/ENV and migration paths at
  those exact revisions. Separate ENV additions/removals/value changes; mask secret
  values. List added/modified/deleted SQL scripts and schema/data impacts supported
  by the diff. Source changes do not prove which migrations have executed in PROD.
  API/runtime compatibility conclusions require evidence beyond commit subjects.
- If the old tag is unknown, describe the new target as verified only where supported;
  do not call every target file/ENV key a new change since the previous release.

## 3. Review and page fields

Present a compact comparison for every requested service, including unchanged and
unresolved entries:

| Service | Previous PROD Release Tag | Previous Docker image | Target Release Tag | Target Docker image | Change | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| example-api | v1.2.3 | example/api:build-23 | v1.2.4 | example/api:build-24 | Upgrade | Prior page ID/version; old/new SHAs; Nexus result |

Save a local manifest containing hierarchy, release date, per-service baseline
provenance, old/new tag/image/commit/digest evidence, classification, changed-file
summary and unresolved issues. Pin every baseline source page, not just one template.
Keep credentials and raw sensitive config out of the manifest and review server.

For a new release page, map the verified previous **Release Tag** (and its link when
available) into `current version`; put the target in `Release Tag` and `version`
when that field is used. `Docker image` is the exact target artifact. Unknown old
values remain blank on the page and explicit in the local comparison. On an active
same-day draft, retain its pre-release `current version`; do not roll the pending
target into the baseline during a formatting edit or a re-review.

Use the requested clean PROD layout: title + release table, numeric `No`/`Order`,
migration first, then app, then dmz, preserving order within each group unless
source-backed dependencies require an explicitly reviewed order. `Branch` names the
agreed branch (for example `develop` when confirmed), not `repo @ SHA`. ENV cells use
YAML `- name: KEY` / `value: 'string'` code blocks. Keep audit prose, source details,
missing-image ENV dependencies and comparison caveats in the local review, not new
page sections. Release Note still follows the new-ENV-only policy; all other fields
and secrets retain the publication workflow's protections.

Include a separate `DEV CHECK` column after `Test` in the clean PROD release table.
For existing pages, add it only within the requested/reviewed scope; if already
present, preserve its values rather than inserting a duplicate. New service cells
start blank unless an explicit dev-check result was supplied or observed. Git/Nexus
existence, Confluence publication, Jira Released state and the `Test`/`Status` fields
do not prove dev verification. Keep headers, cell highlighting and all other fields
unchanged when adding this column; include the new cells in approval/read-back.
Update matching colgroup geometry as part of a reviewed column insertion; for an
existing known omission, use the shared Confluence table helper's explicit repair
before inserting another column. Header/cell/colgroup counts must agree.

### Service and Branch source links

Apply this source-link contract to release tables generally, including link-only
updates. `Service` displays the deployed service name and links to its verified
GitLab code repository root. `Branch` displays the agreed branch name and links
to `<repository>/-/tree/<URL-encoded-branch>`. For confirmed `develop`, link to
`/-/tree/develop`; do not add explanatory prose or replace it with `repo @ SHA`.

Resolve the GitLab **web base** from trusted configuration or ask when missing;
SSH host/port, API base, registry authority and web base are separate facts. Keep
real endpoints in local config, not skill text. Validate the repository using
per-service remote/CI evidence and branch existence via read-only Git discovery.
Use `scripts/source_links.py` to build escaped storage anchors from that mapping;
the helper constructs URLs but does not verify repository or branch existence.
An API PAT is unnecessary when Git SSH provides the required verification.

Match project/group and repository explicitly. Twin Product/User services, misspelled
repository names, portals and migration image paths can differ from their displayed
runtime service names. Multiple images from one repository may share its source
link but remain separate service rows. Missing/conflicting mappings remain
unverified; expose them in local review rather than guessing links.

For link-only corrections, preserve `Service`/`Branch` text, highlight attributes,
row ordering, tags, `current version`, images, ENV code blocks and all other cells.
Include the exact destinations and source URLs in the approved diff; neither
previous page publication nor a skill edit authorizes remote link changes.
After saving, check anchor labels and hrefs by column/service identity, confirming
both links name the same intended repository and the branch path is correct.
A mutable branch link is navigation, not evidence of the released tag's commit.

## 4. Approval and verification

Before publication, the comparison must account for every requested service with
either an evidenced baseline or an explicit unresolved classification. Include
unresolved items in the reviewed plan; filling them later changes the plan.
Re-read all baseline page versions/hashes and the destination, and re-check mutable
Git refs/image evidence used for the approved targets. Material drift requires a
new review, not a silently refreshed baseline. Apply only the saved approved body.

After publication, verify each service's old/new mapping, tags/images, numeric order,
branch, ENV YAML values, protected fields and highlights. Save the returned page ID,
version and body hash in the manifest for the next release. Mark it as a published
release record; deployment confirmation is a separate event.

## Engine boundary

`sync_release_tags.py` currently chooses newest Git tags and rolls over a single
template. It does not reconstruct sparse PROD history, peel/ref-compare both
releases, compute code/SQL/ENV diffs, or persist this comparison manifest. Complete
the workflow above read-only and publish its reviewed storage body through the
generic Confluence helper. Do not claim an ordinary engine dry run performed these
checks or use it to replace an explicitly pinned target with a newer tag.
