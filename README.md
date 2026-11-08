# Thinkback

An AI learning partner that gives hints and Socratic questions instead of answers.

## Running locally

You need Docker, Python 3.13 and Node 22. Put your real keys in `.env` at the repo root (gitignored; never commit it).

```bash
# 1. Start PostgreSQL (from the repo root)
docker compose up -d

# 2. Create the tables, then start the API on http://localhost:8000 (from backend/)
cd backend
alembic upgrade head
uvicorn app.main:app --reload --port 8000

# 3. In a second terminal, start the web app on http://localhost:5173 (from frontend/)
cd frontend
npm install        # first time only
npm run dev
```

The frontend talks to `http://localhost:8000` by default. To point it elsewhere, copy
`frontend/.env.example` to `frontend/.env` and set `VITE_API_URL`.
The API only accepts browser requests from origins listed in `CORS_ORIGINS`
(default `http://localhost:5173`).

Checks: `npm run lint`, `npm test` and `npm run build` in `frontend/`.
