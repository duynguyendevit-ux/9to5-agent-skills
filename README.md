# 9to5 Agent Skills

Agent skills for OpenCode v2, used for day-to-day work on the OTS/C7 platform (Jira, release pages, Oracle migrations, Kubernetes debugging, Spring conventions).

> **Internal.** These skills reference internal hostnames, service names, namespaces, and repository paths. Keep the repository private.

## Install

Skills are discovered from these directories (identical copies):

- `~/.config/opencode/skills/` — OpenCode
- `~/.agents/skills/` — agent-agnostic
- `~/.claude/skills/` — Claude Code
- `~/.codex/skills/` — Codex

```bash
git clone git@github.com:<account>/9to5-agent-skills.git
cd 9to5-agent-skills
./install.sh
```

`install.sh` links or copies every directory under `skills/` into the four locations above. Pass `--copy` to copy instead of symlinking.

## Skills

| Skill | Version | Purpose |
|-------|---------|---------|
| `9to5-jira` | 2.1.1 | Fetch a Jira issue and linked Confluence spec, explore the repo, write an implementation plan to `.kit/plans/`. |
| `9to5-logwork` | 1.4.1 | Log Jira worklogs via conversation, normalize duration to seconds, and derive date-filtered agent activity. |
| `9to5-jira-day-check` | 1.0.1 | Daily read-only summary: sprint issues, missing worklogs, releases still pending tag sync. |
| `9to5-release-confluence-sync` | 1.0.2 | Verify service tags, reset inherited highlights on cloned pages, and reject stale-body updates. |
| `9to5-release-audit` | 1.0.1 | Read-only release-record comparisons; rejects duplicate service rows and reports empty records and source changes. |
| `9to5-confluence-doc` | 1.0.1 | Draft and publish Vietnamese technical design pages with the OTS structure. |
| `9to5-confluence` | 1.1.0 | General Confluence operations; updates require the reviewed base version and explicit approval. |
| `9to5-sql-migration` | 1.0.1 | Write and review Oracle migration scripts (`admin/sql/oracle`, Flyway-style naming). |
| `9to5-oracle-index` | 1.0.1 | Oracle-specific index candidates, actual-plan verification, null coverage, top-N and write trade-offs. |
| `9to5-id-design` | 1.0.1 | Identity, explicit sequences and application IDs: Oracle storage, allocation, concurrency and exposure. |
| `9to5-env-config-sync` | 1.0.1 | Compare and align service env configs across environments; keep secrets out. |
| `9to5-spring-conventions` | 1.0.1 | Review Java/Spring changes against house conventions. |
| `9to5-spring-core` | 1.0.0 | Source-backed starter coding guide and Java 17 service init template: core API contracts, JPA routing, auditing, context cleanup and environment configuration. |
| `9to5-k8s-service-debug` | 1.0.1 | Debug cluster services with source-filtered configuration inspection and local evidence. |
| `9to5-kafka` | 1.1.1 | Kafka contracts, corrected Oracle outbox diagnosis, long-running jobs and share-group trade-offs. |
| `9to5-lib-bump` | 1.0.1 | Audit and bump shared libraries; reject ambiguous checkout names and allow explicit paths. |
| `9to5-skill-sync` | 1.0.1 | Synchronize only 9to5 skills, preserve local mirror config, filter repository exports and detect unresolved drift. |

## Structure

```
skills/<name>/
├── SKILL.md          # frontmatter (name, description) + instructions
├── config/           # registries and read-only reference data
├── debug/            # investigation artifacts (gitignored except .gitkeep)
├── notes/            # durable flow notes
├── references/       # docs loaded on demand
└── scripts/          # deterministic helpers
```

`SKILL.md` frontmatter `description` is the trigger contract: it states what the skill does and when to use it. The body stays under ~500 lines; detail lives in `references/` and `scripts/`.

## Conventions

Every skill includes an **Example output** section with illustrative, non-secret data.
These examples define presentation expectations, not evidence of executed operations.

## Validation

```bash
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s skills/9to5-jira/scripts/tests -v
```

The regression suite uses temporary directories and mocked remote APIs. It covers
version conflicts, write gates, duplicate rows/checkouts, worklog durations, resumed
session dates, sync scope and mirror/export policy. Set `SKILLS_ROOT` to validate a
canonical collection before regeneration. Oracle guidance is documentation- and
schema-reviewed, not validated by running these Python tests against Oracle.

## Authoring conventions

- Skills are imperative and explain the reasoning, not just the rule.
- Registries record verified facts; unknown values are `null` or `TODO(unverified)`, never a plausible guess.
- Never commit secrets: tokens, passwords, private keys, kubeconfig content, or production logs. `cache.json` files are working state and stay out of the repository.
- After editing a skill, keep the four install locations in sync — `install.sh` re-links them.

## License

MIT — see [LICENSE](LICENSE).
