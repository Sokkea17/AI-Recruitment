import logging
import os
from datetime import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot
from telegram.constants import ParseMode

from app.config import settings
from app.models.setting import SystemSetting
from app.models.audit_log import AuditLog
from app.models.application import Application
from app.models.candidate import Candidate
from app.models.vacancy import Vacancy
from app.utils.formatters import format_datetime

logger = logging.getLogger(__name__)

class NotificationService:
    @staticmethod
    async def get_setting(key: str, session: AsyncSession, default: str = "") -> str:
        stmt = select(SystemSetting).where(SystemSetting.key == key)
        result = await session.execute(stmt)
        record = result.scalar_one_or_none()
        return record.value if record else default

    @staticmethod
    async def send_new_application_alert(
        application: Application,
        candidate: Candidate,
        vacancy: Vacancy,
        session: AsyncSession,
        bot: Optional[Bot] = None
    ) -> bool:
        try:
            # 1. Check if notifications are enabled
            enabled_str = await NotificationService.get_setting("notifications_enabled", session, default="true")
            if enabled_str.lower() != "true":
                logger.info("HR notifications are currently disabled in settings.")
                return False

            # 2. Get target HR Telegram Chat ID
            chat_id = await NotificationService.get_setting("hr_telegram_chat_id", session, default=settings.HR_TELEGRAM_CHAT_ID)
            if not chat_id:
                logger.warning("HR Telegram Chat ID is not configured. Skipping alert.")
                return False

            # 3. If bot instance not passed, initialize one if token is present
            token = settings.TELEGRAM_BOT_TOKEN
            if not bot:
                if not token:
                    logger.warning("Telegram Bot Token not configured. Cannot send HR alert.")
                    return False
                bot = Bot(token=token)

            # 4. Check whether to include AI summary
            include_ai = await NotificationService.get_setting("include_ai_summary", session, default="true")

            # 5. Format notification text matching user specification
            received_str = format_datetime(application.submitted_at)
            
            message_lines = [
                "🔔 <b>NEW RECRUITMENT APPLICATION</b>\n",
                f"📌 <b>Position:</b> {vacancy.title}",
                f"🏢 <b>Department:</b> {vacancy.department or 'General'}",
                f"👤 <b>Candidate:</b> {candidate.full_name}",
                f"📞 <b>Phone:</b> {candidate.phone or 'Not provided'}",
                f"📧 <b>Email:</b> {candidate.email or 'Not provided'}",
                f"🕒 <b>Received:</b> {received_str} (Cambodia Time)",
                f"🆔 <b>Application ID:</b> {application.application_code}\n",
                f"<b>Status:</b> {application.status}"
            ]

            if include_ai.lower() == "true" and application.ai_summary:
                message_lines.append(f"\n💡 <b>AI Summary:</b>\n{application.ai_summary}")

            message_text = "\n".join(message_lines)

            # 6. Send text alert to HR chat
            await bot.send_message(
                chat_id=chat_id,
                text=message_text,
                parse_mode=ParseMode.HTML
            )

            # 7. Also send CV file directly to HR chat for immediate preview
            if application.cv_file_path and os.path.exists(application.cv_file_path):
                with open(application.cv_file_path, "rb") as cv_f:
                    await bot.send_document(
                        chat_id=chat_id,
                        document=cv_f,
                        filename=application.cv_original_filename,
                        caption=f"📄 CV for {candidate.full_name} ({application.application_code}) - {vacancy.title}"
                    )

            # 8. Record audit log
            audit = AuditLog(
                action="HR_NOTIFICATION_SENT",
                target_entity="application",
                target_id=application.id,
                details=f"Notification dispatched to HR Chat ID {chat_id} for {application.application_code}"
            )
            session.add(audit)
            await session.commit()

            logger.info(f"HR alert sent successfully for application {application.application_code}")
            return True

        except Exception as e:
            logger.error(f"Failed to dispatch HR notification: {e}", exc_info=True)
            # Fail gracefully without breaking candidate workflow
            audit = AuditLog(
                action="HR_NOTIFICATION_FAILED",
                target_entity="application",
                target_id=application.id,
                details=f"Error sending HR notification: {str(e)}"
            )
            session.add(audit)
            await session.commit()
            return False

notification_service = NotificationService()
