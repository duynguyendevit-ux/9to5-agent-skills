# One overall Jira Release Version link

Use this branch when asked to note/link a release version, including a supplied
`/projects/<PROJECT>/versions/<ID>` URL. This is Confluence content work, not a Jira
metadata update or a per-service task map.

1. Resolve Jira credentials through the separate auth helper. Match the provided
   origin to the trusted Jira endpoint before sending credentials; Confluence auth
   does not verify Jira access.
2. GET the exact version ID and its project identity. Preserve the supplied target;
   another version with a similar date/name is not permission to substitute it.
   If no ID was supplied, discover the requested day's existing version and resolve
   ambiguity before drafting. Report absence/access failures accurately.
3. Build one overall `Jira Release Version: <linked verified name>` paragraph before
   the release table when that note was requested. Use
   `scripts/source_links.py::release_version_note` for escaped storage markup.
   Keep version metadata, task membership, ENV, service cells and existing Jira
   macros unchanged. An explicit request to remove old notes is a separate scope.
4. Show that note plus any other requested corrections in the complete sanitized
   preview. Pin page version/source/body hashes; apply the approved body and verify
   both storage and server-view href/label. A link does not prove deployment.

Read only version/project metadata for this branch. Issue counts, unresolved-task
enumeration, commit-to-task mapping and issue membership polling do not establish
a release-version link and unnecessarily expand the work. A name/date mismatch
belongs in local review evidence; linking the explicit verified record does not
authorize fixing its date or changing `released`.

When an overall note is explicitly requested, that note is the scoped exception
to the clean title/table layout. Put no task-by-task notes or new task column on
the page unless that mapping was separately requested.

## Explicit task mapping

Enter only for a request to associate tasks with services. Define the selected
services, Jira version(s) and source range first. Prefer pinned source diffs and
relevant issue reads over scanning every checkout or repeatedly enumerating a whole
release. Commit-message references are evidence of mentions/reachability, not proof
that all task requirements were implemented; state the coverage limits.

Issue membership can change independently of source tags. Re-check only membership
claims actually included in the reviewed content before publication. A browse link
can remain valid after its issue moves to another version: do not treat membership
as a write dependency when the content makes no membership claim. Changed claimed
membership requires corrected evidence/review, not automatic Jira repair. Retain
source-backed links and protected page data; unproven service associations remain
explicitly unverified rather than being guessed from ticket titles.
