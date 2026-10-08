# Public export boundary

Use this branch when a skill collection is published publicly and its canonical
copy contains organization-specific examples, release records, inventories or paths.

1. Pin existing work and check private mirror parity before changing export rules.
2. Set `public_export_policy` in `config/paths.json` to a machine-local JSON file
   outside the skills tree, e.g. `~/.config/opencode/skill-data/9to5-skill-sync/public-export.json`.
   An absent policy setting
   means identity export; a configured missing policy is a blocker.
3. Use policy `replacements` for text examples, `path_replacements` for filenames,
   `overrides` for synthetic inventories, `omit` for private notes, and `deny_patterns`
   to reject remaining identifiers. Paths are relative to a skill; override/omit
   keys are prefixed with the skill directory name. Policy values stay private.
4. Run scoped `--apply`, then `--check --leak-check`. The synchronizer prepares an
   isolated public tree before writing any destination. Mirrors still use the raw
   canonical source. Public export preserves file permissions and binary bytes,
   rejects path collisions/unhandled symlinks and validates output before replacing
   copies. A private-file symlink is exported only through an explicit synthetic
   override or omitted; its target is never read for that export.
5. Regenerate the repo catalog from exported metadata. Sanitize repo-owned docs/test
   examples separately; run the full offline suite on the exported tree. Check
   executable examples, links, synthetic registry selection and filename references.
6. Review and commit only the requested scope. Report that current-tree cleanup
   does not erase previously pushed Git history. History rewriting, removal of
   remote data and credential rotation have separate authorization boundaries.

An example policy uses fictional identifiers only:

```json
{
  "replacements": [["INTERNAL_EXAMPLE", "DEMO"]],
  "path_replacements": [["internal-example", "demo"]],
  "overrides": {"9to5-example/projects.json": "{\"projects\": {}}\n"},
  "omit": ["9to5-example/notes/private-*.md"],
  "deny_patterns": ["INTERNAL_EXAMPLE"]
}
```

The scanner is a disclosure screen, not proof of absence. Review its policy coverage
and any binary assets separately. Tokens/endpoints/private artifacts stay excluded
even when a textual replacement could disguise them. The renderer is for copied
staging trees only, not editing canonical files or another contributor's worktree.
