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
| [`9to5-code-review`](skills/9to5-code-review/SKILL.md) | 1.0.0 | Review a pinned diff along separate Standards and Spec axes, with concrete correctness/security findings and explicit coverage limits. |
| [`9to5-confluence`](skills/9to5-confluence/SKILL.md) | 1.4.0 | Work with Confluence pages generally — find a page with CQL when you only know part of its title, read it as markdown, walk its hierarchy, then create, update, comment on, label, or attach files to it. |
| [`9to5-confluence-auth`](skills/9to5-confluence-auth/SKILL.md) | 1.1.0 | Resolve Confluence PAT auth from dotfiles and provide separate masked-terminal PAT login/status for Confluence, Jira and GitLab. |
| [`9to5-confluence-doc`](skills/9to5-confluence-doc/SKILL.md) | 1.3.0 | Draft source-backed Vietnamese API/flow notes and technical pages for local review and approved Confluence publication, with dotfile auth preflight and missing-login handling. |
| [`9to5-container-build`](skills/9to5-container-build/SKILL.md) | 1.0.0 | Build and review service container images and CI release wiring for Platform services — the two-stage Dockerfile convention, internal registry base images, shared GitLab CI templates for dev-product, CI_TAG to APP_VERSION wiring, JVM flags, and OOM dump paths inside containers. |
| [`9to5-debug-loop`](skills/9to5-debug-loop/SKILL.md) | 1.0.0 | Diagnose a reported bug or performance regression with a symptom-specific reproduction loop, falsifiable hypotheses and measured verification. |
| [`9to5-env-config-sync`](skills/9to5-env-config-sync/SKILL.md) | 1.0.1 | Compare and update Platform environment service configs in env-config/service-configs/&lt;env&gt;/&lt;service&gt;/ (values.yaml and .env) — align environment variables across dev-product, dev-user, dev-uat-*, report drift, and keep secrets out of commits. |
| [`9to5-feature-prototype`](skills/9to5-feature-prototype/SKILL.md) | 1.0.0 | Prototype a proposed Platform/Product feature as a source-backed explanation and diagram fitted to the current repository's real services, modules, packages, APIs and data flow. |
| [`9to5-git-publish`](skills/9to5-git-publish/SKILL.md) | 1.0.0 | Commit and push changes in the exact repository requested, with scoped staging, repository checks and remote verification. |
| [`9to5-github-audit`](skills/9to5-github-audit/SKILL.md) | 1.0.0 | Read-only GitHub repository inventory and workflow audit, with paginated counts and commit-specific CI evidence. |
| [`9to5-github-settings`](skills/9to5-github-settings/SKILL.md) | 1.0.0 | Change explicitly requested GitHub repository visibility or description with a concrete plan, scoped authorization and read-back verification. |
| [`9to5-grpc-contracts`](skills/9to5-grpc-contracts/SKILL.md) | 1.0.0 | Design and review gRPC/protobuf contracts for Platform services — the proto3 layout in the shared proto repository (service definitions versus domain messages, versioned packages), java_package conventions, wire-compatibility rules, artifact version flow, and server/client patterns with the lognet starter. |
| [`9to5-handoff`](skills/9to5-handoff/SKILL.md) | 1.0.0 | Save a concise, source-linked handoff so another coding session can continue from verified state. |
| [`9to5-heap-triage`](skills/9to5-heap-triage/SKILL.md) | 1.0.0 | Triage JVM heap dumps (*.hprof) with Eclipse MAT headless — locate dumps, run leak-suspect/overview reports, read the dominator evidence, and link findings to the service or IDE that wrote them. |
| [`9to5-id-design`](skills/9to5-id-design/SKILL.md) | 1.0.1 | Choose and review primary-key ID strategy — database identity/sequence versus application UUID/ULID/UUIDv7/Snowflake, index locality, Oracle storage, generator lifetime, and exposure. |
| [`9to5-jira`](skills/9to5-jira/SKILL.md) | 2.1.3 | Work with local Jira and Confluence through the zjira CLI — fetch a Jira issue (summary, description, acceptance criteria, last comments), read a linked Confluence spec when present, explore the repository, then write a structured implementation plan to .kit/plans/; also search and read Confluence pages. |
| [`9to5-jira-day-check`](skills/9to5-jira-day-check/SKILL.md) | 1.0.1 | Daily Jira check — current sprint issues assigned to me, worklogs missing this week (zjira weekstatus), and release rows still pending tag sync. |
| [`9to5-k8s-service-debug`](skills/9to5-k8s-service-debug/SKILL.md) | 1.0.1 | Debug Platform/Product services running on Kubernetes — locate a pod by app name across dev-product and dev-user, tail and filter logs, extract Hibernate SQL with bound parameters into runnable Oracle statements, inspect env/limits, and correlate failures back to the local repo. |
| [`9to5-kafka`](skills/9to5-kafka/SKILL.md) | 1.1.2 | Work on Platform/Product Kafka contracts, transactional outbox, and Kafka-versus-work-queue design. |
| [`9to5-lib-bump`](skills/9to5-lib-bump/SKILL.md) | 1.0.1 | Bump a shared Platform/Product library version (kafka starter, common-core, ISC, platform-service-common, microservice starter) across the services that consume it — audit drift, resolve the target version from the library repository's git state, write the gradle.properties change, build each service, and commit with the repository's convention. |
| [`9to5-logwork`](skills/9to5-logwork/SKILL.md) | 1.4.1 | Log Jira worklogs via conversation: scan assigned issues, accept task/hours/note input in chat, generate Vietnamese descriptions, and submit. |
| [`9to5-mqtt-notifications`](skills/9to5-mqtt-notifications/SKILL.md) | 1.0.0 | Design and review MQTT delivery of notification and refresh events in Platform services — the merchant gateway pattern, destination semantics, NotificationMessage payloads, QoS choice, client limits, environment configuration keys, and when MQTT is the wrong channel. |
| [`9to5-mydevtools`](skills/9to5-mydevtools/SKILL.md) | 1.0.0 | Use and extend MyDevTools, the browser-first Platform developer utilities — Oracle execution-plan visual, Rancher log analyzer, SQL extractor, protobuf and Kafka decoding, environment-to-Kubernetes conversion, case and hash utilities, cron and nginx generators. |
| [`9to5-oracle-index`](skills/9to5-oracle-index/SKILL.md) | 1.0.1 | Decide and verify an Oracle index for a query shape — choose columns and order, read DBMS_XPLAN access/filter predicates, inspect index-disabling conversions, and weigh read gains against write costs. |
| [`9to5-oracle-locking`](skills/9to5-oracle-locking/SKILL.md) | 1.0.0 | Design and review work-claim queries and lock contention on Oracle — FOR UPDATE SKIP LOCKED claiming, batch refill semantics, NOWAIT versus waiting, lock waits and deadlock (ORA-00060) diagnosis, and transaction hygiene for outbox-style jobs. |
| [`9to5-redis-design`](skills/9to5-redis-design/SKILL.md) | 1.0.0 | Review and design Redis usage in Platform services — key namespacing, TTL policy, cache-first reads with DB fallback, AFTER_COMMIT invalidation, Lua guards that protect partial cache entries, and runtime control keys with safe fallbacks. |
| [`9to5-release-audit`](skills/9to5-release-audit/SKILL.md) | 1.0.1 | Read-only audit of a Confluence release page. |
| [`9to5-release-confluence-sync`](skills/9to5-release-confluence-sync/SKILL.md) | 1.8.1 | Prepare and publish Confluence release pages with verified tags/images, PROD comparison, ENV notes and an overall Jira Release Version link. |
| [`9to5-scheduled-jobs`](skills/9to5-scheduled-jobs/SKILL.md) | 1.0.0 | Design and review scheduled work and milestone pipelines in Platform services — DB polling versus Redis ZSET scheduling, dispatcher-to-Kafka handoffs, runtime mode switches, timezone and delay configuration, catch-up and missed-fire handling, and multi-replica safety. |
| [`9to5-skill-sync`](skills/9to5-skill-sync/SKILL.md) | 1.1.0 | Keep an edited 9to5 skill consistent across its canonical directory, the three mirror directories, and the git repository copy — mirror the change, regenerate the repo copy with the correct exclusions, and verify parity by hash. |
| [`9to5-spring-conventions`](skills/9to5-spring-conventions/SKILL.md) | 1.0.1 | Review Java/Spring changes against the house conventions — Objects.isNull/nonNull for null checks, CollectionUtils/StringUtils for emptiness and presence, explicit imports, no unused imports, and no new test files unless requested. |
| [`9to5-spring-core`](skills/9to5-spring-core/SKILL.md) | 1.0.1 | Code and initialize Platform Spring services using microservice-spring-boot-starter. |
| [`9to5-spring-env-scan`](skills/9to5-spring-env-scan/SKILL.md) | 1.0.0 | Inventory environment variables and their Java/Spring consumers from application YAML/properties, @Value, @ConfigurationProperties and programmatic property lookups. |
| [`9to5-sql-forensics`](skills/9to5-sql-forensics/SKILL.md) | 1.0.0 | Reconstruct runnable Oracle SQL from Hibernate log output with bound parameters and assemble an index-review packet. |
| [`9to5-sql-migration`](skills/9to5-sql-migration/SKILL.md) | 1.0.1 | Write and review Oracle migration scripts for the Product/User schemas (admin/sql/oracle, V&lt;YYYYMMDD&gt;_&lt;NN&gt;__&lt;type&gt;_&lt;description&gt;.sql). |
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
