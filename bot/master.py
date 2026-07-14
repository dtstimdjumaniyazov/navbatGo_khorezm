"""
Режим мастера: день с навигацией, карточка записи, статусы, продление и
сдвиг очереди. Роутер подключается РАНЬШЕ клиентского и своим фильтром
забирает все апдейты мастеров — клиентское меню мастеру не показывается.

Язык интерфейса — ServiceManager.language (RU/UZ), меняется кнопкой «🌐».
Бот — тонкий клиент: вся бизнес-логика в core/services (та же, что у панели).
"""
from datetime import date, timedelta
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandStart, Filter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    KeyboardButton,
    Message,
    ReplyKeyboardMarkup,
    TelegramObject,
)

from bot import db
from bot.i18n import btn_texts, t, weekdays
from core.models import Appointment, ServiceManager
from core.services.appointments import BookingError, ShiftRequired, SlotTakenError

master_router = Router()

STATUS_EMOJI = {
    "scheduled": "📋",
    "confirmed": "🔵",
    "in_progress": "🔧",
    "done": "✔️",
    "no_show": "⚠️",
    "cancelled": "❌",
    "rescheduled": "🔁",
}

EXTEND_PRESETS = (15, 30, 60)


class IsMaster(Filter):
    """Определяет роль на каждом апдейте; менеджер попадает в хендлер."""

    async def __call__(self, event: TelegramObject) -> bool | dict:
        manager = await db.get_manager(event.from_user.id)
        return {"manager": manager} if manager else False


master_router.message.filter(IsMaster())
master_router.callback_query.filter(IsMaster())


# ---------- построение экранов ----------

def _tz(manager: ServiceManager) -> ZoneInfo:
    return ZoneInfo(manager.service_point.timezone)


def _lang(manager: ServiceManager) -> str:
    return manager.language or "ru"


def _menu_kb(lang: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "m_btn_today"), callback_data="mday:0")],
        [InlineKeyboardButton(text=t(lang, "m_btn_tomorrow"), callback_data="mday:1")],
        [InlineKeyboardButton(text=t(lang, "m_btn_now"), callback_data="mnow")],
        [InlineKeyboardButton(text=t(lang, "m_btn_add"), callback_data="madd")],
    ])


def _reply_kb(lang: str) -> ReplyKeyboardMarkup:
    """
    Постоянная клавиатура мастера. Заменяет клиентскую, которая могла
    «залипнуть» в чате с тех пор, когда аккаунт ещё не был мастером.
    """
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=t(lang, "m_btn_today")),
                KeyboardButton(text=t(lang, "m_btn_now")),
            ],
            [
                KeyboardButton(text=t(lang, "m_btn_add")),
                KeyboardButton(text=t(lang, "m_btn_menu")),
            ],
            [KeyboardButton(text=t(lang, "m_btn_language"))],
        ],
        resize_keyboard=True,
    )


async def _menu_text(manager: ServiceManager) -> str:
    tz = _tz(manager)
    from datetime import datetime

    today = datetime.now(tz).date()
    appts = await db.get_day_appointments(manager.service_point, today)
    in_progress = sum(1 for a in appts if a.status == Appointment.Status.IN_PROGRESS)
    return t(
        _lang(manager), "m_menu",
        name=manager.service_point.name,
        count=len(appts),
        in_progress=in_progress,
    )


def _day_label(d: date, tz: ZoneInfo, lang: str) -> str:
    from datetime import datetime

    today = datetime.now(tz).date()
    if d == today:
        return f"{t(lang, 'today')}, {d:%d.%m}"
    if d == today + timedelta(days=1):
        return f"{t(lang, 'tomorrow')}, {d:%d.%m}".replace(" ▶️", "")
    return f"{weekdays(lang)[d.weekday()]}, {d:%d.%m}"


