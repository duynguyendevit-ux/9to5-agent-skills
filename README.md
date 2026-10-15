# 9to5 Agent Skills

Agent skills for OpenCode v2, used for day-to-day development work (Jira, release pages, Oracle migrations, Kubernetes debugging, Spring conventions).

Start with [workflow routes](docs/workflows.md) to select an owner and CLI.
For edits or sync, resolve [authoring mode](docs/authoring.md) first; installation
and canonical-owned authoring use different source/copy directions.

## Download and install

### Install with the Skills CLI

Requires Git, Node.js and npm (`npx`). List the available skills without installing:

```bash
npx skills add duynguyendevit-ux/9to5-agent-skills --list
```

#### Global — available across all repositories

Install the collection for OpenCode, Claude Code and Codex in your user directories:

```bash
npx skills add duynguyendevit-ux/9to5-agent-skills \
  --skill '*' --agent opencode claude-code codex --global
```

#### Repository — available in one project

Run from the repository where the skills should be installed. Without `--global`,
the CLI installs into that project's skill directories:

```bash
cd /path/to/your/repository
npx skills add duynguyendevit-ux/9to5-agent-skills \
  --skill '*' --agent opencode claude-code codex
```

Project skills go into `.agents/skills/` for OpenCode/Codex and `.claude/skills/`
for Claude Code. Review the generated files before committing them to your repository.

