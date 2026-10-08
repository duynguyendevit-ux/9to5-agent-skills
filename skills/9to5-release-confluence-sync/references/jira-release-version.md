# Optional same-day Jira Release Version bump

Use when a release task supplies a Jira project-version link/ID or explicitly
configures Jira version synchronization. A request to update this skill defines
future behavior; it does not authorize updating the supplied live Jira version.

This reference handles **explicit metadata changes**. A request to add only a
Confluence release-version note uses [the overall-link branch](jira-release-link.md)
instead; supplying a URL alone does not select a date/state bump.

## Resolve and inspect

1. Reuse the auth skill's separate Jira resolver/status check. If missing or 401,
   provide its masked `access.py login jira` command for the user's terminal.
   Confirm the Jira project and destination from the supplied link or task context;
   match it to the configured Jira origin before sending credentials. Confluence
   authentication does not prove Jira access. A Jira issue key is not required to
   manage a project version.
2. Parse an explicit `/projects/<PROJECT>/versions/<ID>` link and GET
   `/rest/api/2/version/<ID>`. Verify ownership using
   `/rest/api/2/project/<PROJECT>` and its project ID. An explicit version ID is
   scoped to that release run, not a permanent default for future dates.
3. Without an ID, list the project's existing versions using the deployed API
   (Server/DC `/rest/api/2/project/<PROJECT>/versions`, or its paginated equivalent).
   Verify the actual project naming convention, e.g. `Release_DD/MM/YYYY`; find
   the requested release day from that convention and metadata. Do not hardcode
   a real project/ID or select newest-modified/highest-ID arbitrarily. Paginate
   when the endpoint requires it. Multiple matching versions require resolution.
4. Compare `name`, `releaseDate`, `released`, `archived`, `startDate`, description
   and project identity. A name/date disagreement is an explicit mismatch, not
   proof of a timezone offset; propose the intended date only when supported by
   the requested release day. Use ISO calendar dates, not a timestamp converted
   via the agent machine's timezone. Check
   `/rest/api/2/version/<ID>/relatedIssueCounts` and
   `/rest/api/2/version/<ID>/unresolvedIssueCount` when supported.

If no matching existing version exists, report `Skipped — no version for this day`
and continue the Confluence release. Creating a version requires its own explicit
scope and approval. Auth/network/permission failure is `Unverified`/`Blocked`, not
version absence. Treat archived versions and ownership/date conflicts as unresolved
rather than modifying them automatically. Partial count coverage stays explicit.

## Propose only the requested version fields

For a daily bump, prepare `releaseDate` → the explicit release day when it differs.
Preserve the version's name, description, `startDate`, `archived` and `released`
unless their changes were separately requested and reviewed. If all approved
fields already match, perform a verified no-op.

Publishing a Confluence plan does not mean PROD was deployed and does not set
`released = true`. A Jira release-state change needs an explicit reviewed request;
if described as marking deployed PROD, obtain deployment confirmation. Report
unresolved issue counts before that approval. Even when approved to mark Released,
keep issue statuses and fixVersions unchanged: release-version metadata, deployment,
issue completion and issue membership are separate operations.

Present the Jira operation alongside the Confluence draft when both are in scope:

| Project | Version ID | Name | Field | Before | After | Action |
| --- | --- | --- | --- | --- | --- | --- |
| DEMO | 12345 | Release_15/01/2030 | releaseDate | 2030-01-14 | 2030-01-15 | proposed date correction |

Include `released`/`archived` preservation and issue-count warnings in the local
review. Retain the user's title/table-only Confluence layout; do not add Jira audit
sections, URLs or missing-version notes to that page as an incidental side effect.

## Review, write and recovery

- Save an approved-plan candidate locally: Jira destination identity, project/version
  ID, requested date, source-field hash, exact before/after fields and payload hash.
  Keep token values and raw sensitive descriptions out of manifests/served previews.
  Hash protected description content instead of exposing it unnecessarily.
- Show the dry run before approval. An approval for Confluence-only content does
  not authorize a newly added Jira write. A combined approval covers Jira only
  when the reviewed plan explicitly includes that destination and those fields.
  Reuse approval for an unchanged combined plan; filling missing IDs, changing the
  version/date or adding `released=true` requires revised review.
- Immediately before `PUT /rest/api/2/version/<ID>`, re-read identity and all reviewed
  fields/hashes. Stop on drift; send only the reviewed writable fields using Jira's
  own PAT. Do not send Confluence page version numbers to Jira. The standard Jira
  version API lacks the Confluence-style version-number compare-and-swap gate:
  re-read detects prior changes but cannot eliminate a concurrent-write race.
  Keep the payload narrow, verify afterwards and report that limitation.
- After the acknowledged PUT, checkpoint the returned ID before verification.
  GET that ID and confirm exact approved changes plus protected metadata and project
  ownership. For approved Released-state changes, verify `released` explicitly.
  Check issue counts/membership read-only if they were part of the approved evidence;
  detect changes, do not repair issue data or silently undo another user's work.
- An uncertain request outcome triggers read-back, not blind replay. Track Confluence
  and Jira receipts separately. Confluence succeeded + Jira failed is partial
  publication, not complete success and not permission to roll either system back.
  Resume only pending approved operations with matching base evidence.

Report Jira status separately: `Review ready`, `Skipped`, `Unverified`, or
`Applied — verified`, with the actual project/version URL after success. A recorded
date bump is metadata synchronization, not proof of deployment. Neither the release
sync engine nor the auth/login CLI currently applies Jira version updates; this
branch uses explicit Jira REST reads and reviewed writes, never an undocumented
`zjira` command or an unapproved creation.
