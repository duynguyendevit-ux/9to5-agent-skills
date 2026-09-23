---
name: 9to5-confluence
description: Work with Confluence pages generally — find a page with CQL when you only know part of its title, read it as markdown, walk its hierarchy, then create, update, comment on, label, or attach files to it. Reads go through the zjira CLI; writes go through the Confluence REST API with the same dry-run and explicit-approval gate as the other skills. Use when asked to find, read, create, edit, move, comment on, or attach something to a Confluence page, or when you need a page's children or labels.
license: MIT
compatibility: Requires the zjira CLI and Confluence credentials in ~/.config/zjira/config.yaml. Reads non-secret endpoints from config/endpoints.json. Writes require --apply --approved.
metadata:
  version: "1.0.0"
---

# Confluence

Two tools, one discipline: **zjira for reading, REST for everything else, and no write
without a dry run and explicit approval.**

| Task | Tool |
|---|---|
| Find a page by title, label, space, or ancestor | `zjira confluence search` or `scripts/confluence.py search` |
| Read a page | `zjira confluence get` |
| Children, ancestors, labels, comments, attachments | `scripts/confluence.py` |
| Create, update, comment, label, attach | `scripts/confluence.py` (dry run first) |

Sibling skills own the specialised page shapes: `9to5-confluence-doc` writes Vietnamese
OTS design pages, `9to5-release-confluence-sync` owns release tables,
`9to5-release-audit` snapshots release records, `9to5-jira` reads ticket specs.

## Reading with zjira

```bash
zjira confluence get 141395368                     # by page ID
zjira confluence get 'https://<confluence>/display/C7GSAFEDA/268.+22.09.2026'
zjira confluence get <ref> --md                    # markdown, skip the picker
zjira confluence get <ref> --json                  # raw JSON for parsing
zjira confluence search 'release' --limit 50       # plain search
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

python3 "$S" search --cql 'space = C7GSAFEDA and title ~ "release PROD"'
python3 "$S" search --cql 'space = C7GSAFEDA and ancestor = 92610522 and type = page'
python3 "$S" search --cql 'label = "spec" and space = C7GSAFEDA'
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
python3 "$S" get      --page 141395368 --body       # metadata + body
python3 "$S" children --page 92610522               # direct children
python3 "$S" ancestors --page 141395368             # breadcrumb
python3 "$S" labels   --page 141395368              # current labels

# writes: dry run first, always
python3 "$S" create --space C7GSAFEDA --parent 92610522 \
    --title 'New page' --body-file /tmp/page.html
python3 "$S" update --page 141395368 --body-file /tmp/page.html
python3 "$S" comment --page 141395368 --text 'Reviewed, one question below.'
python3 "$S" set-labels --page 141395368 --add spec,review
python3 "$S" attach --page 141395368 --file /tmp/report.pdf
```

Every write prints the exact request it would send, then stops. To actually write:

```bash
python3 "$S" update --page 141395368 --body-file /tmp/page.html --apply --approved
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

## Concurrency

Updates carry a version number. The script re-reads the page immediately before the
`PUT` and writes `current + 1`, so a concurrent edit surfaces as a conflict instead of
being overwritten. If a conflict happens, re-read the page, re-apply the intended change
to the new body, and try again — never force the write.

## Endpoints and credentials

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

## Safety

- Read-only until the user approves a specific write. Dry run, show, ask, then apply.
- Never delete a page or a comment as a side effect of another task.
- Never paste secrets, tokens, or internal hostnames into page content.
- Space-wide or hierarchy-wide edits (renaming, moving, bulk labelling) are their own
  task with their own approval, not a step inside another one.
- If the page is a release table or an OTS design document, use the sibling skill that
  owns its structure instead of editing it by hand.