def _day_screen(manager, appts, offset: int, on_date: date):
    """Текст списка дня + клавиатура: записи, навигация ← Сегодня →, меню."""
    tz = _tz(manager)
    lang = _lang(manager)
    header = t(lang, "m_day_header", date=_day_label(on_date, tz, lang))
    if not appts:
        text = t(lang, "m_day_empty", date=_day_label(on_date, tz, lang))
    else:
        lines = [header, ""]
        for a in appts:
            s = a.start_time.astimezone(tz)
            lines.append(
                f"{STATUS_EMOJI[a.status]} {s:%H:%M} · {a.client.name or '—'} · "
                f"{a.service.name} · {a.bay.name}"
            )
        text = "\n".join(lines)

    rows = [
        [InlineKeyboardButton(
            text=f"{a.start_time.astimezone(tz):%H:%M} {a.client.name or '—'} "
                 f"{STATUS_EMOJI[a.status]}",
            callback_data=f"mappt:{a.id}:{offset}",
        )]
        for a in appts
        if a.status not in (Appointment.Status.CANCELLED,)
    ]
    rows.append([
        InlineKeyboardButton(text="◀️", callback_data=f"mday:{offset - 1}"),
        InlineKeyboardButton(
            text=t(lang, "m_btn_today").replace("📅 ", ""), callback_data="mday:0"
        ),
        InlineKeyboardButton(text="▶️", callback_data=f"mday:{offset + 1}"),
    ])
    rows.append([InlineKeyboardButton(text=t(lang, "m_btn_menu"), callback_data="mmenu")])
    return text, InlineKeyboardMarkup(inline_keyboard=rows)


def _card_text(appt: Appointment, tz: ZoneInfo, lang: str) -> str:
    s = appt.start_time.astimezone(tz)
    e = appt.estimated_end_time.astimezone(tz)
    client = appt.client.name or "—"
    if appt.client.phone:
        client += f" · {appt.client.phone}"
    source_key = {
        "telegram": "m_source_telegram",
        "app": "m_source_app",
    }.get(appt.source, "m_source_manual")
    lines = [
        f"🔧 {appt.service.name}",
        t(lang, "m_client_line", name=client),
    ]
    if appt.client.no_show_count > 0:
        lines.append(t(lang, "m_no_show_badge", n=appt.client.no_show_count))
    if appt.car_details:
        lines.append(f"🚗 {appt.car_details}")
    lines.append(t(
        lang, "m_bay_time_line",
        bay=appt.bay.name, date=f"{s:%d.%m}", start=f"{s:%H:%M}", end=f"{e:%H:%M}",
    ))
    lines.append(t(
        lang, "m_status_line",
        emoji=STATUS_EMOJI[appt.status], status=appt.get_status_display(),
    ))
    lines.append(t(lang, "m_source_line", source=t(lang, source_key)))
    if appt.note:
        lines.append(f"📝 {appt.note}")
    return "\n".join(lines)


def _card_kb(appt: Appointment, offset: int, lang: str) -> InlineKeyboardMarkup:
    aid = appt.id
    rows = []
    if appt.status in (Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED):
        rows.append([InlineKeyboardButton(
            text=t(lang, "m_btn_start"), callback_data=f"mact:start:{aid}:{offset}"
        )])
        rows.append([
            InlineKeyboardButton(
                text=t(lang, "m_btn_noshow"), callback_data=f"mconf:noshow:{aid}:{offset}"
            ),
            InlineKeyboardButton(
                text=t(lang, "m_btn_cancel_appt"), callback_data=f"mconf:cancel:{aid}:{offset}"
            ),
        ])
    if appt.status == Appointment.Status.IN_PROGRESS:
        rows.append([InlineKeyboardButton(
            text=t(lang, "m_btn_finish"), callback_data=f"mact:finish:{aid}:{offset}"
        )])
        rows.append([
            InlineKeyboardButton(
                text=t(lang, "m_btn_extend", min=m), callback_data=f"mext:{m}:{aid}:{offset}"
            )
            for m in EXTEND_PRESETS
        ])
    if appt.status in Appointment.ACTIVE_STATUSES:
        rows.append([
            InlineKeyboardButton(
                text=t(lang, "m_btn_shift", min=m), callback_data=f"mshift:{m}:{aid}:{offset}"
            )
            for m in EXTEND_PRESETS
        ])
    rows.append([
        InlineKeyboardButton(text=t(lang, "m_btn_back_day"), callback_data=f"mday:{offset}"),
        InlineKeyboardButton(text=t(lang, "m_btn_menu"), callback_data="mmenu"),
    ])
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _show_day(callback: CallbackQuery, manager: ServiceManager, offset: int):
    from datetime import datetime

    tz = _tz(manager)
    on_date = datetime.now(tz).date() + timedelta(days=offset)
    appts = await db.get_day_appointments(manager.service_point, on_date)
    text, kb = _day_screen(manager, appts, offset, on_date)
    await callback.message.edit_text(text, reply_markup=kb)
    await callback.answer()


