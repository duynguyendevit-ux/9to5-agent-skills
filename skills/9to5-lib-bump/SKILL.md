---
name: 9to5-lib-bump
description: Bump a shared Platform/Product library version (kafka starter, common-core, ISC, platform-service-common, microservice starter) across the services that consume it — audit drift, resolve the target version from the library repository's git state, write the gradle.properties change, build each service, and commit with the repository's convention. Use when the user asks to update libs, bump or sync a library version across services, upgrade the kafka starter or common-core, find which services are behind on a shared dependency, or check DEBUG_* flags before a release. Also use to audit version drift without changing anything.
license: MIT
compatibility: Requires git checkouts of the services and the library repositories, JDK 17 at ~/.jdks/corretto-17.0.19, and network access to Nexus for dependency resolution. Dry run by default; set --apply to write.
metadata:
  version: "1.0.1"
---

# Shared Library Bump

## Example output

Illustrative dry run; versions below are placeholders, not publishable artifacts.

```text
Property: EXAMPLE_LIB_VERSION
Mode: dry run
Service          Old version      Proposed version    Result
example-api      <old-version>    <target-version>    Would update
example-worker   <target-version> <target-version>    Already current
Ambiguous names: none
Builds: not run in dry-run mode
Files written: 0
```

Bump a shared library across every service that consumes it, without touching dead copies and without leaving debug flags enabled.

Registry: `config/libraries.json` (property → library repo → artifact, DEBUG flag map, build commands). Scan scope: `config/roots.json`.

## Two traps that cause silent wrong results

1. **Bulk-download mirrors.** `~/workspace/tools/gitlab-download-scripts/gitlab-repos/` holds ~65 cloned copies of the same services. A naive `rglob("gradle.properties")` over `~/workspace` finds them and bumps dead code. They are excluded in `config/roots.json` — keep them excluded, and if a new mirror tree appears, add it there rather than loosening the scan.
2. **`DEBUG_*` flags.** When a flag is `true`, the build resolves that dependency from a local Gradle project instead of Nexus, so a version bump has no effect on the artifact actually used. `gradle.properties` in several services currently sits with `DEBUG_PLATFORM_SERVICE_COMMON=true` or `DEBUG_COMMON_CORE=true`. Always run `audit` before a bump and require those flags to be `false` in the commit.

## Versions are git-derived, not semantic

A library's CI builds version `<CI_CURRENT_BRANCH>-<CI_COMMIT_SHORT_SHA>-SNAPSHOT`, or the tag when `CI_TAG` is set. So the target version is a statement about the library repository's state:

```bash
python3 scripts/lib_versions.py suggest --property KAFKA_STARTER_VERSION
```

Prefer a released tag over a branch snapshot when one exists. If the library branch is a feature branch, say so — bumping services onto an unreleased feature branch is a different decision than a develop sync.

## Workflow

1. **Audit first.** `python3 scripts/lib_versions.py audit --property <PROP>` — reports enabled debug flags, duplicate checkouts, and drift for every tracked library. Read the duplicate section: `notification-service`, `export-file-service`, `platform-admin-service`, `platform-dashboard-service` each exist in two places with different versions, so "bump all" can mean editing a stale copy.
2. **Resolve the target.** `suggest --property <PROP>` prints the candidate, the library's git state, and which services already match. Confirm the candidate with the user when it comes from a feature branch.
3. **Preview.** `set --property <PROP> --version <V>` (dry run) lists every file that would change. Use `--only a,b` for unique service names or comma-separated absolute checkout paths. Duplicate names are refused, including in unrestricted runs; select the intended paths explicitly.
4. **Apply.** Re-run with `--apply`.
5. **Verify each service.** From the changed checkout:
   ```bash
   JAVA_HOME=~/.jdks/corretto-17.0.19 ./gradlew build
   ```
   `compileJava` is enough for a fast check but does not run the checkstyle convention plugin. Report failures rather than reverting silently — a service that fails to resolve the new version is the finding.
6. **Commit per repository.** Match the subject style already used in that repo (`git log --oneline -10`). Observed styles: `update libs`, `update lib`, `update kafka, common core`. Include the version when the repo's style does, and reference the Jira key when the repo's history does.
7. **Report the table**: service, old version, new version, build result. Call out services skipped because they were already current, and any that failed.

## Reading the audit output

| Signal | Meaning | Action |
|--------|---------|--------|
| `DEBUG_X=true` | build resolves a local project, not Nexus | set to `false` in the same commit, or the bump is cosmetic |
| duplicate checkout with different versions | one copy is stale | ask which checkout is the working one before writing |
| many distinct versions for one property | normal drift | bump the set the user asked for, not everything by default |
| property missing from a checkout | service does not use that library | skip it; do not add the property |

## Rules

- Dry run by default. Never write without the user asking for the bump.
- One library per commit intent. Bumping kafka and common-core together is fine when that is what the user asked for and the repo's history does it; do not add unrelated libraries.
- Never commit, push, or open an MR from this skill. It prepares the change; the user or `9to5-gitlab` flow ships it.
- Never edit the mirror tree under `gitlab-download-scripts`, vendored copies, or `build/` directories.
- Do not invent versions. If the library repo is not checked out or git state is unreadable, stop and say so.
