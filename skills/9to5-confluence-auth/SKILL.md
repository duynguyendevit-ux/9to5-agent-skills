---
name: 9to5-confluence-auth
description: Resolve Confluence PAT auth from local dotfiles, verify Confluence access separately from Jira, and initialize the CLI only when credentials are missing or unauthorized. Use before Confluence reads/publication, for missing config, expired PAT/401, dotfile credential loading, or requests to login if auth is absent. Authentication does not authorize page writes.
compatibility: Python 3, PyYAML, and zjira for interactive initialization; Confluence Server/Data Center Bearer PAT transport.
license: MIT
metadata:
  version: "1.0.0"
---

# Confluence Auth Preflight

## Example output

Illustrative safe status, not a live login:

```json
{"url_present": true, "token_present": true, "url_source": "zjira-config", "token_source": "zjira-config:confluence_token", "status": "authenticated", "verified": true, "login_needed": false, "http_status": 200}
```

## Load config, not secret values into the conversation

Use [`scripts/auth.py`](scripts/auth.py) to read dotfiles in process memory.
It prints presence, source labels and status only: no PAT, endpoint hostname,
identity, auth header, raw parser error or server response body.

```bash
AUTH=~/.config/opencode/skills/9to5-confluence-auth/scripts/auth.py
python3 "$AUTH" --check
```

Default paths honor `$XDG_CONFIG_HOME` (otherwise `~/.config`):

- `zjira/config.yaml`: `confluence_url`, optional `confluence_token`, fallback `token`.
- `opencode/release-sync.json`: optional string-valued overlay; not required to exist.
- Use `--endpoints <local-file>` when the REST helper uses a local endpoints override.

URL precedence: explicit flag → `CONFLUENCE_URL` → supplied endpoints JSON → merged
dotfiles. Token precedence preserves the existing helper: merged `confluence_token`
→ merged `token` → `CONFLUENCE_TOKEN` fallback. Empty values do not mask valid ones.
An overlay may intentionally override dotfile fields; inspect source labels when
login appears to have no effect. Do not copy local config into a skill/export.

Malformed config is a blocker, not permission to overwrite it. The helper reads
YAML safely and withholds parser excerpts. Verify PyYAML is installed before use.

## Verify the actual service

`zjira whoami --json` verifies **Jira**; it does not prove Confluence auth works.
The helper performs a read-only GET of `/rest/api/user/current`, checks for a known
user, and blocks redirects so the PAT is not forwarded to a login page/other host.
This transport targets self-hosted Bearer PAT auth, not Cloud email/API-token Basic
auth or OAuth; report unsupported setups instead of guessing another scheme.

| Result | Action |
| --- | --- |
| `authenticated` | Continue the requested read/draft workflow; no login needed. |
| `configured` without `--check` | Local resolution only; remote auth remains unverified. |
| Missing config / 401 / anonymous user | Initialize or refresh credentials through the CLI. |
| 403 | Report access denied; do not run login repeatedly or broaden permissions. |
| Redirect / network / server error | Report unverified access; do not treat it as missing credentials. |

Page/space permissions still require reading the specific target; a current-user
check does not prove edit permission or authorize publication.

`zjira` itself reads its YAML config, not this helper's environment/endpoints/JSON
overrides. If the report selects an override, use the REST helper with that same
configuration or verify the CLI's intended target separately. Do not assume a
successful REST preflight proves `zjira` is using the same account/server.

## Login only when needed and authorized

Inspect `zjira --help` and `zjira init --help` for the installed version. The verified
CLI's setup/login entry point is **`zjira init`**, not `zjira auth login`. Its TUI
pre-fills existing config and masks PAT input. Enter credentials in that terminal,
not chat, process arguments, shell tracing or a scripted answer pipe.

When the user has authorized missing-auth setup, run in an interactive terminal:

```bash
python3 "$AUTH" --check --login-if-needed
```

The helper invokes `zjira init` once only for missing/401/anonymous auth, reloads
dotfiles and checks Confluence again. It does not initialize already-working auth,
403, network errors or malformed config. Custom config paths require their own
setup because the CLI writes its default path, not arbitrary `--config` locations.

In a non-interactive agent shell it reports `needs-interactive-login` with the
actual command instead of hanging or fabricating successful login. A configured
environment/overlay override can still mask the new CLI values; report that source.
Initializing credentials is not permission to modify pages, log work or publish.

Offline cases: [`evals/evals.json`](evals/evals.json).
