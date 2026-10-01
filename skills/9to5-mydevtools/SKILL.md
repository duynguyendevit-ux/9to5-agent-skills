---
name: 9to5-mydevtools
description: Use and extend MyDevTools, the browser-first OTS developer utilities — Oracle execution-plan visual, Rancher log analyzer, SQL extractor, protobuf and Kafka decoding, environment-to-Kubernetes conversion, case and hash utilities, cron and nginx generators. Use when a task involves viewing an execution plan, pulling or filtering Rancher logs, extracting SQL from Hibernate logs, decoding Kafka payloads, or converting env configs — and before writing a new script that duplicates one of these tools.
license: MIT
compatibility: Requires the MyDevTools checkout (default ~/Documents/duylab/oracle-plan-visualizer) and Node.js for local runs. The Rancher log agent is loopback-only; hosted deployments cannot reach local clusters.
metadata:
  version: "1.0.0"
---

# MyDevTools — the shared toolbox before the next one-off script

## Example output

Illustrative session; paths and versions come from the actual checkout.

```text
Task: "turn this DBMS_XPLAN output into something readable"
Tool: Execution Plan Visual (route /, plan history in IndexedDB)
Run:  npm run dev -> http://127.0.0.1:3000
Result: plan rendered with per-operation buffers; screenshot attached to the ticket.
Note: plan collection SQL still belongs to 9to5-oracle-index.
```

## Scope and boundaries

- This is the **toolbox skill**: it points at the maintained implementation instead of
  re-deriving parsers in ad-hoc scripts. If a tool exists for the job, use it; extend
  the tool only when the workflow truly needs it.
- MyDevTools is a Next.js app. Product-level agent rules live in its own `AGENTS.md`
  (navigation, session keys, worker rules, SQL extractor semantics); read that file
  before changing anything inside the checkout.
- The SQL extractor in MyDevTools and the `9to5-sql-forensics` script answer different
  needs — interactive extraction in the browser versus a scriptable review packet. Both
  are valid; do not silently fork a third.
- Cluster operations stay in `9to5-k8s-service-debug`; this skill covers the tool that
  reads logs, not the investigation workflow.

## Locate and run

1. Default checkout `~/Documents/duylab/oracle-plan-visualizer` (the repo predates the
   MyDevTools name). Confirm identity by `package.json` and `README.md`; if missing,
   say so instead of guessing another path.
2. Run locally:
   ```bash
   npm install
   npm run dev            # http://127.0.0.1:3000
   ```
3. Rancher log analyzer (needs a local kubeconfig):
   ```bash
   npm run setup:rancher -- /absolute/path/to/kubeconfig.yaml
   npm run dev:rancher    # loopback agent on 127.0.0.1:3210
   ```
   Public cluster hostnames require `KUBECTL_ALLOWED_HOSTS=<host>`; the agent is
   loopback-only and kubeconfig content never enters browser storage or workspace
   snapshots.
4. Before handing off any change inside the checkout, run `npm run verify` (typecheck →
   lint → agent tests → Playwright → local build). Narrow with `npm run typecheck`,
   `npm run lint`, `npm run test:agent`. Known unrelated `chromium-mobile` Excel test
   failures are documented in the repo `AGENTS.md` — do not chase them.
5. Product-level detail (routes, key files, tool inventory) is in
   [`references/tools.md`](references/tools.md).

## Tool catalog (short form)

| Need | Tool |
|---|---|
| Read a DBMS_XPLAN / execution plan | Execution Plan Visual (root route) |
| Pull, filter or follow Rancher pod logs | Log Analyzer |
| Turn Hibernate log lines into runnable SQL | SQL Extractor |
| Decode protobuf / Kafka payloads | Protobuf Decoder |
| Convert service env config to Kubernetes manifests | Env-to-K8s |
| Cron and nginx generators, case conversion, hashing, diffing, spreadsheets | the respective routes listed in the reference |

## Rules that keep the toolbox usable

- Check `data/tools.ts` and `app/<slug>/page.tsx` for the real route before citing a URL.
- Session state keys (`mydevtools:session:<tool>:v1`) are persisted contracts; renaming
  them breaks saved sessions and workspace snapshots.
- CPU-heavy work runs in web workers through `useWorkerRpc`; keep payloads serializable
  and pure logic in `lib/`.
- Cross-tool handoffs use `sendToolTransfer` with envelopes that expire after ten
  minutes; do not invent a second transfer mechanism.
- The SQL extractor semantics are specific and tested (positional binds per statement,
  `?` inside quoted strings skipped, value-based literals, ISO timestamps normalized to
  Oracle form, empty binding `[]` means empty string). Read `lib/sql-extractor.ts` plus
  the repo `AGENTS.md` before changing behavior; regressions here silently corrupt
  reconstructed SQL.

## Safety

- Kubeconfig handling stays inside the tool: never paste kubeconfig content into notes,
  tickets or agent conversations, and never route it through browser storage, workspace
  snapshots or hosted deployments.
- Large logs, SQL and spreadsheets may contain personal or production data; sanitize
  before attaching outputs to tickets or committing artifacts.
- The tool is local-only for Rancher workflows; do not present hosted URLs as able to
  reach internal clusters.

## Handoffs

- Cluster investigation workflow and evidence layout → `9to5-k8s-service-debug`.
- Log-derived SQL packets for review → `9to5-sql-forensics`.
- Index decisions from rendered plans → `9to5-oracle-index`; DDL → `9to5-sql-migration`.
- Changes inside the MyDevTools checkout follow its own `AGENTS.md` and `npm run verify`
  gate — treat it as a normal repository, not a scratch space.

## Stop conditions

- Checkout missing or not the expected project: report that; do not clone or guess.
- The needed tool does not exist: say which tools come closest and what a new tool would
  require (route, worker, tests, verify gate); build it only if the user asks.
- A change inside the checkout would alter persisted session keys, transfer contracts or
  extractor semantics: stop and get an explicit decision first.
