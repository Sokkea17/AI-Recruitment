import logging
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

from app.config import settings
from app.bot.handlers.start import start_command, help_command, cancel_command
from app.bot.handlers.vacancies import jobs_command, vacancy_detail_callback
from app.bot.handlers.my_applications import my_applications_command
from app.bot.handlers.apply import get_apply_conversation_handler
from app.bot.handlers.interview_response import candidate_interview_response_callback

logger = logging.getLogger(__name__)

def create_bot_application(token: str = None):
    bot_token = token or settings.TELEGRAM_BOT_TOKEN
    if not bot_token:
        logger.warning("TELEGRAM_BOT_TOKEN not provided. Bot cannot connect to Telegram live.")
        return None

    app = ApplicationBuilder().token(bot_token).build()

    # 1. Register ConversationHandler for CV apply flow (higher priority)
    app.add_handler(get_apply_conversation_handler())

    # 2. Register command handlers
    app.add_handler(CommandHandler("start", start_command))
    app.add_handler(CommandHandler("jobs", jobs_command))
    app.add_handler(CommandHandler("myapplications", my_applications_command))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cancel", cancel_command))

    # 3. Register callback handlers for browsing
    app.add_handler(CallbackQueryHandler(jobs_command, pattern=r"^browse_vacancies$"))
    app.add_handler(CallbackQueryHandler(vacancy_detail_callback, pattern=r"^vac_\d+$"))
    app.add_handler(CallbackQueryHandler(cancel_command, pattern=r"^cancel_flow$"))

    # 4. Register callback handler for candidate interview responses
    app.add_handler(CallbackQueryHandler(candidate_interview_response_callback, pattern=r"^intv_(confirm|resched|decline)_\d+$"))

    return app
