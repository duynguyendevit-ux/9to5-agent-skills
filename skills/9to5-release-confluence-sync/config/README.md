# config/

Internal endpoints for this skill. Not committed with real values.

| File | Purpose |
|------|---------|
| `endpoints.example.json` | Tracked template. Placeholders only. |
| `endpoints.json` | Real values. Gitignored. Created on first use. |

## Keys

| Key | Used by |
|-----|---------|
| `confluence_url` | Confluence REST calls (`scripts/sync_release_tags.py`) |
| `confluence_space` | Space key when neither `--space` nor the project registry provides one |
| `git_ssh_base` | `git ls-remote` tag discovery when the cwd repo has no usable remote |
| `jira_url` | reserved; zjira uses its own config |

## Resolution order

1. CLI flag (`--space`, `--git-base`)
2. Environment variable (`CONFLUENCE_URL`, `CONFLUENCE_SPACE`, `GIT_SSH_BASE`)
3. `config/endpoints.json`
4. Caller fallback (project registry, cwd repo remote)
5. Fail with instructions — never fall back to a hardcoded internal host

`config/endpoints.json` is authoritative for non-secret keys. It wins over a
legacy `confluence_url` in `~/.config/opencode/release-sync.json`; when both are
set and differ, the script warns on stderr and uses this file.

Credentials are not stored here. Tokens stay in `~/.config/zjira/config.yaml`
or the `~/.config/opencode/release-sync.json` overlay (mode `600`).

## File mode

`--set-endpoint` writes `endpoints.json` with mode `600`. Keep it that way if you
edit by hand.

## First use

If a value is missing, ask the user for the internal URL or key, confirm it, then
persist it:

```bash
python3 scripts/sync_release_tags.py --set-endpoint confluence_url=<url>
python3 scripts/sync_release_tags.py --set-endpoint git_ssh_base=<ssh-base>
python3 scripts/sync_release_tags.py --set-endpoint confluence_space=<KEY>
```

Refresh these whenever the environment changes or the user corrects a value.
Never commit `endpoints.json`.
