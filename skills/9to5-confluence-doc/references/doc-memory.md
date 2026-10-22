# Documentation profiles and lessons

Lets every agent (OpenCode, Claude Code, Codex) write any document in the
user's established structure and wording, and stop repeating corrected mistakes.
Profiles and lessons are **private local files**; this skill only defines the
mechanism. Never copy profile content, internal names or hostnames into the skill.

## Locations

| File | Role |
|------|------|
| `~/.local/state/opencode/preferences/doc-profiles.md` | Index: which profile applies to which repo, Confluence space, page-ID set or title prefix |
| `~/.local/state/opencode/preferences/<project>-doc-style.md` | Project profile: page-type templates, vocabulary, table headers, storage-format idioms, open decisions |
| `~/.local/state/opencode/preferences/<project>-doc-lessons.md` | Project lessons: corrected mistakes with a check for each |
| `~/.local/state/opencode/preferences/doc-lessons.md` | Cross-project lessons (writing habits that apply to every document) |

Create a missing directory/file when recording the first entry. Keep the index
as the only place mapping targets to profiles.

## Load order (before drafting or editing)

1. Read the index; match by working repository path, Confluence space key, page
   ID, parent page or title prefix. Several profiles may match; load all.
2. Read the repo's `AGENTS.md` / `CLAUDE.md` and any linter it names.
3. Read the matched profile(s), their lessons, then `doc-lessons.md`.
4. Read the latest version of the target page and one sibling page of the same
   type; the user's latest manual wording beats any profile text.

Precedence: current user request > repo instructions/linter > project lessons >
project profile > cross-project lessons > this skill's default template.

No match: use the skill defaults and the generic page types below. After the
user's first correction, propose creating a profile and index entry.

## Lesson entry format

Append, never rewrite history. One entry per distinct mistake:

```markdown
### L<NNN> — <short rule in the document's language>
- Date: YYYY-MM-DD · Scope: <page type | file | all>
- Mistake: <what was written / done wrong, quoted briefly>
- Rule: <what to do instead>
- Check: <how to detect it before publishing: grep pattern, linter rule, or manual question>
- Source: <user correction | linter | review diff | commit hash>
```

Record a lesson when the user corrects wording, structure, scope, a fact, or a
removed row; when a linter/pre-commit rejects text the agent wrote; or when a
published version had to be reverted. Search existing entries first: if the same
rule exists, add the new date/source to it instead of a duplicate. When an entry
recurs twice, promote it into the profile's rules and keep the lesson as a pointer.
If the check is mechanical and the repo has a linter, propose (do not silently add)
a linter rule.

Do not record: one-off content facts that belong in the document itself,
secrets, tokens, internal hostnames, or personal data.

## Before handing over a draft

Run every lesson's `Check` against the changed text and report which were
checked. A lesson whose check fails blocks the dry run until fixed.

## Generic page types

Use when no profile defines the type. Headings in the document's language.

| Type | Structure |
|------|-----------|
| Hub / overview | Scope → actors and services (one line of responsibility each) → main flow → links to child pages; no copied reference tables |
| Business flow | Overview (diagram + node table) → per flow: trigger/input, conditions, actions, result, exceptions |
| API | Summary table (business action, owner service, method + full route, downstream call) → per API: request, rules, response, flow diagram |
| Scheduled/milestone | Milestone table → per milestone: what it handles, which records, conditions, config → shared config |
| Reference (ENV / DB / enum / source) | One fixed table header per page; one row per item; purpose column states the business effect |
| Troubleshooting | One section per problem: symptom → mechanism → causes → resolution (commands/queries verified against real schema) |
| Checklist / handover | Item → owner → status → evidence link; never mark done without evidence |

## Writing checks that apply everywhere

- Every table/column/topic/route/class named in the page exists in source or
  schema; never invent illustrative names in a reference or troubleshooting page.
- Plain Markdown arrows (`→`), no LaTeX; one table row per line; fenced code
  with a language. In storage format use the `code` macro with `language`.
- Regenerating storage from Markdown must keep existing macros, attachments,
  anchors and sections that the Markdown does not represent.
- Write the rule where it applies; no repeated "core principles" banners.
- Concise by default: enrich only what the user asked; an over-detailed section
  that the user later trims is a lesson.
