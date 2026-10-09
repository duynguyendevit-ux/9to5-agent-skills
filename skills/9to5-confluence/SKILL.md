---
name: 9to5-confluence
description: Work with Confluence pages generally — find, read, create, edit, move, comment, label or attach files. Also use for per-service ENV tables, comparing release-record values with code defaults, or filling missing ENV values from code. Reads use zjira; writes use the Confluence REST API with dry-run, content-bound approval and read-back verification.
license: MIT
compatibility: Requires Python 3, PyYAML, sibling 9to5-confluence-auth, the zjira CLI and Confluence PAT credentials. Reads non-secret endpoints from config/endpoints.json. Writes require --apply --approved.
metadata:
  version: "1.5.0"
---

# Confluence

## Example output

Illustrative update preview; show the full replacement body/diff as well as this summary.

```text
Page: Example design (ID 12345)
Base version: 7
Action: replace storage body; target version 8
Changes: add retry policy; preserve existing API section
Mode: dry run — no remote write
Apply requires the reviewed body, --expected-version 7, --apply --approved.
```

Two tools, one discipline: **zjira for reading, REST for everything else, and no write
without a dry run and explicit approval.**

| Task | Tool |
|---|---|
| Find a page by title, label, space, or ancestor | `zjira confluence search` or `scripts/confluence.py search` |
| Read a page | `zjira confluence get` |
| Children, ancestors, labels, comments, attachments | `scripts/confluence.py` |
| Create, update, comment, label, attach | `scripts/confluence.py` (dry run first) |

Sibling skills own the specialised page shapes: `9to5-confluence-doc` writes Vietnamese
Platform design pages, `9to5-release-confluence-sync` owns release tables,
`9to5-release-audit` snapshots release records, `9to5-jira` reads ticket specs.

## Reading with zjira

```bash
zjira confluence get 12003                     # by page ID
zjira confluence get 'https://<confluence>/display/DEMO/268.+22.09.2026'
zjira confluence get <ref> --md                    # markdown, skip the picker
zjira confluence get <ref> --json                  # raw JSON for parsing
zjira confluence search 'release' --limit 50       # plain search; without a TTY this lists matches instead of opening the picker
zjira confluence search 'prod' --json              # structured results
```

- Any Confluence URL works: `?pageId=`, `/display/SPACE/Title`, or a bare ID.
- Without `--md`, an interactive shell shows a picker; in a non-interactive shell pass
  `--md` or a full ID so nothing waits on input.
- `search` takes a plain string, not CQL. For CQL, use the script below.

## Finding a page when you only know part of the title

`scripts/confluence.py search` takes real CQL. Recipes:

```bash
S=~/.config/opencode/skills/9to5-confluence/scripts/confluence.py

python3 "$S" search --cql 'space = DEMO and title ~ "release PROD"'
python3 "$S" search --cql 'space = DEMO and ancestor = 12004 and type = page'
python3 "$S" search --cql 'label = "spec" and space = DEMO'
python3 "$S" search --cql 'text ~ "outbox pattern" and lastmodified > now("-30d")'
```

CQL notes that save a round trip:

- `title ~ "x"` is a full-text match on the title, not a prefix match.
- `ancestor = <id>` searches the whole subtree; `parent = <id>` searches direct children only.
- CQL results are paginated: the script follows `_links.next` up to `--limit`.
- Sorting is not stable across edits unless you add `order by lastmodified desc`.
- Escape embedded quotes by doubling them inside the string.

## Reading and writing with the script

```bash
python3 "$S" get      --page 12003 --body       # metadata + body
python3 "$S" children --page 12004               # direct children
python3 "$S" ancestors --page 12003             # breadcrumb
python3 "$S" labels   --page 12003              # current labels

# writes: dry run first, always
python3 "$S" create --space DEMO --parent 12004 \
    --title 'New page' --body-file /tmp/page.html
python3 "$S" update --page 12003 --expected-version <base-version> --body-file /tmp/page.html
python3 "$S" comment --page 12003 --text 'Reviewed, one question below.'
python3 "$S" set-labels --page 12003 --add spec,review
python3 "$S" attach --page 12003 --file /tmp/report.pdf
```

Every write prints the exact request it would send, then stops. To actually write:

```bash
python3 "$S" update --page 12003 --expected-version <base-version> --body-file /tmp/page.html --apply --approved
```

`--apply` without `--approved` is refused. Show the dry-run output to the user and get
approval for that exact plan before adding the flags.

