---
name: 9to5-spring-conventions
description: Review Java/Spring changes against the house conventions — Objects.isNull/nonNull for null checks, CollectionUtils/StringUtils for emptiness and presence, explicit imports, no unused imports, and no new test files unless requested. Use when the user asks to review an MR or diff, check coding conventions or style, or asks whether a Java/Spring change follows the project standards.
license: MIT
metadata:
  version: "1.0.0"
---

# Spring Conventions Review

Review only changed code. Read the surrounding file for context before judging a line.

## Checklist

| Rule | Bad | Good |
|------|-----|------|
| Null checks | `x == null`, `x != null` | `Objects.isNull(x)`, `Objects.nonNull(x)` with `import java.util.Objects` |
| Collection emptiness | `list == null \|\| list.isEmpty()` | `CollectionUtils.isEmpty(list)` (project util) |
| Non-empty | `list != null && !list.isEmpty()` | `CollectionUtils.isNotEmpty(list)` |
| Strings | manual null/blank checks | `StringUtils.isBlank/isNotBlank/equals` when the project provides it |
| Imports | wildcard imports, unused imports | explicit imports, unused removed |
| Tests | new test files by default | run existing tests; add tests only when requested or for high-risk contracts with a stated reason |

Do not invent helpers that do not exist in the project — verify with
`grep -rn "class CollectionUtils\|interface CollectionUtils" <repo>/src` first.

## How to review

1. Get the diff: `git diff <base>...HEAD` (or `git diff` for uncommitted).
2. Read each modified file fully enough to understand the changed branch.
3. Output findings with severity and `file:line`, ordered by impact:

```
[Medium] OrderService.java:88 — `order != null` -> `Objects.nonNull(order)` (null-check convention)
[Low]    OrderMapper.java:12 — unused import java.util.List
```

4. If nothing violates the checklist, say so in one line. Do not invent findings
   and do not review pre-existing code that was not touched.

## Also check on Java changes

- Env placeholders follow the repo style (`${DOMAIN_INTERNAL_*}` in YAML, no hardcoded hosts).
- Exceptions: no swallowing (`catch (Exception e) {}`); log or rethrow with context.
- Unused imports introduced by the change are removed.
