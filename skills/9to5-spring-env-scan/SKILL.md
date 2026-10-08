---
name: 9to5-spring-env-scan
description: Inventory environment variables and their Java/Spring consumers from application YAML/properties, @Value, @ConfigurationProperties and programmatic property lookups. Use when asked to scan env vars in a Spring repository, trace a variable to config classes/code, or derive an environment-key checklist from source. For changing deployment configs use 9to5-env-config-sync instead.
license: MIT
compatibility: Python 3.10+ and PyYAML; offline, no JVM or build required.
metadata:
  version: "1.0.0"
---

# Spring Environment Scan

## Workflow

1. Resolve the requested checkout and read its `AGENTS.md`. Check its Git remote
   when duplicate service checkouts exist. Scan only the requested root.
2. Run the bundled scanner, rather than reproducing it with grep:

   ```bash
   python3 <skill-dir>/scripts/scan_env.py --root <checkout> --format markdown
   ```

   Use `--format json` for automation, `--format env` for a **names-only** checklist.
   Default scope excludes tests, symlinks and generated/vendor directories.
   Use `--include-tests` when requested; `--config path/to/custom.yaml` adds custom
   config inside the checkout; `--exclude 'module/**'` narrows scope. Read `--help`
   for all options. Output goes to stdout; save it only to the user's requested
   destination or a private operation directory. The scanner does not edit source.
3. Inspect the warnings and coverage summary. Exit `1` means partial coverage;
   exit `2` means invalid input/dependency. Report either, rather than presenting
   a partial inventory as complete. Read [scan semantics](references/scan-semantics.md)
   when interpreting aliases, inferred names, config-class bindings or limitations.
4. Report explicit variable names, mapped properties and `file:line` evidence;
   separate inferred Spring environment candidates. `no_default` means that one
   placeholder has no fallback, **not** that startup necessarily requires it.
   State that profiles are inventoried independently, not evaluated/merged.
   For unused-looking config-class fields, trace getters/accessors manually before
   claiming they are unused: binding discovery is not a runtime usage analysis.

## Safety and completion

Read source only. The scanner outputs key names, locations, default **presence**
and static binding evidence; all values and source snippets are withheld.
It does not read `.env`, query process environment, resolve placeholders, run Maven/
Gradle, fetch dependencies, connect to services or change deployment configuration.
Remote publication, deployment edits and git commits require separate authorization.

Finish with counts for explicit variables and inferred candidates, warning/coverage
limits, and the artifact path if one was requested. An empty scan is not proof that
the service uses no environment variables: dependencies and runtime sources remain
outside this inventory.

## Example

Input: `app.timeout: ${REQUEST_TIMEOUT:5000}` and `@Value("${app.timeout}")`.

Output: `REQUEST_TIMEOUT` → `app.timeout` → YAML declaration and Java `@Value`
locations; `has_default` at the YAML location. `APP_TIMEOUT` is a separate inferred
override candidate. The value `5000` is not emitted.
