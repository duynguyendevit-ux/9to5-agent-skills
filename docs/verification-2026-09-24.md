# Verification fixes — 2026-09-24

**Historical snapshot.** Counts and results below describe that audit, not the
current collection or checkout. Use [current validation commands](workflows.md#validation)
for today's result; the [documentation index](README.md) lists active guidance.

All 14 findings from the installed-collection audit were addressed. All 16 skills
also include clearly labeled illustrative example outputs and updated version metadata.

| Finding | Resolution |
|---|---|
| Worklog hours interpreted as minutes | Duration parser normalizes hours, fractional hours and hour/minute inputs to integral seconds. |
| Release sync overwrites intervening edits | Compare the fresh page version to the original body version; PUT uses original + 1. |
| General Confluence update lacks reviewed-base version | Required `--expected-version` for both preview/apply; full JSON preview instead of 300-character truncation. |
| Oracle ID rules confuse identity and sequences | Rewritten around preallocated NEXTVAL, concurrent/RAC use, variable NUMBER storage and conditional performance trade-offs. |
| Oracle index rules overstate optimizer behavior | Corrected skip scans, hints, top-N, null coverage, ICP and unmeasured plan claims; fixed reversed cutoff explanation. |
| Outbox age calculation uses numeric ROUND on interval | Extract interval components to numeric minutes; document timezone assumptions. |
| Library selection updates duplicate checkouts | Refuse ambiguous names before writes; accept explicit checkout paths. |
| Release audit discards duplicate rows | Fail on duplicate service names rather than overwrite evidence. |
| Audit output contract differs from implementation | Report UNKNOWN for unchanged empty records and source metadata changes; document free-form project metadata and comparison-only scope; fix anchor extraction. |
| Sync empty scope expands to everything | Reject invalid/empty selectors; manage only real 9to5 directories. |
| Mirror copy and hashing policies disagree | Local mirrors receive local-only files; repository export excludes them. Report orphans and return nonzero on unresolved drift. |
| Codex activity uses session creation day | Discover older sessions and filter each record timestamp in local time. |
| Debug examples print secret values | Enumerate Secret/environment key names at source; avoid raw Secret YAML and printenv output. |
| Unsupported zjira version command | Use supported --help for binary verification. |

## Validation

- 18 new offline regression tests passed; 13 existing Jira release-script tests passed.
- All 16 skills have parseable frontmatter, matching README versions, existing concrete
  local resource references, and an Example output section.
- Eight canonical Python source/test files parse; both shell scripts pass bash -n;
  all 17 local JSON files parse; all seven command entry points pass --help.
- Canonical, three local mirrors and filtered repository copies match by the sync check.
- Current-file hostname scan and git diff --check pass.

Regression tests use mocked remote APIs and temporary fixtures. Oracle SQL and
optimizer guidance were reviewed against types, reference DDL and documentation;
no Oracle instance was used to execute the revised SQL. No Confluence/Jira/cluster
writes were needed for verification. The hostname check does not audit Git history.

## Compatibility notes

- Confluence update callers must supply the version used to prepare their body file;
  do not fetch a new version merely to force a stale body through.
- Existing release snapshots that already lost duplicate rows must be recaptured from
  a source with disambiguated service rows. The old snapshot cannot recover lost data.
- `lib_versions.py set --only` now rejects duplicate names; use absolute checkout paths.
- Local mirrors intentionally contain local endpoint/cache/debug files. Publish only
  the filtered repository copy.
