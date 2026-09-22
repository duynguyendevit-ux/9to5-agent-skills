# config/

| File | Purpose |
|------|---------|
| `libraries.json` | Library registry: version property → local repo, published artifact, DEBUG flag map, build commands, commit conventions. |
| `roots.json` | Where to scan for real working checkouts, and what to exclude (notably the `gitlab-download-scripts` mirror tree). |

## Editing

Add a library when a new shared starter appears: a `libraries.json` entry with the property name, the local repo, the artifact coordinates, and any `DEBUG_*` flag. Add the property to `not_local` instead when the source is not checked out on this machine — the audit will still find consumers but `suggest` will refuse, which is the correct behaviour.

Add a path to `exclude_paths` whenever a second copy of the repositories appears (extracted archives, temp clones, bulk mirrors). Bumping a copy nobody builds is the failure mode this file exists to prevent.

## Rules

- Paths and property names only. No tokens, no Nexus credentials, no connection strings.
- The scan is read-only for `audit`, `list`, and `suggest`. Only `set --apply` writes, and only to `gradle.properties` files that already define the property.
