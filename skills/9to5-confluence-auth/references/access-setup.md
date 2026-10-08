# First-use configuration and separate PAT login

Inspect existing config first. Ask only for missing non-secret fields needed by the
active task: Git source/base and project namespace, GitLab API URL, Confluence URL
and space/parent page, Jira URL and issue key when a Jira-linked task is requested.
An ordinary release does not require a Jira task or GitLab API PAT when SSH suffices.
An issue key is task context, not a credential; confirm a saved `jira_task` before
reusing it for another release. Space keys/page IDs are distinct from access tokens.

Token entry happens in the user's terminal, never chat, CLI arguments, shell
history or an echo/pipe. Ask the user to generate a PAT in the relevant service's
account settings, then paste it at the masked prompt. The CLI validates a supplied
token; it does not mint one, open a browser, obtain broader scopes, or deploy.

```bash
ACCESS=~/.config/opencode/skills/9to5-confluence-auth/scripts/access.py
python3 "$ACCESS" status confluence
python3 "$ACCESS" login confluence
python3 "$ACCESS" login jira
python3 "$ACCESS" login gitlab
python3 "$ACCESS" configure git_ssh_base confluence_space
# Only when the active task is linked to Jira:
python3 "$ACCESS" configure jira_task
# Changing task context preserves tokens and all other configuration:
python3 "$ACCESS" configure jira_task --replace
```

Global `--config` and `--endpoints` precede the subcommand. Use the release skill's
actual endpoints file when present, so preflight and publication reach the same
server. Missing files are allowed; malformed files stop setup. A non-interactive
agent shell returns an actionable terminal-required result; give the user the
command rather than collecting PATs through a question tool.
On this machine `9to5-access` is a wrapper for this script; other installations
can use the `python3 "$ACCESS"` form above without installing a wrapper.

Default storage: `$XDG_CONFIG_HOME/opencode/release-sync.json`, otherwise
`~/.config/opencode/release-sync.json`. It is an atomic mode-600 JSON file retaining
unrelated keys. It contains `confluence_url/confluence_token`, `jira_url/jira_token`,
`gitlab_url/gitlab_token`, and optional `git_ssh_base`, `confluence_space`, `jira_task`.
Back it up only through the user's private credential process; exclude it from
skills, git, served previews and diagnostic output. Writes reject concurrent edits.

Existing Confluence dotfile/endpoint precedence remains that of `auth.py`. GitLab
and Jira use service URL environment override → supplied endpoints → dotfiles;
service token dotfile → service token environment fallback. Jira alone accepts
zjira's legacy generic token. GitLab never borrows an Atlassian token. Legacy
Confluence generic-token fallback remains for compatibility; new login saves an
explicit Confluence token. The destination is displayed only in the interactive
terminal before a newly pasted PAT is sent.

`status` makes read-only requests and reports presence/status only. Checks are
Confluence `/rest/api/user/current`, Jira `/rest/api/2/myself`, GitLab `/api/v4/user`.
Transport is Server/DC Bearer PAT for Jira/Confluence and GitLab PRIVATE-TOKEN;
Cloud Basic/OAuth is not supported. Redirects are blocked. A working login is a
no-op; missing/401 prompts only for that service. `--replace` explicitly requests
credential replacement. Only a successfully verified credential is saved. A 403,
network error or redirect does not automatically prompt for replacement.

## Consumption boundary

- Confluence REST helpers already consume this overlay. Use the matching endpoints
  override and `auth.py --check` before publication.
- `access.py` is the separate login/status CLI for Jira and GitLab. API callers can
  import its `resolve()` and keep returned credentials in process memory; do not
  print a token or put it in a URL/command argument.
- zjira itself reads its own YAML, not this overlay. For zjira commands, initialize
  through `zjira init` and check that CLI separately. Do not claim overlay login
  logged zjira or glab in. Git SSH needs the user's SSH key/agent independently;
  a GitLab API PAT does not verify `git ls-remote` access.
- Read `git_ssh_base` from the dotfile in process and pass it explicitly as the
  release engine's `--git-base`; the engine does not automatically consume that
  overlay key. Project root/group/date remain the release registry/task inputs.
  The legacy sync engine requires an existing zjira YAML file; if absent, use the
  generic Confluence helper for approved publication rather than claiming the
  new login bootstraps that engine or overwriting zjira's config.

Successful authentication permits the requested reads, not Confluence publication,
Jira edits or Git pushes. Their normal review/approval gates remain in force.
