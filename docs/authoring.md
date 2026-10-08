# Choose the source before editing

Two supported setups use opposite copy directions. Determine which one is active
before editing or running either installer or synchronizer.

## Repository-owned installation

For a downloaded checkout installed with `install.sh`, the checkout is the source.
Default installation symlinks agent directories to `skills/`; edits propagate
through those links. `--copy` installs independent copies: refresh them through
the installer after reviewing local changes and its dry run.

Edit `skills/<name>/` in this setup. The canonical-directory synchronizer deliberately
skips symlinked canonical entries: use the checkout/installer route instead.

## Canonical-owned authoring

For independently maintained installed skills, use
[`9to5-skill-sync`](../skills/9to5-skill-sync/SKILL.md). Its `config/paths.json`
defines the canonical directory, mirrors, export destination and exclusions.
Confirm the selected entry is a real canonical directory, not a symlink to a checkout.

1. Run a scoped `skill_sync.sh --check --skill <name>` and investigate drift.
2. Edit the canonical skill. Existing mirror/export changes are not disposable.
3. Validate it using `SKILLS_ROOT=<canonical-directory>` with the relevant tests.
4. Run scoped `--apply --skill <name>`, then scoped `--check`.
5. In the export checkout, regenerate the catalog and run its `--check` plus the full
   offline suite. Review the diff and run the synchronizer's leak check before publication.

Edit repo-owned files (`AGENTS.md`, `README.md`, `docs/`, `tests/`, root `scripts/`)
in the checkout in either mode. Synchronization owns only the exported `skills/` trees.

## Local files and evidence

Endpoint/auth files are machine-local; read them through the auth helpers and keep
values out of export/docs. Mirror copies and public exports have different exclusion
policies. Generated caches such as `.gradle/` are neither template inputs nor skill
source; exclude them from copying/hashing without deleting somebody else's cache.

Operation snapshots, private payloads and receipts belong in a private working
directory. Publish only sanitized review artifacts. Record durable behavior in the
owning skill/reference, not by checking private snapshots into this repository.

Store actual config and inventory under `~/.config/opencode/skill-data/<skill>/`,
outside both the skill installation and public checkout. Existing installed paths
may be compatibility symlinks to these private files; the public export uses
synthetic replacements or excludes them. Keep the dotfile directories private.

Task memory belongs in `<working-repo>/.kit/memory/`; release drafts, snapshots,
approval manifests and receipts belong in `<working-repo>/.kit/releases/<request>/`.
Add both directories to that repo's `.gitignore` before saving private data. Without
a working repo, use `~/.local/state/opencode/requests/<request>/` (mode 700), or the
approved private temporary directory for short-lived work. Public skills carry the
workflow/templates, not real request data. Serve sanitized previews separately.

Public exports can differ deliberately from canonical/mirror copies. Read the
[public-export boundary](../skills/9to5-skill-sync/references/public-export.md) when
maintaining a public collection: use synthetic product/user examples, reserved
example hosts and documentation IP ranges instead of publishing internal names,
inventories, endpoints or release records. Keep disclosure rules machine-local.
Parity compares the export with the sanitized expected representation.

The installer backs up existing destinations, but running it is still a replacement
operation. It is not an interchangeable way to synchronize canonical-owned work.
