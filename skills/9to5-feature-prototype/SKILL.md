---
name: 9to5-feature-prototype
description: Prototype a proposed Platform/Product feature as a source-backed explanation and diagram fitted to the current repository's real services, modules, packages, APIs and data flow. Use when the user asks how a new feature would fit, wants a quick technical prototype, concept sketch, or visual walkthrough before implementation, even without a Jira key. Produces a Markdown prototype with a Mermaid diagram; does not change application code. For a full Jira ticket implementation plan use 9to5-jira; for a Confluence design page use 9to5-confluence-doc; for code implementation use the relevant coding skills.
license: MIT
compatibility: Requires Python 3 and a local git checkout of the project. Mermaid rendering depends on the Markdown viewer; an optional polished HTML diagram uses the separate archify skill when installed.
metadata:
  version: "1.0.0"
---

# Feature prototype — explain before implementing

## Example output

Illustrative only; use real names and paths from the selected checkout.

```text
Feature: Retry a failed export
Placement: example-service/src/main/java/tech/app/usecase/ExportUseCaseService.java (existing)
Proposed: status endpoint under the existing export controller; retry state in the existing job store.
Diagram: sequence showing client → controller → use case → repository → worker.
Unverified: retry limit and result retention policy.
Artifact: .kit/prototypes/2026-09-25-export-retry/PROTOTYPE.md
Application code: unchanged.
```

## Scope and handoffs

- This is a **design prototype**, not an executable spike: explain the proposed behavior, place it in the real project structure, and visualize the important interaction. Do not create stubs, migrations, branches, remote resources, or application-code edits.
- A Jira key may be background context, but a request for a full ticket plan belongs to `9to5-jira`. Do not write to `.kit/plans/` here.
- For a detailed Kafka contract, Oracle DDL/index, ID strategy, or starter API, consult `9to5-kafka`, `9to5-sql-migration`, `9to5-oracle-index`, `9to5-id-design`, or `9to5-spring-core` respectively. Do not substitute this prototype for their verification workflows.
- Never publish to Confluence or change environment configuration in this workflow; use the dedicated skills when explicitly asked.

## Workflow

1. **Select one checkout.** Resolve `git rev-parse --show-toplevel` from the working directory or the service directory named by the user. If the directory is not a git checkout, identify the intended repository before claiming any project-specific placement. If multiple services could own the feature, present the competing owners as unknown rather than inventing an owner.
2. **Inventory structure (read-only).** Run `python3 <this-skill>/scripts/detect_structure.py --root <repo-root>` (use the installed skill path, not a project-relative path). Read [`references/structure-detection.md`](references/structure-detection.md) for the evidence protocol. The JSON is a navigation hint, not proof of runtime wiring.
3. **Follow the closest existing feature.** Search up to eight targeted times using the feature's domain terms; read one entry point, one orchestration/business layer and the relevant persistence/event contract if present. Prefer real implementation and tests over the inventory's directory names. Check the build/module relationships and existing conventions before naming proposed paths. If no analogue exists, label new paths as *proposed*, not *existing*.
4. **Design the smallest useful slice.** Specify a user-visible behavior, entry point, state/data ownership, main flow, error/duplicate path and verification. Mark each claim `Existing`, `Proposed`, or `Unverified`. Distinguish source code evidence from assumptions about deployed infrastructure. Do not paste secrets, credentials, internal hostnames or full configuration values into the artifact.
5. **Explain and draw.** Read [`references/prototype-template.md`](references/prototype-template.md) and [`references/diagrams.md`](references/diagrams.md). Follow the request language; default to Vietnamese for Platform/Product work, keeping identifiers unchanged. Add one Mermaid diagram that teaches the central design decision; add a second only if a different viewpoint is necessary. If the user specifically requests a polished presentation diagram, use `archify` and follow its validation/delivery rules; do not claim HTML validation without running it.
6. **Deliver.** Write `.kit/prototypes/{YYYY-MM-DD}-{short-slug}/PROTOTYPE.md` relative to the selected checkout; that directory is the only permitted project write location. If using archify, put its output there as well. Do not overwrite an unrelated existing prototype: choose a disambiguated slug or stop. Show the explanation and diagram in the reply and preview the artifact where supported. State clearly that application code was not modified and whether any behavior was actually verified.

## Stop conditions

- No checkout or no evidence for a unique service owner: supply a clearly generic sketch only if useful; do not present it as a project-fitted prototype or create an artifact in a guessed repository.
- Missing schema, API, topic, library version, or deployment setting: leave `Cần xác nhận` / `Unverified`; do not fabricate.
- User asks for running code or an implementation instead of a design prototype: hand off to the relevant coding skill and follow the user's implementation request separately.