In either command, replace `--skill '*'` with `--skill 9to5-git-publish` to select
one skill. For Confluence documentation, select the cooperating set with
`--skill 9to5-confluence-doc 9to5-confluence 9to5-confluence-auth`.
The CLI prompts for confirmation and installation method; review the destination
before accepting. See the [Skills CLI documentation](https://github.com/vercel-labs/skills#install-a-skill).

### Download the repository and install everything

Requires Git and Bash (Linux, macOS or WSL). HTTPS cloning a public repository does
not require a GitHub account or SSH key:

```bash
git clone https://github.com/duynguyendevit-ux/9to5-agent-skills.git
cd 9to5-agent-skills
./install.sh --dry-run
./install.sh
```

Alternatively, [download the ZIP](https://github.com/duynguyendevit-ux/9to5-agent-skills/archive/refs/heads/main.zip),
extract it, and run the installer from the extracted directory.

`install.sh` installs every skill globally into all four directories:

- `~/.config/opencode/skills/` — OpenCode
- `~/.agents/skills/` — agent-agnostic
- `~/.claude/skills/` — Claude Code
- `~/.codex/skills/` — Codex

The default is a symlink to the checkout; keep that directory in place. For an
initial installation using independent copies, run `./install.sh --copy` instead.
Existing entries not already linked to this checkout are moved to timestamped
`.bak.*` paths before replacement. Use the dry run to inspect those changes first.

### Update and verify

For Skills CLI installations:

```bash
npx skills list --global
npx skills update 9to5-git-publish --global
```

For repository-level installs, run from that repository: use `npx skills list` to
inspect installed skills and `npx skills update 9to5-git-publish --project` to update
only the project copy.

For Git checkouts, run from the downloaded repository:

```bash
git pull --ff-only
./install.sh --dry-run
./install.sh
```

Existing symlinks reflect pulled changes; re-running the installer adds newly
introduced skills. For copy-based installs, use `./install.sh --copy` to refresh
the copies. ZIP downloads have no Git history; download/extract the latest ZIP to
update them. Do not discard local edits if a pull refuses to proceed.

Restart the agent after installation or updates. Confirm the selected skill has
a `SKILL.md` in the agent's skill directory. Installing skills does not install
their external tools or credentials: check each skill's prerequisites. Confluence
helpers need Python 3, PyYAML and the `zjira` CLI; local endpoint/auth files are not
included in the public download.

## Skills

Generated from skill frontmatter by `python3 scripts/update_catalog.py`.
Validate without writing using its `--check` mode.

<!-- skill-catalog:start -->
| Skill | Version | Purpose |
| --- | --- | --- |
| [`9to5-code-review`](skills/9to5-code-review/SKILL.md) | 1.0.2 | Perform a rigorous two-axis code review on a git diff along Standards (clean code, team patterns) and Spec (correctness, safety, edge cases) axes with concrete findings and explicit verification limits. |
| [`9to5-confluence`](skills/9to5-confluence/SKILL.md) | 1.6.3 | Search, read, create, update, and manage Confluence documentation pages via zjira CLI and REST API — navigate page trees, inspect versions, update storage format content, manage comments, labels, and attachments with dry-run verification. |
| [`9to5-confluence-auth`](skills/9to5-confluence-auth/SKILL.md) | 1.1.2 | Resolve, verify, and manage authentication credentials (PAT tokens) for Confluence, Jira, and GitLab from local dotfiles and configurations. |
| [`9to5-confluence-doc`](skills/9to5-confluence-doc/SKILL.md) | 1.3.7 | Draft, structure, and publish source-backed technical documentation and system design pages on Confluence in Vietnamese following standard architecture templates. |
| [`9to5-container-build`](skills/9to5-container-build/SKILL.md) | 1.0.2 | Build, review, and optimize container images and CI release configurations for service containers — two-stage Dockerfiles, internal registry base images, shared CI/CD pipeline templates, APP_VERSION wiring, JVM flags, and container OOM dump paths. |
| [`9to5-debug-loop`](skills/9to5-debug-loop/SKILL.md) | 1.0.2 | Execute an evidence-driven, hypothesis-testing debug loop to isolate, reproduce, and diagnose bugs, test failures, wrong behavior, or performance regressions. |
| [`9to5-env-config-sync`](skills/9to5-env-config-sync/SKILL.md) | 1.0.3 | Compare, validate, and synchronize environment service configurations (values.yaml, .env) across deployment environments (dev, staging, uat, prod) — align environment variables, report configuration drift, and keep secrets out of source control. |
| [`9to5-feature-prototype`](skills/9to5-feature-prototype/SKILL.md) | 1.0.2 | Prototype a proposed feature or architecture change as a source-backed technical explanation and Mermaid diagram fitted to the repository's real services, APIs, and data flow before implementation. |
| [`9to5-git-publish`](skills/9to5-git-publish/SKILL.md) | 1.0.2 | Safely stage, check, commit, and push git changes in the explicitly targeted repository with pre-commit validation and remote branch verification. |
| [`9to5-github-audit`](skills/9to5-github-audit/SKILL.md) | 1.0.2 | Perform a read-only audit of visible GitHub repositories, permissions, branch protections, and Actions CI/CD workflows with commit-specific evidence. |
| [`9to5-github-settings`](skills/9to5-github-settings/SKILL.md) | 1.0.2 | Safely review and update GitHub repository settings (visibility public/private, repository description, topics) with explicit dry-run planning and authorization. |
| [`9to5-grpc-contracts`](skills/9to5-grpc-contracts/SKILL.md) | 1.0.2 | Design, review, and maintain gRPC and Protocol Buffer contracts — proto3 directory layouts, versioned packages, java_package conventions, wire-compatibility rules, artifact versioning, and client/server integrations. |
| [`9to5-handoff`](skills/9to5-handoff/SKILL.md) | 1.0.2 | Save a concise, source-linked handoff document so another coding session or agent can continue from verified state without losing context. |
| [`9to5-heap-triage`](skills/9to5-heap-triage/SKILL.md) | 1.0.2 | Analyze JVM heap dumps (*.hprof) using headless Eclipse Memory Analyzer (MAT) — detect memory leaks, identify dominator tree retainers, inspect biggest retained objects, and correlate memory exhaustion back to code. |
| [`9to5-id-design`](skills/9to5-id-design/SKILL.md) | 1.0.3 | Evaluate, design, and review primary key and unique identifier strategies — database identity/sequence vs application UUID, ULID, UUIDv7, Snowflake, index locality, Oracle heap storage, and API exposure. |
| [`9to5-jira`](skills/9to5-jira/SKILL.md) | 2.1.5 | Plan, research, or estimate Jira issues using the zjira CLI. |
| [`9to5-jira-day-check`](skills/9to5-jira-day-check/SKILL.md) | 1.0.3 | Perform a daily Jira and workflow status check — sprint issues currently in progress or assigned, missing worklogs for the current week, and pending release tag synchronizations. |
| [`9to5-k8s-service-debug`](skills/9to5-k8s-service-debug/SKILL.md) | 1.0.3 | Debug microservices and workers running on Kubernetes clusters — locate pods by app name across namespaces, tail and filter logs, extract Hibernate SQL with bound parameters into runnable statements, inspect container env/limits, and correlate failures back to code. |
| [`9to5-kafka`](skills/9to5-kafka/SKILL.md) | 1.1.4 | Design, review, and troubleshoot Kafka event streaming, transactional outbox patterns, and work queue consumers — event schema bindings, partition keys, consumer groups, poll timeouts, offset commit strategies, duplicate handling, and outbox backlog diagnostics. |
| [`9to5-lib-bump`](skills/9to5-lib-bump/SKILL.md) | 1.0.3 | Audit and bump shared library dependencies (kafka starter, common-core, service starters) across consuming microservices — inspect dependency drift, resolve target versions from library git tags, update gradle.properties, verify builds, and commit cleanly. |
| [`9to5-logwork`](skills/9to5-logwork/SKILL.md) | 1.4.3 | Log Jira worklogs via structured conversation: scan assigned issues, gather task/hours/note input in chat, generate professional Vietnamese worklog descriptions, and submit via zjira. |
| [`9to5-mqtt-notifications`](skills/9to5-mqtt-notifications/SKILL.md) | 1.0.2 | Design, review, and debug MQTT real-time message delivery and UI refresh events — merchant gateway patterns, topic hierarchy, NotificationMessage payloads, QoS selection, connection limits, and channel trade-offs (MQTT vs Kafka). |
| [`9to5-mydevtools`](skills/9to5-mydevtools/SKILL.md) | 1.0.2 | Inspect, run, and extend MyDevTools developer utilities — Oracle execution plan visualizer, log analyzer, SQL parameter extractor, Kafka/Protobuf payload decoder, environment-to-k8s converter, cron and nginx generators. |
| [`9to5-oracle-index`](skills/9to5-oracle-index/SKILL.md) | 1.0.3 | Analyze, design, and verify Oracle database indexes for query performance — column selection and ordering, DBMS_XPLAN access/filter predicates, implicit type conversions, and read gain vs write overhead trade-offs. |
| [`9to5-oracle-locking`](skills/9to5-oracle-locking/SKILL.md) | 1.0.2 | Design and review concurrent work claiming and lock contention on Oracle databases — SELECT FOR UPDATE SKIP LOCKED batch claiming, NOWAIT semantics, lock wait analysis, ORA-00060 deadlock diagnosis, and transaction hygiene for high-throughput workers. |
| [`9to5-redis-design`](skills/9to5-redis-design/SKILL.md) | 1.0.2 | Design, review, and debug Redis caching and runtime control patterns — key namespacing, TTL strategies, cache-aside with database fallback, AFTER_COMMIT cache invalidation, Lua script concurrency guards, and runtime feature flags in Redis. |
| [`9to5-release-audit`](skills/9to5-release-audit/SKILL.md) | 1.0.3 | Audit and snapshot recorded service versions and release tags on Confluence release documentation — capture traceable snapshots, compare release pages over time, and report recorded drift without claiming production runtime verification. |
| [`9to5-release-confluence-sync`](skills/9to5-release-confluence-sync/SKILL.md) | 1.8.4 | Prepare, verify, and publish Confluence release pages with validated Git tags, container images, PROD environment comparisons, ENV variable notes, and Jira release version links. |
| [`9to5-scheduled-jobs`](skills/9to5-scheduled-jobs/SKILL.md) | 1.0.2 | Design, review, and troubleshoot scheduled batch jobs and milestone processing pipelines — DB polling vs Redis ZSET scheduling, dispatcher-to-Kafka handoffs, runtime mode switches, timezone handling, delay tuning, catch-up logic, and multi-replica safety. |
| [`9to5-skill-sync`](skills/9to5-skill-sync/SKILL.md) | 1.1.2 | Synchronize, validate, and export 9to5 agent skills across canonical source (~/.config/opencode/skills), local mirrors (.agents, .claude, .codex), and the public git repository (9to5-agent-skills) with strict parity and leak checks. |
| [`9to5-spring-conventions`](skills/9to5-spring-conventions/SKILL.md) | 1.0.3 | Review Java and Spring Boot code changes against established team coding standards — Objects.isNull/nonNull, CollectionUtils/StringUtils, explicit imports, clean exception handling, and test file discipline. |
| [`9to5-spring-core`](skills/9to5-spring-core/SKILL.md) | 1.0.3 | Scaffold, initialize, and structure Spring Boot microservices using the shared starter — clean architecture layers (controller, use-case, repository), standard API responses, auditing, writer-reader database routing, and environment-driven configuration. |
| [`9to5-spring-env-scan`](skills/9to5-spring-env-scan/SKILL.md) | 1.0.2 | Inventory environment variables and their Java/Spring consumers from application YAML/properties, @Value, @ConfigurationProperties, and programmatic property lookups. |
| [`9to5-sql-forensics`](skills/9to5-sql-forensics/SKILL.md) | 1.0.2 | Reconstruct clean, runnable Oracle SQL statements from Hibernate/JPA log output with bound parameter values, and prepare query performance review packets. |
| [`9to5-sql-migration`](skills/9to5-sql-migration/SKILL.md) | 1.0.3 | Write, review, and validate Oracle database migration scripts (admin/sql/oracle, V&lt;YYYYMMDD&gt;_&lt;NN&gt;__&lt;type&gt;_&lt;description&gt;.sql) — DDL changes, table/column additions, indexes, constraints, sequence generation, and data migrations. |
| [`zjira`](skills/zjira/SKILL.md) | 1.0.0 | Work with local Jira and Confluence through zjira: fetch Jira issues and optional Confluence specifications, explore the codebase, and write structured implementation plans; or search, read, and safely update Confluence pages such as release tables. |
<!-- skill-catalog:end -->

`skills/zjira/` is the upstream skill for the zjira CLI, included because the
`9to5-jira` workflow builds on that CLI; the `9to5-*` skills are local adaptations.

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

Private configuration and inventories live outside the skill tree, under
`~/.config/opencode/skill-data/<skill>/`. Request-specific artifacts — release
drafts, snapshots and approval receipts — belong to the working repository under
`.kit/` (`memory/`, `releases/`, `plans/`), or a private state directory when no
repository applies. The public checkout ships schemas and synthetic examples only.

## Conventions

Each `9to5-*` skill includes an **Example output** section with illustrative, non-secret
data. These examples define presentation expectations, not evidence of executed
operations. The upstream `zjira` skill keeps its original structure.

## Validation

```bash
python3 scripts/update_catalog.py --check
python3 -m unittest discover -s tests -v
python3 -m unittest discover -s skills/9to5-jira/scripts/tests -v
python3 -m unittest discover -s skills/zjira/scripts/tests -v
```

The regression suite uses temporary directories and mocked remote APIs. It covers
version conflicts, write gates, duplicate rows/checkouts, worklog durations, resumed
session dates, sync scope and mirror/export policy. Set `SKILLS_ROOT` to validate a
canonical collection before regeneration. Oracle guidance is documentation- and
schema-reviewed, not validated by running these Python tests against Oracle.

Confluence helpers require Python 3 and PyYAML, and `9to5-confluence` depends on
the sibling `9to5-confluence-auth` skill (the installer includes both). They target
Confluence Server/Data Center Bearer PAT auth. Auth tests use local fixtures and
mocked HTTP/CLI calls; they cover credential precedence, safe diagnostics, redirect
blocking and conditional initialization, not live interactive login or page edits.

The daily coding and Git/GitHub skills include offline review prompts in `evals/evals.json`.
Their cases exercise repository scope, staged user work, failed checks, paginated
counts, commit-specific CI, preserved visibility exceptions and concurrent edits.
The contract tests validate their metadata and fixtures; simulated agent outputs
are separate evidence and do not establish live GitHub integration coverage.

## Design reference

The daily coding skills draw on Matt Pocock's small, composable workflows:
reproduce before fixing, separate Standards from Spec, and link existing evidence
in handoffs. They are local adaptations, not installations or bundled copies of
his collection. See [design notes and pinned sources](docs/daily-skill-design.md).

## Authoring conventions

- Skills are imperative and explain the reasoning, not just the rule.
- Registries record verified facts; unknown values are `null` or `TODO(unverified)`, never a plausible guess.
- Never commit secrets: tokens, passwords, private keys, kubeconfig content, or production logs. `cache.json` files are working state and stay out of the repository.
- After editing a skill, follow [the active authoring mode](docs/authoring.md):
  checkout-owned installs use the installer; independent canonical-owned skills use
  scoped skill synchronization. Regenerate the catalog after metadata changes.

## License

MIT — see [LICENSE](LICENSE).
