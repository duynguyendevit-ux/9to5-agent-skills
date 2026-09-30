# Prototype format

Use these headings in the artifact; translate to the request language. Keep the answer short enough to review, but make every proposed connection testable. `Existing` means directly observed in source; `Proposed` means not in source yet; `Unverified` means source or requirement is missing. Never present an illustrative API or table as if already deployed.

````markdown
# <Feature name> — design prototype

> Repository: `<verified root>` (branch/revision if useful)
> Status: design only; application code unchanged

## Purpose and smallest end-to-end slice
<who needs what, one success criterion, explicit exclusions>

## Fit in the current structure
| Role | Current evidence | Proposed change |
| --- | --- | --- |
| Entry point | `path` and existing symbol, or Unverified | exact proposed module and path |
| Business flow | ... | ... |
| Persistence / events | ... | ... |

## Contract and behavior
<request/response or event shape only if relevant; success, errors, idempotency/security when applicable>

## Diagram
```mermaid
<the selected viewpoint and only justified actors/arrows>
```

## Decisions and unknowns
- Existing: <path-backed observation>
- Proposed: <choice and reason>
- Cần xác nhận / Unverified: <what evidence or decision is missing>

## Verification without implementation
<tests that would demonstrate the slice later; never claim they already passed>
````

Add a second diagram only when it answers a different question (e.g. architecture ownership versus runtime sequence). If the viewer does not support Mermaid, still keep the diagram source in the Markdown file and render an alternate artifact only when asked. The reply should include the high-level placement, Mermaid diagram, unknowns, artifact path and a clear no-code-change statement.
