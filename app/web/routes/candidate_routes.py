import os
from typing import Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.models.candidate import Candidate
from app.models.application import Application
from app.web.auth import get_current_user_required
from app.utils.formatters import (
    get_status_badge_class,
    get_candidate_initials,
    calculate_preliminary_fit,
    format_date_only,
    format_datetime,
    parse_date_range_to_utc
)

router = APIRouter(prefix="/candidates")
templates = Jinja2Templates(directory=os.path.join(settings.BASE_DIR, "app/web/templates"))
templates.env.globals["get_badge_class"] = get_status_badge_class
templates.env.globals["get_initials"] = get_candidate_initials
templates.env.globals["get_fit"] = calculate_preliminary_fit
templates.env.globals["format_date"] = format_date_only
templates.env.globals["format_datetime"] = format_datetime

@router.get("", response_class=HTMLResponse)
async def list_candidates(
    request: Request,
    q: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    from_utc, to_utc, date_error = parse_date_range_to_utc(from_date, to_date)

    stmt = (
        select(Candidate)
        .options(selectinload(Candidate.applications).selectinload(Application.vacancy))
        .order_by(desc(Candidate.created_at))
    )

    if from_utc:
        stmt = stmt.where(Candidate.created_at >= from_utc)
    if to_utc:
        stmt = stmt.where(Candidate.created_at <= to_utc)

    if q and q.strip():
        words = [w for w in q.strip().split() if w]
        cand_conditions = []
        for word in words:
            w_term = f"%{word}%"
            cand_conditions.append(
                or_(
                    Candidate.full_name.ilike(w_term),
                    Candidate.email.ilike(w_term),
                    Candidate.phone.ilike(w_term),
                    Candidate.telegram_username.ilike(w_term)
                )
            )
        stmt = stmt.where(and_(*cand_conditions))

    result = await session.execute(stmt)
    candidates = list(result.scalars().all())

    return templates.TemplateResponse(
        request=request,
        name="candidates.html",
        context={
            "request": request,
            "current_user": current_user,
            "candidates": candidates,
            "search_query": q or "",
            "from_date": from_date or "",
            "to_date": to_date or "",
            "date_error": date_error,
            "active_nav": "candidates"
        }
    )