## Page bodies are storage format, not markdown

Confluence stores XHTML ("storage format"). `--body-file` expects that, unless you pass
`--format wiki` to send wiki markup instead. Element reference, code macro, panels, and
tables: `references/storage-format.md`.

Two things that break silently:

- **A body that is not valid storage XHTML still saves**, and the page renders wrong.
  After a write, re-read the page and check the result rather than assuming.
- **Tables and highlights need the attributes Confluence expects** — a highlight is
  `class="highlight-<color>"` plus `data-highlight-colour="<color>"`, because Confluence
  renders from the class. The release skills already encode this; do not invent a variant.

## Publication verification

For a per-service ENV page, an update from a dated PROD release, or replacing
missing-note values with code defaults, follow
[service ENV pages](references/service-env-pages.md). This branch keeps recorded
PROD overrides, code defaults and runtime evidence separate; it does not edit
deployment configs or the source release page as a side effect.

For cell/column edits, missing colgroup repair or storage-width normalization,
read [offline table helpers](references/storage-tables.md) and reuse
`scripts/storage_tables.py` before writing a one-off transformer. Unsupported table
layouts fail explicitly; preserve protected cells/macros and validate the full body.

For page publication, image attachments, moves or a failed post-write check, follow
[`references/publication-verification.md`](references/publication-verification.md).
It separates storage text from rendered labels, verifies link targets without
depending on optional HTML attributes, and resumes partial publication from saved
state. Reuse the offline helpers in `scripts/publication_checks.py` for page-link
matching, flat HTML table text and approved source/image hash checks; they perform
no network calls. Parse `body.view` as HTML, not storage XHTML.

## Collapsible groups and moves

When the user wants a separate collapsible group in the page tree, plan the parent
and children before writing. Use a native folder only when the deployed API supports
it; otherwise describe a parent-page container, not a filesystem folder. Keep
business notes outside the sequence group and link to the detailed pages when that
is the requested structure.

Moving a page is a separately approved hierarchy operation. The current helper has
no `move` subcommand: prepare a REST PUT with the pinned `version.number`, the new
`ancestors` parent ID and the unchanged `body.storage`, title and page ID. If the
container is new, put its placeholder ID in the dry run and substitute only the ID
returned by the approved create. Preserve attachments; verify the destination's
direct children and the page's ancestors before declaring the move complete.

## Concurrency

Updates require `--expected-version`: the version returned when you read the original
body used to prepare the replacement. Use the same value and unchanged reviewed body
for dry run and apply. The script refuses a different current version, then submits
`expected + 1`; Confluence rejects a race after that check. Do not obtain a fresh
version just to attach it to a stale body. On conflict, re-read, rebase the change,
and review the new body before retrying. JSON request previews are printed in full.

## Endpoints and credentials

Use `9to5-confluence-auth` before service reads/publication and whenever auth is
missing. It loads dotfiles without printing secrets, checks Confluence itself,
and uses the verified `zjira init` entry point for authorized interactive login.
`zjira whoami` checks Jira only. The REST helper shares this credential resolver;
malformed YAML/JSON is a blocker rather than a silently ignored override.

```bash
python3 ~/.config/opencode/skills/9to5-confluence-auth/scripts/auth.py --check \
  --endpoints ~/.config/opencode/skills/9to5-confluence/config/endpoints.json
```

Internal hostnames never live in this skill. They come from `config/endpoints.json`
(gitignored; the repository ships `config/endpoints.example.json`) or the zjira config.

Resolution order: CLI flag → environment variable → `config/endpoints.json` → zjira
config → actionable error. There is no hardcoded fallback. To persist a value:

```bash
python3 "$S" --set-endpoint confluence_url=<url>
python3 "$S" --set-endpoint confluence_space=<KEY>
```

The token is read from `~/.config/zjira/config.yaml`, or from
`~/.config/opencode/release-sync.json` if you already keep it there. Never print it, never
write it into a page, a snapshot, or this repository.

These paths honor `$XDG_CONFIG_HOME` when set. PyYAML is required for YAML parsing.

## Safety

- Read-only until the user approves a specific write. Dry run, show, ask, then apply.
- Never delete a page or a comment as a side effect of another task.
- Never paste secrets, tokens, or internal hostnames into page content.
- Space-wide or hierarchy-wide edits (renaming, moving, bulk labelling) are their own
  task with their own approval, not a step inside another one.
- If the page is a release table or an Platform design document, use the sibling skill that
  owns its structure instead of editing it by hand.
