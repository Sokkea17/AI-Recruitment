import os
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, UploadFile, File, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.web.auth import get_current_user_required
from app.services.vacancy_service import vacancy_service
from app.schemas.vacancy import VacancyCreate, VacancyUpdate
from app.utils.formatters import get_status_badge_class

router = APIRouter(prefix="/vacancies")
templates = Jinja2Templates(directory=os.path.join(settings.BASE_DIR, "app/web/templates"))
templates.env.globals["get_badge_class"] = get_status_badge_class

@router.get("", response_class=HTMLResponse)
async def list_vacancies(
    request: Request,
    status: Optional[str] = None,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    vacancies = await vacancy_service.get_all_vacancies(session, status_filter=status)
    return templates.TemplateResponse(request=request, name="vacancies.html", context={
            "request": request,
            "current_user": current_user,
            "vacancies": vacancies,
            "current_status": status,
            "active_nav": "vacancies"
        })

@router.get("/import-jd", response_class=HTMLResponse)
async def import_jd_page(
    request: Request,
    current_user: User = Depends(get_current_user_required)
):
    return templates.TemplateResponse(request=request, name="jd_import.html", context={
            "request": request,
            "current_user": current_user,
            "active_nav": "jd_import"
        })

@router.post("/upload-jd")
async def upload_jd_file(
    jd_file: UploadFile = File(...),
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    try:
        content = await jd_file.read()
        jd_record, extracted_data = await vacancy_service.process_jd_upload(
            file_bytes=content,
            filename=jd_file.filename,
            session=session
        )
        return JSONResponse({
            "success": True,
            "jd_file_id": jd_record.id,
            "extracted": extracted_data
        })
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )

@router.get("/new", response_class=HTMLResponse)
async def new_vacancy_page(
    request: Request,
    current_user: User = Depends(get_current_user_required)
):
    return templates.TemplateResponse(request=request, name="vacancy_form.html", context={
            "request": request,
            "current_user": current_user,
            "vacancy": None,
            "active_nav": "vacancies"
        })

@router.post("/new")
async def create_vacancy_submit(
    title: str = Form(...),
    department: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    employment_type: Optional[str] = Form("Full-time"),
    salary_range: Optional[str] = Form(None),
    short_description: Optional[str] = Form(None),
    requirements: str = Form(...),
    responsibilities: Optional[str] = Form(None),
    education: Optional[str] = Form(None),
    experience: Optional[str] = Form(None),
    skills: Optional[str] = Form(None),
    instructions: Optional[str] = Form(None),
    full_description: Optional[str] = Form(None),
    status: str = Form("Draft"),
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    data = VacancyCreate(
        title=title.strip(),
        department=department.strip() if department else None,
        location=location.strip() if location else None,
        employment_type=employment_type,
        salary_range=salary_range.strip() if salary_range else None,
        short_description=short_description.strip() if short_description else None,
        requirements=requirements.strip(),
        responsibilities=responsibilities.strip() if responsibilities else None,
        education=education.strip() if education else None,
        experience=experience.strip() if experience else None,
        skills=skills.strip() if skills else None,
        instructions=instructions.strip() if instructions else None,
        full_description=full_description.strip() if full_description else None
    )
    vacancy = await vacancy_service.create_vacancy(data, session)
    if status == "Published":
        await vacancy_service.publish_vacancy(vacancy.id, session)

    return RedirectResponse(url="/vacancies", status_code=303)

@router.get("/{id}/edit", response_class=HTMLResponse)
async def edit_vacancy_page(
    id: int,
    request: Request,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    vacancy = await vacancy_service.get_vacancy_by_id(id, session)
    if not vacancy:
        raise HTTPException(status_code=404, detail="Vacancy not found.")

    return templates.TemplateResponse(request=request, name="vacancy_form.html", context={
            "request": request,
            "current_user": current_user,
            "vacancy": vacancy,
            "active_nav": "vacancies"
        })

@router.post("/{id}/edit")
async def edit_vacancy_submit(
    id: int,
    title: str = Form(...),
    department: Optional[str] = Form(None),
    location: Optional[str] = Form(None),
    employment_type: Optional[str] = Form("Full-time"),
    salary_range: Optional[str] = Form(None),
    short_description: Optional[str] = Form(None),
    requirements: str = Form(...),
    responsibilities: Optional[str] = Form(None),
    education: Optional[str] = Form(None),
    experience: Optional[str] = Form(None),
    skills: Optional[str] = Form(None),
    instructions: Optional[str] = Form(None),
    status: str = Form("Draft"),
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    update_data = VacancyUpdate(
        title=title.strip(),
        department=department.strip() if department else None,
        location=location.strip() if location else None,
        employment_type=employment_type,
        salary_range=salary_range.strip() if salary_range else None,
        short_description=short_description.strip() if short_description else None,
        requirements=requirements.strip(),
        responsibilities=responsibilities.strip() if responsibilities else None,
        education=education.strip() if education else None,
        experience=experience.strip() if experience else None,
        skills=skills.strip() if skills else None,
        instructions=instructions.strip() if instructions else None,
        status=status
    )
    await vacancy_service.update_vacancy(id, update_data, session)
    return RedirectResponse(url="/vacancies", status_code=303)

@router.post("/{id}/publish")
async def publish_vacancy_action(
    id: int,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    await vacancy_service.publish_vacancy(id, session)
    return RedirectResponse(url="/vacancies", status_code=303)

@router.post("/{id}/close")
async def close_vacancy_action(
    id: int,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    await vacancy_service.close_vacancy(id, session)
    return RedirectResponse(url="/vacancies", status_code=303)
