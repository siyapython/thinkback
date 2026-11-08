# Learning notes

Plain-English notes on what was built and why, one section per milestone.

## Milestone 1: backend foundation

### What got built
A FastAPI app (`GET /health`), settings read from the repo-root `.env`, SQLAlchemy models for the
whole schema, an Alembic migration that creates it in Postgres, a seed script for a demo user,
and pytest tests (including tests that the database rejects bad values). See `docs/schema.md` for
every table.

### Setting up and running it (you run these; nothing is activated for you)
From the repo root:

```bash
docker compose up -d db                 # start Postgres on 127.0.0.1:5432
cd backend
python3 -m venv .venv                   # one-time: create the virtual environment
source .venv/bin/activate               # every new terminal: turn it on
pip install -r requirements.txt         # one-time: install dependencies
alembic upgrade head                    # create the tables
python -m app.seed                      # create the demo user (safe to re-run)
pytest                                  # run tests (needs the db + migration above)
uvicorn app.main:app --reload           # run the API, then open http://localhost:8000/health
ruff check . && ruff format .           # lint + format
```

A *virtual environment* is a private folder of Python packages for this project, so versions
don't clash with other projects. `.venv/` is gitignored.

Settings: `DATABASE_URL`, `ANTHROPIC_API_KEY`, `LLM_MODE` (`fake` or `real`), `MODEL_FAST`,
`MODEL_STRONG` come from the repo-root `.env` (defaults exist, so the app starts without them).
`LLM_MODE=fake` lets us build and test without spending API credits.

### What is an ORM?
An Object-Relational Mapper lets you work with database rows as Python objects. `User(display_name="Ada")`
plus `session.add(...)` becomes an `INSERT`; a Python class stands for a table, an attribute for a column.
SQLAlchemy is the ORM here. It saves boilerplate and catches typos earlier, but the SQL still exists
underneath. Because this is a SQL-learning project, read the SQL it generates (set `echo=True` on the engine).

### What is a migration?
A migration is a versioned script that changes the database structure (create a table, add a column).
The history lives in git (`backend/alembic/versions/`), so every machine can reach the same schema with
`alembic upgrade head`, and you can go back with `alembic downgrade`. Without migrations the schema is
only whatever happens to be in your local database. Alembic stores the current version in a table
called `alembic_version`. Here the first migration was generated from the models with `--autogenerate`
and then read through by hand: always review generated migrations.

### Why TEXT + CHECK instead of ENUM?
A Postgres `ENUM` is its own type. Adding a value is awkward (`ALTER TYPE`), removing or renaming one
is worse, and it interacts badly with migrations. `TEXT` with `CHECK (status IN ('a','b'))` gives the
same protection (the database rejects bad values) but changing the allowed list is a plain
drop-and-recreate of one constraint. Tests prove it: level `5` and rubric score `1.5` are rejected by
the database itself, even if the Python code had a bug. Numeric ranges (`BETWEEN 0 AND 1`) use the same tool.

### Why does events_raw have no foreign keys (except user)?
It is an append-only log of what happened at a moment in time. Foreign keys would (1) slow inserts,
(2) block deleting a question or document because old events point at it, or force cascading
deletes that erase history, and (3) make the log depend on the live tables' shape. Without them, the
log stays a faithful record even after rows are deleted or the app changes. The cost is that ids in
events can dangle, so the analytics pipeline must tolerate missing joins (use LEFT JOINs). There is a
test that dangling ids are accepted.

### Why does concepts use an array of chunk ids instead of a join table?
The "proper" design is a `concept_chunks(concept_id, chunk_id)` join table, with real foreign keys,
and the ability to ask "which concepts use this chunk?" efficiently. For a one-day build that is more
tables, more code, and more joins for something we mostly read as "show the sources for this concept".
A `BIGINT[]` column is one column, read together with the concept. The trade-off: Postgres cannot
enforce that the ids exist, and reverse lookups are harder (possible with `= ANY(...)` or a GIN index).
This is a **deliberate simplification for tonight**; if reverse lookups or integrity start to matter,
migrate to a join table.

### What to study
- SQLAlchemy 2.0: `DeclarativeBase`, `Mapped[]`, `mapped_column`, `Session`.
- Alembic basics: `revision --autogenerate`, `upgrade`, `downgrade`, `check`.
- Postgres: `CHECK` and `UNIQUE` constraints, `ON DELETE CASCADE`, identity columns, `TIMESTAMPTZ`, array and `JSONB` types.
- Testing against a real database with a transaction that is rolled back after each test (`tests/conftest.py`).
