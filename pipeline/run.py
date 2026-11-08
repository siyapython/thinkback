"""Full-refresh analytics pipeline: bronze (operational tables) -> silver -> gold.

Usage, from the repo root:   python -m pipeline.run

Every run drops the `silver` and `gold` schemas and rebuilds them from scratch by executing
pipeline/sql/*.sql in numeric order, all inside ONE transaction. Postgres DDL is transactional,
so readers see either the old tables or the new ones, never a half-built state, and a failure
in any file rolls everything back.
"""

from pathlib import Path

from sqlalchemy import Connection, create_engine, text

SQL_DIR = Path(__file__).parent / "sql"

# Order matters: gold reads silver.
TABLES = (
    "silver.attempt_facts",
    "gold.learner_daily",
    "gold.concept_summary",
    "gold.funnel",
)


def sql_files() -> list[Path]:
    return sorted(SQL_DIR.glob("[0-9][0-9]_*.sql"))


def run_pipeline(conn: Connection) -> dict[str, int]:
    """Rebuild silver and gold on `conn`. The caller owns the transaction (commit/rollback).
    Returns {table_name: row_count}."""
    conn.execute(text("DROP SCHEMA IF EXISTS gold CASCADE"))
    conn.execute(text("DROP SCHEMA IF EXISTS silver CASCADE"))
    for path in sql_files():
        # exec_driver_sql sends the file as-is: no bind-parameter parsing, several statements OK.
        conn.exec_driver_sql(path.read_text())
    return {t: conn.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar_one() for t in TABLES}


def main() -> None:
    from app.config import get_settings  # reads DATABASE_URL from env / .env; never printed

    engine = create_engine(get_settings().DATABASE_URL)
    with engine.begin() as conn:  # one transaction: commit on success, roll back on error
        counts = run_pipeline(conn)
    for table, n in counts.items():
        print(f"{table:<24}{n:>8} rows")


if __name__ == "__main__":
    main()
