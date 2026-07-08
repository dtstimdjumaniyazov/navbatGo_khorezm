"""Клавиатуры бота. Все подписи — через bot.i18n по языку клиента."""
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from aiogram.types import (
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    ReplyKeyboardMarkup,
)

from bot.i18n import svc_name, t, weekdays


def language_kb() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="lang:ru"),
        InlineKeyboardButton(text="🇺🇿 Ўзбекча", callback_data="lang:uz"),
    ]])


def main_menu(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "btn_book")),
                KeyboardButton(text=t(lang, "btn_my")),
            ],
            [KeyboardButton(text=t(lang, "btn_language"))],
        ],
        resize_keyboard=True,
    )


def phone_request(lang: str) -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text=t(lang, "btn_send_phone"), request_contact=True)],
            [KeyboardButton(text=t(lang, "btn_skip"))],
        ],
        resize_keyboard=True,
        one_time_keyboard=True,
    )


def services_kb(services, lang: str) -> InlineKeyboardMarkup:
    rows = []
    for s in services:
        price = ""
        if s.price:
            price = " — " + f"{int(s.price):,}".replace(",", " ") + (" сўм" if lang == "uz" else " сум")
        unit = "дақ." if lang == "uz" else "мин"
        rows.append([
            InlineKeyboardButton(
                text=f"{svc_name(s, lang)} ({s.duration_minutes} {unit}){price}",
                callback_data=f"svc:{s.id}",
            )
        ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def dates_kb(service_point, lang: str, days_ahead: int = 7) -> InlineKeyboardMarkup:
    """Ближайшие рабочие дни сервиса."""
    tz = ZoneInfo(service_point.timezone)
    today = datetime.now(tz).date()
    wd = weekdays(lang)
    rows = []
    for i in range(days_ahead):
        d = today + timedelta(days=i)
        if d.weekday() not in service_point.work_days:
            continue
        if i == 0:
            label = t(lang, "today")
        elif i == 1:
            label = t(lang, "tomorrow")
        else:
            label = f"{wd[d.weekday()]} {d:%d.%m}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"day:{d.isoformat()}")])
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back_services"), callback_data="back:services")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def slots_kb(slots, lang: str) -> InlineKeyboardMarkup:
    """Сетка времён, по 3 в ряд. Время передаётся как HH:MM (дата лежит в FSM)."""
    rows, row = [], []
    for slot in slots:
        tm = slot.start.strftime("%H:%M")
        row.append(InlineKeyboardButton(text=tm, callback_data=f"tm:{tm}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append([InlineKeyboardButton(text=t(lang, "btn_back_dates"), callback_data="back:dates")])
    return InlineKeyboardMarkup(inline_keyboard=rows)


def confirm_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "btn_confirm"), callback_data="ok:yes"),
        InlineKeyboardButton(text=t(lang, "btn_cancel"), callback_data="ok:no"),
    ]])


def my_appointments_kb(appointments, lang: str) -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(
            text=t(
                lang, "btn_cancel_appt",
                date=f"{a.start_time_local:%d.%m %H:%M}",
                service=svc_name(a.service, lang),
            ),
            callback_data=f"cxl:{a.id}",
        )]
        for a in appointments
    ]
    return InlineKeyboardMarkup(inline_keyboard=rows)
