-- Outbox diagnosis queries (Oracle). Read-only.
--
-- Scope every query to one producer: the table can be shared by several services in
-- one schema, and `producer` is `spring.application.name` at write time.
--
--   DEFINE producer = 'establishment-registration'
--
-- Run through the k8s helper when the DB is not local:
--   ksql <app> <namespace>   then pipe the log-derived SQL
-- or paste into DataGrip against the service schema.

-- 1. Backlog by status — the first query to run. A growing PENDING count with a flat
--    PUBLISHED count means the publish worker is not draining.
-- created_at is TIMESTAMP without a timezone, populated from SYSTIMESTAMP by the
-- reference DDL. Compare the same server wall-clock representation. If a deployment
-- stores UTC instead, use a UTC timestamp here. Convert interval fields to NUMBER.
WITH backlog AS (
    SELECT status, COUNT(*) AS rows_count,
           MIN(created_at) AS oldest, MAX(created_at) AS newest,
           CAST(SYSTIMESTAMP AS TIMESTAMP) - MIN(created_at) AS age
    FROM   outbox_record
    WHERE  producer = '&producer'
    GROUP  BY status
)
SELECT status, rows_count, oldest, newest,
       ROUND(EXTRACT(DAY FROM age) * 1440
           + EXTRACT(HOUR FROM age) * 60
           + EXTRACT(MINUTE FROM age)
           + EXTRACT(SECOND FROM age) / 60, 1) AS oldest_age_minutes
FROM   backlog
ORDER  BY status;

-- 2. Stuck records — retried repeatedly without acknowledgement. attempt_count is the
--    signal; a high count with a recent next_attempt_at means the worker is alive but
--    the publish keeps failing (check last_error).
SELECT outbox_id, aggregate_type, aggregate_id, event_type, topic,
       attempt_count, next_attempt_at, created_at, last_error
FROM   outbox_record
WHERE  producer = '&producer'
AND    status = 'PENDING'
AND    attempt_count > 3
ORDER  BY attempt_count DESC, created_at
FETCH FIRST 50 ROWS ONLY;

-- 3. Due now — records the worker should be claiming on its next pass. Empty means the
--    backlog is waiting on backoff, not blocked.
SELECT COUNT(*) AS due_now
FROM   outbox_record
WHERE  producer = '&producer'
AND    status = 'PENDING'
AND    (next_attempt_at IS NULL OR next_attempt_at <= SYSTIMESTAMP);

-- 4. Failure reasons grouped — the fastest way to see whether one payload shape,
--    topic, or template is responsible for the whole backlog.
SELECT SUBSTR(last_error, 1, 120) AS error_head, COUNT(*) AS rows_count,
       MIN(created_at) AS first_seen, MAX(created_at) AS last_seen
FROM   outbox_record
WHERE  producer = '&producer'
AND    status = 'PENDING'
AND    last_error IS NOT NULL
GROUP  BY SUBSTR(last_error, 1, 120)
ORDER  BY rows_count DESC;

-- 5. Throughput — publishes per 15 minutes over the last 6 hours. Flat zero with a
--    non-empty backlog points at the worker; non-zero with a growing backlog points at
--    producer volume or Kafka latency.
SELECT TRUNC(published_at, 'HH24') + (FLOOR(TO_CHAR(published_at, 'MI') / 15) * 15) / 1440 AS bucket,
       COUNT(*) AS published
FROM   outbox_record
WHERE  producer = '&producer'
AND    status = 'PUBLISHED'
AND    published_at > SYSTIMESTAMP - INTERVAL '6' HOUR
GROUP  BY TRUNC(published_at, 'HH24') + (FLOOR(TO_CHAR(published_at, 'MI') / 15) * 15) / 1440
ORDER  BY bucket;

-- 6. Ordering check — the Kafka record key is the aggregate type, not the aggregate id.
--    All events of one aggregate type share a partition, and concurrent sends/retries do
--    not guarantee business commit order, so this query is a canary, not proof of a bug:
--    a published row preceding a still-pending row for the same aggregate id deserves a look
--    when the contract requires per-aggregate order.
SELECT p.aggregate_id,
       p.created_at      AS published_created,
       p.published_at,
       n.created_at      AS pending_created,
       n.attempt_count
FROM   outbox_record p
JOIN   outbox_record n
       ON n.aggregate_id = p.aggregate_id
       AND n.producer = p.producer
       AND n.status = 'PENDING'
WHERE  p.producer = '&producer'
AND    p.status = 'PUBLISHED'
AND    p.created_at < n.created_at
FETCH FIRST 20 ROWS ONLY;

-- 7. Malformed rows — a blank aggregate_id or topic. The writer re-resolves a blank topic
--    (it is never rejected) and validates the aggregate at append time, so stored rows
--    should always have both populated; any hit here is direct-SQL or corruption.
SELECT outbox_id, aggregate_type, event_type, topic, aggregate_id, status, created_at
FROM   outbox_record
WHERE  producer = '&producer'
AND    (TRIM(aggregate_id) IS NULL OR TRIM(topic) IS NULL);

-- 8. Payload templates referenced but missing or inactive — the publish path resolves
--    the template, so a missing row fails every event using that code.
SELECT o.payload_template_code, COUNT(*) AS pending_rows,
       CASE WHEN t.template_code IS NULL THEN 'MISSING'
            WHEN t.is_active = 0 THEN 'INACTIVE'
            ELSE 'ok' END AS template_state
FROM   outbox_record o
LEFT   JOIN payload_template t ON t.template_code = o.payload_template_code
WHERE  o.producer = '&producer'
AND    o.status = 'PENDING'
AND    o.payload_template_code IS NOT NULL
GROUP  BY o.payload_template_code,
          CASE WHEN t.template_code IS NULL THEN 'MISSING'
               WHEN t.is_active = 0 THEN 'INACTIVE'
               ELSE 'ok' END
HAVING CASE WHEN t.template_code IS NULL THEN 'MISSING'
            WHEN t.is_active = 0 THEN 'INACTIVE'
            ELSE 'ok' END <> 'ok';

-- 9. Cleanup candidates — PUBLISHED rows older than the configured retention. A large
--    number here with cleanup enabled means the cron is not running or is failing.
SELECT COUNT(*) AS cleanup_candidates,
       MIN(published_at) AS oldest_published
FROM   outbox_record
WHERE  producer = '&producer'
AND    status = 'PUBLISHED'
AND    published_at < SYSTIMESTAMP - INTERVAL '7' DAY;

-- 10. Table size and index health — a full scan on the claim query shows up as a slow
--     publish loop before it shows up as a backlog.
SELECT COUNT(*) AS total_rows,
       SUM(CASE WHEN status = 'PENDING' THEN 1 ELSE 0 END) AS pending_rows,
       ROUND(SUM(LENGTH(payload)) / 1024 / 1024, 1) AS payload_mb
FROM   outbox_record
WHERE  producer = '&producer';

-- 11. Confirm the claim indexes exist before blaming the query.
SELECT index_name, column_name, column_position
FROM   user_ind_columns
WHERE  table_name = 'OUTBOX_RECORD'
ORDER  BY index_name, column_position;
