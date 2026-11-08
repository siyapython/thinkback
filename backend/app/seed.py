"""Seed one demo user. Run from backend/:  python -m app.seed  (safe to re-run)."""

from sqlalchemy import select

from app.db import SessionLocal
from app.models import User

# The real account. Synthetic learners are labelled "synthetic data" in the dashboard instead.
DEMO_NAME = "You"


def seed() -> int:
    with SessionLocal() as session:
        user = session.scalar(select(User).where(User.display_name == DEMO_NAME))
        if user is None:
            user = User(display_name=DEMO_NAME)
            session.add(user)
            session.commit()
            print(f"Created demo user id={user.id}")
        else:
            print(f"Demo user already exists id={user.id}")
        return user.id


if __name__ == "__main__":
    seed()
