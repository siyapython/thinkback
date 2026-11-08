-- GOLD: one row per (learner, concept): how are they doing on each concept?
--
-- is_gap re-implements backend/app/services/mastery.py::is_gap in SQL so the dashboard and the
-- app can never disagree:
--   gap  =  (mastery < 0.6 AND concept_mastery.attempt_count >= 2)
--           OR the same (normalised) misconception on the two most recent completed attempts.

CREATE SCHEMA IF NOT EXISTS gold;
DROP TABLE IF EXISTS gold.concept_summary;

CREATE TABLE gold.concept_summary AS
WITH
-- Completed attempts only, with the misconception text normalised exactly like the backend
-- (lower-case, punctuation -> space, trimmed, empty -> NULL) so near-identical text matches.
completed AS (
    SELECT
        user_id, concept_id, attempt_id, completed_at,
        max_hint_level, revealed, effective_score,
        NULLIF(BTRIM(REGEXP_REPLACE(LOWER(last_misconception), '[\W_]+', ' ', 'g')), '')
            AS misconception_norm,
        last_misconception
    FROM silver.attempt_facts
    WHERE status = 'completed'
),

-- Plain per-(user, concept) aggregates.
per_concept AS (
    SELECT
        user_id,
        concept_id,
        COUNT(*)                          AS attempts,
        ROUND(AVG(effective_score), 3)    AS avg_effective_score,
        ROUND(AVG(max_hint_level), 3)     AS avg_max_hint_level,
        COUNT(*) FILTER (WHERE revealed)  AS reveal_count
    FROM completed
    GROUP BY user_id, concept_id
),

-- Window function: number each concept's completed attempts newest-first, so rn <= 2 are
-- "the two most recent". Ties on completed_at are broken by attempt id, like the backend.
recency AS (
    SELECT
        user_id, concept_id, misconception_norm,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, concept_id ORDER BY completed_at DESC, attempt_id DESC
        ) AS rn
    FROM completed
),
repeat_misconception AS (
    -- Two latest attempts exist, both have a misconception, and it is the same one.
    SELECT user_id, concept_id, TRUE AS repeated
    FROM recency
    WHERE rn <= 2
    GROUP BY user_id, concept_id
    HAVING COUNT(*) = 2
       AND COUNT(misconception_norm) = 2
       AND COUNT(DISTINCT misconception_norm) = 1
),

-- Most common misconception per (user, concept). Group by the normalised text, show the
-- most recent raw wording, and rank by frequency (then recency) with another window function.
misconception_counts AS (
    SELECT
        user_id, concept_id, misconception_norm,
        COUNT(*) AS n,
        MAX(completed_at) AS last_seen,
        (ARRAY_AGG(last_misconception ORDER BY completed_at DESC))[1] AS display_text
    FROM completed
    WHERE misconception_norm IS NOT NULL
    GROUP BY user_id, concept_id, misconception_norm
),
top_misconception AS (
    SELECT user_id, concept_id, display_text
    FROM (
        SELECT
            *,
            ROW_NUMBER() OVER (
                PARTITION BY user_id, concept_id ORDER BY n DESC, last_seen DESC
            ) AS rk
        FROM misconception_counts
    ) ranked
    WHERE rk = 1
)

SELECT
    p.user_id,
    p.concept_id,
    c.document_id,
    c.name                               AS concept_name,
    p.attempts,
    p.avg_effective_score,
    p.avg_max_hint_level,
    p.reveal_count,
    cm.mastery                           AS mastery,
    (
        (cm.mastery < 0.6 AND COALESCE(cm.attempt_count, 0) >= 2)
        OR COALESCE(r.repeated, FALSE)
    )                                    AS is_gap,
    t.display_text                       AS top_misconception
FROM per_concept p
JOIN public.concepts c ON c.id = p.concept_id
LEFT JOIN public.concept_mastery cm ON cm.user_id = p.user_id AND cm.concept_id = p.concept_id
LEFT JOIN repeat_misconception r ON r.user_id = p.user_id AND r.concept_id = p.concept_id
LEFT JOIN top_misconception t ON t.user_id = p.user_id AND t.concept_id = p.concept_id;

-- (cm.mastery < 0.6 AND ...) is NULL when mastery is NULL; make is_gap strictly true/false.
UPDATE gold.concept_summary SET is_gap = COALESCE(is_gap, FALSE);
ALTER TABLE gold.concept_summary ADD PRIMARY KEY (user_id, concept_id);
