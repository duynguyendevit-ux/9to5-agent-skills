# config/

| File | Purpose |
|------|---------|
| `paths.json` | Canonical directory, mirror directories, repository path, and the exclusion lists. |

## Editing

Change a path here when a directory moves — the script reads everything from this file. Two lists control what is copied:

- `exclude_always` — applied everywhere: `__pycache__`, `*.pyc`, `.DS_Store`.
- `exclude_from_repo` — applied only to the repository copy: `cache.json`, `endpoints.json`, `debug/artifacts/*`.

Add to `exclude_from_repo` whenever a new class of local-only file appears in a skill. The test is simple: if the content contains an internal hostname, a token, or is regenerated at runtime, it does not belong in the repository.

`keep_empty_dirs` lists files that must survive the copy even though their directory is otherwise excluded (`debug/artifacts/.gitkeep`).

## Rules

- Paths only. No tokens, no credentials.
- Keep `exclude_from_repo` in step with the repository's `.gitignore`; the two describe the same intent from different sides.
