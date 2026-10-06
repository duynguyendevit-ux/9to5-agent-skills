# Source-backed documentation review

Use this checklist for API and service-flow notes derived from repository evidence.
Complete relevant branches before delivering the local draft.

## Evidence

- Identify the correct repository lineage, HEAD and working-tree changes. Cite
  committed paths only when they match the inspected code; label local differences.
- Start from an entry point and follow only the relevant mapper, use case,
  persistence, listener and sender paths. Narrow searches to the mapped repositories.
- Distinguish source defaults, environment overrides and observed runtime behavior.
  Source inspection alone does not prove deployment or effective cluster config.
- Inspect config with targeted, non-secret keys or redacted output. Full YAML,
  `.env` and local-profile reads can expose credentials even during a read-only task.

## API behavior

- List request fields from the actual contract. Separate protobuf optionality,
  business requirements and enforced validation; domain/template fields need not
  exist in the request.
- Inspect the actual response builder and mapper. An empty response is not the
  saved entity, and an unpopulated result list is not the query result.
- Verify sorting, IDs, defaulting and enum/string codes from implementation rather
  than old documentation, comments or illustrative snippets.

## Asynchronous handoffs

- Record each service boundary, payload type, topic suffix/binding and sender.
  Keep save requests distinct from saved-record events.
- Separate event publication inside a transaction from listener execution after
  commit. Identify which side effects are awaited before the response.
- Verify what each success/pending flag means: marked before send, broker handoff,
  skip-send policy or downstream acknowledgement are different states.
- Separate transport retry from per-record rejection, terminal handling and worker
  recovery. State selection gates and duplicate windows without claiming exactly-once.

## Cache and Web configuration

When Redis influences the flow, include:

| Required evidence | What to record |
| --- | --- |
| Identity | Namespace, physical key pattern, ID/index fields and data structure. |
| Ownership | Writer/invalidation owner, readers and where the same key is shared. |
| Lifecycle | Miss/error fallback, cache warm-up, update/eviction timing and TTL. Label unverified runtime TTL separately from model declarations. |
| Recovery | Whether workers read only cache or can fall back to the database; effects of cache eviction on eligibility. |

For user-facing settings, trace the UI route and actual API call to the backend:
relative Web path, screen/menu label, editable fields, API method/path and owning
service. Do not invent an environment hostname. Distinguish Web-editable template
flags from deployment-only variables and from unused configuration keys.

Read both sides of shared template/cache update paths before describing their
contract. A Web reload that lists database rows does not imply cache warm-up.

## Diagrams and delivery

- Place diagrams in their corresponding flow/API sections when requested. Use
  rectangles for processing and diamonds with true/false branches for conditions;
  keep labels short and explain detailed policy in adjacent text/tables.
- Keep Mermaid source in the review Markdown. Reuse a known converter/renderer
  rather than repeatedly probing unrelated directories or importing functions
  from task-specific temporary scripts.
- For Confluence, verify macro support or render approved diagram images. Keep
  placement, topology and labels consistent with the reviewed Markdown; upload
  attachments before referencing them. Do not represent a code macro as a rendered
  diagram or claim a browser check when only storage was verified.
- Finish only when the requested folder contains the latest review file, source
  references are traceable, and requested cache/Web details are included. Publish
  from that file under the content-bound approval workflow in the parent skill.