async def _show_card(callback: CallbackQuery, manager: ServiceManager, appointment_id, offset: int):
    appt = await db.get_sp_appointment(appointment_id, manager.service_point)
    if appt is None:
        await callback.answer(t(_lang(manager), "m_not_found"), show_alert=True)
        return
    await callback.message.edit_text(
        _card_text(appt, _tz(manager), _lang(manager)),
        reply_markup=_card_kb(appt, offset, _lang(manager)),
    )
    await callback.answer()


# ---------- хендлеры ----------

@master_router.message(CommandStart())
@master_router.message(Command("menu"))
async def master_start(message: Message, manager: ServiceManager, state: FSMContext):
    await state.clear()
    # Reply-клавиатура мастера вытесняет клиентскую (если была)
    await message.answer(await _menu_text(manager), reply_markup=_reply_kb(_lang(manager)))
    if not manager.onboarding_seen:
        await message.answer(t(_lang(manager), "m_onboard_msg"))
        await db.mark_onboarding_seen(manager.id)


@master_router.callback_query(F.data == "mmenu")
async def master_menu_cb(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await state.clear()
    await callback.message.edit_text(
        await _menu_text(manager), reply_markup=_menu_kb(_lang(manager))
    )
    await callback.answer()


# ---------- кнопки постоянной клавиатуры мастера ----------
# Регистрируются раньше FSM-хендлеров: нажатие кнопки в любом состоянии
# выходит из сценария (state.clear) и открывает нужный экран

@master_router.message(F.text.in_(btn_texts("m_btn_today")))
async def master_today_btn(message: Message, manager: ServiceManager, state: FSMContext):
    from datetime import datetime

    await state.clear()
    on_date = datetime.now(_tz(manager)).date()
    appts = await db.get_day_appointments(manager.service_point, on_date)
    text, kb = _day_screen(manager, appts, 0, on_date)
    await message.answer(text, reply_markup=kb)


@master_router.message(F.text.in_(btn_texts("m_btn_now")))
async def master_now_btn(message: Message, manager: ServiceManager, state: FSMContext):
    await state.clear()
    appt = await db.get_current_appointment(manager.service_point)
    if appt is None:
        await message.answer(t(_lang(manager), "m_no_current"))
        return
    await message.answer(
        _card_text(appt, _tz(manager), _lang(manager)),
        reply_markup=_card_kb(appt, 0, _lang(manager)),
    )


@master_router.message(F.text.in_(btn_texts("m_btn_add")))
async def master_add_btn(message: Message, manager: ServiceManager, state: FSMContext):
    await state.clear()
    lang = _lang(manager)
    bays = await db.get_active_bays(manager.service_point)
    rows = [
        [InlineKeyboardButton(text=b.name, callback_data=f"madd_bay:{b.id}")]
        for b in bays
    ]
    rows.append(_abort_row(lang))
    await message.answer(
        t(lang, "m_add_bay"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )


@master_router.message(F.text.in_(btn_texts("m_btn_menu")))
async def master_menu_btn(message: Message, manager: ServiceManager, state: FSMContext):
    await state.clear()
    await message.answer(await _menu_text(manager), reply_markup=_menu_kb(_lang(manager)))


@master_router.message(F.text.in_(btn_texts("m_btn_language")))
async def master_language_btn(message: Message, manager: ServiceManager, state: FSMContext):
    await state.clear()
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="🇷🇺 Русский", callback_data="mlang:ru"),
        InlineKeyboardButton(text="🇺🇿 Ўзбекча", callback_data="mlang:uz"),
    ]])
    await message.answer(t(_lang(manager), "m_lang_choose"), reply_markup=kb)


