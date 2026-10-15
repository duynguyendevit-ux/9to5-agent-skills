---
name: 9to5-env-config-sync
description: "Compare, validate, and synchronize environment service configurations (values.yaml, .env) across deployment environments (dev, staging, uat, prod) — align environment variables, report configuration drift, and keep secrets out of source control. Use when asked to sync env configs, add or change an environment variable, compare dev vs uat/prod values, investigate config drift, or when the user says 'đồng bộ env', 'sync biến môi trường', 'so sánh config giữa các môi trường', 'kiểm tra config drift'."
license: MIT
metadata:
  version: "1.0.3"
---
# Environment Config Sync

## Example output

Illustrative comparison; replace values with verified non-secret configuration.

```text
Service: example-worker
Variable                 dev-product   uat-product   Action
WORKER_BATCH_SIZE         100      50           Intentional load difference; preserve
WORKER_RETRY_ENABLED      true     missing      Add true to requested UAT config
Validation: YAML parsed; git diff --check passed
Changed: service-configs/uat-product/example-worker/values.yaml
```

Keep per-environment service configs consistent across the deployment environments.

## Layout

`~/workspace/env-config`

```
service-configs/<env>/<service>/
├── values.yaml   # helm values (tracked)
└── .env          # env vars (tracked)
```

Environments seen: `dev-product`, `dev-user`, `uat-product`, `uat-user`,
`dev-example`, `prod-example`, ... Compare like-for-like (product vs product, user vs user).

## Workflow

1. Find the service dirs across environments:
   `find service-configs -maxdepth 2 -type d -name '<service>'`
2. Diff the pairs:
   - `diff -u service-configs/dev-product/<svc>/values.yaml service-configs/uat-product/<svc>/values.yaml`
   - env keys: `grep -oE '^[A-Za-z_]+' <env>/.env | sort`
3. Make the change in every environment that should match, one commit per intent.
   Keep placeholders intact: `${IMAGE_NAME}`, `${IMAGE_TAG}`, `${SERVICE_NAME}` —
   image tags are injected by CI (`CI_REGISTRY_IMAGE` / `IMAGE_TAG`), never hardcode them.
4. Validate: `git diff` for the touched files, `git diff --check` for whitespace,
   and read the changed YAML block back. There is no YAML linter installed.
5. Report a drift table:

```
| Variable | dev-product | uat-product | Action |
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
