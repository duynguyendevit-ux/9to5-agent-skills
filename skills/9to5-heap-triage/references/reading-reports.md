# Reading MAT reports

Anatomy of the headless report set, the patterns worth acting on, and the limits of
each claim. Written for MAT 1.17 (JDK 21+ required; JDK 17 shows an "Incompatible JVM"
dialog and the parse never starts).

## The report set

`analyze` archives three zips per dump and unzips each next to it:

| Report | Open it for | Key sections |
|---|---|---|
| `<dump-stem>_Leak_Suspects` | retained-heap suspects | Problem Suspect N, Suspect Objects by Class, All Objects by Class Retained by Suspect Objects |
| `<dump-stem>_System_Overview` | whole-heap shape and context | Heap details, OutOfMemoryError presence, System Properties, Thread Overview |
| `<dump-stem>_Top_Components` | named memory waste | Duplicate Strings, Empty Collections, Zero-Length Arrays, Collection/Array Fill Ratios |

The HTML is grep-able after unzipping; `Problem Suspect` sections carry the percentages.

## Anatomy of a Problem Suspect

```
Problem Suspect 1
  <N> instances of <class>, loaded by <loader>
  occupy <bytes> (<pct>%) bytes.
  The top consumers of their minimum retained heap are
  <class A> (<n> instances totaling <bytes>), ...
  Keywords: <class>
```

- `occupy` is the shallow/dominator-ish measure MAT attributes to the suspect set.
- "top consumers of their minimum retained heap" names what those instances retain —
  the actual payload. For a class-bloat suspect this is typically `byte[]`, `String`,
  `Object[]`.
- The table "All Objects by Class Retained by Suspect Objects" shows the payload sizes
  with `>=` because retained heap is shared between suspects; do not add rows.

## Pattern table

| Pattern | Mechanism to check | Evidence that confirms it |
|---|---|---|
| `java.lang.Class` suspect, tens of thousands of instances | class/metadata bloat — generated classes, proxies, script engines, plugin trees, or stale class loaders | compare class counts across two dumps; count distinct loaders |
| One domain class with huge instance count | unbounded collection/cache | GUI: histogram → class → Path to GC Roots; find the owning service/structure |
| `java.lang.Thread`, `ThreadLocal`, executor internals | leaked threads or thread-local payloads | Thread Overview; thread count growth between dumps |
| `char[]`/`byte[]`/`String` leading the consumers | payloads held as text/bytes: logs, JSON, message bodies, caches | identify the retaining container class in the same table |
| Duplicate strings / empty collections in Top Components | waste, usually secondary | act only when the percentage is material and the fix is local |
| `OutOfMemoryError` object present | snapshot was taken after an OOME | if the suspect list is flat, read it as allocation spike, not leak |
| Very flat suspect list with high total | could be normal distribution or a spike | prefer an allocation record (`-XX:+HeapDumpOnOutOfMemoryError` with JFR allocation events) |

## Worked example (real dump, no secrets)

`DB-261.24374.56_memory_15.06.2026_08.35.33.hprof` (619 MB, JetBrains snapshot):

- Problem Suspect 1: 37,875 `java.lang.Class` instances, system class loader, 10.43% of
  heap; retained through 249,225 `byte[]` and 247,463 `String`.
- One `OutOfMemoryError[]` instance present.
- Reading: class/metadata bloat recorded after an OOME, consistent with the machine's
  two `unload-*.hprof` dumps (failed unloading). A healthy IDE sits far below 37k
  loaded classes; the fix direction is plugin/loader inventory, not heap size.
- Unverified without GUI: whether the classes come from duplicated loaders.

## Limits to state in the write-up

- Headless MAT proves retention structure; it does not prove the retention is a leak
  (growth over time) or the allocation that triggered the OOME.
- Percentages are of the dump's heap, not of the JVM's configured maximum; a 619 MB
  dump from an 8 GB JVM says nothing about the JVM's ceiling.
- System Properties can contain credentials or internal hostnames; quote nothing from
  that table into tickets.
- An `.index` cache is removed after archiving; re-analysis of the same dump re-creates
  it and re-runs MAT (minutes). Prefer re-reading the report.
