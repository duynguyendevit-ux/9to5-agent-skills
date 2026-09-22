---
name: 9to5-release-confluence-sync
description: Sync a project's daily Confluence release page — create it when missing, update it when it exists — and refresh version, current version, Release Tag and Docker image cells to the newest git tags of the project's service repos; also paint or clear release-row highlights and check pending releases. Projects come from the skill's projects.json registry (dev-c7, dev-c7-ttdvkh). Use when the user mentions a release page, release tag, Docker image tag, dev-c7 or ttdvkh release, asks to prepare today's release page, sync release tags, or check which services still need release.
license: MIT
compatibility: Requires the zjira CLI and Confluence credentials in ~/.config/zjira/config.yaml; GitLab SSH access for tag discovery. Reads non-secret endpoints from config/endpoints.json.
metadata:
  version: "1.0.0"
---

# Release Sync

One engine for every project. Project settings live in a registry file instead of
per-skill hardcoding.

## Projects registry

`projects.json` next to this file:

```json
{
  "projects": {
    "dev-c7": {
      "root": "92618728",
      "group": "c7",
      "space": "C7GSAFEDA",
      "hl_color": "#998dd9",
      "page_link": "",
      "doc_link": ""
    },
    "dev-c7-ttdvkh": {
      "root": "92618730",
      "group": "c7-ttdvkh",
      "space": "C7GSAFEDA",
      "hl_color": "#c0b6f2",
      "page_link": "",
      "doc_link": ""
    }
  }
}
```

Fields: `root` (hierarchy root page whose monthly children hold the daily release
pages), `group` (top-level git namespace used for tag lookup), `space`
(Confluence space key), `hl_color` (highlight for rows that need release),
`page_link`/`doc_link` (reference links for humans and agents).

Selection order for a run: `--project` -> auto-detect by matching the cwd repo's
group against the registry -> explicit `--root/--group/--space/--hl-color`.

## Missing config — ask first

When the target project is not in the registry, or credentials do not work, stop
and collect the values from the user before syncing:

1. **Project key** — registry name, e.g. `dev-c7-ttdvkh`.
2. **Release page link** — a daily release page or its monthly parent page URL.
3. **Document link** — the space or root page that holds the release pages.
4. **Git group** — top-level repository namespace for tag lookup (e.g. `c7`, `c7-ttdvkh`).
5. **Highlight color** — purple shade for rows that need release (default `#998dd9`).
6. **Credentials** — Confluence base URL and token if `zjira whoami` fails.

## Internal endpoints — ask on first use

Internal hostnames are never hardcoded in this skill. They live in
`config/endpoints.json`, which is gitignored so they never enter the repository;
version control ships only `config/endpoints.example.json`.

Resolution order for every endpoint: CLI flag -> environment variable
(`CONFLUENCE_URL`, `GIT_SSH_BASE`, `CONFLUENCE_SPACE`) -> `config/endpoints.json`
-> ask the user. There is no hardcoded fallback.

If a required value is missing the script exits with instructions. Ask the user
for the internal URL or key, confirm it, then persist it:

```bash
python3 scripts/sync_release_tags.py --set-endpoint confluence_url=<url>
python3 scripts/sync_release_tags.py --set-endpoint git_ssh_base=<ssh-base>
python3 scripts/sync_release_tags.py --set-endpoint confluence_space=<KEY>
```

Keys: `confluence_url`, `confluence_space`, `git_ssh_base`, `jira_url`.
Run this whenever the environment changes or the user corrects a value.

Store non-secret project values with the registry command:

```bash
python3 scripts/sync_release_tags.py --add-project dev-c7-ttdvkh \
  --root 92618730 --group c7-ttdvkh --hl-color '#c0b6f2' \
  --page-link '<confluence-base>/display/<SPACE>/<page>' \
  --doc-link '<confluence-base>/display/<SPACE>'
```

Store secrets in `~/.config/opencode/release-sync.json` (mode `600`), which
overlays the zjira config. Only the token belongs here — the URL belongs in
`config/endpoints.json`:

```json
{
  "confluence_token": "<token>"
}
```

`config/endpoints.json` wins over this file for non-secret keys; if both define
`confluence_url` with different values, the script warns and uses
`config/endpoints.json`. A legacy `confluence_url` here still works when
`config/endpoints.json` does not define one.

Never print the token; write the file with the user's pasted value, then
`chmod 600`. Prefer `zjira init` when the user already uses the zjira CLI.
After storing, verify with a dry run (`--project <name>`) before any `--apply`.

## Write safety

Every remote write (page creation, tag/paint/clear updates) requires a dry run and
explicit user approval:

