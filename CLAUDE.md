# Thinkback

An AI learning partner for SQL practice. It gives escalating Socratic hints
(never full answers) and tracks learner independence through an analytics pipeline.

## Stack
- Frontend: React + TypeScript (Vite), Ant Design, ECharts, TanStack Query
- Backend: Python, FastAPI, SQLAlchemy, Alembic
- Database: PostgreSQL (run via Docker Compose)
- AI: Anthropic API (hint engine)
- Pipeline: plain SQL transforms (bronze/silver/gold) run from Python
- Testing/CI: pytest, Ruff, ESLint, GitHub Actions

## Folder layout
- backend/   FastAPI app, models, hint engine, tests
- frontend/  React app
- pipeline/  SQL transforms and data quality tests
- docs/      architecture notes and decision records

## How to work in this repo
- I'm a student under a deadline. Build features end to end, but after each
  feature write a short plain-English explanation into docs/LEARNING.md
  (what it does, why it's designed this way, what to study).
- Commit after each working feature with a conventional commit message,
  on a feature branch, and push it.
- Never commit secrets. Real keys live in .env, which is gitignored.
- Write tests alongside code and run them before committing.

## Conventions
- Conventional commits: feat:, fix:, test:, docs:, chore:
- Python formatted and linted with Ruff
- TypeScript: function components and hooks only