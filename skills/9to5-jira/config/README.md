# config/

Internal endpoints for this skill. Not committed with real values.

| File | Purpose |
|------|---------|
| `endpoints.example.json` | Tracked template. Placeholders only. |
| `endpoints.json` | Real values. Gitignored. Created on first use. |

## Keys

| Key | Used by |
|-----|---------|
| `confluence_url` | `scripts/update_confluence_release.py` page reads and writes |
| `jira_url` | issue links in generated plans |
| `gitlab_url` | `--tag-url` parsing, tag links |
| `git_ssh_base` | reserved for SSH tag discovery |

## Resolution order

1. CLI flag (`--base-url`, `--gitlab-url`)
2. Environment variable (`CONFLUENCE_URL`, `GITLAB_URL`)
3. `config/endpoints.json`
4. Fail with instructions — never fall back to a hardcoded internal host

Credentials are not stored here. Tokens stay in `~/.config/zjira/config.yaml`
(or the `~/.config/opencode/release-sync.json` overlay, mode `600`).

## First use

If a value is missing, ask the user for the internal URL, then persist it:

```bash
python3 scripts/update_confluence_release.py --set-endpoint confluence_url=<url>
```

Confirm before writing, and never commit `endpoints.json`. `--set-endpoint`
writes the file with mode `600`; keep it that way if you edit by hand.
