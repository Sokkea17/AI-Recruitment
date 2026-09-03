from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.database.session import async_session_factory
from app.services.application_service import application_service
from app.utils.formatters import format_datetime

STATUS_EMOJIS = {
    "New": "🆕",
    "Under Review": "🔍",
    "Shortlisted": "⭐",
    "Interview": "📅",
    "Selected": "🎉",
    "Rejected": "❌",
    "Withdrawn": "⚪"
}

async def my_applications_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user

    async with async_session_factory() as session:
        applications = await application_service.get_candidate_applications(session, user.id)

    if not applications:
        text = (
            "📋 <b>Your Applications</b>\n\n"
            "You haven't submitted any applications yet.\n\n"
            "Type /jobs to view available job positions and apply!"
        )
        await update.message.reply_text(text, parse_mode=ParseMode.HTML)
        return

    lines = [
        "📋 <b>Your Submitted Applications</b>\n",
        f"Found {len(applications)} application(s) linked to your Telegram account:\n"
    ]

    for app in applications:
        emoji = STATUS_EMOJIS.get(app.status, "📌")
        vac_title = app.vacancy.title if app.vacancy else "Unknown Role"
        date_str = format_datetime(app.submitted_at)

        lines.append(f"━━━━━━━━━━━━━━━━━━━━")
        lines.append(f"📌 <b>{vac_title}</b>")
        lines.append(f"🆔 <b>Ref:</b> <code>{app.application_code}</code>")
        lines.append(f"🕒 <b>Submitted:</b> {date_str}")
        lines.append(f"{emoji} <b>Status:</b> <b>{app.status}</b>")
        if app.duplicate_submission_count > 0:
            lines.append(f"🔄 <i>CV updated {app.duplicate_submission_count} time(s)</i>")

    lines.append("━━━━━━━━━━━━━━━━━━━━")
    lines.append("\n<i>Our HR team will reach out directly if your profile matches the role.</i>")

    await update.message.reply_text("\n".join(lines), parse_mode=ParseMode.HTML)
