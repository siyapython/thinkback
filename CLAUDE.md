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
- I am a student learning full-stack development. Explain non-obvious decisions briefly.
- Make one small change per request. Do not build multiple features at once.
- Write tests alongside code.
- Never commit secrets. Real keys live in .env, which is gitignored.
- I am writing the hint-engine system prompt, the SQL transforms, and the
  metric definitions myself. Review those for me, but do not rewrite them.
- When I'm debugging, prefer guiding questions over handing me the fix.

## Conventions
- Conventional commits: feat:, fix:, test:, docs:, chore:
- Python formatted and linted with Ruff
- TypeScript: function components and hooks only