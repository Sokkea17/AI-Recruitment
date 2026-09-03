import re
import logging
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database.session import async_session_factory
from app.models.interview import Interview
from app.models.audit_log import AuditLog
from app.services.interview_notification_service import interview_notification_service

logger = logging.getLogger(__name__)

async def candidate_interview_response_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data or ""
    match = re.match(r"^intv_(confirm|resched|decline)_(\d+)$", data)
    if not match:
        return

    action = match.group(1)
    interview_id = int(match.group(2))

    async with async_session_factory() as session:
        stmt = (
            select(Interview)
            .where(Interview.id == interview_id)
            .options(
                selectinload(Interview.application),
                selectinload(Interview.candidate),
                selectinload(Interview.vacancy)
            )
        )
        res = await session.execute(stmt)
        interview = res.scalar_one_or_none()

        if not interview:
            await query.edit_message_text("⚠️ Interview record not found.")
            return

        if interview.status == "Cancelled":
            await query.edit_message_text(
                "⚠️ This interview invitation has been cancelled by HR. "
                "If you have questions, please reach out to our recruitment team."
            )
            return

        candidate = interview.candidate
        vacancy = interview.vacancy
        application = interview.application

        if action == "confirm":
            interview.status = "Confirmed"
            if application:
                application.status = "Interview Confirmed"
                application.updated_at = datetime.utcnow()
            
            response_text = (
                f"✅ <b>Thank you! Your interview is confirmed.</b>\n\n"
                f"📌 <b>Position:</b> {vacancy.title if vacancy else 'Position'}\n"
                f"📅 <b>Date:</b> {interview.interview_date}\n"
                f"⏰ <b>Time:</b> {interview.interview_time} (Cambodia Time)\n"
                f"📍 <b>Location:</b> {interview.interview_location}\n\n"
                f"We look forward to meeting you!\n\n"
                f"<b>MekongNet</b>\nHR Department"
            )
        elif action == "resched":
            interview.status = "Reschedule Requested"
            if application:
                application.status = "Reschedule Requested"
                application.updated_at = datetime.utcnow()
            
            response_text = (
                f"🔄 <b>Reschedule Request Received</b>\n\n"
                f"Thank you for letting us know. Our HR team has been notified of your reschedule request "
                f"and will contact you soon regarding an alternate schedule.\n\n"
                f"<b>MekongNet</b>\nHR Department"
            )
        else:  # decline
            interview.status = "Declined"
            if application:
                application.status = "Interview Declined"
                application.updated_at = datetime.utcnow()
            
            response_text = (
                f"❌ <b>Interview Declined</b>\n\n"
                f"Thank you for informing us that you cannot attend the interview. "
                f"We appreciate your interest in <b>MekongNet</b> and wish you every success in your career journey.\n\n"
                f"<b>MekongNet</b>\nHR Department"
            )

        interview.updated_at = datetime.utcnow()

        audit = AuditLog(
            action=f"INTERVIEW_{action.upper()}",
            target_entity="interview",
            target_id=interview.id,
            details=f"Candidate {candidate.full_name if candidate else 'Unknown'} responded: {interview.status}"
        )
        session.add(audit)
        await session.commit()

        # Edit message to reflect the response and remove inline buttons
        try:
            await query.edit_message_text(response_text, parse_mode=ParseMode.HTML)
        except Exception as e:
            logger.warning(f"Could not edit candidate telegram message: {e}")

        # Send alert to HR Chat
        await interview_notification_service.send_hr_candidate_response_alert(
            interview=interview,
            response_type=action,
            session=session,
            bot=context.bot
        )
