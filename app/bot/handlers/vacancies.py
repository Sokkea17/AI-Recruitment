from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.database.session import async_session_factory
from app.services.vacancy_service import vacancy_service
from app.bot.keyboards import get_vacancies_keyboard, get_vacancy_detail_keyboard

async def jobs_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session_factory() as session:
        vacancies = await vacancy_service.get_published_vacancies(session)

    text = "💼 <b>Available Job Vacancies</b>\n\nPlease select a position to view details and apply:"
    if not vacancies:
        text = "💼 <b>Available Job Vacancies</b>\n\n<i>No positions are open at this time. Please check back later!</i>"

    keyboard = get_vacancies_keyboard(vacancies)

    if update.message:
        await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

async def vacancy_detail_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    vacancy_id = int(data.replace("vac_", ""))

    async with async_session_factory() as session:
        vacancy = await vacancy_service.get_vacancy_by_id(vacancy_id, session)

    if not vacancy or vacancy.status != "Published":
        await query.edit_message_text("⚠️ This position is no longer open for applications. Type /jobs to browse available roles.")
        return

    # Prepare detailed message
    lines = [
        f"📌 <b>{vacancy.title}</b>",
        f"🏢 <b>Department:</b> {vacancy.department or 'General'}",
    ]
    if vacancy.location:
        lines.append(f"📍 <b>Location:</b> {vacancy.location}")
    if vacancy.employment_type:
        lines.append(f"⏱ <b>Employment Type:</b> {vacancy.employment_type}")
    if vacancy.salary_range:
        lines.append(f"💰 <b>Salary:</b> {vacancy.salary_range}")

    lines.append("")
    if vacancy.short_description:
        lines.append(f"<b>Summary:</b>\n{vacancy.short_description}\n")

    if vacancy.requirements:
        lines.append(f"<b>Key Requirements:</b>\n{vacancy.requirements}\n")
    elif vacancy.skills:
        lines.append(f"<b>Required Skills:</b>\n{vacancy.skills}\n")

    lines.append("<i>Click below to apply with your CV.</i>")
    message_text = "\n".join(lines)

    keyboard = get_vacancy_detail_keyboard(vacancy.id)
    await query.edit_message_text(message_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
