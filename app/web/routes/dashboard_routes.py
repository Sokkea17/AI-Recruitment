import os
from datetime import datetime, date
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.session import get_db
from app.models.application import Application
from app.models.vacancy import Vacancy
from app.models.user import User
from app.web.auth import get_current_user_required
from app.utils.formatters import get_status_badge_class

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(settings.BASE_DIR, "app/web/templates"))
templates.env.globals["get_badge_class"] = get_status_badge_class

@router.get("/", response_class=HTMLResponse)
async def dashboard_overview(
    request: Request,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    # 1. Total Applications
    total_apps_res = await session.execute(select(func.count(Application.id)))
    total_applications = total_apps_res.scalar() or 0

    # 2. New Applications
    new_apps_res = await session.execute(
        select(func.count(Application.id)).where(Application.status == "New")
    )
    new_applications = new_apps_res.scalar() or 0

    # 3. Applications Received Today
    today_start = datetime.combine(date.today(), datetime.min.time())
    today_apps_res = await session.execute(
        select(func.count(Application.id)).where(Application.submitted_at >= today_start)
    )
    applications_today = today_apps_res.scalar() or 0

    # 4. Published Vacancies
    pub_vac_res = await session.execute(
        select(func.count(Vacancy.id)).where(Vacancy.status == "Published")
    )
    published_vacancies = pub_vac_res.scalar() or 0

    # 5. Breakdown by Status
    all_statuses = ["New", "Under Review", "Shortlisted", "Interview", "Selected", "Rejected", "Withdrawn"]
    by_status = {}
    for st in all_statuses:
        st_count_res = await session.execute(
            select(func.count(Application.id)).where(Application.status == st)
        )
        by_status[st] = st_count_res.scalar() or 0

    # 6. Breakdown by Position
    pos_res = await session.execute(
        select(Vacancy.title, func.count(Application.id))
        .join(Application, Application.vacancy_id == Vacancy.id, isouter=True)
        .group_by(Vacancy.title)
        .order_by(desc(func.count(Application.id)))
        .limit(6)
    )
    by_position = {row[0]: row[1] for row in pos_res.all()}

    # 7. Recent Applications
    recent_res = await session.execute(
        select(Application)
        .options(selectinload(Application.candidate), selectinload(Application.vacancy))
        .order_by(desc(Application.submitted_at))
        .limit(8)
    )
    recent_applications = list(recent_res.scalars().all())

    metrics = {
        "total_applications": total_applications,
        "new_applications": new_applications,
        "applications_today": applications_today,
        "published_vacancies": published_vacancies,
        "by_status": by_status,
        "by_position": by_position
    }

    return templates.TemplateResponse(request=request, name="dashboard.html", context={
            "request": request,
            "current_user": current_user,
            "metrics": metrics,
            "recent_applications": recent_applications,
            "active_nav": "dashboard"
        })
