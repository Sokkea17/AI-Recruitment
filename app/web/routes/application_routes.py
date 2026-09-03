import os
import io
import csv
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, FileResponse, Response, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.models.application import Application
from app.models.audit_log import AuditLog
from app.web.auth import get_current_user_required
from app.services.application_service import application_service
from app.services.vacancy_service import vacancy_service
from app.services.ai_service import ai_service
from app.utils.formatters import (
    get_status_badge_class,
    get_candidate_initials,
    calculate_preliminary_fit,
    parse_structured_ai_summary,
    format_date_only,
    format_datetime
)

router = APIRouter(prefix="/applications")
templates = Jinja2Templates(directory=os.path.join(settings.BASE_DIR, "app/web/templates"))
templates.env.globals["get_badge_class"] = get_status_badge_class
templates.env.globals["get_initials"] = get_candidate_initials
templates.env.globals["get_fit"] = calculate_preliminary_fit
templates.env.globals["format_date"] = format_date_only
templates.env.globals["format_datetime"] = format_datetime

@router.get("", response_class=HTMLResponse)
async def list_applications(
    request: Request,
    status: Optional[str] = None,
    vacancy_id: Optional[int] = None,
    q: Optional[str] = None,
    fit: Optional[str] = None,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    applications = await application_service.get_applications(
        session=session,
        status=status,
        vacancy_id=vacancy_id,
        search=q
    )
    
    # Filter by fit tier if requested
    if fit and fit != "all":
        filtered = []
        for a in applications:
            f_data = calculate_preliminary_fit(a)
            score = f_data["score"]
            if fit == "strong" and score >= 80:
                filtered.append(a)
            elif fit == "moderate" and 65 <= score < 80:
                filtered.append(a)
            elif fit == "review" and score < 65:
                filtered.append(a)
        applications = filtered

    vacancies = await vacancy_service.get_all_vacancies(session)

    return templates.TemplateResponse(
        request=request,
        name="applications.html",
        context={
            "request": request,
            "current_user": current_user,
            "applications": applications,
            "vacancies": vacancies,
            "current_status": status,
            "current_vacancy": vacancy_id,
            "current_fit": fit,
            "search_query": q,
            "active_nav": "applications"
        }
    )

@router.get("/export/csv")
async def export_applications_csv(
    status: Optional[str] = None,
    vacancy_id: Optional[int] = None,
    q: Optional[str] = None,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    applications = await application_service.get_applications(
        session=session,
        status=status,
        vacancy_id=vacancy_id,
        search=q
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Application ID", "Candidate Name", "Phone", "Email", "Telegram Username",
        "Position", "Department", "Submission Date", "AI Fit Score", "Status", "CV Filename", "HR Notes"
    ])

    for app in applications:
        cand = app.candidate
        vac = app.vacancy
        fit = calculate_preliminary_fit(app)
        writer.writerow([
            app.application_code,
            cand.full_name if cand else "",
            cand.phone if cand else "",
            cand.email if cand else "",
            cand.telegram_username if cand else "",
            vac.title if vac else "",
            vac.department if vac else "",
            app.submitted_at.strftime("%Y-%m-%d %H:%M:%S"),
            f"{fit['score']}% ({fit['label']})",
            app.status,
            app.cv_original_filename,
            app.hr_notes or ""
        ])

    csv_data = output.getvalue()
    return Response(
        content=csv_data,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="recruitment_applications.csv"'}
    )

@router.get("/{id}", response_class=HTMLResponse)
async def view_application_detail(
    id: int,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    application = await application_service.get_application_by_id(session, id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")

    # Cross-position application history for this candidate
    other_apps_stmt = (
        select(Application)
        .where(Application.candidate_id == application.candidate_id, Application.id != application.id)
        .options(selectinload(Application.vacancy))
    )
    res = await session.execute(other_apps_stmt)
    other_applications = list(res.scalars().all())

    structured_ai = parse_structured_ai_summary(application)
    fit = calculate_preliminary_fit(application)

    return templates.TemplateResponse(
        request=request,
        name="application_detail.html",
        context={
            "request": request,
            "current_user": current_user,
            "application": application,
            "other_applications": other_applications,
            "structured_ai": structured_ai,
            "fit": fit,
            "active_nav": "applications"
        }
    )

@router.post("/{id}/regenerate-ai")
async def regenerate_ai_summary(
    id: int,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    application = await application_service.get_application_by_id(session, id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")

    vacancy = application.vacancy
    cv_text = application.extracted_cv_text or ""

    # Re-run AI analysis
    analysis = await ai_service.analyze_application(
        cv_text=cv_text,
        vacancy_title=vacancy.title if vacancy else "Position",
        vacancy_requirements=vacancy.requirements if vacancy else None,
        vacancy_skills=vacancy.skills if vacancy else None
    )

    application.ai_summary = analysis["ai_summary"]
    application.ai_matching_analysis = analysis["ai_matching_analysis"]
    application.updated_at = datetime.utcnow()

    # Log audit
    audit = AuditLog(
        user_id=current_user.id,
        action="AI_SUMMARY_REGENERATED",
        target_entity="application",
        target_id=application.id,
        details=f"Regenerated AI Summary for application {application.application_code}"
    )
    session.add(audit)
    await session.commit()
    await session.refresh(application)

    structured = parse_structured_ai_summary(application)

    if request.headers.get("accept", "").startswith("application/json") or request.headers.get("x-requested-with") == "XMLHttpRequest":
        return JSONResponse({
            "success": True,
            "message": "AI Summary regenerated successfully.",
            "structured_ai": structured
        })

    return RedirectResponse(url=f"/applications/{id}", status_code=303)

@router.post("/{id}/status")
async def update_application_status_post(
    id: int,
    request: Request,
    status: Optional[str] = Form(None),
    hr_notes: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    # Check if JSON or Form
    if request.headers.get("content-type", "").startswith("application/json"):
        data = await request.json()
        new_status = data.get("status")
        notes = data.get("hr_notes")
    else:
        new_status = status
        notes = hr_notes

    if not new_status:
        raise HTTPException(status_code=400, detail="Status is required.")

    app = await application_service.update_status(
        session=session,
        application_id=id,
        new_status=new_status,
        user_id=current_user.id,
        hr_notes=notes
    )
    if not app:
        raise HTTPException(status_code=404, detail="Application not found.")

    if request.headers.get("content-type", "").startswith("application/json"):
        return JSONResponse({"success": True, "status": app.status})

    return RedirectResponse(url=f"/applications/{id}", status_code=303)

@router.get("/{id}/cv")
async def download_candidate_cv(
    id: int,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    application = await application_service.get_application_by_id(session, id)
    if not application:
        raise HTTPException(status_code=404, detail="Application not found.")

    cv_path = application.cv_file_path
    if not os.path.exists(cv_path):
        raise HTTPException(status_code=404, detail="CV file not found on disk.")

    return FileResponse(
        path=cv_path,
        media_type=application.cv_mime_type,
        filename=application.cv_original_filename
    )