@master_router.callback_query(F.data.startswith("mlang:"))
async def master_language_set(callback: CallbackQuery, manager: ServiceManager):
    lang = callback.data.removeprefix("mlang:")
    if lang not in ("ru", "uz"):
        await callback.answer()
        return
    await db.set_manager_language(manager.id, lang)
    manager.language = lang  # объект в памяти — для текущего ответа
    await callback.message.edit_text(t(lang, "m_lang_saved"))
    # Новая reply-клавиатура на выбранном языке
    await callback.message.answer(await _menu_text(manager), reply_markup=_reply_kb(lang))
    await callback.answer()


@master_router.callback_query(F.data.startswith("mday:"))
async def master_day(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await state.clear()
    offset = int(callback.data.split(":")[1])
    await _show_day(callback, manager, offset)


@master_router.callback_query(F.data == "mnow")
async def master_now(callback: CallbackQuery, manager: ServiceManager):
    appt = await db.get_current_appointment(manager.service_point)
    if appt is None:
        await callback.answer(t(_lang(manager), "m_no_current"), show_alert=True)
        return
    from datetime import datetime

    tz = _tz(manager)
    offset = (appt.start_time.astimezone(tz).date() - datetime.now(tz).date()).days
    await _show_card(callback, manager, appt.id, offset)


@master_router.callback_query(F.data.startswith("mappt:"))
async def master_card(callback: CallbackQuery, manager: ServiceManager):
    _, aid, offset = callback.data.split(":")
    await _show_card(callback, manager, aid, int(offset))


@master_router.callback_query(F.data.startswith("mconf:"))
async def master_confirm(callback: CallbackQuery, manager: ServiceManager):
    """Экран подтверждения для необратимых действий (отмена, неявка)."""
    _, action, aid, offset = callback.data.split(":")
    lang = _lang(manager)
    appt = await db.get_sp_appointment(aid, manager.service_point)
    if appt is None:
        await callback.answer(t(lang, "m_not_found"), show_alert=True)
        return
    tz = _tz(manager)
    params = {
        "client": appt.client.name or "—",
        "time": f"{appt.start_time.astimezone(tz):%d.%m %H:%M}",
    }
    key = "m_confirm_cancel" if action == "cancel" else "m_confirm_noshow"
    # Отмену подтверждает не сразу «Да» — сначала просим причину (уйдёт клиенту)
    yes_target = f"mcancelask:{aid}:{offset}" if action == "cancel" else f"mact:{action}:{aid}:{offset}"
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "m_btn_yes"), callback_data=yes_target),
        InlineKeyboardButton(
            text=t(lang, "m_btn_no"), callback_data=f"mappt:{aid}:{offset}"
        ),
    ]])
    await callback.message.edit_text(t(lang, key, **params), reply_markup=kb)
    await callback.answer()


class CancelAppt(StatesGroup):
    reason = State()


@master_router.callback_query(F.data.startswith("mcancelask:"))
async def cancel_ask_reason(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    _, aid, offset = callback.data.split(":")
    await state.set_state(CancelAppt.reason)
    await state.update_data(aid=aid, offset=offset)
    lang = _lang(manager)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "m_btn_abort"), callback_data=f"mcancel_abort:{aid}:{offset}")]
    ])
    await callback.message.edit_text(t(lang, "m_cancel_reason_prompt"), reply_markup=kb)
    await callback.answer()


