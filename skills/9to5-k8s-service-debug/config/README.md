# config/

Read-only registries for the skill. No secrets, no kubeconfig content, no tokens.

| File | Purpose |
|------|---------|
| `k8s-env.json` | Cluster access: kubectl path, kubeconfig path, contexts, environment -> namespace map, helper command reference, known-not-covered environments. |
| `apps.json` | Service registry: deployed app -> namespaces and local repo path. 70 apps across `dev-product` and `dev-user`. |
| `helpers/rancher-log-alias.sh` | Snapshot of the shell helpers (`klog`, `kfind`, `kerror`, `ksql`, `_hibernate_bind_sql_stream`). Reference copy only; the live file is sourced from `~/.bashrc`. |

## apps.json schema

```jsonc
{
  "platform-admin-service": {
    "namespaces": ["dev-product", "dev-user"],   // every namespace where the app is deployed
    "repo": "/home/example/workspace/product/services/platform-admin-service",
    "repo_confidence": "remote",                 // remote | project | inferred
    "duplicate_repos": ["/home/example/workspace/service/platform-admin-service"]
  }
}
```

- `namespaces` is an array: 17 services run in both namespaces. Never collapse it to one — the workflow selects the namespace under investigation.
- `repo` is `null` when no local checkout was verified. Do not invent a path; 48 of 70 apps are `null`.
- `repo_confidence` states how the path was matched:
  - `remote` — git remote basename equals the app name. Trusted.
  - `project` — `rootProject.name` equals the app name. Trusted, but confirm the remote.
  - `inferred` — directory basename only. Verify the remote before using it.
- `duplicate_repos` lists additional checkouts of the same service.

## Refresh

Regenerate from the live cluster, never hand-edit rows.

```bash
for ns in dev-product dev-user; do
  kubectl -n "$ns" get deploy -o name | sed "s|deployment.apps/|$ns |"
done
```

Then re-resolve each repo with `git -C <dir> config --get remote.origin.url` and keep only matches where the remote basename or `rootProject.name` equals the app name. Record anything weaker as `"repo": null`.

Helper snapshot drift check:

```bash
diff -q config/helpers/rancher-log-alias.sh ~/workspace/k8slog/rancher-log-alias.sh
```

## Rules

- Never write kubeconfig content, client certificates, bearer tokens, or service account secrets into `config/`.
- `k8s-env.json` records the kubeconfig **path** only. The file at that path is `chmod 600` and stays where it is.
- A repo path that cannot be traced to the app name through the git remote is not a repo path — use `null` plus an `inferred` marker at most.