1. Run without `--apply` and show the resulting table to the user.
2. Ask for approval (question tool, or in chat).
3. Only then re-run with `--apply --approved`.

The script refuses `--apply` without `--approved`. Never bundle the dry run and the
approved write in one command unless the user already approved that exact plan.

## Run

Dry-run first, show the plan, then apply.

```bash
S=~/.config/opencode/skills/9to5-release-confluence-sync/scripts/sync_release_tags.py

# explicit project
python3 "$S" --project dev-c7                         # dry run
python3 "$S" --project dev-c7 --apply --approved      # after approval

# auto-detect from the cwd repo's remote group
python3 "$S"
python3 "$S" --apply --approved

# another date / explicit page
python3 "$S" --project dev-c7 --date 2026-09-18
python3 "$S" --page 141395270 --project dev-c7 --apply --approved
```

Flags:

| Flag | Meaning |
|------|---------|
| `--project NAME` | Project from the registry (`dev-c7`, `dev-c7-ttdvkh`, ...) |
| `--config PATH` | Alternate registry file |
| `--add-project NAME` | Register/update a project, then exit (`--root --group --space --hl-color --page-link --doc-link`) |
| `--page URL\|ID` | Explicit page; skips the today lookup and creation |
| `--root URL\|ID` | Hierarchy root; daily pages resolve under its monthly children |
| `--space KEY` | Confluence space key (default: the project's or `config/endpoints.json`) |
| `--date YYYY-MM-DD` | Release date, default today |
| `--template URL\|ID` | Page cloned when creating a missing page |
| `--no-create` | Fail instead of creating a missing page |
| `--hl-color HEX` | Highlight for rows that need release (project default) |
| `--group G` | Git group, default from the registry or the cwd repo remote |
| `--git-base URL` | SSH base; default the cwd repo remote or `config/endpoints.json` |
| `--set-endpoint KEY=VALUE` | Persist an internal endpoint to `config/endpoints.json` and exit |
| `--service NAME` | Restrict to rows whose service name contains this string |
| `--paint N,N` | Force the purple highlight on the given row numbers |
| `--clear-highlight [N,N]` | Remove highlights: all highlighted rows, or the listed numbers |
| `--scan` | Refresh every repo from git and report new services/tags (ignores the cache) |
| `--no-cache` | Do not read or write the repo/tag cache |
| `--cache-ttl SECONDS` | Cached tag list lifetime, default `120` |
| `--jobs N` | Parallel `git ls-remote` fetches, default `8` |
| `--apply` | Write changes; requires `--approved` |
| `--approved` | Confirms the user approved the dry-run result |

## Behavior

- Today's page is created when missing and updated when it exists: numbered
  `max NNN + 1`, parented under the current monthly page, cloned from the newest
  daily page; numbering/template fall back to the newest month with daily pages.
  A missing monthly page stops the run with an explicit error.
- Repositories are derived from each row's own GitLab links (`/-/tree/`, `/-/tags/`).
- Tag series comes from the row's current tag (`c7-ttch-v0.0.341` -> prefix
  `c7-ttch-v0.0.`), highest `prefix + number` wins; `hotfix` tags are ignored.
- `version` cell -> newest tag (when it already holds one); `current version` rolls
  over to the previous `version`; `Release Tag` and `Docker image` follow the newest.
- Updated rows (service needs release) get the project highlight on every cell
  (`class="highlight-<color>"` plus `data-highlight-colour`) — Confluence renders
  from the class, so both are written.
- Rows sharing one repository with different current tags (append-only logs such as
  `alleyway-portal`, `ttch-migration`) are marked `skip: ambiguous` and left alone.
- Cache: `cache.json` next to this skill stores service->repo and tag lists per
  group; stale entries refresh in parallel with a 15s SSH connect timeout.
- The PUT re-reads the page version immediately before writing; a concurrent edit
  surfaces as a conflict instead of a silent overwrite.
- After every apply the page is re-read and highlights are verified.

## Output

Dry run first, then:

```
| No | Service | Tag | Status |
```

Status: `update: <fields>`, `paint: purple`, `up-to-date`, `skip: ambiguous`,
`skip: no tag`, `error:<message>`.

After `--apply`: `=== SERVICES TO RELEASE ===` (`| No | Service | Tag |`) or
`painted purple: N, N`, then `cleared highlights: N, N`, then the applied counts
and `release page: <url>`, then `=== VERIFY HIGHLIGHT ===`
(`| No | Service | Highlight | Result |` with `ok`/`MISMATCH`).

`=== RELEASE PAGE ===` (`| No | Service | Tag | Highlight |` for every service on
the page) prints after every run.

## Report back

Show the project used, the page created/used with its link, the dry-run table,
the applied/released rows, and the verification result (including `MISMATCH`).
