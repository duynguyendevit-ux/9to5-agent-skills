---
name: 9to5-redis-design
description: Review and design Redis usage in Platform services — key namespacing, TTL policy, cache-first reads with DB fallback, AFTER_COMMIT invalidation, Lua guards that protect partial cache entries, and runtime control keys with safe fallbacks. Use when adding or reviewing a cache, diagnosing stale or missing cache data, deciding TTL versus explicit invalidation, or putting a runtime switch into Redis.
license: MIT
compatibility: Read-only review; running examples need the service checkout and, for live inspection, cluster access through 9to5-k8s-service-debug. No FLUSH or KEYS commands against shared Redis instances.
metadata:
  version: "1.0.0"
---

# Redis design — keys, TTL and consistency

## Example output

Illustrative review; keys, TTLs and owners must come from the actual service.

```text
Cache: cacheEventHandle:{eventHandleId} (hash), TTL 2700s, written by command service on
  event entry, updated by AFTER_COMMIT listeners on state change, guarded by a Lua script
  that refuses to create the hash when it does not exist.
Verdict: consistency model is sound (no partial hashes); TTL is the backstop.
Risks: cache-first reads in REDIS mode must keep the DB fallback for misses;
  runtime mode key must fall back safely when Redis is unreachable.
Unverified: eviction policy on the deployed instance — confirm with ops before relying on TTL.
```

## Scope and boundaries

- Covers cache/data structures and their lifecycle. Milestone scheduling on ZSETs is a
  mechanism owned by `9to5-scheduled-jobs`; this skill owns the key, TTL and consistency
  review around it.
- No writes to shared Redis in review mode. `KEYS` is forbidden on shared instances —
  use `SCAN` with filters if enumeration is genuinely required.
- Runtime diagnosis of a service touching Redis stays with `9to5-k8s-service-debug`;
  this skill decides whether the design is right.

## Review workflow

1. **Inventory the keys.** For each key or namespace, record shape (string/hash/ZSET),
   owner (which service writes it), readers, TTL, and whether it is cache, config, queue
   or control data. See [`references/patterns.md`](references/patterns.md) for the
   namespaces already in use and their rules.
2. **Trace read paths.** Cache-first flows must define the miss path explicitly
   (read-through to DB and repopulate, or fallback read only). A cache-first read with no
   documented fallback turns Redis into a single point of failure.
3. **Trace write and invalidation paths.** State changes should update or evict the
   affected key at `AFTER_COMMIT` time, not inside the transaction. Publishing
   invalidation before commit races the commit; never do it.
4. **Check partial-write guards.** A multi-field write must not create a half-populated
   entry when the entry expired between read and write. The house guard is a Lua script
   that checks `EXISTS` and refuses to write when the hash is gone.
5. **Check TTL semantics.** TTL is the backstop for missed invalidation, so it must be
   longer than the worst-case processing window and short enough that stale data heals.
   Document the number and the reason, not just the constant.
6. **Check control keys.** Runtime switches stored in Redis need a documented key, a
   default value, and a fallback when Redis is unreachable. The fallback must be the
   safe mode, never the aggressive one.
7. **Check operational constraints.** Eviction policy versus business data, memory
   headroom, serialization format versioning, and whether key rename would break
   rolling deploys. When the instance policy is unknown, mark it unverified and ask ops.
8. **Report** with the collection's proof labels and one next action.

When the design is still open, ask about the read path (cache-first, filter-then-hydrate, or
cached response) and the write path (enrich entries at save vs hydrate on read) as two
separate questions — one combined question conflates two independent decisions.

## Rules worth enforcing

| Rule | Reason |
|---|---|
| Namespaces use lowercase `segment:segment` or `cacheXxxYyy` prefixes with `{id}` as the last segment | Greppable, collision-free across services |
| Every cache key has an explicit TTL | Eviction policy is not a retention policy |
| Config caches name the owning service (`cache<Service><Domain>Config`) | Readers know where updates come from |
| Control keys live under a dedicated prefix and have env-configured names | Operators can switch behaviour without deploys |
| Multi-field writes never create missing entries | Partial cache entries surface as wrong business decisions |
| Consumers of a cache tolerate a miss without failing the flow | Default: fallback to the source of truth |

## Safety

- Do not print Redis connection details, passwords or key values that carry personal
  data into reports; cite key names, TTLs and owners only.
- `SCAN`/`TTL`/`MEMORY USAGE` are acceptable read-only checks; `KEYS`, `FLUSH*`,
  `MONITOR` and script execution on shared instances are not part of review.
- A TTL removal ("make it permanent") is a design change requiring the same review as a
  schema change.

## Handoffs

- ZSET scheduler mechanics and mode switching → `9to5-scheduled-jobs`.
- Publish/outbox flow around cache updates → `9to5-kafka`.
- Cache-miss pressure suspected of hitting Oracle down to slow queries →
  `9to5-oracle-index` after `9to5-sql-forensics` reconstructs the statements.
- Live instance behaviour, keyspace stats, pod-level Redis connectivity →
  `9to5-k8s-service-debug`.

## Stop conditions

- Service checkout unavailable: review what exists (vault notes, logs, config) and mark
  the rest unverified; do not guess key shapes.
- Deployed eviction policy unknown and the design depends on it: state the dependency and
  stop at the recommendation.
- Request is "just add a cache" with no owner for invalidation: refuse the shortcut; a
  cache without an invalidation owner is a defect, not an optimization.
