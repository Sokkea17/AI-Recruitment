import os
from datetime import datetime
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    ContextTypes,
    ConversationHandler,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)

from app.config import settings
from app.database.session import async_session_factory
from app.services.vacancy_service import vacancy_service
from app.services.application_service import application_service
from app.services.document_parser import document_parser
from app.schemas.application import ApplicationCreate
from app.bot.keyboards import (
    get_duplicate_confirm_keyboard,
    get_contact_confirm_keyboard,
    get_cancel_keyboard
)
from app.utils.formatters import format_datetime

# Conversation States
AWAITING_CV = 1
CONFIRMING_CONTACT = 2
EDITING_NAME = 3
EDITING_PHONE = 4
EDITING_EMAIL = 5

async def apply_start_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    data = query.data
    vacancy_id = int(data.replace("apply_", ""))
    context.user_data["apply_vacancy_id"] = vacancy_id
    context.user_data["is_update"] = False

    user = update.effective_user

    async with async_session_factory() as session:
        vacancy = await vacancy_service.get_vacancy_by_id(vacancy_id, session)
        if not vacancy or vacancy.status != "Published":
            await query.edit_message_text("⚠️ This position is no longer accepting applications. Type /jobs to see open roles.")
            return ConversationHandler.END

        context.user_data["vacancy_title"] = vacancy.title

        # Check duplicate application
        existing_app = await application_service.check_duplicate(user.id, vacancy_id, session)
        if existing_app:
            dup_text = (
                f"ℹ️ <b>Application Notice</b>\n\n"
                f"You have already applied for <b>{vacancy.title}</b> (Application: {existing_app.application_code}).\n\n"
                f"Would you like to submit an updated CV?"
            )
            keyboard = get_duplicate_confirm_keyboard(vacancy_id)
            await query.edit_message_text(dup_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
            return AWAITING_CV

    prompt_text = (
        f"📝 <b>Applying for {vacancy.title}</b>\n\n"
        f"Please send your CV as a PDF or Word document (.pdf or .docx).\n\n"
        f"<i>Max file size: {settings.MAX_FILE_SIZE_MB}MB</i>"
    )
    keyboard = get_cancel_keyboard()
    await query.edit_message_text(prompt_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return AWAITING_CV

async def confirm_update_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    context.user_data["is_update"] = True
    vac_title = context.user_data.get("vacancy_title", "the position")

    prompt_text = (
        f"📝 <b>Updating CV for {vac_title}</b>\n\n"
        f"Please send your updated CV as a PDF or Word document (.pdf or .docx)."
    )
    keyboard = get_cancel_keyboard()
    await query.edit_message_text(prompt_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return AWAITING_CV

async def cv_received_document(update: Update, context: ContextTypes.DEFAULT_TYPE):
    message = update.message
    document = message.document

    filename = document.file_name or "resume.pdf"
    ext = os.path.splitext(filename)[1].lower()

    # 1. Validate file extension
    if ext not in [".pdf", ".docx"]:
        await message.reply_text(
            "⚠️ <b>Unsupported file format.</b>\n\n"
            "Please send your CV as a PDF (.pdf) or Word (.docx) document.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_CV

    # 2. Validate file size
    if document.file_size > settings.max_file_size_bytes:
        await message.reply_text(
            f"⚠️ <b>File too large.</b>\n\n"
            f"The file exceeds the {settings.MAX_FILE_SIZE_MB}MB limit. Please upload a smaller file.",
            parse_mode=ParseMode.HTML,
            reply_markup=get_cancel_keyboard()
        )
        return AWAITING_CV

    status_msg = await message.reply_text("⏳ <i>Processing your CV...</i>", parse_mode=ParseMode.HTML)

    # 3. Download file bytes securely into memory
    tg_file = await document.get_file()
    file_bytes = await tg_file.download_as_bytearray()
    file_bytes = bytes(file_bytes)

    # 4. Extract details
    extracted_text = ""
    try:
        extracted_text = document_parser.extract_text_from_bytes(file_bytes, filename)
    except Exception:
        pass

    extracted_details = document_parser.extract_cv_details(extracted_text)

    # Pre-fill candidate info
    user = update.effective_user
    full_name = extracted_details.get("full_name") or user.full_name or user.first_name or "Applicant"
    phone = extracted_details.get("phone") or "Not provided"
    email = extracted_details.get("email") or "Not provided"

    # Store in user_data
    context.user_data["cv_bytes"] = file_bytes
    context.user_data["cv_original_filename"] = filename
    context.user_data["full_name"] = full_name
    context.user_data["phone"] = phone
    context.user_data["email"] = email

    # 5. Ask candidate to confirm details
    confirm_text = (
        "📄 <b>CV Received Successfully!</b>\n\n"
        "Please confirm your contact details below:\n\n"
        f"👤 <b>Name:</b> {full_name}\n"
        f"📞 <b>Phone:</b> {phone}\n"
        f"📧 <b>Email:</b> {email}\n\n"
        "<i>If any information is incorrect, use the buttons below to adjust it before submitting.</i>"
    )
    keyboard = get_contact_confirm_keyboard()
    await status_msg.delete()
    await message.reply_text(confirm_text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return CONFIRMING_CONTACT

async def cv_received_text_fallback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "Please send your CV as a PDF or Word document so we can process your application.",
        reply_markup=get_cancel_keyboard()
    )
    return AWAITING_CV

async def confirm_contact_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    user = update.effective_user
    vacancy_id = context.user_data.get("apply_vacancy_id")
    vac_title = context.user_data.get("vacancy_title", "Selected Position")
    is_update = context.user_data.get("is_update", False)

    app_data = ApplicationCreate(
        vacancy_id=vacancy_id,
        telegram_user_id=user.id,
        telegram_username=user.username,
        full_name=context.user_data.get("full_name", user.full_name),
        phone=context.user_data.get("phone") if context.user_data.get("phone") != "Not provided" else None,
        email=context.user_data.get("email") if context.user_data.get("email") != "Not provided" else None,
        cv_original_filename=context.user_data.get("cv_original_filename", "resume.pdf"),
        cv_bytes=context.user_data.get("cv_bytes")
    )

    await query.edit_message_text("⏳ <i>Submitting your application...</i>", parse_mode=ParseMode.HTML)

    async with async_session_factory() as session:
        application = await application_service.submit_application(
            app_data,
            session=session,
            is_update=is_update,
            bot=context.bot
        )

    # Step 6: Confirmation message to candidate
    submission_time_str = format_datetime(application.submitted_at)
    confirmation_text = (
        f"✅ <b>Application Submitted Successfully!</b>\n\n"
        f"Thank you for applying for <b>{vac_title}</b>.\n"
        f"We have received your CV successfully.\n"
        f"Our HR team will review your application and contact you if your qualifications match the position.\n\n"
        f"🆔 <b>Application Reference:</b> <code>{application.application_code}</code>\n"
        f"📌 <b>Position Applied:</b> {vac_title}\n"
        f"📅 <b>Submission Date:</b> {submission_time_str}\n\n"
        f"💡 <i>You can check your application status at any time with /myapplications.</i>"
    )

    await query.edit_message_text(confirmation_text, parse_mode=ParseMode.HTML)
    context.user_data.clear()
    return ConversationHandler.END

# Edit field handlers
async def edit_name_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✏️ Please type and send your <b>Full Name</b>:", parse_mode=ParseMode.HTML)
    return EDITING_NAME

async def save_name_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data["full_name"] = name
    return await _redisplay_contact_confirmation(update, context)

async def edit_phone_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📞 Please type and send your <b>Phone Number</b>:", parse_mode=ParseMode.HTML)
    return EDITING_PHONE

async def save_phone_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text.strip()
    context.user_data["phone"] = phone
    return await _redisplay_contact_confirmation(update, context)

async def edit_email_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("📧 Please type and send your <b>Email Address</b>:", parse_mode=ParseMode.HTML)
    return EDITING_EMAIL

async def save_email_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    context.user_data["email"] = email
    return await _redisplay_contact_confirmation(update, context)

async def _redisplay_contact_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    full_name = context.user_data.get("full_name", "Applicant")
    phone = context.user_data.get("phone", "Not provided")
    email = context.user_data.get("email", "Not provided")

    text = (
        "📄 <b>Updated Contact Details:</b>\n\n"
        f"👤 <b>Name:</b> {full_name}\n"
        f"📞 <b>Phone:</b> {phone}\n"
        f"📧 <b>Email:</b> {email}\n\n"
        "<i>Confirm your details to submit:</i>"
    )
    keyboard = get_contact_confirm_keyboard()
    await update.message.reply_text(text, reply_markup=keyboard, parse_mode=ParseMode.HTML)
    return CONFIRMING_CONTACT

async def cancel_flow_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    context.user_data.clear()
    await query.edit_message_text("❌ Application cancelled. Type /jobs to browse positions.")
    return ConversationHandler.END

def get_apply_conversation_handler() -> ConversationHandler:
    return ConversationHandler(
        entry_points=[
            CallbackQueryHandler(apply_start_callback, pattern=r"^apply_\d+$")
        ],
        states={
            AWAITING_CV: [
                CallbackQueryHandler(confirm_update_callback, pattern=r"^confirm_update_\d+$"),
                CallbackQueryHandler(cancel_flow_callback, pattern=r"^cancel_flow$"),
                MessageHandler(filters.Document.ALL, cv_received_document),
                MessageHandler(filters.TEXT & ~filters.COMMAND, cv_received_text_fallback)
            ],
            CONFIRMING_CONTACT: [
                CallbackQueryHandler(confirm_contact_callback, pattern=r"^confirm_contact$"),
                CallbackQueryHandler(edit_name_callback, pattern=r"^edit_name$"),
                CallbackQueryHandler(edit_phone_callback, pattern=r"^edit_phone$"),
                CallbackQueryHandler(edit_email_callback, pattern=r"^edit_email$"),
                CallbackQueryHandler(cancel_flow_callback, pattern=r"^cancel_flow$")
            ],
            EDITING_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_name_message)
            ],
            EDITING_PHONE: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_phone_message)
            ],
            EDITING_EMAIL: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, save_email_message)
            ]
        },
        fallbacks=[
            CommandHandler("cancel", cancel_flow_callback),
            CallbackQueryHandler(cancel_flow_callback, pattern=r"^cancel_flow$")
        ],
        per_chat=True,
        per_user=True
    )
