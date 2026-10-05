# Device availability error taxonomy and data shapes

Grounded in the seeded `TTDVKH_AVAILABILITY.availability_errors` table, the ops counting
script and the availability service checkouts. Recheck the seed data before relying on a
code; codes are data, not enums in a schema migration.

## Error codes seen in seed data

| Code | Vietnamese name | Reading | Likely cause | First checks |
|---|---|---|---|---|
| `EVENT_TYPE_DEVICE_DISCONNECTED` | Lỗi mất kết nối | Device lost connection | Power, network drop, device offline | Device-side, LAN, heartbeat gap |
| `SERVICE_DISCONTECTED` | Lỗi mất kết nối service | Service (iot-gateway) unreachable | Platform/service outage |availability-cron health checks, deployment events |
| `DEVICE_LATE_EVENT` | Lỗi tin chậm | Events arriving late | Congestion, backlog, clock | Ingestion lag, Kafka lag, device clock |
| `LAN_FAULT_CHANNEL` | Lỗi kênh LAN | LAN channel fault | Wiring/switch/VLAN | Site-side wiring, switch logs |
| `FOUR_GENERATION_FAULT_CHANNEL` | Lỗi kênh 4G | 4G channel fault | Coverage, SIM/quota, carrier | Signal, SIM state, carrier incidents |

Notes:

- **`SERVICE_DISCONTECTED` is spelled that way in the data** (both the code and the table
  comment). Queries and scripts must match the data exactly; treat a rename as a data
  migration, not a typo fix.
- `sourceType` distinguishes record families in the daily index; device-origin failures
  are queried with `DEVICE_ERROR`. Service-health records come from scheduled health
  checks, not from devices.
- Codes carry a "property" linkage in the seed (`property_id`, `property_path`,
  `property_name`) — null in the base rows. Do not invent a property mapping.

## Calculation version mapping

`availability_version_mappings` maps a `version_id` to `calc_code` values, e.g.:

```
version_id 1 -> A_FATP_LAN, A_FATP_4G, FATP_LAN, A_FATSN, FATP_4G, A_FATB, ...
```

- A `calc_code` encodes the calculation variant (which faults count, which channel) for a
  version of the methodology.
- The same raw downtime can produce different availability under different versions; a
  report without the version is not reproducible.
- Adding a variant is a data/config change in the availability domain — coordinate with
  the owning service, not this skill.

## Daily index field reference (observed)

| Field | Meaning | Notes |
|---|---|---|
| `calcDate` | Calculation day bucket | Range filter field; format is date-based |
| `deviceCode` | Device identifier | `.keyword` for term/aggregation |
| `errorCode` | Taxonomy code above | `.keyword` for exact filter |
| `sourceType` | Record family (`DEVICE_ERROR`, service-health, ...) | `.keyword` term filter |
| `downtimeSeconds` | Accumulated downtime for the bucket range | Summed per device for the math |

Indices: daily availability index family used by ops counting (`device_avai_daily`), plus
install-base snapshot indices (`device_availability_installs`,
`device_availability_installs_full`) from the service side. Confirm alias/name against
the environment before running anything.

## Formula references

```text
downTimeMinutes = ceil(sum(downtimeSeconds) / 60)
availability    = (1 - downTimeMinutes / periodMinutes) * 100
failed          = availability < threshold
```

Worked example: 412 minutes down over a 10080-minute period →
`1 - 412/10080 = 95.91%`. With threshold 99.99 this device fails by a wide margin;
with a 1440-minute (1-day) period the same downtime is a total outage — the window is
half the finding.

## Service-side surfaces (availability-service)

- Query/export service with Excel templates and summary queries; cron-job tracking index
  distinguishes computed days from missing ones.
- Oracle view `vw_device_availability_installs` (schema `TTDVKH_ADMIN_GEIC`) is the
  installed-device base used by queries; a device outside it does not appear in results.
- Architecture follows the house clean layering; tests use a `Test` suffix and focused
  `--tests` runs (`./gradlew test --tests '*DeviceAvailabilitySummaryTotalQueryServiceTest'`).

## Reporting checklist

1. Window (`calcDate` range), period minutes, threshold, `sourceType` filter.
2. Calculation `version_id` (and calc codes when relevant).
3. Counts split by error family; worst-N devices with downtime minutes and percentage.
4. Denominator check against the install base for small device sets.
5. One next action per family (site wiring ticket, device replacement, platform check).
