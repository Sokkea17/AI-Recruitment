import os
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.web.auth import get_current_user_required
from app.services.interview_service import interview_service
from app.services.vacancy_service import vacancy_service
from app.utils.formatters import (
    get_status_badge_class,
    get_candidate_initials,
    calculate_preliminary_fit,
    format_date_only,
    format_datetime
)

router = APIRouter(prefix="/interviews")
templates = Jinja2Templates(directory=os.path.join(settings.BASE_DIR, "app/web/templates"))
templates.env.globals["get_badge_class"] = get_status_badge_class
templates.env.globals["get_initials"] = get_candidate_initials
templates.env.globals["get_fit"] = calculate_preliminary_fit
templates.env.globals["format_date"] = format_date_only
templates.env.globals["format_datetime"] = format_datetime

ALL_INTERVIEW_STATUSES = [
    "Scheduled", "Confirmed", "Reschedule Requested",
    "Completed", "Cancelled", "Declined"
]

@router.get("", response_class=HTMLResponse)
async def list_interviews(
    request: Request,
    q: Optional[str] = None,
    vacancy_id: Optional[int] = None,
    status: Optional[str] = None,
    interview_type: Optional[str] = None,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    date_error = None
    if from_date and to_date:
        try:
            d_from = datetime.strptime(from_date.strip(), "%Y-%m-%d").date()
            d_to = datetime.strptime(to_date.strip(), "%Y-%m-%d").date()
            if d_from > d_to:
                date_error = "From Date cannot be later than To Date."
        except Exception as e:
            date_error = f"Invalid date format: {str(e)}"

    interviews = await interview_service.get_all_interviews(
        session=session,
        search=q,
        vacancy_id=vacancy_id,
        status=status,
        interview_type=interview_type,
        from_date=from_date if not date_error else None,
        to_date=to_date if not date_error else None
    )

    vacancies = await vacancy_service.get_all_vacancies(session)

    return templates.TemplateResponse(
        request=request,
        name="interviews.html",
        context={
            "request": request,
            "current_user": current_user,
            "interviews": interviews,
            "vacancies": vacancies,
            "all_statuses": ALL_INTERVIEW_STATUSES,
            "search_query": q or "",
            "current_vacancy": vacancy_id,
            "current_status": status or "",
            "current_type": interview_type or "",
            "from_date": from_date or "",
            "to_date": to_date or "",
            "date_error": date_error,
            "active_nav": "interviews"
        }
    )
