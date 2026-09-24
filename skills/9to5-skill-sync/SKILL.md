---
name: 9to5-skill-sync
description: Keep an edited 9to5 skill consistent across its canonical directory, the three mirror directories, and the git repository copy — mirror the change, regenerate the repo copy with the correct exclusions, and verify parity by hash. Use when a skill has just been created or edited, when asked to sync or publish skills, when checking whether the skill copies have drifted, before committing skill changes, or when a skill works in one agent but not another.
license: MIT
compatibility: Requires bash, rsync, python3, and a checkout of the skills repository. Reads paths from config/paths.json.
metadata:
  version: "1.0.1"
---

# Skill Sync

## Example output

Illustrative successful parity check; digests here are placeholders.

```text
skill           canonical  .agents   .claude   .codex    repo
9to5-example    <digest>   <digest>  <digest>  <digest>  OK
all locations match canonical
```

For a failed check, report the affected destination and nonzero status, for example:

```text
orphan skill (not removed): /example/mirror/9to5-retired/
1 unresolved difference(s) or leak(s)
Exit status: 1
```

A skill exists in five places. Only one is edited by hand.

| Location | Role |
|----------|------|
| `~/.config/opencode/skills/` | **canonical** — edit here |
| `~/.agents/skills/` | mirror |
| `~/.claude/skills/` | mirror |
| `~/.codex/skills/` | mirror |
| `~/Documents/duylab/9to5-agent-skills/skills/` | generated repo copy, committed and pushed |

Paths and exclusion lists live in `config/paths.json`. If a location moves, change it there rather than in the script.

## Why the repo copy is not a plain copy

Three things must never reach the repository:

| Excluded | Reason |
|----------|--------|
| `cache.json` | transient working state (release tag cache, ~100 KB) |
| `endpoints.json` | real internal hostnames; the repo ships `endpoints.example.json` instead |
| `debug/artifacts/*` | investigation evidence; only `.gitkeep` is tracked |

The comparison therefore applies the repo exclusions to the canonical side too — otherwise every skill that has an `endpoints.json` would report permanent false drift.

Mirrors receive all canonical files except `exclude_always`, including local endpoint
files (with their permissions), caches, and debug artifacts. They are local working
copies, not publishable exports. Only the repository copy applies `exclude_from_repo`.
Copy rules and hash comparisons use the same policy for each destination.

## Workflow

1. **Edit** the skill under `~/.config/opencode/skills/<name>/`.
2. **Check** for drift and confirm the baseline is clean before changing anything:
   ```bash
   scripts/skill_sync.sh --check
   ```
3. **Apply** to the mirrors and the repo copy:
   ```bash
   scripts/skill_sync.sh --apply
   ```
   Use `--skill <name>` to limit it, `--no-repo` when the repo should not be touched.
4. **Verify** — re-run `--check`. It exits non-zero while any location differs, so a clean exit is the proof.
5. **Commit and push the repo.** The script deliberately does not: skill changes deserve a real message, and the user decides when to publish. Run the leak check first — it derives the forbidden hostnames from the local `endpoints.json` files, so the repository itself never contains them:
   ```bash
   scripts/skill_sync.sh --leak-check
   ```
   Expect `repo is free of internal hostnames`. Any `LEAK` line names the file to fix.

## When a skill is new

The `--check` output shows `missing` for a location that does not have the skill yet. `--apply` creates it. After the first apply, add the skill to the repository README table so the repo documents what it ships.

## Reading the check output

| Cell | Meaning |
|------|---------|
| same digest in every column | in sync |
| `missing` | that location does not have the skill |
| a different digest | content differs; `--apply` fixes it |
| `OK` in the repo column | matches canonical once the repo exclusions are applied |
| `N location(s) differ` | count of cells needing action; exit code 1 |
| `skipped (symlink, …)` | entry in the canonical directory that points elsewhere; never mirrored or published |

## Rules

- Edit the canonical copy only. Editing a mirror or the repo copy directly guarantees drift on the next apply.
- Manage only real `9to5-*` directories. Other prefixes are outside this collection.
- Reject empty, option-valued, or invalid `--skill` selectors before any copy occurs.
- Report orphan `9to5-*` destination directories without deleting them. Both check and
  apply exit nonzero if drift, orphans, or a requested leak scan remains unresolved.
- A symlinked entry in the canonical directory is not a skill this script owns — it is a working
  tree or a package install, and its contents change without notice. It is skipped and reported,
  never mirrored and never committed.
- `--skill <name>` limits a run to one skill. A bare `--skill` with no name is an error; it must
  never silently expand into a whole-collection sync.
- Never hand-edit the repo copy to make `--check` pass; fix the canonical copy and re-apply.
- Never commit `endpoints.json`, `cache.json`, or debug artifacts. If one appears in `git status`, the exclusion list or the copy step is wrong — fix the cause, do not `git add` around it.
- Run `--check` before and after: before proves the baseline, after proves the change landed everywhere.
- If a mirror directory is missing entirely, `--apply` creates it. A tool that is not installed on the machine still gets a directory; that is harmless.
