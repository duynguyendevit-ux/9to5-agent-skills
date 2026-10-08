# Repository navigation

This repository exports agent skills; it is not a service checkout.

- **Authoring or syncing:** read [authoring modes](docs/authoring.md) before editing
  `skills/`. Resolve the source of truth first; preserve existing local work.
- **Choosing a workflow or CLI:** read [workflow routes](docs/workflows.md).
  Release-version links, Jira metadata writes and task mapping are separate scopes.
- **Finding a skill:** use the generated [catalog](README.md#skills), then read only
  that skill's `SKILL.md` and the references for the requested branch.
- **Validation:** use the focused checks in [workflow routes](docs/workflows.md#validation),
  then `python3 -m unittest discover -s tests` for the full offline suite.
- **Catalog changes:** run `python3 scripts/update_catalog.py`, then its `--check`
  mode. Skill frontmatter owns names, versions and descriptions.
- **Historical evidence:** [documentation index](docs/README.md) distinguishes
  past verification snapshots from current checks. A dated report is not today's result.

Keep endpoint/auth files and private operation artifacts out of this export.
Remote publication and git commit/push retain their separate approval gates.