@master_router.callback_query(F.data.startswith("mcancel_abort:"))
async def cancel_abort(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await state.clear()
    _, aid, offset = callback.data.split(":")
    await _show_card(callback, manager, aid, int(offset))


@master_router.message(CancelAppt.reason, F.text)
async def cancel_reason_received(message: Message, manager: ServiceManager, state: FSMContext):
    lang = _lang(manager)
    reason = message.text.strip()
    if not reason:
        await message.answer(t(lang, "m_cancel_reason_empty"))
        return
    data = await state.get_data()
    await state.clear()
    try:
        appt = await db.master_action(data["aid"], manager.service_point, "cancel", reason=reason)
    except BookingError as exc:
        await message.answer(str(exc))
        return
    if appt is None:
        await message.answer(t(lang, "m_not_found"))
        return
    offset = int(data["offset"])
    await message.answer(
        _card_text(appt, _tz(manager), lang), reply_markup=_card_kb(appt, offset, lang)
    )


@master_router.callback_query(F.data.startswith("mact:"))
async def master_act(callback: CallbackQuery, manager: ServiceManager):
    _, action, aid, offset = callback.data.split(":")
    lang = _lang(manager)
    try:
        appt = await db.master_action(aid, manager.service_point, action)
    except BookingError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if appt is None:
        await callback.answer(t(lang, "m_not_found"), show_alert=True)
        return
    await callback.message.edit_text(
        _card_text(appt, _tz(manager), lang), reply_markup=_card_kb(appt, int(offset), lang)
    )
    await callback.answer(t(lang, "m_action_done"))


@master_router.callback_query(F.data.startswith("mext:"))
async def master_extend(callback: CallbackQuery, manager: ServiceManager):
    _, minutes, aid, offset = callback.data.split(":")
    minutes = int(minutes)
    lang = _lang(manager)
    try:
        appt = await db.master_extend(aid, manager.service_point, minutes)
    except ShiftRequired as exc:
        # Наезд на следующие записи → предлагаем сдвиг на те же X минут
        kb = InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(
                text=t(lang, "m_btn_shift", min=minutes),
                callback_data=f"mshift:{minutes}:{aid}:{offset}",
            ),
            InlineKeyboardButton(
                text=t(lang, "m_btn_no"), callback_data=f"mappt:{aid}:{offset}"
            ),
        ]])
        await callback.message.edit_text(
            t(lang, "m_extend_conflict", min=minutes, n=exc.conflicts), reply_markup=kb
        )
        await callback.answer()
        return
    except BookingError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if appt is None:
        await callback.answer(t(lang, "m_not_found"), show_alert=True)
        return
    tz = _tz(manager)
    await callback.message.edit_text(
        _card_text(appt, tz, lang), reply_markup=_card_kb(appt, int(offset), lang)
    )
    await callback.answer(
        t(lang, "m_extend_ok", time=f"{appt.estimated_end_time.astimezone(tz):%H:%M}")
    )


@master_router.callback_query(F.data.startswith("mshift:"))
async def master_shift_confirm(callback: CallbackQuery, manager: ServiceManager):
    """Подтверждение перед сдвигом и рассылкой — случайно не разошлём."""
    _, minutes, aid, offset = callback.data.split(":")
    lang = _lang(manager)
    appt = await db.get_sp_appointment(aid, manager.service_point)
    if appt is None:
        await callback.answer(t(lang, "m_not_found"), show_alert=True)
        return
    n = await db.count_shift_targets(appt)
    if n == 0:
        await callback.answer(t(lang, "m_shift_nothing"), show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(
            text=t(lang, "m_btn_yes"), callback_data=f"mshiftok:{minutes}:{aid}:{offset}"
        ),
        InlineKeyboardButton(
            text=t(lang, "m_btn_no"), callback_data=f"mappt:{aid}:{offset}"
        ),
    ]])
    await callback.message.edit_text(
        t(lang, "m_shift_confirm", n=n, min=minutes), reply_markup=kb
    )
    await callback.answer()


@master_router.callback_query(F.data.startswith("mshiftok:"))
async def master_shift_do(callback: CallbackQuery, manager: ServiceManager):
    _, minutes, aid, offset = callback.data.split(":")
    lang = _lang(manager)
    try:
        result = await db.master_shift(aid, manager.service_point, int(minutes))
    except BookingError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if result is None:
        await callback.answer(t(lang, "m_not_found"), show_alert=True)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=t(lang, "m_btn_back_day"), callback_data=f"mday:{offset}"),
        InlineKeyboardButton(text=t(lang, "m_btn_menu"), callback_data="mmenu"),
    ]])
    await callback.message.edit_text(
        t(lang, "m_shift_done", n=result["shifted"], sent=result["sent"], failed=result["failed"]),
        reply_markup=kb,
    )
    await callback.answer()


# ---------- «Записать с улицы»: пост → услуга → день → время → имя → телефон ----------

class AddWalkIn(StatesGroup):
    name = State()
    phone = State()


def _abort_row(lang: str) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=t(lang, "m_btn_abort"), callback_data="madd_abort")]


