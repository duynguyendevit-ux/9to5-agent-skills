---
name: 9to5-heap-triage
description: Triage JVM heap dumps (*.hprof) with Eclipse MAT headless — locate dumps, run leak-suspect/overview reports, read the dominator evidence, and link findings to the service or IDE that wrote them. Use when a JVM produced an .hprof, a service or IDE hit OutOfMemoryError, memory keeps growing, someone asks what retains the heap, or a crash dump (java_error_in_*.hprof, unload-*.hprof) must be explained. Analysis is read-only and report-only; for live cluster symptoms start with 9to5-k8s-service-debug.
license: MIT
compatibility: Requires bash, curl and unzip for the one-time MAT install, and JDK 21+ to run MAT 1.17 (it rejects 17 with an "Incompatible JVM" dialog). Analysis is RAM-heavy and paced by MAT_XMX in ~/.config/hprof-autopilot.conf.
metadata:
  version: "1.0.0"
---

# Heap triage — from dump to retention answer

## Example output

Illustrative; sizes, classes and counts must come from the actual dump.

```text
Dump: DB-261.24374.56_memory_15.06.2026_08.35.33.hprof (619M, 105d old)
MAT: 1.17.0 headless, heap 8g — reports archived under ~/Documents/heap-reports
Problem Suspect 1: 37,875 java.lang.Class instances loaded by <system class loader>
  retain 10.43% of the heap through 249,225 byte[] and 247,463 String instances.
Also present: one OutOfMemoryError[] — the snapshot was taken after an OOME.
Hypothesis: class/metadata bloat (generated or framework classes, stale class loaders).
Unverified: whether the classes are duplicated loaders; needs the dominator path (GUI step).
Next action: correlate with the unload-*.hprof pair; check IDE plugin set before filing upstream.
Artifact: ~/Documents/heap-reports/DB-261..._Leak_Suspects/index.html
```

## Scope and boundaries

- Read-only over the machine and the JVM that wrote the dump. The only writes are MAT
  reports (plus MAT index caches, removed after archiving).
- MAT is not bundled in this skill; `install-mat` downloads it once into
  `~/.local/share/eclipse-mat`. Never point MAT at a JDK below 21.
- One dump per MAT run, and one heavy parse at a time. The nightly
  `hprof-autopilot.timer` analyzes at most one dump per run; do not start a manual
  parse of the same dump while it is running.
- A report is evidence, not a verdict: headless MAT finds suspicious retention, it
  does not prove a leak or an allocation spike. Say which claim is proved.

## Workflow

1. **Locate candidate dumps.**
   ```bash
   <this-skill>/scripts/hprof-autopilot.sh scan
   ```
   Scan covers `DUMP_DIRS` (default `$HOME`, `maxdepth 1`) from
   `~/.config/hprof-autopilot.conf`. Typical names: `java_pid*.hprof` (manual jmap),
   `java_error_in_*.hprof` (HeapDumpOnOutOfMemoryError), `unload-*.hprof` and
   `DB-*_memory_*.hprof` (JetBrains IDE leak snapshots).
2. **Confirm MAT is installed and can run.** `install-mat` is idempotent; skip it if
   `MAT_HOME/MemoryAnalyzer` exists. JDK 21+ is mandatory.
3. **Analyze.**
   ```bash
   <this-skill>/scripts/hprof-autopilot.sh analyze <dump>
   ```
   MAT writes `Leak_Suspects`, `System_Overview` and `Top_Components` reports; the
   script moves the zips to `REPORT_DIR` and unzips them. The parse of a multi-GB dump
   takes minutes and sits at `nice 19`.
4. **Read in order** — Leak Suspects first, then System Overview, then Top Components.
   Use [`references/reading-reports.md`](references/reading-reports.md) for the anatomy
   and the pattern table. For a deep dominator path, open the same dump in the MAT GUI
   (`eclipse-mat/mat/MemoryAnalyzer`) and use *Path to GC Roots*; headless reports do
   not include that path.
5. **Report with proof labels.** Every finding gets one of: *measured* (a number from
   the report), *hypothesis* (retention pattern with a named mechanism), *unverified*
   (needs GUI path, allocation record, or a second dump). End with one concrete next
   action (fix, ticket, or "not reproducible").
6. **Close the capture loop.** If no dump will exist next time, add the flags to the
   service's JVM options (through `9to5-env-config-sync` for deployed services):
   ```
   -XX:+HeapDumpOnOutOfMemoryError -XX:HeapDumpPath=<dump-dir>
   ```
   The purge policy deletes a raw dump only after its report exists and the dump is
   older than `PURGE_RETENTION_DAYS` (default 7). Never delete dumps by hand.

## Interpreting a report (short form)

| Observation | Likely mechanism | Next evidence |
|---|---|---|
| Huge `java.lang.Class` count under one loader | class/metadata bloat: generated proxies, script engines, plugin trees, stale loaders | count classes per loader; compare with a second dump after unload |
| One class dominates instance count | unbounded collection or cache holding domain objects | dominator path to the owning structure; check eviction code |
| `Thread`, `ThreadLocal`, pool internals high | leaked threads or thread-local payloads | Thread Overview; compare thread count growth across dumps |
| `char[]`/`byte[]`/`String` at top with few suspects | large payloads stored as strings/bytes (logs, JSON, payload caches) | find the container class retaining them |
| Duplicate Strings / Empty Collections in Top Components | waste, usually secondary | fix only if the percentage is material and the fix is safe |
| `OutOfMemoryError` in the object list | snapshot taken after an OOME, not a healthy baseline | prefer an allocation-spike reading when the suspect list is flat |

Detailed guidance, including the worked example and reporting limits:
[`references/reading-reports.md`](references/reading-reports.md).

## Safety

- A dump contains the JVM's memory: system properties, environment values, cached
  request data, possibly credentials or personal data. Never paste report dumps or
  system-property tables into tickets; cite the suspect summary only, and strip
  identifiers first.
- Do not raise `MAT_XMX` beyond free RAM; a 3 GB dump typically needs 6–8 GB. If the
  machine is busy, defer to the nightly timer instead of forcing the parse.
- Do not run `analyze` against a dump on a remote share or a spinning disk for a
  multi-GB file; copy locally first.
- No service, cluster, or database write belongs to this workflow.

## Handoffs

- Live symptom (pod OOMKilled, crash loop, rising RSS) → `9to5-k8s-service-debug`
  first; the dump explains retention, not the incident timeline.
- JVM flag or memory-limit change on a deployed service → `9to5-env-config-sync`.
- Retention rooted in a query returning unbounded rows or a missing index →
  `9to5-sql-forensics` for the statement, `9to5-oracle-index` for the decision.
- IDE-side snapshots (DataGrip, IDEA): triage identically; use the suspect list for the
  IDE issue tracker instead of a service ticket.

## Stop conditions

- No dump and no live process to trigger one: state the flags needed and stop; do not
  speculate about retention from symptoms alone.
- Dump is truncated (MAT parse fails or reports sections missing): report the parse
  failure; do not interpret partial output as the memory profile.
- MAT demands a newer JDK than installed: fix the JDK first; a "suitable JVM" dialog is
  not a dump problem.
