# Choose a useful diagram

| Question | Mermaid type |
| --- | --- |
| Which existing/new service or module owns what? | `flowchart LR` grouped with `subgraph` |
| What happens in one request or event delivery? | `sequenceDiagram` |
| What branches on success/failure? | `flowchart TD` |
| Which states can a job/entity enter? | `stateDiagram-v2` |
| How is data passed or stored? | `flowchart LR` with labeled data edges |

Start with the viewpoint that explains the proposed change. Use real component names and arrows backed by the inspected call chain; label newly proposed nodes/edges `(proposed)`. Show external actors explicitly. No implied direct call from an HTTP controller to a database if a use-case/repository intervenes. For async flow, make broker/outbox/worker and acknowledgement boundaries visible if known; otherwise label as unverified. Limit to roughly 5–9 primary nodes; split only when a second view adds information.

Avoid nonportable Mermaid syntax and secrets in labels. A diagram is a model of a proposal, not runtime proof. Add a brief caption stating what is existing versus proposed. When a polished standalone diagram is explicitly requested, invoke `archify` and use its validated HTML output instead of improvising an untested HTML diagram; keep the Markdown explanation and a source-readable diagram in `PROTOTYPE.md`.
