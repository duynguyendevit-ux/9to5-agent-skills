# 9to5 Agent Skills

Agent skills for OpenCode v2, used for day-to-day development work (Jira, release pages, Oracle migrations, Kubernetes debugging, Spring conventions).

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

| Skill | Version | Purpose |
|-------|---------|---------|
| `9to5-debug-loop` | 1.0.0 | Symptom-specific reproduction, falsifiable hypotheses and measured bug-fix verification. |
| `9to5-code-review` | 1.0.0 | Read-only, pinned-diff review with separate Standards and Spec findings. |
| `9to5-handoff` | 1.0.0 | Explicit-request coding-session handoff; automatic advertising disabled in OpenCode V2. |
| `9to5-git-publish` | 1.0.0 | Commit/push the requested repo only; scoped staging, validation and remote-SHA verification. |
| `9to5-github-audit` | 1.0.0 | Read-only paginated repo inventory and commit-specific, per-workflow Actions evidence. |
| `9to5-github-settings` | 1.0.0 | Scoped visibility/description changes, preserved exceptions and read-back verification. |
| `9to5-jira` | 2.1.2 | Fetch a Jira issue and linked Confluence spec, explore the repo, write an implementation plan to `.kit/plans/`. |
| `9to5-logwork` | 1.4.1 | Log Jira worklogs via conversation, normalize duration to seconds, and derive date-filtered agent activity. |
| `9to5-jira-day-check` | 1.0.1 | Daily read-only summary: sprint issues, missing worklogs, releases still pending tag sync. |
| `9to5-release-confluence-sync` | 1.0.4 | Roll previous release tags into current version, verify service tags, and reset inherited highlights on cloned pages. |
| `9to5-release-audit` | 1.0.1 | Read-only release-record comparisons; rejects duplicate service rows and reports empty records and source changes. |
| `9to5-confluence-auth` | 1.0.0 | Load dotfile PAT config safely, verify Confluence independently of Jira, and initialize the CLI only when auth is missing. |
| `9to5-confluence-doc` | 1.2.0 | Source-backed Vietnamese technical notes with auth preflight, local review and approved publication. |
| `9to5-confluence` | 1.2.0 | General Confluence operations with shared auth; updates require the reviewed base version and explicit approval. |
| `9to5-sql-migration` | 1.0.1 | Write and review Oracle migration scripts (`admin/sql/oracle`, Flyway-style naming). |
| `9to5-oracle-index` | 1.0.1 | Oracle-specific index candidates, actual-plan verification, null coverage, top-N and write trade-offs. |
| `9to5-sql-forensics` | 1.0.0 | Reconstruct runnable Oracle SQL from Hibernate logs; packet feeds index review and migration. |
| `9to5-oracle-locking` | 1.0.0 | Claim-query and lock-contention review: SKIP LOCKED semantics, deadlock traces, transaction hygiene. |
| `9to5-id-design` | 1.0.1 | Identity, explicit sequences and application IDs: Oracle storage, allocation, concurrency and exposure. |
| `9to5-env-config-sync` | 1.0.1 | Compare and align service env configs across environments; keep secrets out. |
| `9to5-spring-conventions` | 1.0.1 | Review Java/Spring changes against house conventions. |
| `9to5-spring-core` | 1.0.0 | Source-backed starter coding guide and Java 17 service init template: core API contracts, JPA routing, auditing, context cleanup and environment configuration. |
| `9to5-feature-prototype` | 1.0.0 | Explain a proposed feature in the current repository's real structure with a Mermaid diagram; design only, no application-code edits. |
| `9to5-mydevtools` | 1.0.0 | Use the browser-first developer utilities (plan visual, log analyzer, SQL extractor, decoders) instead of one-off scripts. |
| `9to5-k8s-service-debug` | 1.0.1 | Debug cluster services with source-filtered configuration inspection and local evidence. |
| `9to5-heap-triage` | 1.0.0 | Triage JVM heap dumps with MAT headless; suspect patterns, dominator evidence, capture loop. |
| `9to5-redis-design` | 1.0.0 | Redis key namespacing, TTL policy, cache consistency and guarded writes. |
| `9to5-scheduled-jobs` | 1.0.0 | Scheduled workers and milestone pipelines: DB polling vs ZSET, mode switches, catch-up, replica safety. |
| `9to5-kafka` | 1.1.2 | Kafka contracts, corrected Oracle outbox diagnosis, long-running jobs and share-group trade-offs. |
| `9to5-mqtt-notifications` | 1.0.0 | MQTT refresh delivery and the merchant gateway pattern; QoS choice and channel decisions. |
| `9to5-grpc-contracts` | 1.0.0 | Proto3 layout, wire compatibility, artifact version flow and server/client patterns. |
| `9to5-device-availability` | 1.0.0 | Device availability math, error taxonomy, daily-index queries and export surfaces. |
| `9to5-lib-bump` | 1.0.1 | Audit and bump shared libraries; reject ambiguous checkout names and allow explicit paths. |
| `9to5-container-build` | 1.0.0 | Two-stage service images, internal registry bases, CI template wiring, JVM flags and dump paths. |
| `9to5-skill-sync` | 1.0.2 | Synchronize only 9to5 skills, preserve local mirror config, filter repository exports and detect unresolved drift. |

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
- After editing a skill, keep the four install locations in sync — `install.sh` re-links them.

## License

MIT — see [LICENSE](LICENSE).
