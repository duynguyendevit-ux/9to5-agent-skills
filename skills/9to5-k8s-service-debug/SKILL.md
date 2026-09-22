---
name: 9to5-k8s-service-debug
description: Debug OTS/C7 services running on Kubernetes — locate a pod by app name across dev-c7 and dev-c7-ttdvkh, tail and filter logs, extract Hibernate SQL with bound parameters into runnable Oracle statements, inspect env/limits, and correlate failures back to the local repo. Use when the user asks to debug or investigate a service on the cluster, read pod logs, find an error in a pod, check why a worker did not run, inspect a service's runtime config, open SQL from logs, mentions klog/ksql/kerror/kfind, or pastes a stack trace from an OTS service. Read-only by default.
license: MIT
compatibility: Requires kubectl at /usr/bin/kubectl, a kubeconfig exposing the dev-buuchinhso context, and the shell helpers from ~/Documents/k8slog/rancher-log-alias.sh sourced in the interactive shell. Cluster access is dev only.
metadata:
  version: "1.0.0"
---

# K8s Service Debug

Diagnose a running OTS service from the cluster before reading code. The cluster is the source of truth for what is deployed; logs and bound SQL are the primary evidence.

## Registries

Read these before touching the cluster. They keep app names, namespaces, and repo paths consistent.

| File | Use |
|------|-----|
| `config/k8s-env.json` | Contexts, env -> namespace map, helper command reference, what is not reachable |
| `config/apps.json` | App name -> namespaces + local repo path (`repo_confidence`, `duplicate_repos`) |
| `config/helpers/rancher-log-alias.sh` | Reference copy of `klog` / `kfind` / `kerror` / `ksql` |

Resolve the repo from `apps.json` rather than guessing a checkout path. An app with `"repo": null` is not checked out locally — say so instead of inventing a path. `repo_confidence` records how the path was matched: `remote` (git remote basename) and `project` (`rootProject.name`) are verified, `inferred` is basename-only. Read the remote before trusting an `inferred` path.

Before relying on the helper snapshot, check it has not drifted from the live file:
`diff -q config/helpers/rancher-log-alias.sh ~/Documents/k8slog/rancher-log-alias.sh`

## Safety

Default posture is read-only: `get`, `logs`, `describe`, `exec` for inspection.

- `kubectl get pods|deploy|svc|configmap|secret -o yaml`, `logs`, `describe` — proceed.
- `exec` that only reads (printenv, cat config, `ls`) — proceed, but never print secret values to the transcript; report key names and whether a value is set.
- `kubectl delete|scale|rollout restart|edit|apply|patch`, port-forward to a datastore, or any write — stop and get explicit confirmation first. State the exact namespace, target, and blast radius.
- Never copy kubeconfig content, bearer tokens, or secret values into notes, `debug/`, or the vault.

## Workflow

1. **Resolve the target.** Look up the app in `config/apps.json`; the namespaces come from there, not from memory. A service can run in both `dev-c7` and `dev-c7-ttdvkh` — pick the namespace under investigation and confirm the pod is running: `kpods -n <ns> | grep <app>`.
2. **Check current errors first.** `kerror <app> <ns>` before reading raw logs. A crash loop or repeated exception is visible immediately; a wide unfiltered tail is noise.
3. **Read logs with intent.** `klog <app> <ns>` for the timeline, `kfind <app> '<pattern>' <ns>` for a specific request id, device code, event id, or coroutine. Pass a specific namespace — cross-namespace pod matching is slow and can select the wrong deployment.
4. **Reconstruct SQL when the failure is data-shaped.** `ksql <app> <ns>` pipes the log tail through `_hibernate_bind_sql_stream`, which walks `Hibernate: <sql>` lines, binds `binding parameter [n] as [TYPE] - [value]` in order, and emits runnable Oracle statements tagged with an inferred business flow. Use it to reproduce the exact query the service ran.
5. **Inspect runtime config.** `kubectl -n <ns> exec <pod> -- printenv` (key names only), then compare with `ots-env-custom/service-configs/<env>/<service>/` — hand off to `9to5-env-config-sync` if the deployed value is wrong.
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
- Manifest-level drift: the deployed state comes from `ots-env-custom`; use `9to5-env-config-sync` for the config change, this skill only for diagnosis.
- Data fix required: use `9to5-sql-migration`; this skill produces the query, it does not ship DDL/DML.
