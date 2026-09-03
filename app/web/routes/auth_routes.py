from app.utils.formatters import get_status_badge_class, get_candidate_initials, calculate_preliminary_fit, format_date_only, format_datetime
from fastapi import APIRouter, Request, Depends, Form, responses
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import os

from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.utils.security import verify_password, create_session_token

router = APIRouter()
templates = Jinja2Templates(directory=os.path.join(settings.BASE_DIR, "app/web/templates"))
templates.env.globals["get_badge_class"] = get_status_badge_class
templates.env.globals["get_initials"] = get_candidate_initials
templates.env.globals["get_fit"] = calculate_preliminary_fit
templates.env.globals["format_date"] = format_date_only
templates.env.globals["format_datetime"] = format_datetime


@router.get("/login", response_class=HTMLResponse)
async def login_page(request: Request, next: str = "/"):
    return templates.TemplateResponse(request=request, name="login.html", context={"request": request, "next": next})

@router.post("/login")
async def login_submit(
    request: Request,
    username: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(User).where(User.username == username.strip(), User.is_active == True)
    result = await session.execute(stmt)
    user = result.scalar_one_or_none()

    if not user or not verify_password(password, user.hashed_password):
        return templates.TemplateResponse(request=request, name="login.html", context={
                "request": request,
                "error": "Invalid username or password.",
                "username": username,
                "next": next
            },
            status_code=400
        )

    # Create session token
    token = create_session_token(
        {"user_id": user.id, "username": user.username, "role": user.role},
        settings.SECRET_KEY,
        expires_hours=settings.SESSION_EXPIRE_HOURS
    )

    response = RedirectResponse(url=next or "/", status_code=303)
    response.set_cookie(
        key="session_token",
        value=token,
        httponly=True,
        max_age=settings.SESSION_EXPIRE_HOURS * 3600,
        samesite="lax"
    )
    return response

@router.get("/logout")
async def logout():
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie("session_token")
    return response
