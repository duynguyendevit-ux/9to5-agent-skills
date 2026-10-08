---
name: 9to5-env-config-sync
description: Compare and update Platform environment service configs in env-config/service-configs/<env>/<service>/ (values.yaml and .env) — align environment variables across dev-product, dev-user, dev-uat-*, report drift, and keep secrets out of commits. Use when the user asks to sync env configs, add or change a service env variable, compare dev vs uat values, or investigate config drift between environments.
license: MIT
metadata:
  version: "1.0.1"
---

# Environment Config Sync

## Example output

Illustrative comparison; replace values with verified non-secret configuration.

```text
Service: example-worker
Variable                 dev-product   dev-uat-product   Action
WORKER_BATCH_SIZE         100      50           Intentional load difference; preserve
WORKER_RETRY_ENABLED      true     missing      Add true to requested UAT config
Validation: YAML parsed; git diff --check passed
Changed: service-configs/dev-uat-product/example-worker/values.yaml
```

Keep per-environment service configs consistent across the Platform environments.

## Layout

`~/workspace/env-config`

```
service-configs/<env>/<service>/
├── values.yaml   # helm values (tracked)
└── .env          # env vars (tracked)
```

Environments seen: `dev-product`, `dev-user`, `dev-uat-product`, `uat-user`,
`dev-example`, `prod-example`, ... Compare like-for-like (Product vs Product, User vs User).

## Workflow

1. Find the service dirs across environments:
   `find service-configs -maxdepth 2 -type d -name '<service>'`
2. Diff the pairs:
   - `diff -u service-configs/dev-product/<svc>/values.yaml service-configs/dev-uat-product/<svc>/values.yaml`
   - env keys: `grep -oE '^[A-Za-z_]+' <env>/.env | sort`
3. Make the change in every environment that should match, one commit per intent.
   Keep placeholders intact: `${IMAGE_NAME}`, `${IMAGE_TAG}`, `${SERVICE_NAME}` —
   image tags are injected by CI (`CI_REGISTRY_IMAGE` / `IMAGE_TAG`), never hardcode them.
4. Validate: `git diff` for the touched files, `git diff --check` for whitespace,
   and read the changed YAML block back. There is no YAML linter installed.
5. Report a drift table:

```
| Variable | dev-product | dev-uat-product | Action |
```

## Secrets

`.env` files are tracked. Never add tokens, passwords, or keys to them — the
pipeline pulls secrets from Vault (`VAULT_TOKEN`). If the user pastes a secret,
stop and redirect it to Vault / CI variables. If a secret is already committed,
flag it to the user instead of editing history.

## Rules

- Change only what the task requires; unrelated formatting churn makes diffs unreadable.
- Values that differ by design (domains, Redis topology, feature flags) are not drift —
  confirm with the user before unifying them.
- One environment at a time when debugging; sync the rest once the value is confirmed.
