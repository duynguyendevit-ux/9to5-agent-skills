# notes/

Service flow notes. One file per deployed app under `notes/services/`, named exactly as the key in `config/apps.json`.

## Why

A debug session should start from a map, not a log tail. These notes record how each service runs so the next investigation does not re-derive the same flow.

## Rules

- Facts only. Anything not verified from code, config, or observed runtime gets `TODO(unverified)`.
- Keep secrets out: no tokens, passwords, connection strings, or kubeconfig content.
- Update the note in the same pass as a debug session that proves or corrects a flow.
- Short. If a section is unknown, write `TODO(unverified)` — an honest gap beats a plausible guess.

## Coverage

| Note | Confidence | Source |
|------|-----------|--------|
| `ttch-worker-service.md` | verified-from-logic | `ksql` business-flow inference in `config/helpers/rancher-log-alias.sh` |
| `ttch-event-diary-service.md` | verified-from-code | local repo + session evidence |
| `ttch-dashboard-service.md` | verified-from-code | repo `CLAUDE.md` |

Apps without a note use `_template.md`. Add the note the first time a service is debugged.
