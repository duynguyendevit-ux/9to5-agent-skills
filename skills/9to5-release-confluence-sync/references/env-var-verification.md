# Verify and complete release environment variables

Use when a release request asks to check or complete the `Cấu hình biến môi trường`
values for the services being released, or to verify a service's env vars against
its release tag. Verification is read-only; adding or changing page values stays
behind the normal review, version gate and read-back.

## Scope the services

- Prefer the services named in the request or the release-page rows.
- To find what a developer worked on: `git log --all --author=<name> --since=<date>`
  per service checkout, or the release version's Jira tasks
  (`assignee = currentUser() AND fixVersion = '<release version>'`).
- A checkout without that author's commits is not that developer's service.

## Compare the release tag with develop

For each service, compare the shipped tag with the current branch:

```bash
git -C <repo> fetch origin develop:refs/remotes/origin/develop
git diff <tag> origin/develop -- src/main/resources gradle.properties
```

- Config changes under `src/main/resources` are env-relevant; code-only diffs are not.
- The tag is what ships: the env vars to set come from the tag, not from develop's
  future ones.
- An unmerged feature branch (for example `oc/...`) is not in the release even when
  the author's commits are recent.
- Identical trees (the tag points at the develop commit) mean no config delta;
  report that explicitly instead of re-deriving defaults.

## Extract and classify the tag's env vars

Read the deployed profile — `application.yml` — never `application-local.yml`:

```bash
git -C <repo> show <tag>:src/main/resources/application.yml
```

Collect every `${VAR:default}` and classify:

| Class | Signal | Why it matters |
| --- | --- | --- |
| On/off switch | default `true`/`false` | A feature stays off until the env flips it; a release usually flips specific switches |
| Date/time | date literal, ISO-8601 duration, `*_FROM`/`*_TO`/`CUTOFF`/`WINDOW`/`DELAY`/`RETENTION` | **Most critical**: a window `TO` bounds a backfill; a stale default can stop coverage |
| Other | everything else | connections, sizes, names |

- Values are the tag's deployed-profile defaults; the local profile may differ and
  must not be copied into the release.
- A var with no default is required and must be configured.
- Check the env configs (`env-config/service-configs/<env>/<service>/values.yaml`):
  connection vars may already exist while the feature vars do not. A var missing there
  is an ops action recorded on the page, not proof that the code lacks it.

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
  byte-identical, apply with the reviewed `--expected-version --apply --approved`,
  and verify both saved storage and rendered text.
- Report added keys and values; never print secret values.
