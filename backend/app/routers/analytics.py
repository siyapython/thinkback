from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_session
from app.models import User
from app.schemas import AnalyticsOverviewOut, AnalyticsUserOut, RefreshOut
from app.services import analytics as analytics_service

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.post("/refresh", response_model=RefreshOut)
def refresh(session: Session = Depends(get_session)) -> RefreshOut:
    """Rebuild the silver and gold tables from scratch (a few hundred ms on demo-sized data)."""
    return RefreshOut(tables=analytics_service.refresh(session))


@router.get("/users", response_model=list[AnalyticsUserOut])
def users(session: Session = Depends(get_session)) -> list[AnalyticsUserOut]:
    """Who the dashboard can show: the real demo user and the synthetic one if it exists."""
    return [AnalyticsUserOut(**u) for u in analytics_service.selectable_users(session)]


@router.get("/overview", response_model=AnalyticsOverviewOut)
def overview(
    user_id: int | None = Query(default=None),
    session: Session = Depends(get_session),
) -> AnalyticsOverviewOut:
    """Dashboard data for one user (default: the demo user), read from the gold tables.
    Only the demo user and the synthetic user are viewable, since there is no auth yet."""
    uid = user_id if user_id is not None else get_settings().DEMO_USER_ID
    allowed = {u["id"] for u in analytics_service.selectable_users(session)}
    user = session.get(User, uid)
    if user is None or uid not in allowed:
        raise HTTPException(404, "User not found")
    return AnalyticsOverviewOut(**analytics_service.overview(session, user))
