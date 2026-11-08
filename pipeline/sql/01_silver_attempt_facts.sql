-- SILVER: one clean row per attempt.
--
-- Bronze (the operational tables + events_raw) is shaped for the app. Silver is shaped for
-- analysis: everything we need to know about an attempt sits in ONE row, with the business
-- definitions (revealed, independent) computed once here so every gold table agrees.
--
-- Independence definition (identical to GET /metrics/independence in the backend):
--   an attempt is independent when it is COMPLETED, max_hint_level <= 1 and it was NOT revealed.
--
-- Abandoned and in-progress attempts stay in this table (so counts reconcile with `attempts`),
-- but their completed-only metrics (seconds_to_complete, is_independent) are NULL, and every
-- gold table filters on status = 'completed'.

CREATE SCHEMA IF NOT EXISTS silver;
DROP TABLE IF EXISTS silver.attempt_facts;

CREATE TABLE silver.attempt_facts AS
WITH
-- One row per attempt with its answer count (every submitted answer, graded or not).
answer_counts AS (
    SELECT attempt_id, COUNT(*) AS answer_count
    FROM public.answers
    GROUP BY attempt_id
),

-- Rank each attempt's GRADED answers newest-first. A window function lets us pick "the last
-- graded answer" per attempt without a self-join: row_number() restarts at 1 for every attempt.
ranked_graded_answers AS (
    SELECT
        attempt_id,
        rubric_score,
        misconception,
        ROW_NUMBER() OVER (PARTITION BY attempt_id ORDER BY id DESC) AS rn
    FROM public.answers
    WHERE graded_at IS NOT NULL
),
final_answers AS (
    SELECT attempt_id, rubric_score, misconception
    FROM ranked_graded_answers
    WHERE rn = 1
),

-- How many hints were requested (the level itself lives on attempts.max_hint_level).
hint_counts AS (
    SELECT attempt_id, COUNT(*) AS hint_count
    FROM public.hint_requests
    GROUP BY attempt_id
)

SELECT
    a.user_id,
    c.document_id,
    q.concept_id,
    a.question_id,
    a.id                              AS attempt_id,
    q.question_type,
    a.started_at,
    a.completed_at,
    a.status,
    a.max_hint_level,
    (a.revealed_at IS NOT NULL)       AS revealed,
    fa.rubric_score                   AS rubric_score,        -- score of the LAST graded answer
    a.effective_score,                                          -- backend: best score * hint factor
    COALESCE(ac.answer_count, 0)      AS answer_count,
    COALESCE(hc.hint_count, 0)        AS hint_count,
    fa.misconception                  AS last_misconception,
    CASE WHEN a.status = 'completed'
         THEN EXTRACT(EPOCH FROM (a.completed_at - a.started_at))
    END                               AS seconds_to_complete,
    CASE WHEN a.status = 'completed'
         THEN (a.max_hint_level <= 1 AND a.revealed_at IS NULL)
    END                               AS is_independent       -- NULL unless completed
FROM public.attempts a
JOIN public.questions q ON q.id = a.question_id
JOIN public.concepts  c ON c.id = q.concept_id
LEFT JOIN answer_counts ac ON ac.attempt_id = a.id
LEFT JOIN final_answers fa ON fa.attempt_id = a.id
LEFT JOIN hint_counts   hc ON hc.attempt_id = a.id;

ALTER TABLE silver.attempt_facts ADD PRIMARY KEY (attempt_id);
CREATE INDEX ix_attempt_facts_user ON silver.attempt_facts (user_id, concept_id);
