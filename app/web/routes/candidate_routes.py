from app.utils.formatters import get_status_badge_class, get_candidate_initials, calculate_preliminary_fit, format_date_only, format_datetime
import os
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.models.candidate import Candidate
from app.models.application import Application
from app.web.auth import get_current_user_required

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
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    stmt = (
        select(Candidate)
        .options(selectinload(Candidate.applications).selectinload(Application.vacancy))
        .order_by(desc(Candidate.created_at))
    )
    result = await session.execute(stmt)
    candidates = list(result.scalars().all())

    return templates.TemplateResponse(request=request, name="candidates.html", context={
            "request": request,
            "current_user": current_user,
            "candidates": candidates,
            "active_nav": "candidates"
        })
