# MyDevTools tool inventory

Verified against the checkout's `README.md`, `AGENTS.md` and `app/` routes. Re-check
`data/tools.ts` before citing a route that may have moved.

## Product shape

- Next.js app, root route `/` is the **Execution Plan Visual**, not a landing page.
- Tools are added/reordered in `data/tools.ts`; each route is `app/<slug>/page.tsx`.
- Pure logic in `lib/`, CPU-heavy work in `workers/*.worker.ts` behind `useWorkerRpc`,
  shared React contracts in `hooks/`.
- Tool sessions persist under `mydevtools:session:<tool>:v1`; workspace snapshots and
  IndexedDB histories (execution plans) are separate stores.
- Cross-tool transfers use `sendToolTransfer` / `useToolTransfer`; envelopes expire
  after 10 minutes.

## Routes

| Slug | Purpose |
|---|---|
| `/` (Execution Plan Visual) | Paste/upload DBMS_XPLAN, visualize operations and buffers; history in IndexedDB |
| `log-analyzer` | Rancher log retrieval and live follow via the loopback agent; context/namespace/pod/container selection, pause/resume/stop |
| `sql-extractor` | Hibernate log to runnable SQL; bind replacement and formatting (see semantics below) |
| `protobuf-decoder` | Decode protobuf / Kafka payloads |
| `env-to-k8s` | Convert service environment config into Kubernetes manifests |
| `k8s-config` | Kubernetes configuration helpers |
| `cron-expression` | Cron expression generation and reading |
| `nginx-redirect` | Nginx redirect rules |
| `activity-diagram` | Diagram authoring |
| `diff-viewer` | Text diffing |
| `excel-tools` | Spreadsheet utilities (`.xlsx`, `.csv`; legacy `.xls` intentionally unsupported) |
| `hash-generator` | Hashes |
| `case-converter` | Case conversions |
| `consistent-hashing` | Consistent-hash ring helper |
| `url-encoder` | URL encoding |
| `useful-websites` | Curated links |

## Commands

| Command | Effect |
|---|---|
| `npm run dev` | Dev server on `http://127.0.0.1:3000` |
| `npm run setup:rancher -- <kubeconfig>` | Save the local kubeconfig path for the log agent |
| `npm run dev:rancher` | Log agent on `127.0.0.1:3210` (loopback only) |
| `npm run verify` | typecheck → lint → agent tests → Playwright → local production build |
| `npm run typecheck` / `npm run lint` / `npm run test:agent` | Narrowed checks |
| `npm run build:local` / `npm run start:local` | Local production artifact on `127.0.0.1:3100` |

Separate build directories are intentional (`NEXT_DIST_DIR`): dev `.next-dev`, Playwright
`.next-e2e`, local prod `.next-prod`. Use the npm scripts, not bare `next build` /
`next dev`.

## SQL Extractor semantics (contract)

Source of truth: `lib/sql-extractor.ts` (worker is a thin wrapper).

- Bind replacement is **positional per SQL statement** (bind index → Nth `?`), skipping
  `?` inside quoted strings.
- Literal formatting is **by value, not JDBC type**: `null` → `NULL`; `true`/`false` →
  `1`/`0`; ISO timestamps → `TIMESTAMP '<value>'` with the `T` separator normalized to a
  space (Oracle rejects the ISO form); everything else, including numbers, is wrapped in
  single quotes.
- Empty binding text (`binding parameter [n] as [TYPE] - []`) means an empty string, **not**
  a missing binding; dropping it shifts every later placeholder.
- Extraction keeps source indentation (trailing whitespace stripped); the Format action
  is what re-lays-out whitespace.
- Compact mode removes only trivially-true conditions (`1=1`, `0=0`, always-false
  prefixes); it is deliberately not a general SQL optimizer.

The scripted alternative `9to5-sql-forensics` formats bind literals by JDBC type instead
(numeric stays numeric). Use the browser tool for interactive work, the script for
packets and pipelines; state which one produced a given artifact.

## Known failures

- Two `chromium-mobile` Excel Playwright tests fail independently of any change
  (documented in the repo `AGENTS.md`, verified on a clean `main`). Do not chase them
  unless they are in scope.

## Safety notes

- The Rancher agent is loopback-only; hosted deployments cannot reach local clusters.
- Kubeconfig content never enters browser storage, workspace snapshots or hosted
  deployments.
- Large inputs are processed in web workers; outputs (logs, SQL, sheets) may contain
  production data and need sanitizing before sharing.
