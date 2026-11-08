-- GOLD: learning funnel per (learner, document), built from the bronze event log.
--
--   concepts_extracted -> question_served -> answer_submitted -> completed -> revealed
--
-- Every stage counts DISTINCT ATTEMPTS (not raw events) so retries and repeated submissions
-- don't inflate the numbers. Failed concept extractions are logged as a concepts_extracted
-- event with payload success=false; they are filtered out below.
--
-- "completed" is derived from events: an attempt completes when it is graded with
-- completed=true, or when its answer is revealed. (The manual POST /attempts/:id/complete
-- endpoint writes no event, so those completions are not visible here.)

CREATE SCHEMA IF NOT EXISTS gold;
DROP TABLE IF EXISTS gold.funnel;

CREATE TABLE gold.funnel AS
WITH
-- Keep only events that belong to a document, and drop failed extractions.
good_events AS (
    SELECT user_id, document_id, event_type, attempt_id, payload
    FROM public.events_raw
    WHERE document_id IS NOT NULL
      AND NOT (event_type = 'concepts_extracted'
               AND payload ->> 'success' IS NOT DISTINCT FROM 'false')
),
-- One row per (event type bucket, attempt) so DISTINCT is explicit.
stages AS (
    SELECT user_id, document_id, 'concepts_extracted' AS stage, NULL::bigint AS attempt_id
    FROM good_events WHERE event_type = 'concepts_extracted'
    UNION ALL
    SELECT user_id, document_id, 'question_served', attempt_id
    FROM good_events WHERE event_type = 'question_served'
    UNION ALL
    SELECT user_id, document_id, 'answer_submitted', attempt_id
    FROM good_events WHERE event_type = 'answer_submitted'
    UNION ALL
    SELECT user_id, document_id, 'completed', attempt_id
    FROM good_events
    WHERE (event_type = 'answer_graded' AND payload ->> 'completed' = 'true')
       OR event_type = 'answer_revealed'
    UNION ALL
    SELECT user_id, document_id, 'revealed', attempt_id
    FROM good_events WHERE event_type = 'answer_revealed'
)
SELECT
    s.user_id,
    s.document_id,
    d.title                                                               AS document_title,
    COUNT(*) FILTER (WHERE s.stage = 'concepts_extracted')                AS concepts_extracted,
    COUNT(DISTINCT s.attempt_id) FILTER (WHERE s.stage = 'question_served')   AS question_served,
    COUNT(DISTINCT s.attempt_id) FILTER (WHERE s.stage = 'answer_submitted')  AS answer_submitted,
    COUNT(DISTINCT s.attempt_id) FILTER (WHERE s.stage = 'completed')         AS completed,
    COUNT(DISTINCT s.attempt_id) FILTER (WHERE s.stage = 'revealed')          AS revealed
FROM stages s
LEFT JOIN public.documents d ON d.id = s.document_id
GROUP BY s.user_id, s.document_id, d.title;

ALTER TABLE gold.funnel ADD PRIMARY KEY (user_id, document_id);
