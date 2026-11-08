-- GOLD: one row per learner per UTC day, ready for the "progress over time" chart.
--
-- Only COMPLETED attempts count, bucketed by the UTC day they were completed on.
-- AT TIME ZONE 'UTC' converts the timestamptz to a plain UTC timestamp, so the day does not
-- depend on the database session's time zone.

CREATE SCHEMA IF NOT EXISTS gold;
DROP TABLE IF EXISTS gold.learner_daily;

CREATE TABLE gold.learner_daily AS
WITH completed AS (
    -- Completed attempts with their UTC calendar day.
    SELECT
        user_id,
        (completed_at AT TIME ZONE 'UTC')::date AS day,
        max_hint_level,
        revealed,
        is_independent,
        effective_score
    FROM silver.attempt_facts
    WHERE status = 'completed'
)
SELECT
    user_id,
    day,
    COUNT(*)                                                         AS attempts_completed,
    ROUND(AVG(is_independent::int), 3)                               AS independence_rate,
    ROUND(AVG(max_hint_level), 3)                                    AS avg_hint_level,
    ROUND(AVG(revealed::int), 3)                                     AS reveal_rate,
    ROUND(AVG(effective_score), 3)                                   AS avg_effective_score
FROM completed
GROUP BY user_id, day;

ALTER TABLE gold.learner_daily ADD PRIMARY KEY (user_id, day);
