import os
from datetime import datetime, date, timedelta
from typing import Optional
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select, func, desc, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.session import get_db
from app.models.application import Application
from app.models.vacancy import Vacancy
from app.models.interview import Interview
from app.models.user import User
from app.web.auth import get_current_user_required
from app.services.interview_service import interview_service
from app.utils.formatters import (
    get_status_badge_class,
    get_greeting,
    get_candidate_initials,
    calculate_preliminary_fit,
    format_datetime,
    format_date_only,
    get_current_cambodia_time,
    to_cambodia_time,
    parse_date_range_to_utc
)

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(settings.BASE_DIR, "app/web/templates"))
templates.env.globals["get_badge_class"] = get_status_badge_class
templates.env.globals["get_initials"] = get_candidate_initials
templates.env.globals["get_fit"] = calculate_preliminary_fit
templates.env.globals["format_date"] = format_date_only
templates.env.globals["format_datetime"] = format_datetime

@router.get("/", response_class=HTMLResponse)
async def dashboard_overview(
    request: Request,
    from_date: Optional[str] = None,
    to_date: Optional[str] = None,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    from_utc, to_utc, date_error = parse_date_range_to_utc(from_date, to_date)

    # Base application query with optional date range filter
    app_base_stmt = select(Application)
    if from_utc:
        app_base_stmt = app_base_stmt.where(Application.submitted_at >= from_utc)
    if to_utc:
        app_base_stmt = app_base_stmt.where(Application.submitted_at <= to_utc)

    # 1. Total Applications in selected range
    total_apps_stmt = select(func.count(Application.id))
    if from_utc:
        total_apps_stmt = total_apps_stmt.where(Application.submitted_at >= from_utc)
    if to_utc:
        total_apps_stmt = total_apps_stmt.where(Application.submitted_at <= to_utc)
    total_apps_res = await session.execute(total_apps_stmt)
    total_applications = total_apps_res.scalar() or 0

    # 2. New Applications in selected range
    new_apps_stmt = select(func.count(Application.id)).where(Application.status == "New")
    if from_utc:
        new_apps_stmt = new_apps_stmt.where(Application.submitted_at >= from_utc)
    if to_utc:
        new_apps_stmt = new_apps_stmt.where(Application.submitted_at <= to_utc)
    new_apps_res = await session.execute(new_apps_stmt)
    new_applications = new_apps_res.scalar() or 0

    # 3. Shortlisted Candidates in selected range
    short_apps_stmt = select(func.count(Application.id)).where(Application.status == "Shortlisted")
    if from_utc:
        short_apps_stmt = short_apps_stmt.where(Application.submitted_at >= from_utc)
    if to_utc:
        short_apps_stmt = short_apps_stmt.where(Application.submitted_at <= to_utc)
    short_apps_res = await session.execute(short_apps_stmt)
    shortlisted_candidates = short_apps_res.scalar() or 0

    # 4. Open (Published) Vacancies
    pub_vac_res = await session.execute(
        select(func.count(Vacancy.id)).where(Vacancy.status == "Published")
    )
    open_vacancies = pub_vac_res.scalar() or 0

    # 5. Scheduled Interviews count
    intv_count_stmt = select(func.count(Interview.id)).where(
        Interview.status.in_(["Scheduled", "Confirmed", "Reschedule Requested"])
    )
    if from_date and from_date.strip():
        intv_count_stmt = intv_count_stmt.where(Interview.interview_date >= from_date.strip())
    if to_date and to_date.strip():
        intv_count_stmt = intv_count_stmt.where(Interview.interview_date <= to_date.strip())
    intv_count_res = await session.execute(intv_count_stmt)
    scheduled_interviews = intv_count_res.scalar() or 0

    # 6. Fetch all applications matching date filter for fit & pipeline distribution
    filtered_apps_stmt = (
        app_base_stmt
        .options(
            selectinload(Application.candidate),
            selectinload(Application.vacancy),
            selectinload(Application.interviews)
        )
        .order_by(desc(Application.submitted_at))
    )
    all_apps_res = await session.execute(filtered_apps_stmt)
    filtered_applications = list(all_apps_res.scalars().all())

    # Calculate Strong Fit candidates count (score >= 75%)
    strong_fit_count = 0
    for app in filtered_applications:
        fit = calculate_preliminary_fit(app)
        if fit["score"] >= 75:
            strong_fit_count += 1

    # 7. Application Status Distribution Pipeline
    recruitment_stages = [
        "New", "Under Review", "Shortlisted",
        "Interview Scheduled", "Interview Confirmed", "Interview Completed",
        "Selected", "Rejected"
    ]
    status_counts = {}
    for st in recruitment_stages:
        count = sum(1 for a in filtered_applications if a.status == st)
        status_counts[st] = count

    # 8. Applications by Position (Top ranked in filtered period)
    pos_counts = {}
    for a in filtered_applications:
        pos_title = a.vacancy.title if a.vacancy else "General Position"
        pos_counts[pos_title] = pos_counts.get(pos_title, 0) + 1
    # Sort descending by count, limit top 5
    by_position = dict(sorted(pos_counts.items(), key=lambda x: x[1], reverse=True)[:5])

    # 9. Timeline in Cambodia Local Time (Asia/Phnom_Penh)
    cambodia_now = get_current_cambodia_time()
    today_cambodia = cambodia_now.date()

    timeline_7d = []
    for i in range(6, -1, -1):
        day_date = today_cambodia - timedelta(days=i)
        day_label = day_date.strftime("%a")
        full_date_str = day_date.strftime("%d %b")
        count = sum(
            1 for a in filtered_applications
            if a.submitted_at and to_cambodia_time(a.submitted_at).date() == day_date
        )
        timeline_7d.append({
            "day": day_label,
            "date": full_date_str,
            "count": count
        })

    timeline_30d = []
    for i in range(29, -1, -1):
        day_date = today_cambodia - timedelta(days=i)
        count = sum(
            1 for a in filtered_applications
            if a.submitted_at and to_cambodia_time(a.submitted_at).date() == day_date
        )
        timeline_30d.append({
            "day": day_date.strftime("%d %b"),
            "date": day_date.strftime("%Y-%m-%d"),
            "count": count
        })

    # 10. Upcoming Interviews (Section 14.E)
    upcoming_interviews = await interview_service.get_upcoming_interviews(session, limit=5)

    recent_applications = filtered_applications[:6]

    kpis = {
        "total_applications": total_applications,
        "new_applications": new_applications,
        "shortlisted_candidates": shortlisted_candidates,
        "open_vacancies": open_vacancies,
        "scheduled_interviews": scheduled_interviews,
        "strong_fit_count": strong_fit_count,
        "status_distribution": status_counts,
        "by_position": by_position,
        "timeline_7d": timeline_7d,
        "timeline_30d": timeline_30d
    }

    greeting = get_greeting(cambodia_now)
    current_date_str = cambodia_now.strftime("%A, %d %B %Y")

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
            "upcoming_interviews": upcoming_interviews,
            "from_date": from_date or "",
            "to_date": to_date or "",
            "date_error": date_error,
            "active_nav": "dashboard"
        }
    )
