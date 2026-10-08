---
name: 9to5-k8s-service-debug
description: Debug Platform/Product services running on Kubernetes — locate a pod by app name across dev-product and dev-user, tail and filter logs, extract Hibernate SQL with bound parameters into runnable Oracle statements, inspect env/limits, and correlate failures back to the local repo. Use when the user asks to debug or investigate a service on the cluster, read pod logs, find an error in a pod, check why a worker did not run, inspect a service's runtime config, open SQL from logs, mentions klog/ksql/kerror/kfind, or pastes a stack trace from an Platform service. Read-only by default.
license: MIT
compatibility: Requires kubectl, a kubeconfig exposing the cluster contexts recorded in config/k8s-env.json, and the shell helpers from ~/workspace/k8slog/rancher-log-alias.sh sourced in the interactive shell. Cluster access is dev only.
metadata:
  version: "1.0.1"
---

# K8s Service Debug

## Example output

Illustrative investigation report; distinguish observations from hypotheses.

```text
Target: example-worker / dev-product / example-worker-abc
Symptom: retries are increasing while completed jobs remain flat.
Evidence: repeated connection timeout to the downstream API in filtered logs.
Config: retry setting exists; secret values not retrieved.
Hypothesis: downstream connectivity is blocking completion.
Unverified: deployed image commit has not yet been matched to the checkout.
Artifacts: debug/artifacts/20260924-example-worker-timeouts/session.md
Next action: verify downstream reachability from the affected namespace.
```

Diagnose a running Platform service from the cluster before reading code. The cluster is the source of truth for what is deployed; logs and bound SQL are the primary evidence.

## Registries

Read these before touching the cluster. They keep app names, namespaces, and repo paths consistent.

| File | Use |
|------|-----|
| `config/k8s-env.json` | Contexts, env -> namespace map, helper command reference, what is not reachable |
| `config/apps.json` | App name -> namespaces + local repo path (`repo_confidence`, `duplicate_repos`) |
| `config/helpers/rancher-log-alias.sh` | Reference copy of `klog` / `kfind` / `kerror` / `ksql` |

Resolve the repo from `apps.json` rather than guessing a checkout path. An app with `"repo": null` is not checked out locally — say so instead of inventing a path. `repo_confidence` records how the path was matched: `remote` (git remote basename) and `project` (`rootProject.name`) are verified, `inferred` is basename-only. Read the remote before trusting an `inferred` path.

Before relying on the helper snapshot, check it has not drifted from the live file:
`diff -q config/helpers/rancher-log-alias.sh ~/workspace/k8slog/rancher-log-alias.sh`

## Safety

Default posture is read-only: `get`, `logs`, `describe`, `exec` for inspection.

- Read resource names and selected metadata; filter sensitive fields at source before tool output. Full Secret YAML exposes base64-encoded credentials, and deployment/configmap/env output may contain plaintext credentials too.
- List Secret names with `kubectl -n <ns> get secrets -o name`. List a Secret's key names without values with `kubectl -n <ns> get secret <name> -o go-template='{{range $key, $value := .data}}{{printf "%s\n" $key}}{{end}}'`.
- Read-only `exec` is permitted, but never run raw `printenv` or `cat` on potentially secret-bearing configuration. Report key names and presence; filter inside the container before returning output.
- `kubectl delete|scale|rollout restart|edit|apply|patch`, port-forward to a datastore, or any write — stop and get explicit confirmation first. State the exact namespace, target, and blast radius.
- Never copy kubeconfig content, bearer tokens, or secret values into notes or `debug/`.

## Workflow

