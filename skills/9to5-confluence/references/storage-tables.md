# Offline storage-table helpers

Use `scripts/storage_tables.py` for flat, rectangular release tables. It performs
no network/filesystem writes and prints no body, credentials or secret values.
Keep inputs/outputs private; publishing still uses the reviewed page-version/hash gate.

| Operation | Function | Contract |
| --- | --- | --- |
| Change one existing service field | `replace_cell(body, service, column, value, table_index=0)` | Match `Service` and column headers; one matching row; replace cell inner markup only |
| Add a blank column | `insert_column(body, name, after, width=8, table_index=0)` | Add header/cells and matching colgroup column; preserve existing cells; an existing correctly placed column is a preservation-only no-op |
| Repair one known missing colgroup column | `repair_colgroup(body, omitted_header, width=8, table_index=0)` | Only when exactly one column is missing and its identity is explicit; insert at its header index |
| Compare approved/saved storage | `storage_matches(approved, saved, width_tolerance="0.000002")` | Full parsed tree, text, attrs, macros and order; allow macro-ID regeneration and only bounded numeric col-width serialization differences |

Supported colgroups contain one explicit percentage-width `<col>` per column.
Adding a column assigns the requested percentage and rescales existing widths
proportionally into the remainder. A table without colgroup stays without one.
Repair an explicitly known missing column **before** inserting another column;
the helper rejects mismatched colgroup counts rather than guessing their identity.

Nested tables, merged cells, duplicate headers/services, unsupported col styles and
malformed XHTML fail closed. `table_index` selects one table; other page content
remains untouched. Escape text/URLs before passing replacement inner markup. Use
the release skill's `source_links.py` for source anchors and its overall Jira-version
note builder instead of deriving web URLs from SSH or registry authorities.

After an acknowledged PUT, checkpoint the returned ID/version before checking.
If only serialization caused a false mismatch, fix the verifier and repeat GET:
verification failure is not permission to resend PUT. `storage_matches` is a
semantic body check, not deployment evidence, a sanitized preview or browser proof.
Verify expected hrefs/labels separately in `body.view`; report browser coverage honestly.
