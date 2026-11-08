from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

engine = create_engine(get_settings().DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)


def get_session():
    """FastAPI dependency: one session per request."""
    with SessionLocal() as session:
        yield session


__all__ = ["engine", "SessionLocal", "get_session", "Session"]