1. **Resolve the target.** Look up the app in `config/apps.json`; the namespaces come from there, not from memory. A service can run in both `dev-product` and `dev-user` — pick the namespace under investigation and confirm the pod is running: `kpods -n <ns> | grep <app>`.
2. **Check current errors first.** `kerror <app> <ns>` before reading raw logs. A crash loop or repeated exception is visible immediately; a wide unfiltered tail is noise.
3. **Read logs with intent.** `klog <app> <ns>` for the timeline, `kfind <app> '<pattern>' <ns>` for a specific request id, device code, event id, or coroutine. Pass a specific namespace — cross-namespace pod matching is slow and can select the wrong deployment.
4. **Reconstruct SQL when the failure is data-shaped.** `ksql <app> <ns>` pipes the log tail through `_hibernate_bind_sql_stream`, which walks `Hibernate: <sql>` lines, binds `binding parameter [n] as [TYPE] - [value]` in order, and emits runnable Oracle statements tagged with an inferred business flow. Use it to reproduce the exact query the service ran.
5. **Inspect runtime config.** If Python is installed in the container, list names with `kubectl -n <ns> exec <pod> -- python3 -c 'import os; print("\n".join(sorted(os.environ)))'`. Otherwise enumerate environment keys using an available runtime inside the container; never fall back to raw `printenv`. Inspect only explicitly selected non-secret values, then compare with `env-config/service-configs/<env>/<service>/` — hand off to `9to5-env-config-sync` if the deployed value is wrong.
6. **Correlate to code.** Read the local repo resolved in step 1 and check its git remote matches the deployed service before claiming a match. Grep for the logged class, method, error code, or SQL fragment. Confirm the branch/commit matches the deployed image before claiming the fix.
7. **Write up and persist.** Record the session under `debug/` and update the service's flow note (below).

## Helper commands

| Command | Behavior |
|---------|----------|
| `kpods` | `kubectl get pods` |
| `klog <app> [ns] [context]` | Follow logs, `--tail=500` |
| `kfind <app> <regex> [ns] [context]` | Follow logs filtered by pattern |
| `kerror <app> [ns] [context]` | `kfind` with `error\|exception\|failed\|fatal\|panic\|stacktrace` |
| `ksql <app> [ns] [context]` | Follow logs, emit bound Oracle SQL |

`klog`, `kfind`, `kerror`, and `ksql` use `_kube_pick_pod`, which matches the app name as a substring of the pod name. Short names therefore match multiple deployments — always pass the namespace when the name is ambiguous. In a non-interactive shell the picker cannot prompt, so pass the namespace explicitly or fall back to raw `kubectl`.

## Debug artifacts

Write evidence to `debug/artifacts/` so findings survive the session and can be attached to a ticket.

```
debug/
├── README.md
└── artifacts/
    └── <YYYYMMDD>-<app>-<short-slug>/
        ├── session.md      # symptom, evidence, hypothesis, conclusion, next action
        ├── logs.txt        # filtered excerpt, not a full tail
        └── queries.sql     # ksql output, if any
```

Keep excerpts small and relevant. Strip tokens, cookies, device credentials, and personal data before saving. `session.md` should end with a concrete next action (fix, ticket, or "not reproducible").

## Service flow notes

`notes/services/<app>.md` captures how a service actually runs, so the next debug session starts from a map instead of the log tail. One file per deployed app, named exactly as in `apps.json`.

Use `notes/services/_template.md`. A useful note answers:

- What triggers this service (Kafka topic, REST, gRPC, cron, MQTT)?
- What does it write, and where (Oracle tables, Redis keys, Kafka topics)?
- Which upstream produces its input and which downstream consumes its output?
- Known failure modes and the log signature for each.

Update the note in the same pass whenever a debug session proves or corrects a flow. Facts only — mark anything unverified as `TODO(unverified)` rather than stating it as true. Flow notes must not contain secrets.

## Escalation

- Wrong environment named (uat/prod): the current kubeconfig only reaches dev. Ask for the correct kubeconfig path.
- Manifest-level drift: the deployed state comes from `env-config`; use `9to5-env-config-sync` for the config change, this skill only for diagnosis.
- Data fix required: use `9to5-sql-migration`; this skill produces the query, it does not ship DDL/DML.
