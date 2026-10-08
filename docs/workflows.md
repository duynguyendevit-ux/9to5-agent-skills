# Workflow routes

Choose the requested operation before loading detailed policy or inspecting source.

| Task | Owner / first read | Supporting entry point | Completion |
| --- | --- | --- | --- |
| Add an overall Jira release-version link to Confluence | [Release sync](../skills/9to5-release-confluence-sync/SKILL.md), its Jira-link branch | [Jira release link](../skills/9to5-release-confluence-sync/references/jira-release-link.md) | One reviewed page-level link; Jira unchanged |
| Change Jira version date/state | Release sync, its Jira-metadata branch | [Jira version update](../skills/9to5-release-confluence-sync/references/jira-release-version.md) | Approved fields applied and read back; no inferred deployment |
| Map tasks to services | Release sync, explicitly requested task-map branch | [Jira release link](../skills/9to5-release-confluence-sync/references/jira-release-link.md#explicit-task-mapping) | Scoped source-backed mapping with limits; not automatic for a version link |
| Verify exact PROD tags/images or prepare a release | Release sync | [PROD comparison](../skills/9to5-release-confluence-sync/references/prod-version-comparison.md) | Exact Git refs and Nexus artifacts verified; plan separate from publication |
| Read/update another Confluence page | [Confluence](../skills/9to5-confluence/SKILL.md) | `confluence.py` and its publication reference | Approved storage and server-view checks; browser coverage stated separately |
| Plan a Jira implementation ticket | [Jira](../skills/9to5-jira/SKILL.md) | `zjira issue get`, linked spec, relevant checkout | Source-backed plan; no implementation implied |
| Install, edit or mirror skills | [Authoring modes](authoring.md) | `install.sh` **or** scoped `skill_sync.sh`, according to source ownership | Source/mirrors/export agree; no automatic commit/push |
| Generate a Spring starter service | [Spring core](../skills/9to5-spring-core/SKILL.md) | `init_core.py` | Dry-run/apply checked; compile/runtime evidence remains separate |
| Publish code or audit GitHub | [Git publish](../skills/9to5-git-publish/SKILL.md), [GitHub audit](../skills/9to5-github-audit/SKILL.md) | Their task-specific instructions | Named repo/commit only; Confluence approval does not authorize git push |

For other domains, choose one owner from the [catalog](../README.md#skills).

## Release/Confluence capability matrix

| Tool | Use | Auth / configuration | Limits |
| --- | --- | --- | --- |
| `9to5-confluence/scripts/confluence.py` | Publish a saved, custom approved storage body | Shared `9to5-confluence-auth` resolver: dotfiles, overrides and trusted endpoints | Full-body replacement requires original `--expected-version`; preview output is private when body contains secrets |
| `9to5-release-confluence-sync/scripts/sync_release_tags.py` | Registry-based daily tag/paint/rollover engine | Its endpoint/project registry and shared auth resolver | Newest-tag selection is not exact PROD target pinning; engine does not verify Nexus or create the complete custom review |
| `9to5-jira/scripts/update_confluence_release.py` | Legacy interactive service/tag picker or an explicitly requested legacy profile | Its endpoint files; token reader currently reads only zjira YAML | Fixed version/tag/image column indexes, no shared overlay-token resolution; use primary release workflow for custom PROD tables |
| `9to5-confluence/scripts/storage_tables.py` | Offline cell/column edits and semantic read-back comparison | No credentials or network | Flat, rectangular tables only; explicit repair for a known missing colgroup column; rejects ambiguous/unsupported layouts |

For custom release pages, prepare through the release owner and publish the saved
body through the general Confluence helper. Read the actual CLI `--help` before
execution; this matrix selects the tool rather than duplicating its flags.

## Validation

Run from the checkout. Python 3 and PyYAML are required for metadata and auth tests.

| Change | Focused check |
| --- | --- |
| Catalog, navigation or source-routing docs | `python3 scripts/update_catalog.py --check`; `python3 -m unittest discover -s tests -p 'test_navigation.py'` |
| Table editing / publication verification | `python3 -m unittest discover -s tests -p 'test_storage_tables.py'`; `python3 -m unittest discover -s tests -p 'test_confluence_publication.py'` |
| Release links and release workflow contracts | `python3 -m unittest discover -s tests -p 'test_release_source_links.py'`; `python3 -m unittest discover -s tests -p 'test_skill_regressions.py'` |
| Starter template generation | `python3 -m unittest discover -s tests -p 'test_core_init.py'` |
| Legacy Jira release script | `python3 -m unittest discover -s skills/9to5-jira/scripts/tests` |

After focused checks, run `python3 -m unittest discover -s tests`.
For canonical-owned work, use `SKILLS_ROOT` to test that source before export, then
test the exported checkout. These are offline checks, not live API/deployment proof.
