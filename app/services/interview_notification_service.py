import logging
from typing import Optional, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode

from app.config import settings
from app.models.interview import Interview
from app.models.setting import SystemSetting
from app.models.audit_log import AuditLog

logger = logging.getLogger(__name__)

def get_candidate_interview_keyboard(interview_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✅ Confirm Interview", callback_data=f"intv_confirm_{interview_id}")],
        [
            InlineKeyboardButton("🔄 Request Reschedule", callback_data=f"intv_resched_{interview_id}"),
            InlineKeyboardButton("❌ I Cannot Attend", callback_data=f"intv_decline_{interview_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

class InterviewNotificationService:
    @staticmethod
    async def get_hr_chat_id(session: AsyncSession) -> str:
        stmt = select(SystemSetting).where(SystemSetting.key == "hr_telegram_chat_id")
        res = await session.execute(stmt)
        record = res.scalar_one_or_none()
        return record.value if record and record.value else settings.HR_TELEGRAM_CHAT_ID

    @staticmethod
    async def send_interview_invitation(
        interview: Interview,
        session: AsyncSession,
        bot: Optional[Bot] = None
    ) -> Tuple[bool, Optional[str]]:
        candidate = interview.candidate
        vacancy = interview.vacancy
        if not candidate or not candidate.telegram_user_id:
            err = "Candidate has no linked Telegram account (missing chat ID)."
            logger.warning(err)
            return False, err

        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            err = "TELEGRAM_BOT_TOKEN not configured."
            logger.warning(err)
            return False, err

        if not bot:
            bot = Bot(token=token)

        try:
            notes_section = f"\n📝 <b>Notes:</b> {interview.notes}" if interview.notes else ""
            interviewer_str = interview.interviewer_name or "HR Department"
            meeting_link_str = f"\n🔗 <b>Meeting Link:</b> {interview.meeting_link}" if interview.meeting_link else ""

            msg_text = (
                f"🔔 <b>INTERVIEW INVITATION</b>\n\n"
                f"Dear <b>{candidate.full_name}</b>,\n\n"
                f"Thank you for applying for the <b>{vacancy.title}</b> position.\n"
                f"You have been shortlisted and we are pleased to invite you to an interview.\n\n"
                f"📌 <b>Position:</b> {vacancy.title}\n"
                f"📅 <b>Date:</b> {interview.interview_date}\n"
                f"⏰ <b>Time:</b> {interview.interview_time} (Cambodia Time)\n"
                f"📍 <b>Location:</b> {interview.interview_location}{meeting_link_str}\n"
                f"👤 <b>Interviewer:</b> {interviewer_str}"
                f"{notes_section}\n\n"
                f"Please confirm your availability by choosing one of the options below.\n\n"
                f"Thank you,\n"
                f"<b>MekongNet</b>\n"
                f"HR Department"
            )

            sent_msg = await bot.send_message(
                chat_id=candidate.telegram_user_id,
                text=msg_text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_candidate_interview_keyboard(interview.id)
            )

            interview.telegram_message_id = sent_msg.message_id
            logger.info(f"Interview invitation sent to candidate {candidate.full_name} (chat {candidate.telegram_user_id})")
            return True, None

        except Exception as e:
            err = f"Telegram error: {str(e)}"
            logger.error(f"Failed to send interview invitation to candidate: {e}", exc_info=True)
            return False, err

    @staticmethod
    async def send_interview_update(
        interview: Interview,
        session: AsyncSession,
        bot: Optional[Bot] = None
    ) -> Tuple[bool, Optional[str]]:
        candidate = interview.candidate
        vacancy = interview.vacancy
        if not candidate or not candidate.telegram_user_id:
            return False, "Candidate has no linked Telegram account."

        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            return False, "TELEGRAM_BOT_TOKEN not configured."

        if not bot:
            bot = Bot(token=token)

        try:
            notes_section = f"\n📝 <b>Notes:</b> {interview.notes}" if interview.notes else ""
            interviewer_str = interview.interviewer_name or "HR Department"
            meeting_link_str = f"\n🔗 <b>Meeting Link:</b> {interview.meeting_link}" if interview.meeting_link else ""

            msg_text = (
                f"🔔 <b>INTERVIEW DETAILS UPDATED</b>\n\n"
                f"Dear <b>{candidate.full_name}</b>,\n\n"
                f"Your interview details for <b>{vacancy.title}</b> have been updated.\n\n"
                f"📌 <b>Position:</b> {vacancy.title}\n"
                f"📅 <b>New Date:</b> {interview.interview_date}\n"
                f"⏰ <b>New Time:</b> {interview.interview_time} (Cambodia Time)\n"
                f"📍 <b>Location:</b> {interview.interview_location}{meeting_link_str}\n"
                f"👤 <b>Interviewer:</b> {interviewer_str}"
                f"{notes_section}\n\n"
                f"Please confirm your availability with the updated schedule below.\n\n"
                f"Thank you,\n"
                f"<b>MekongNet</b>\n"
                f"HR Department"
            )

            sent_msg = await bot.send_message(
                chat_id=candidate.telegram_user_id,
                text=msg_text,
                parse_mode=ParseMode.HTML,
                reply_markup=get_candidate_interview_keyboard(interview.id)
            )

            interview.telegram_message_id = sent_msg.message_id
            return True, None

        except Exception as e:
            err = f"Telegram error: {str(e)}"
            logger.error(f"Failed to send interview update: {e}", exc_info=True)
            return False, err

    @staticmethod
    async def send_interview_cancellation(
        interview: Interview,
        session: AsyncSession,
        bot: Optional[Bot] = None
    ) -> Tuple[bool, Optional[str]]:
        candidate = interview.candidate
        vacancy = interview.vacancy
        if not candidate or not candidate.telegram_user_id:
            return False, "Candidate has no linked Telegram account."

        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            return False, "TELEGRAM_BOT_TOKEN not configured."

        if not bot:
            bot = Bot(token=token)

        try:
            msg_text = (
                f"🔔 <b>INTERVIEW CANCELLATION NOTICE</b>\n\n"
                f"Dear <b>{candidate.full_name}</b>,\n\n"
                f"We regret to inform you that the interview for <b>{vacancy.title}</b> "
                f"scheduled for <b>{interview.interview_date} at {interview.interview_time}</b> has been cancelled.\n\n"
                f"Our HR team will contact you if a new interview schedule is arranged.\n\n"
                f"Thank you for your understanding,\n"
                f"<b>MekongNet</b>\n"
                f"HR Department"
            )

            await bot.send_message(
                chat_id=candidate.telegram_user_id,
                text=msg_text,
                parse_mode=ParseMode.HTML
            )
            return True, None

        except Exception as e:
            err = f"Telegram error: {str(e)}"
            logger.error(f"Failed to send interview cancellation: {e}", exc_info=True)
            return False, err

    @staticmethod
    async def send_hr_candidate_response_alert(
        interview: Interview,
        response_type: str,  # 'confirm', 'resched', 'decline'
        session: AsyncSession,
        bot: Optional[Bot] = None
    ) -> bool:
        hr_chat_id = await InterviewNotificationService.get_hr_chat_id(session)
        if not hr_chat_id:
            logger.warning("HR Chat ID not configured. Skipping HR alert.")
            return False

        token = settings.TELEGRAM_BOT_TOKEN
        if not token:
            return False

        if not bot:
            bot = Bot(token=token)

        candidate = interview.candidate
        vacancy = interview.vacancy
        app = interview.application

        if response_type == "confirm":
            response_label = "✅ Confirmed"
        elif response_type == "resched":
            response_label = "⚠️ Reschedule Requested"
        else:
            response_label = "❌ Declined"

        msg_text = (
            f"🔔 <b>INTERVIEW RESPONSE</b>\n\n"
            f"👤 <b>Candidate:</b> {candidate.full_name if candidate else 'Unknown'}\n"
            f"📌 <b>Position:</b> {vacancy.title if vacancy else 'Position'}\n"
            f"📅 <b>Interview:</b> {interview.interview_date}, {interview.interview_time} (Cambodia Time)\n"
            f"📍 <b>Location:</b> {interview.interview_location}\n\n"
            f"<b>Response:</b> {response_label}\n"
            f"🆔 <b>Application ID:</b> {app.application_code if app else 'N/A'}"
        )

        try:
            await bot.send_message(
                chat_id=hr_chat_id,
                text=msg_text,
                parse_mode=ParseMode.HTML
            )
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch HR response alert: {e}", exc_info=True)
            return False

interview_notification_service = InterviewNotificationService()