async def _walkin_days_kb(sp, lang: str) -> InlineKeyboardMarkup:
    from datetime import datetime

    schedule = await db.get_week_schedule(sp)
    tz = ZoneInfo(sp.timezone)
    today = datetime.now(tz).date()
    rows = []
    for i in range(14):
        if len(rows) >= 7:
            break
        d = today + timedelta(days=i)
        if schedule[d.weekday()]["start"] is None:  # выходной
            continue
        if i == 0:
            label = t(lang, "today")
        elif i == 1:
            label = t(lang, "tomorrow")
        else:
            label = f"{weekdays(lang)[d.weekday()]} {d:%d.%m}"
        rows.append([InlineKeyboardButton(text=label, callback_data=f"madd_day:{d.isoformat()}")])
    rows.append(_abort_row(lang))
    return InlineKeyboardMarkup(inline_keyboard=rows)


async def _walkin_slots_kb(manager, data: dict) -> InlineKeyboardMarkup | None:
    """Сетка свободных времён выбранного поста; None — слотов нет."""
    service = await db.get_sp_service(data["service_id"], manager.service_point)
    if service is None:
        return None
    on_date = date.fromisoformat(data["day"])
    # Клиент уже на месте — ограничение на онлайн-запись не нужно
    slots = await db.get_slots(service, on_date, apply_lead_time=False)
    times = [s.start.strftime("%H:%M") for s in slots if data["bay_id"] in map(str, s.bay_ids)]
    if not times:
        return None
    rows, row = [], []
    for tm in times:
        row.append(InlineKeyboardButton(text=tm, callback_data=f"madd_tm:{tm}"))
        if len(row) == 3:
            rows.append(row)
            row = []
    if row:
        rows.append(row)
    rows.append(_abort_row(_lang(manager)))
    return InlineKeyboardMarkup(inline_keyboard=rows)


