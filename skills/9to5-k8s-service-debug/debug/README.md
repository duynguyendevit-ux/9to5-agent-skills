# debug/

Session evidence for cluster investigations.

```
debug/artifacts/<YYYYMMDD>-<app>-<short-slug>/
├── session.md      # symptom -> evidence -> hypothesis -> conclusion -> next action
└── logs.txt        # filtered excerpt
```

## Rules

- One directory per investigation, named `<date>-<app>-<slug>` (e.g. `20260922-ttch-worker-service-outbox-lag`).
- Save filtered excerpts, not full `--tail=500` dumps. Keep the lines that prove the point.
- Strip before saving: bearer tokens, cookies, device credentials, phone numbers, email addresses, personal names.
- `session.md` always ends with a next action. "No conclusion" is acceptable; a dead end written down saves the next run.
- These artifacts are working evidence, not documentation. Durable conclusions belong in `notes/services/<app>.md`; release-relevant changes belong in the ticket.

## Format for session.md

```markdown
# <app> — <symptom in one line>

- Date: YYYY-MM-DD
- Namespace: dev-c7 | dev-c7-ttdvkh
- Pod: <pod name>
- Trigger: <ticket / request / report>
- Deployed image: <image tag if known>

## Symptom

What was observed, by whom, when.

## Evidence

Log lines (quoted, trimmed) and queries run. Reference logs.txt / queries.sql.

## Hypothesis

What the evidence supports. Separate fact from guess.

## Conclusion

Root cause, or the narrowed search space if unresolved.

## Next action

Concrete: code fix, ticket, config change, or "not reproducible, watch for X".
```
