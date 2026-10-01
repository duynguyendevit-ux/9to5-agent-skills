# Redis naming and consistency patterns in OTS services

Grounded in the ttch-worker-service / TTDVKH flows as recorded in the vault
(`Internal/Code/TTDVKH/ttch-worker-service/`). Recheck the service checkout before
relying on any specific key; treat this file as the pattern catalogue, not the registry.

## Namespace inventory seen in practice

| Key | Type | Role | TTL | Owner |
|---|---|---|---|---|
| `cacheEventHandle:{eventHandleId}` | hash | event-handle snapshot, cache-first read in REDIS mode | 2700s | worker/write services; queue path writers |
| `cacheTtdvkhDiaryContentTemplateConfig` | hash/config | diary template policy (`allowSendC7`, `markSendOnly`, `isActive`) | long/refresh-based | diary-service writes, worker reads |
| `schedule:event-handle:due` | ZSET | milestone due queue | none (drained) | worker registration + dispatcher |
| `event-handle:schedule:processing-mode` | string | runtime mode switch (`DB`/`REDIS`) | none | operators; env-configured key name |

Rules distilled from these:

- `cache<Domain>` marks cache-shaped data (snapshot, config). Non-cache operational data
  uses lowercase `segment:segment` names.
- `{id}` is the final segment; scans and monitoring assume the prefix is stable.
- Config caches are owned by the service that writes them; readers never write.
- Operational keys that operators touch (mode switches) are documented with their
  default and their safe fallback.

## Consistency model that works here

1. **Write-through on state change.** Command services update the snapshot at state
   transitions; scheduled reads then hit cache first and fall back to the DB on a miss.
2. **Invalidate/refresh from AFTER_COMMIT listeners.** Listener failures must not corrupt
   state: they update cache best-effort after the transaction commits, and the TTL is the
   backstop for a missed update.
3. **Guard multi-field writes with Lua.** The house guard:

   ```lua
   if redis.call('EXISTS', KEYS[1]) == 0 then
       return 0
   end
   redis.call('HSET', KEYS[1], ARGV[1], ARGV[2])
   return 1
   ```

   Rationale: between reading and writing, the entry can expire; creating it from a
   partial update produces a cache that looks warm but is wrong. Refusing the write and
   letting the next read repopulate from the DB is the safe failure mode.
4. **TTL is the healing mechanism.** 2700s (45 min) exceeds the longest milestone window
   in the flow; a stale snapshot heals by expiry even if every listener failed.
5. **Reads tolerate misses.** Cache-first code paths define the DB fallback; there is no
   path where a missing key fails the business flow.

## Runtime control keys

Resolution order seen in practice (generalize it):

1. Global kill switch (env flag) wins over everything.
2. Redis key read; errors → safe default.
3. Empty/invalid value → configured default.
4. Valid value → use it.

Operations use `SET`/`DEL` on the mode key for live switching; the key name is
env-configured so environments can differ. Any new control key must answer — what is the
kill switch, what is the default, what happens when Redis is unreachable — in its
docstring or ticket.

## Anti-patterns to reject in review

- Permanent keys whose only refresh path is an event you have not validated.
- Cache writes inside the database transaction (races the commit; holds locks longer).
- `KEYS`-style enumeration in production code; use `SCAN` or maintained sets.
- Cache entries that encode authorization or policy decisions without an expiry and
  without an owner for updates.
- "Temporary" removal of a guard script during an incident without a follow-up to
  restore it.
- Redis as the only copy of business state without a rebuild path from the database.

## Operational checks (read-only)

```redis
SCAN 0 MATCH cacheEventHandle:* COUNT 100   # presence/shape check, not enumeration
TTL cacheEventHandle:<id>                   # is the expected TTL actually applied
TYPE schedule:event-handle:due              # confirm ZSET before ZRANGEBYSCORE checks
```

Instance-level questions (eviction policy, memory headroom, persistence, cluster mode)
belong to the platform team; record the answer next to the design that depends on it.