@master_router.callback_query(F.data == "madd")
async def walkin_start(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await state.clear()
    lang = _lang(manager)
    bays = await db.get_active_bays(manager.service_point)
    rows = [
        [InlineKeyboardButton(text=b.name, callback_data=f"madd_bay:{b.id}")] for b in bays
    ]
    rows.append(_abort_row(lang))
    await callback.message.edit_text(
        t(lang, "m_add_bay"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await callback.answer()


@master_router.callback_query(F.data.startswith("madd_bay:"))
async def walkin_bay(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await state.update_data(bay_id=callback.data.split(":")[1])
    lang = _lang(manager)
    unit = "дақ." if lang == "uz" else "мин"
    services = await db.get_active_services(manager.service_point)
    rows = [
        [InlineKeyboardButton(
            text=f"{s.name} ({s.duration_minutes} {unit})", callback_data=f"madd_svc:{s.id}"
        )]
        for s in services
    ]
    rows.append(_abort_row(lang))
    await callback.message.edit_text(
        t(lang, "m_add_service"), reply_markup=InlineKeyboardMarkup(inline_keyboard=rows)
    )
    await callback.answer()


@master_router.callback_query(F.data.startswith("madd_svc:"))
async def walkin_service(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await state.update_data(service_id=callback.data.split(":")[1])
    lang = _lang(manager)
    await callback.message.edit_text(
        t(lang, "m_add_day"),
        reply_markup=await _walkin_days_kb(manager.service_point, lang),
    )
    await callback.answer()


@master_router.callback_query(F.data.startswith("madd_day:"))
async def walkin_day(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await state.update_data(day=callback.data.split(":")[1])
    lang = _lang(manager)
    data = await state.get_data()
    kb = await _walkin_slots_kb(manager, data)
    if kb is None:
        bay = next(
            (b for b in await db.get_active_bays(manager.service_point)
             if str(b.id) == data["bay_id"]),
            None,
        )
        await callback.message.edit_text(
            t(lang, "m_add_no_slots", bay=bay.name if bay else "?"),
            reply_markup=await _walkin_days_kb(manager.service_point, lang),
        )
        await callback.answer()
        return
    on_date = date.fromisoformat(data["day"])
    bay = next(
        (b for b in await db.get_active_bays(manager.service_point)
         if str(b.id) == data["bay_id"]),
        None,
    )
    await callback.message.edit_text(
        t(lang, "m_add_time", bay=bay.name if bay else "?", date=f"{on_date:%d.%m}"),
        reply_markup=kb,
    )
    await callback.answer()


@master_router.callback_query(F.data.startswith("madd_tm:"))
async def walkin_time(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await state.update_data(time=callback.data.removeprefix("madd_tm:"))
    await state.set_state(AddWalkIn.name)
    lang = _lang(manager)
    await callback.message.edit_text(
        t(lang, "m_add_name"),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[_abort_row(lang)]),
    )
    await callback.answer()


@master_router.message(AddWalkIn.name, F.text)
async def walkin_name(message: Message, manager: ServiceManager, state: FSMContext):
    await state.update_data(name=message.text.strip()[:200])
    await state.set_state(AddWalkIn.phone)
    lang = _lang(manager)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=t(lang, "m_btn_skip"), callback_data="madd_skip")],
        _abort_row(lang),
    ])
    await message.answer(t(lang, "m_add_phone"), reply_markup=kb)


async def _walkin_finalize(target: Message, manager: ServiceManager, state: FSMContext, phone: str):
    """Создание записи; при занятом слоте — вернуться к выбору времени."""
    from datetime import datetime

    data = await state.get_data()
    tz = _tz(manager)
    lang = _lang(manager)
    start_time = datetime.combine(
        date.fromisoformat(data["day"]),
        datetime.strptime(data["time"], "%H:%M").time(),
        tzinfo=tz,
    )
    try:
        appt = await db.master_create_walkin(
            manager.service_point,
            data["bay_id"], data["service_id"], start_time,
            data["name"], phone,
        )
    except SlotTakenError:
        # Слот увели, пока вводили имя — предлагаем другое время
        await state.set_state(None)  # выходим из текстовых состояний, данные храним
        kb = await _walkin_slots_kb(manager, data)
        if kb is None:
            await target.answer(
                t(lang, "m_add_no_slots", bay="—"),
                reply_markup=await _walkin_days_kb(manager.service_point, lang),
            )
        else:
            await target.answer(t(lang, "m_add_slot_taken"), reply_markup=kb)
        return
    except BookingError as exc:
        await state.clear()
        await target.answer(f"⚠️ {exc}")
        await target.answer(await _menu_text(manager), reply_markup=_menu_kb(lang))
        return
    await state.clear()
    s = appt.start_time.astimezone(tz)
    await target.answer(
        t(
            lang, "m_add_done",
            client=appt.client.name or "—",
            service=appt.service.name,
            bay=appt.bay.name,
            date=f"{s:%d.%m}",
            time=f"{s:%H:%M}",
        ),
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[
            InlineKeyboardButton(text=t(lang, "m_btn_menu"), callback_data="mmenu"),
        ]]),
    )


@master_router.message(AddWalkIn.phone, F.text)
async def walkin_phone(message: Message, manager: ServiceManager, state: FSMContext):
    await _walkin_finalize(message, manager, state, phone=message.text.strip()[:32])


@master_router.callback_query(AddWalkIn.phone, F.data == "madd_skip")
async def walkin_skip_phone(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await callback.answer()
    await _walkin_finalize(callback.message, manager, state, phone="")


@master_router.callback_query(F.data == "madd_abort")
async def walkin_abort(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await state.clear()
    lang = _lang(manager)
    await callback.message.edit_text(await _menu_text(manager), reply_markup=_menu_kb(lang))
    await callback.answer(t(lang, "m_add_aborted"))


# ---------- catch-all: мастер не проваливается в клиентский роутер ----------

@master_router.message()
async def master_fallback_msg(message: Message, manager: ServiceManager, state: FSMContext):
    await state.clear()
    await message.answer(await _menu_text(manager), reply_markup=_menu_kb(_lang(manager)))


@master_router.callback_query()
async def master_fallback_cb(callback: CallbackQuery, manager: ServiceManager, state: FSMContext):
    await state.clear()
    await callback.message.answer(
        await _menu_text(manager), reply_markup=_menu_kb(_lang(manager))
    )
    await callback.answer()
