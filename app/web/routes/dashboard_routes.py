import os
from datetime import datetime, date, timedelta
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
from app.utils.formatters import (
    get_status_badge_class,
    get_greeting,
    get_candidate_initials,
    calculate_preliminary_fit,
    format_datetime,
    format_date_only
)

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(settings.BASE_DIR, "app/web/templates"))
templates.env.globals["get_badge_class"] = get_status_badge_class
templates.env.globals["get_initials"] = get_candidate_initials
templates.env.globals["get_fit"] = calculate_preliminary_fit
templates.env.globals["format_date"] = format_date_only

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

    # 3. Open (Published) Vacancies
    pub_vac_res = await session.execute(
        select(func.count(Vacancy.id)).where(Vacancy.status == "Published")
    )
    open_vacancies = pub_vac_res.scalar() or 0

    # 4. Fetch all applications for fit calculations and timeline
    all_apps_res = await session.execute(
        select(Application)
        .options(selectinload(Application.candidate), selectinload(Application.vacancy))
        .order_by(desc(Application.submitted_at))
    )
    all_applications = list(all_apps_res.scalars().all())

    # Calculate Strong Fit candidates count (score >= 75%)
    strong_fit_count = 0
    for app in all_applications:
        fit = calculate_preliminary_fit(app)
        if fit["score"] >= 75:
            strong_fit_count += 1

    # 5. Application Status Distribution Pipeline
    all_statuses = ["New", "Under Review", "Shortlisted", "Interview", "Selected", "Rejected"]
    status_counts = {}
    for st in all_statuses:
        count = sum(1 for a in all_applications if a.status == st)
        status_counts[st] = count

    # 6. Applications by Position (Top ranked)
    pos_res = await session.execute(
        select(Vacancy.title, func.count(Application.id))
        .join(Application, Application.vacancy_id == Vacancy.id, isouter=True)
        .group_by(Vacancy.title)
        .order_by(desc(func.count(Application.id)))
        .limit(5)
    )
    by_position = {row[0]: row[1] for row in pos_res.all()}

    # 7. Timeline: Applications Over Time (Last 7 Days)
    today = date.today()
    timeline_7d = []
    for i in range(6, -1, -1):
        day_date = today - timedelta(days=i)
        day_label = day_date.strftime("%a") # e.g. Mon, Tue
        full_date_str = day_date.strftime("%d %b")
        count = sum(
            1 for a in all_applications
            if a.submitted_at and a.submitted_at.date() == day_date
        )
        timeline_7d.append({
            "day": day_label,
            "date": full_date_str,
            "count": count
        })

    # Timeline: Applications Over Time (Last 30 Days)
    timeline_30d = []
    for i in range(29, -1, -1):
        day_date = today - timedelta(days=i)
        count = sum(
            1 for a in all_applications
            if a.submitted_at and a.submitted_at.date() == day_date
        )
        timeline_30d.append({
            "day": day_date.strftime("%d %b"),
            "date": day_date.strftime("%Y-%m-%d"),
            "count": count
        })

    # Recent Applications (Top 6)
    recent_applications = all_applications[:6]

    kpis = {
        "total_applications": total_applications,
        "new_applications": new_applications,
        "open_vacancies": open_vacancies,
        "strong_fit_count": strong_fit_count,
        "status_distribution": status_counts,
        "by_position": by_position,
        "timeline_7d": timeline_7d,
        "timeline_30d": timeline_30d
    }

    now = datetime.now()
    greeting = get_greeting(now)
    current_date_str = now.strftime("%A, %d %B %Y")

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "request": request,
            "current_user": current_user,
            "greeting": greeting,
            "current_date": current_date_str,
            "kpis": kpis,
            "recent_applications": recent_applications,
            "active_nav": "dashboard"
        }
    )
