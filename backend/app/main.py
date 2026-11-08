from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import get_settings
from app.routers import documents, practice

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


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
