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

## Milestones 2+3: document upload, chunking and concept extraction

### What got built
- `POST /documents` takes pasted text (JSON `{title, text}`) or a PDF (multipart `file`). It checks size (10 MB) and page count (30), hashes the content (SHA-256) to reject duplicates with a `409`, pulls text out of PDFs page by page with `pypdf`, and saves **chunks**.
- `POST /documents/{id}/extract-concepts` sends the chunks to an LLM, validates what comes back, and stores **concepts**. `GET /documents`, `GET /documents/{id}` and `GET /documents/{id}/concepts` read it all back.
- `document_uploaded` and `concepts_extracted` rows go into `events_raw`, so the analytics pipeline will have something to read.
- Run it: `uvicorn app.main:app --reload`, then open http://localhost:8000/docs to try the endpoints.

### What is chunking, and why?
Chunking means cutting a long document into smaller pieces ("chunks"), here roughly 500-800 tokens each (we approximate a token as 4 characters). We do it because:
1. An LLM can only read so much at once, and cost grows with length, so we work on pieces.
2. Later, a hint can point to *the specific chunk* that supports it, and a concept can say which chunks it came from. That only works if chunks have stable ids.
3. We break on paragraph boundaries so a chunk never cuts a thought in half. Each chunk also remembers its `page_start`/`page_end` so a learner can be pointed back to the right page.

If one paragraph is bigger than the maximum, it is split on sentence boundaries as a fallback. The last chunk of a document can be shorter than 500 tokens; that is normal.

### What are a prompt template and a prompt version for?
A **prompt template** is the fixed instruction text with a gap where the changing material goes (`app/prompts/extract_concepts.py`). Keeping it in its own file, not buried in code, makes it easy to read, review and change. A **prompt version** (`PROMPT_VERSION = "extract_concepts_v1"`) is a label you bump whenever the wording changes. We store it on every concept (and later on questions, hints and grades), so when results look better or worse you can answer "which prompt produced this?". Without it you can't compare prompts, or tell old data from new.

### Why does the LLM client have a fake mode?
`LLM_MODE=fake` returns canned, deterministic JSON instead of calling the API. Reasons: tests run offline, instantly, for free, and give the same answer every time; you can build and demo without an API key; and tests can feed in *bad* output (malformed JSON, invalid chunk indexes) that the real model rarely produces, to prove our error handling works. Both implementations share one interface (`complete(system, user) -> text + model name`), so the rest of the app doesn't know or care which one it has. The test suite forces fake mode, whatever your `.env` says.

### What does idempotent mean?
An operation is idempotent if doing it twice leaves things the same as doing it once. Running "extract concepts" again on the same document must not create a second copy of every concept. We match concepts by a *normalized name* (lowercase, punctuation removed, so "Left-Join" equals "left join") and update the existing row instead of inserting. This matters because users double-click, requests are retried after network failures, and failed extractions get re-run. Related: the duplicate-upload check (same content hash -> `409`) makes uploads safe to repeat.

### How does grounding reduce hallucination?
A *hallucination* is when a model confidently states something that isn't true. The prompt is **grounded**: it says to use ONLY the provided material, and each concept must cite the chunk indexes that support it. Then our code checks the citations: an index that doesn't exist is dropped, and a concept with no valid chunk is thrown away. So every stored concept points at real text the learner uploaded, and the learner can verify it. This reduces hallucination but does not eliminate it, since a model can still misread a chunk. Citations make mistakes *checkable*, which is the real benefit. The prompt also tells the model to treat the material as data and ignore instructions hidden inside it (a basic defence against "prompt injection" from uploaded documents).

### Other design notes
- The PDF is saved to `backend/uploads/` (gitignored) under a name made from the user id and content hash, never from the uploaded filename, so a malicious filename like `../../x.pdf` can't write elsewhere. The API never returns `file_path`.
- A PDF with no text layer (scanned images) is saved with `status=failed` and an explanatory `error_message`, instead of failing silently.
- Malformed model JSON is retried once; a second failure marks the document `failed` with a clear message (HTTP 502).
- Everything acts as the demo user (id 1) for now. `app/deps.py` is the single place to swap in real auth later.

### What to study
- HTTP status codes: 201, 404, 409 (conflict), 413 (too large), 422 (can't process), 502 (upstream failed).
- FastAPI dependency injection (`Depends`) and `dependency_overrides`, which is how the tests swap in a fake LLM and a test database session.
- Hashing (SHA-256) for de-duplication; why you never trust user-supplied filenames.
- Pydantic validation of untrusted (LLM) output.
