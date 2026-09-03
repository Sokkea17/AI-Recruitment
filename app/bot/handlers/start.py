from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from app.database.session import async_session_factory
from app.services.vacancy_service import vacancy_service
from app.bot.keyboards import get_vacancies_keyboard

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    async with async_session_factory() as session:
        vacancies = await vacancy_service.get_published_vacancies(session)

    welcome_text = (
        "👋 <b>Welcome to our Recruitment Assistant.</b>\n\n"
        "Please select the position you would like to apply for below:"
    )

    if not vacancies:
        welcome_text += "\n\n<i>There are currently no active job vacancies open for applications. Please check back later!</i>"

    keyboard = get_vacancies_keyboard(vacancies)

    if update.message:
        await update.message.reply_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(welcome_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "🤖 <b>Recruitment Assistant Guide</b>\n\n"
        "Here are the available commands:\n"
        "• /jobs - View all active job vacancies\n"
        "• /myapplications - Check the status of your submitted applications\n"
        "• /help - Display this guide\n"
        "• /cancel - Cancel an active application process\n\n"
        "💡 <i>Tip: You can submit your CV as a PDF or Word (.docx) document when applying for any vacancy.</i>"
    )
    if update.message:
        await update.message.reply_text(help_text, parse_mode=ParseMode.HTML)

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    text = "❌ Application process cancelled. Type /jobs to browse available positions."
    if update.message:
        await update.message.reply_text(text)
    elif update.callback_query:
        await update.callback_query.answer()
        await update.callback_query.edit_message_text(text)
