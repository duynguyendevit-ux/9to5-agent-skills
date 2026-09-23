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
| `9to5-jira` | 2.1.0 | Fetch a Jira issue and linked Confluence spec, explore the repo, write an implementation plan to `.kit/plans/`. |
| `9to5-logwork` | 1.4.0 | Log Jira worklogs via conversation (day, week, month flows) with Vietnamese descriptions, agent-activity sync from local session history, and a Jira REST fallback when zjira AI drafting is unavailable. |
| `9to5-jira-day-check` | 1.0.0 | Daily read-only summary: sprint issues, missing worklogs, releases still pending tag sync. |
| `9to5-release-confluence-sync` | 1.0.0 | Create or update the daily Confluence release page and refresh version, Release Tag, and Docker image cells. |
| `9to5-release-audit` | 1.0.0 | Read-only Confluence release-record snapshots and comparisons; distinguishes recorded release state from actual deployment. |
| `9to5-confluence-doc` | 1.0.0 | Draft and publish Vietnamese technical design pages with the OTS structure. |
| `9to5-sql-migration` | 1.0.0 | Write and review Oracle migration scripts (`admin/sql/oracle`, Flyway-style naming). |
| `9to5-oracle-index` | 1.0.0 | Decide and verify an Oracle index for a query shape: access vs filter, column order, plan reading, write cost, DDL handoff. |
| `9to5-id-design` | 1.0.0 | Choose and review primary-key strategy: identity vs UUID/ULID/UUIDv7/Snowflake, storage width, generator lifetime, exposure. |
| `9to5-env-config-sync` | 1.0.0 | Compare and align service env configs across environments; keep secrets out. |
| `9to5-spring-conventions` | 1.0.0 | Review Java/Spring changes against house conventions. |
| `9to5-k8s-service-debug` | 1.0.0 | Debug cluster services: locate pods, tail and filter logs, reconstruct Hibernate SQL, correlate to the local repo. |
| `9to5-kafka` | 1.0.0 | Kafka event contracts and the transactional outbox: catalog and bindings, topic placeholders, partition keys, outbox backlog and retry diagnosis. |
| `9to5-lib-bump` | 1.0.0 | Bump a shared library version across the services that consume it: drift audit, DEBUG flag check, version resolution, per-service build. |
| `9to5-skill-sync` | 1.0.0 | Keep an edited skill consistent across the canonical directory, the three mirrors, and this repository copy. |

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

- Skills are imperative and explain the reasoning, not just the rule.
- Registries record verified facts; unknown values are `null` or `TODO(unverified)`, never a plausible guess.
- Never commit secrets: tokens, passwords, private keys, kubeconfig content, or production logs. `cache.json` files are working state and stay out of the repository.
- After editing a skill, keep the four install locations in sync — `install.sh` re-links them.

## License

MIT — see [LICENSE](LICENSE).
