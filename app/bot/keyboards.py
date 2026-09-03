from typing import List
from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from app.models.vacancy import Vacancy

def get_vacancies_keyboard(vacancies: List[Vacancy]) -> InlineKeyboardMarkup:
    keyboard = []
    for v in vacancies:
        btn_text = f"💼 {v.title}"
        if v.department:
            btn_text += f" ({v.department})"
        keyboard.append([InlineKeyboardButton(btn_text, callback_data=f"vac_{v.id}")])
    
    if not vacancies:
        keyboard.append([InlineKeyboardButton("🔄 Refresh Vacancies", callback_data="browse_vacancies")])
    return InlineKeyboardMarkup(keyboard)

def get_vacancy_detail_keyboard(vacancy_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("📝 Apply for this position", callback_data=f"apply_{vacancy_id}")],
        [
            InlineKeyboardButton("⬅️ Back to vacancies", callback_data="browse_vacancies"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_duplicate_confirm_keyboard(vacancy_id: int) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("🔄 Yes, submit updated CV", callback_data=f"confirm_update_{vacancy_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow")]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_contact_confirm_keyboard() -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton("✅ Confirm & Submit", callback_data="confirm_contact")],
        [
            InlineKeyboardButton("✏️ Edit Name", callback_data="edit_name"),
            InlineKeyboardButton("📞 Edit Phone", callback_data="edit_phone")
        ],
        [
            InlineKeyboardButton("📧 Edit Email", callback_data="edit_email"),
            InlineKeyboardButton("❌ Cancel", callback_data="cancel_flow")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def get_cancel_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup([
        [InlineKeyboardButton("❌ Cancel Application", callback_data="cancel_flow")]
    ])
