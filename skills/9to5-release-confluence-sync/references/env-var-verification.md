# Verify and complete release environment variables

Use when a release request asks to check or complete the `Cấu hình biến môi trường`
values for the services being released, or to verify a service's env vars against
its release tag. Verification is read-only; adding or changing page values stays
behind the normal review, version gate and read-back.

## Scope the services

- Prefer the services named in the request or the release-page rows.
- To find what a developer worked on: `git log --all --author=<name> --since=<date>`
  per service checkout, and the release version's Jira tasks
  (`assignee = currentUser() AND fixVersion = '<release version>'`).
- Author history is supporting evidence, not an exclusion rule: squash/cherry-pick
  attribution or a partial checkout can hide contributions. Retain services backed
  by the requested scope or verified Jira-to-service mapping; label unresolved ones
  unverified. Inspect relevant subtasks/parents when fixVersion is only on the parent.

Completion: record the selected services, repository identities, target environment
and release tags, with the evidence or mapping limits for each service.

## Compare the release tag with develop

For each service, compare the shipped tag with the current branch:

```bash
git -C <repo> fetch origin develop:refs/remotes/origin/develop
git -C <repo> diff --name-status <tag> origin/develop -- .
```

- Inspect config, Java consumers and build/dependency changes. Java-only changes can
  introduce or alter `@Value`, `System.getenv`, `Environment.getProperty` or
  `@ConfigurationProperties` bindings; classify them only after inspection.
- The tag is what ships: the env vars to set come from the tag, not from develop's
  future ones. Verify feature inclusion against the tag's contents/history; whether
  a branch merged into develop alone does not establish inclusion in a release tag.
- Equal config files establish no config-file delta, not no Java ENV delta. Equal
  trees establish no source delta within that comparison, not a complete page cell.
- Keep tag-versus-develop comparison separate from the previous-release-versus-tag
  comparison required to identify newly introduced ENV keys for Release Note.

Completion: record resolved tag/develop SHAs, inspected changes and coverage limits.
Continue the tag inventory even when no source delta is found.

## Extract and classify the tag's env vars

Inventory a clean snapshot of the release tag, rather than the current working tree.
Export tracked tag source into a fresh private operation directory and follow
[Spring env scan](../../9to5-spring-env-scan/SKILL.md) using its bundled scanner:

```bash
python3 <spring-env-scan-dir>/scripts/scan_env.py --root <tag-snapshot> --format json
```

The scanner inventories YAML/properties, Java consumers and inferred bindings; it
withholds values and does not evaluate profile precedence. Report its warnings and
partial coverage. Inspect defaults privately at the tag for relevant non-secret keys.

- Resolve active profiles and config locations/imports for the **target environment**
  from deployment/CI configuration or read-only runtime evidence. Inspect base
  `application*.yml/yaml/properties`, active profile files, multi-document conditions
  and applicable imports; trace precedence before calling a value effective.
- `application.yml` is a base config, not automatically the deployed profile.
  A local-profile default is not a PROD value unless that profile is confirmed active.
- Unknown profiles, unavailable external config or dependency sources are coverage
  limits. Report candidate defaults by source instead of inventing an effective value.

Classify the relevant keys:

| Class | Signal | Why it matters |
| --- | --- | --- |
| On/off switch | boolean default or binding | Verify the active default and any override before deciding which switch to flip |
| Date/time | date literal, ISO-8601 duration, `*_FROM`/`*_TO`/`CUTOFF`/`WINDOW`/`DELAY`/`RETENTION` | **Most critical**: a window `TO` bounds a backfill; a stale default can stop coverage |
| Other | everything else | connections, sizes, names |

- `no_default` means no fallback at one placeholder occurrence. Establish whether
  that occurrence is active and how it is supplied/consumed before calling it required.
  Inactive profiles, conditional consumers and external property sources can change
  that conclusion. Distinguish explicit ENV keys from inferred Spring override names.
- For window dates, verify timezone and inclusive/exclusive bounds in the consumer;
  for durations/delays, verify units. A source default is evidence, not authorization
  to change an approved operational value.

Completion: each relevant key has source/profile evidence and an effective value or
an explicit unresolved status, with switches and date windows prioritized.

## Check deployment sources for the target environment

Follow [environment config sync](../../9to5-env-config-sync/SKILL.md) in read-only mode.
Check `env-config/service-configs/<env>/<service>/values.yaml` **and `.env`**, plus
applicable Helm/CI overrides, ConfigMaps and secret references. Inspect secret key
presence/reference only; withhold values and raw configuration from review output.

- Record the actual environment and checked paths/sources. DEV/UAT presence or
  absence is not PROD evidence. A missing PROD directory is unverified PROD config,
  not proof that all its variables are absent.
- Distinguish present/overridden, absent in inspected sources and unverified external
  sources. A source default can satisfy an omitted variable; propose an ops action
  only when the target environment's intended value or verified requirement needs it.

Completion: report per-key deployment evidence and source coverage, without modifying
deployment configuration or implying that a page edit enables a running job.

## Check and complete the page cell

The cell holds a YAML code block:

```
- name: KEY
  value: 'value'
```

- Quote values; keep related vars together (switches, then the window dates, then
  connection values).
- List the release-relevant vars: switches to flip from their defaults, the date
  windows, and required connection values.
- Flag a missing date var when its default would bound or stop the job early.
- Add missing vars to the existing cell only on request; keep the rest of the body
  byte-identical. Show the exact additions and values, obtain approval of that body,
  apply with the reviewed `--expected-version --apply --approved`, and verify both
  saved storage and rendered text. Follow [review/publication](review-publication.md)
  for content-bound approval and concurrent-edit handling.
- Report added keys and values; never print secret values.
