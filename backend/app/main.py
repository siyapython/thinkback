from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import analytics, documents, practice

settings = get_settings()

app = FastAPI(title="Thinkback API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(documents.router)
app.include_router(practice.router)
app.include_router(analytics.router)


@app.get("/health")
def health() -> dict[str, str]:
    """`llm_mode` tells the UI whether AI replies are canned placeholders ("fake") or real."""
    return {"status": "ok", "llm_mode": get_settings().LLM_MODE}
