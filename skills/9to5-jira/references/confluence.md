# Confluence Operations

Use this reference for Confluence-only work and the optional Confluence step of
Jira planning.

## Read and search

```bash
ZJIRA=$(command -v zjira 2>/dev/null || echo "$HOME/.local/bin/zjira")
$ZJIRA confluence get 128244471 --md
$ZJIRA confluence search '255. 27.07.2026' --json
```

For `/display/SPACE/title` URLs, search by decoded title when a normal `get`
cannot resolve the URL. The release script below resolves these URLs directly.

## Update safety

Only write after the user explicitly requests an update, and always dry-run first:

1. Run the update with `--dry-run` and show the JSON summary to the user.
2. Ask for explicit approval (never infer it from the request alone).
3. Re-run without `--dry-run` only with `--approved` (non-interactive) or by
   answering the interactive `Apply this update to Confluence? [y/N]` prompt.

Before writing:

1. Resolve exactly one page and GET `body.storage`, `version`, `title`, `space`.
2. Resolve every service, tag, target row, expected column, URL, and image.
3. Preserve the complete storage body and each row's `current version` value.
4. PUT once with version `current + 1`; never retry against stale content.
5. GET the page again and verify version, tags, images, current versions, and highlights.

Never print or hardcode tokens. Scripts read `confluence_token` from
`~/.config/zjira/config.yaml`.

## Release table script

`scripts/update_confluence_release.py` updates these zero-based columns:

- `3`: version and tag link
- `5`: Release Tag URL
- `7`: Docker image
- `4`: current version is validated but never changed

It highlights columns `0-8` with `#c0b6f2` by default. Tag discovery fetches
tags into an isolated `refs/remotes/origin/tags/` namespace, sorts by creator
date, and skips tags containing `hotfix` unless `--include-hotfix` or an
explicit `--tag SERVICE=TAG` is supplied. This avoids overwriting a conflicting
local tag.

Interactive mode is the default. When `--profile` is omitted, it first asks for
the release project (`c7-ttch` or `c7-ttdvkh`). Without `--page`, it finds the
unique release page whose title ends with today's `DD.MM.YYYY` date. When
several pages share that date, it selects the unique page containing the chosen
profile's service rows. It then lists current/latest versions, lets the operator
select services and tags, previews the change, and asks before PUT:

```bash
python3 scripts/update_confluence_release.py
```

Interactive mode skips registry entries whose local/remote repository has no
usable tag and shows the reason. An explicitly requested service still fails
before PUT when its tag cannot be resolved.

The service picker normally shows only repositories with one or more commits on
`origin/develop` after the latest tag. Each visible row shows deployed/current
version, page release version, latest tag, and `develop +N`. Existing tags that
only need a Confluence update should use `--tag-url`. Use `--all-services` to
disable the develop-change filter.

The tag picker also offers `c. Create a new tag`. It suggests the next numeric
tag, accepts a source ref (default `origin/develop`), resolves and previews the
source commit, and checks that the remote tag does not exist. `--dry-run` never
pushes. In a real interactive run, the script asks for confirmation, pushes and
verifies each new remote tag, then updates Confluence.

For an existing GitLab tag, pass the page and tag URLs directly. The script
infers the profile from the URLs, maps the GitLab project to the registered
service/Docker image, and verifies that the tag exists on `origin`:

```bash
python3 scripts/update_confluence_release.py \
  --page 'https://confluence-local.ots.vn/display/C7GSAFEDA/243.+27.07.2026' \
  --tag-url 'http://10.0.0.40/c7-ttdvkh/ttch/ttch-migration/-/tags/c7-ttdvkh-v0.0.123' \
  --dry-run
```

Repeat `--tag-url` to update several rows in one Confluence version.

Use `--dry-run` to keep the same service/tag picker but disable PUT:

```bash
python3 scripts/update_confluence_release.py --dry-run
```

Non-interactive dry-run using `references/release-services.json`:

```bash
python3 scripts/update_confluence_release.py \
  --service-name ttch-event-diary-service \
  --service-name ttch-receive-service \
  --service-name export-file-service \
  --dry-run
```

After reviewing the JSON summary, remove `--dry-run` only when the user has
explicitly authorized the write. All rows are updated in one Confluence version.

Use `--page today` for the same behavior, or `--date 27.07.2026` to select a
historical release page by date. Numeric IDs and full URLs remain supported for
an explicit page override.

For the TTDVKH release page, use the dedicated profile. It resolves the page
`243. DD.MM.YYYY` by matching the profile's service rows:

```bash
python3 scripts/update_confluence_release.py \
  --profile c7-ttdvkh \
  --page 'https://confluence-local.ots.vn/display/C7GSAFEDA/243.+27.07.2026' \
  --dry-run
```

Omit `--page` to find the current TTDVKH release page automatically:

```bash
python3 scripts/update_confluence_release.py --profile c7-ttdvkh --dry-run
```

Override one discovered tag:

```bash
python3 scripts/update_confluence_release.py \
  --page-id 128244471 \
  --service-name ttch-receive-service \
  --tag ttch-receive-service=c7-ttch-v0.0.107 \
  --dry-run
```

Ad-hoc service not in the registry:

```bash
python3 scripts/update_confluence_release.py \
  --page-id 128244471 \
  --service 'service-name|/local/repo|group/project|registry/group/project' \
  --dry-run
```

Use `--release 'NAME|TAG|TAG_URL|DOCKER_IMAGE'` when all release fields are
already known. Use `--no-fetch` only for offline diagnostics. If internal TLS
is not trusted locally, add `--insecure`.
