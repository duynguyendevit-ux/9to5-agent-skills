# config/

Internal endpoints for this skill. Not committed with real values.

| File | Purpose |
|------|---------|
| `endpoints.example.json` | Tracked template. Placeholders only. |
| `endpoints.json` | Real values. Gitignored. Created on first use. |

## Keys

| Key | Used by |
|-----|---------|
| `confluence_url` | Every REST call in `scripts/confluence.py` |
| `confluence_space` | Default space for `create` when `--space` is omitted |

## Resolution order

1. CLI flag (`--confluence-url`, `--space`)
2. Environment variable (`CONFLUENCE_URL`, `CONFLUENCE_SPACE`)
3. `config/endpoints.json`
4. `~/.config/zjira/config.yaml`
5. Fail with instructions — never fall back to a hardcoded internal host

Credentials are not stored here. The token stays in `~/.config/zjira/config.yaml`
or the `~/.config/opencode/release-sync.json` overlay (mode `600`).

## File mode

`--set-endpoint` writes `endpoints.json` with mode `600`. Keep it that way if you
edit by hand.

## First use

If a value is missing, ask the user for the internal URL or key, confirm it, then
persist it:

```bash
python3 scripts/confluence.py --set-endpoint confluence_url=<url>
python3 scripts/confluence.py --set-endpoint confluence_space=<KEY>
```

Never commit `endpoints.json`.
