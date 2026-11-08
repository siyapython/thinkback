"""Data quality checks. Each check runs one query and returns the OFFENDING rows, so an empty
list means "passed". Tests assert emptiness; a human can run `python -m pipeline.quality`."""

from sqlalchemy import Connection, create_engine, text

# Keep in sync with backend/app/models.py::EVENT_TYPES (a test compares the two).
ALLOWED_EVENT_TYPES = (
    "document_uploaded",
    "concepts_extracted",
    "question_served",
    "hint_requested",
    "answer_submitted",
    "answer_graded",
    "answer_revealed",
)

# name -> SQL returning one row per violation.
CHECKS: dict[str, str] = {
    "completed_not_before_started": """
        SELECT attempt_id, started_at, completed_at FROM silver.attempt_facts
        WHERE completed_at < started_at""",
    "hint_level_in_range": """
        SELECT attempt_id, max_hint_level FROM silver.attempt_facts
        WHERE max_hint_level NOT BETWEEN 0 AND 4""",
    "one_silver_row_per_attempt": """
        SELECT attempt_id, COUNT(*) AS n FROM silver.attempt_facts
        GROUP BY attempt_id HAVING COUNT(*) > 1""",
    "silver_count_equals_attempts": """
        SELECT s.n AS silver_rows, a.n AS attempts_rows
        FROM (SELECT COUNT(*) AS n FROM silver.attempt_facts) s,
             (SELECT COUNT(*) AS n FROM public.attempts) a
        WHERE s.n <> a.n""",
    "rates_and_mastery_in_unit_range": """
        SELECT 'learner_daily' AS tbl, user_id, day::text AS key FROM gold.learner_daily
        WHERE independence_rate NOT BETWEEN 0 AND 1 OR reveal_rate NOT BETWEEN 0 AND 1
        UNION ALL
        SELECT 'concept_summary', user_id, concept_id::text FROM gold.concept_summary
        WHERE mastery NOT BETWEEN 0 AND 1""",
    "gold_daily_reconciles_with_silver": """
        SELECT COALESCE(g.user_id, s.user_id) AS user_id, g.n AS gold_total, s.n AS silver_total
        FROM (SELECT user_id, SUM(attempts_completed) AS n FROM gold.learner_daily
              GROUP BY user_id) g
        FULL JOIN (SELECT user_id, COUNT(*) AS n FROM silver.attempt_facts
                   WHERE status = 'completed' GROUP BY user_id) s USING (user_id)
        WHERE g.n IS DISTINCT FROM s.n""",
    "event_types_allowed": """
        SELECT id, event_type FROM public.events_raw
        WHERE event_type <> ALL (:allowed)""",
    "funnel_excludes_failed_extractions": """
        SELECT f.user_id, f.document_id, f.concepts_extracted AS funnel_count, e.n AS ok_events
        FROM gold.funnel f
        LEFT JOIN (
            SELECT user_id, document_id, COUNT(*) AS n FROM public.events_raw
            WHERE event_type = 'concepts_extracted'
              AND payload ->> 'success' IS DISTINCT FROM 'false'
            GROUP BY user_id, document_id
        ) e ON e.user_id = f.user_id AND e.document_id = f.document_id
        WHERE f.concepts_extracted <> COALESCE(e.n, 0)""",
}


def run_check(conn: Connection, name: str) -> list[dict]:
    rows = conn.execute(text(CHECKS[name]), {"allowed": list(ALLOWED_EVENT_TYPES)}).mappings()
    return [dict(r) for r in rows]


def run_all(conn: Connection) -> dict[str, list[dict]]:
    return {name: run_check(conn, name) for name in CHECKS}


def main() -> None:
    from app.config import get_settings

    with create_engine(get_settings().DATABASE_URL).connect() as conn:
        failed = {k: v for k, v in run_all(conn).items() if v}
    for name in CHECKS:
        print(f"{'FAIL' if name in failed else 'ok  '}  {name}")
    raise SystemExit(1 if failed else 0)


if __name__ == "__main__":
    main()
