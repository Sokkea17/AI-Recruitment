import os
from typing import Optional
from fastapi import APIRouter, Request, Depends, Form, HTTPException, status
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot

from app.config import settings
from app.database.session import get_db
from app.models.user import User
from app.models.setting import SystemSetting
from app.models.audit_log import AuditLog
from app.web.auth import get_current_user_required

router = APIRouter(prefix="/settings")
templates = Jinja2Templates(directory=os.path.join(settings.BASE_DIR, "app/web/templates"))

@router.get("", response_class=HTMLResponse)
async def view_settings(
    request: Request,
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(SystemSetting)
    result = await session.execute(stmt)
    settings_records = result.scalars().all()
    settings_dict = {s.key: s.value for s in settings_records}

    return templates.TemplateResponse(request=request, name="settings.html", context={
            "request": request,
            "current_user": current_user,
            "settings_dict": settings_dict,
            "active_nav": "settings"
        })

@router.post("")
async def save_settings(
    request: Request,
    hr_telegram_chat_id: str = Form(""),
    notifications_enabled: str = Form("true"),
    include_ai_summary: str = Form("true"),
    notify_on_duplicates: str = Form("true"),
    duplicate_cv_policy: str = Form("allow_update"),
    ai_provider: str = Form("none"),
    ai_api_key: Optional[str] = Form(None),
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    updates = {
        "hr_telegram_chat_id": hr_telegram_chat_id.strip(),
        "notifications_enabled": notifications_enabled,
        "include_ai_summary": include_ai_summary,
        "notify_on_duplicates": notify_on_duplicates,
        "duplicate_cv_policy": duplicate_cv_policy,
        "ai_provider": ai_provider
    }
    if ai_api_key and ai_api_key.strip():
        updates["ai_api_key"] = ai_api_key.strip()

    for key, val in updates.items():
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        result = await session.execute(stmt)
        setting_rec = result.scalar_one_or_none()
        if setting_rec:
            setting_rec.value = val
        else:
            session.add(SystemSetting(key=key, value=val))

    audit = AuditLog(
        user_id=current_user.id,
        action="SETTINGS_UPDATED",
        target_entity="system_settings",
        details="HR updated notification and system settings."
    )
    session.add(audit)
    await session.commit()

    # Re-fetch settings
    stmt = select(SystemSetting)
    result = await session.execute(stmt)
    settings_records = result.scalars().all()
    settings_dict = {s.key: s.value for s in settings_records}

    return templates.TemplateResponse(request=request, name="settings.html", context={
            "request": request,
            "current_user": current_user,
            "settings_dict": settings_dict,
            "message": "Settings updated successfully!",
            "active_nav": "settings"
        })

@router.post("/test-telegram")
async def test_telegram_ping(
    current_user: User = Depends(get_current_user_required),
    session: AsyncSession = Depends(get_db)
):
    stmt = select(SystemSetting).where(SystemSetting.key == "hr_telegram_chat_id")
    result = await session.execute(stmt)
    rec = result.scalar_one_or_none()
    chat_id = rec.value if rec else settings.HR_TELEGRAM_CHAT_ID

    if not chat_id:
        raise HTTPException(status_code=400, detail="HR Telegram Chat ID is not configured.")

    if not settings.TELEGRAM_BOT_TOKEN:
        raise HTTPException(status_code=400, detail="TELEGRAM_BOT_TOKEN is not configured in .env.")

    try:
        bot = Bot(token=settings.TELEGRAM_BOT_TOKEN)
        test_msg = (
            "🔔 <b>RECRUITMENT BOT TEST PING</b>\n\n"
            "This is a test notification confirming your HR Telegram Chat ID is configured properly!\n\n"
            "• Bot: Online\n"
            "• Channel: Verified\n"
            "• Status: Ready for candidate applications"
        )
        await bot.send_message(chat_id=chat_id, text=test_msg, parse_mode="HTML")
        return JSONResponse({"success": True, "message": f"Test message sent to chat {chat_id}"})
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to send Telegram message: {str(e)}")
