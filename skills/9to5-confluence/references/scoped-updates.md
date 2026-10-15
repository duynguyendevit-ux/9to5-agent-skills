# Fast scoped page updates

Use `scripts/doc_update.py` for a small text/section/table change. Read current
content once, select only the requested region, review a short diff, then apply
the pinned body once. Reuse this tool instead of a per-request publisher/server.
It does not move pages, create pages, upload images or change deployment configs.

## Prepare

After the usual authentication preflight, save a JSON operations list privately:

```json
[
  {
    "op": "cell",
    "table_index": 0,
    "key_column": "source",
    "key": "alarm-service",
    "column": "description",
    "value": "Nhận tin báo cháy thiết bị qua Kafka."
  }
]
```

```bash
python3 scripts/doc_update.py prepare --page 123 --patch-file changes.json --bundle edit-001
python3 scripts/doc_update.py serve --port 8792
```

The state root defaults to `$XDG_STATE_HOME/opencode/doc-updates` (otherwise
`~/.local/state/opencode/doc-updates`). Use `--root <private-directory>` before
the subcommand to override it. Keep real requests out of the public skill repo.

Use the same server/port throughout the session. `/latest` follows the newest
bundle; `/edit-001` stays pinned to its immutable plan. Give the user the stable
link and identify the current bundle. Approval binds that bundle and its printed
contract hash, never whatever `/latest` happens to show later.

The preview shows just the changed regions. Full original/proposed storage, diff,
contract and dry-run request remain available as plaintext links. Existing page
markup is escaped, not executed in the local review origin. Serve only on loopback.

## Operations

- `replace`: `before` and `after`, each a string; exactly one nonempty match.
- `section`: unique top-level `heading` and replacement content `html`; retain the
  heading and stop at the next heading of equal/higher level. Nested headings
  fail rather than risking a broader change.
- `cell`: `table_index`, `key_column`, `key`, `column`, and plain `value` or storage
  `html`. Column matching ignores case, so `source`, `service`, `Service` work
  without changing headers. Row keys remain exact and unique.
- `add_row`: `table_index`, `key_column`, `values` mapping every existing header
  to plain text. Append after an existing data row; reject duplicate keys.

Validate storage fragments and preserve every byte outside the selected ranges.
Nested/merged tables, ambiguous selectors, malformed XHTML, active markup and new
attachment references fail closed. Use the normal reviewed full-body workflow for
unsupported layouts; do not silently broaden scope. Plain `value` cannot add an
anchor: use explicitly reviewed `html` for a requested GitLab/source link.

## Apply and recovery

Show the changes, full diff/request links and contract hash; obtain approval of
that exact plan. Then:

```bash
python3 scripts/doc_update.py apply --bundle edit-001 --contract-sha256 <reviewed-hash> --apply --approved
```

Apply rechecks file hashes, endpoint, base version/body, title/space/ancestors and
attachments. A concurrent edit stops before PUT. Prepare a fresh scoped patch
against the new page, review it again; never attach a new version to an old body.

Each bundle records an in-flight checkpoint and the write acknowledgement before
read-back. Saved full storage, server-view tables/hrefs, identity/hierarchy and
attachments are checked. These are not live-browser verification.
Outer XML whitespace is tolerated; interior content remains significant. Page links
are checked by same-origin target ID rather than literal relative/absolute spelling;
fragments and repeated occurrences must still match.

Repeating a successfully completed apply is a read-only verified no-op. A partial
or unknown outcome refuses another PUT. Inspect the same bundle with:

```bash
python3 scripts/doc_update.py status --bundle edit-001
```

Reconcile acknowledged/unknown writes read-only using the publication verification
guide. The tool never retries writes automatically. Tell the user only what changed
and whether publication completed; keep receipts and transport detail in the bundle.
