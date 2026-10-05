---
name: 9to5-device-availability
description: Query and reason about TTDVKH device availability — the error-event taxonomy recorded by availability-cron (disconnects, LAN and 4G faults, late events), downtime-based availability math over the daily index, period and threshold selection, the availability-service query and export surface, and calculation version mappings. Use when asked which devices failed availability, to compute or explain an uptime percentage, to investigate a LAN or 4G fault report, or to export availability data.
license: MIT
compatibility: Read-only analysis. Live queries need access to the availability Elasticsearch indices or the Oracle views; live service checks go through 9to5-k8s-service-debug. Endpoints and credentials come from environment configs and are never hardcoded.
metadata:
  version: "1.0.0"
---

# Device availability — fail counts, uptime math, error taxonomy

## Example output

Illustrative scan; devices, windows and numbers come from the actual data.

```text
Window: calcDate 2026-09-22 .. 2026-09-29, period 10080 min (7d), threshold 99.99%
Filter: sourceType DEVICE_ERROR
Devices below threshold: 14
Worst: DEV-00123 — 412 min down (LAN_FAULT_CHANNEL) → availability 95.9%
Family split: 9 devices LAN/4G channel faults, 3 disconnects, 2 late-event runs
Calc version: version_id 1 (calc codes FATP_LAN / A_FATP_4G ...) — stated with the report
Unverified: whether any of the 14 were uninstalled mid-window; check the install base view.
```

## Scope and boundaries

- Owns reading and explaining availability results: windows, thresholds, error families,
  arithmetic and versioning. Writing events happens in `availability-cron` from Kafka
  device-error streams; the query/export surface is `availability-service`.
- A service-health outage (iot-gateway down) is not a device fault: split the two before
  attributing a device failure — different owners, different fixes.
- Scheduling/locking mechanics of the cron service → `9to5-scheduled-jobs`; Kafka
  ingestion/replay of error events → `9to5-kafka`; schema changes → `9to5-sql-migration`.

## Availability math used by the ops tooling

From the counting script pattern (verify against the current script before quoting):

```text
downTimeMinutes = ceil(sum(downtimeSeconds) / 60)
availability    = (1 - downTimeMinutes / periodMinutes) * 100
failed          = availability < threshold
```

- 1 second of downtime costs a full minute (`ceil`) — small blips are expensive; say so
  when numbers look harsh.
- `period` is the window length in minutes (the ops default is 10080 = 7 days).
- `threshold` is the pass line (the ops default is 99.99%).
- Always state window, period, threshold and calculation version next to any number you
  report. The same device can pass one window and fail another.

## Query pattern (daily index)

The counting approach aggregates per device over the daily availability index
(fields seen in practice: `calcDate`, `deviceCode`, `errorCode`, `sourceType`,
`downtimeSeconds`; index family `device_avai_daily`):

```json
{
  "size": 0,
  "query": { "bool": { "filter": [
    { "range": { "calcDate": { "gte": "<from>", "lt": "<to>" } } },
    { "term":  { "sourceType.keyword": ["DEVICE_ERROR"] } }
  ] } },
  "aggs": { "by_device": {
    "composite": { "size": 10000, "sources": [ { "device": { "terms": { "field": "deviceCode.keyword" } } } ] },
    "aggs": {
      "sum_downtime_seconds": { "sum": { "field": "downtimeSeconds" } },
      "failed_only": { "bucket_selector": { "buckets_path": { "total": "sum_downtime_seconds" },
        "script": { "source": "double d = Math.ceil(params.total / 60.0); return (1.0 - (d / params.period)) * 100.0 < params.threshold;",
                    "params": { "period": 10080, "threshold": 99.99 } } } }
    }
  } }
}
```

- Page the composite aggregation with `after_key`; never scroll unbounded.
- Filter by `errorCode` when investigating one fault family; keep the field
  `.keyword`-suffixed for term filters.
- Endpoints, tokens and index aliases come from environment config; the script-level
  values are placeholders and must be taken from configuration, not from this file.

## Workflow

1. **Fix the question.** Which devices, which window (`calcDate` range), which period and
   threshold, which error family. Undefined thresholds produce unanswerable reports.
2. **Query the daily index** with the pattern above; collect per-device downtime and
   availability.
3. **Split families.** Use the taxonomy in
   [`references/error-taxonomy.md`](references/error-taxonomy.md): device disconnects and
   late events are device/telemetry stories; LAN/4G channel faults are connectivity
   stories; service disconnects belong to platform health and come from the cron's health
   checks, not from devices.
4. **State the calculation version.** Availability results are versioned through
   `availability_version_mappings` (`version_id` → `calc_code` set such as `FATP_LAN`,
   `A_FATP_4G`, `A_FATSN`). A recalculation with a new version can change results without
   any device changing behaviour — name the version in every report.
5. **Cross-check the denominator.** The export/query side works from the installed-device
   base (`vw_device_availability_installs` view and the install snapshot indices);
   devices without an install record fall out of exports. For a small device set, confirm
   membership before declaring "no failures".
6. **Prefer the service surface for anything shareable.** `availability-service` exposes
   query and Excel export; ad-hoc spreadsheets can go through MyDevTools Excel utilities.
   Cite the service artifact instead of a hand-built query when the audience is wider
   than the investigation.
7. **Report** counts by family, worst devices with downtime minutes and percentage, and
   the window/period/threshold/version block.

## Rules worth enforcing

| Rule | Reason |
|---|---|
| Window, period, threshold, version always stated | Same device passes/fails different windows |
| `ceil` to minutes is intentional | Blips cost a minute; explain before "fixing" |
| Device faults and service-health outages separated | Different owners and fix paths |
| Days are `calcDate` buckets on the daily index | Avoids recomputing from raw events |
| Error codes are seed data — match them exactly | `SERVICE_DISCONTECTED` is misspelled in the data; queries must match the data, not the intention |
| Endpoints from config, never from notes | Environment drift and secrets |

## Safety

- Read-only. Do not insert or backfill availability rows from this workflow; data fixes
  go through the owning service or `9to5-sql-migration`.
- Availability queries can be heavy: always bound `calcDate`, use composite paging, and
  avoid fetching raw per-event documents when an aggregation answers the question.
- Exports carry device and facility operation data; handle as operational information,
  not public content, and keep them out of the published vault area.

## Handoffs

- Error-event ingestion, consumer lag, replays → `9to5-kafka`.
- Cron scheduling, ShedLock locking, catch-up after downtime → `9to5-scheduled-jobs`.
- Live cron/service evidence (job did not run, health endpoint state) →
  `9to5-k8s-service-debug`.
- Schema/table changes for the availability domain → `9to5-sql-migration`.
- Excel-side manipulation of exports → `9to5-mydevtools`.

## Stop conditions

- Window or threshold unspecified: state the assumption used (period 10080, threshold
  99.99, sourceType DEVICE_ERROR) or ask on the ticket; never silently pick one.
- Index or view access missing: deliver the query and the exact expected fields; do not
  approximate from other tables.
- Results contradict the incident narrative and the calculation version is unknown: stop
  and identify the version before drawing conclusions.
