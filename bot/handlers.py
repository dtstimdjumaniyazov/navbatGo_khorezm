"""Хендлеры бота: выбор языка, регистрация, запись на слот, мои записи, отмена."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from bot import db, keyboards as kb
from bot.i18n import LANGS, btn_texts, svc_name, t
from core.services.appointments import BookingError, SlotTakenError

router = Router()


class Registration(StatesGroup):
    language = State()
    name = State()
    phone = State()


class Booking(StatesGroup):
    service = State()
    day = State()
    slot_time = State()
    confirm = State()


# ---------- старт, язык, регистрация ----------

@router.message(CommandStart())
async def cmd_start(message: Message, state: FSMContext):
    await state.clear()
    client, created = await db.get_or_create_client(message.from_user.id)
    if created:
        # Первое знакомство: сначала язык, потом имя и телефон
        await state.set_state(Registration.language)
        await message.answer(
            t("ru", "choose_language"),
            reply_markup=kb.language_kb(),
        )
        return
    lang = client.language
    if not client.name:
        await state.set_state(Registration.name)
        await message.answer(t(lang, "ask_name"), reply_markup=ReplyKeyboardRemove())
        return
    await message.answer(
        t(lang, "welcome_back", name=client.name), reply_markup=kb.main_menu(lang)
    )


@router.message(Command("language"))
@router.message(F.text.in_(btn_texts("btn_language")))
async def cmd_language(message: Message):
    await message.answer(t("ru", "choose_language"), reply_markup=kb.language_kb())


@router.callback_query(F.data.startswith("lang:"))
async def set_language(callback: CallbackQuery, state: FSMContext):
    lang = callback.data.removeprefix("lang:")
    if lang not in LANGS:
        await callback.answer()
        return
    client, _ = await db.get_or_create_client(callback.from_user.id)
    await db.update_client(client.id, language=lang)

    if await state.get_state() == Registration.language:
        # Продолжаем регистрацию на выбранном языке
        await state.set_state(Registration.name)
        await callback.message.edit_text(t(lang, "ask_name"))
    else:
        await callback.message.edit_text(t(lang, "language_saved"))
        await callback.message.answer(t(lang, "fallback"), reply_markup=kb.main_menu(lang))
    await callback.answer()


@router.message(Registration.name, F.text)
async def reg_name(message: Message, state: FSMContext):
    client, _ = await db.get_or_create_client(message.from_user.id)
    lang = client.language
    await db.update_client(client.id, name=message.text.strip()[:200])
    await state.set_state(Registration.phone)
    await message.answer(t(lang, "ask_phone"), reply_markup=kb.phone_request(lang))


@router.message(Registration.phone, F.contact | F.text)
async def reg_phone(message: Message, state: FSMContext):
    client, _ = await db.get_or_create_client(message.from_user.id)
    lang = client.language
    if message.contact:
        await db.update_client(client.id, phone=message.contact.phone_number[:32])
    elif message.text and message.text not in btn_texts("btn_skip"):
        await db.update_client(client.id, phone=message.text.strip()[:32])
    await state.clear()
    await message.answer(t(lang, "registered"), reply_markup=kb.main_menu(lang))


# ---------- запись: услуга → дата → время → подтверждение ----------

@router.message(F.text.in_(btn_texts("btn_book")))
async def start_booking(message: Message, state: FSMContext):
    client, _ = await db.get_or_create_client(message.from_user.id)
    lang = client.language
    services = await db.get_active_services()
    if not services:
        await message.answer(t(lang, "no_services"))
        return
    await state.set_state(Booking.service)
    await message.answer(t(lang, "choose_service"), reply_markup=kb.services_kb(services, lang))


@router.callback_query(F.data == "back:services")
async def back_to_services(callback: CallbackQuery, state: FSMContext):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    services = await db.get_active_services()
    await state.set_state(Booking.service)
    await callback.message.edit_text(
        t(lang, "choose_service"), reply_markup=kb.services_kb(services, lang)
    )
    await callback.answer()


@router.callback_query(Booking.service, F.data.startswith("svc:"))
async def choose_service(callback: CallbackQuery, state: FSMContext):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    service = await db.get_service(callback.data.removeprefix("svc:"))
    if service is None:
        await callback.answer(t(lang, "restart"), show_alert=True)
        return
    await state.update_data(service_id=str(service.id))
    await state.set_state(Booking.day)
    hint = t(lang, "flexible_hint") if service.service_type == "flexible" else ""
    await callback.message.edit_text(
        t(lang, "service_line", name=svc_name(service, lang)) + hint + "\n\n" + t(lang, "choose_day"),
        reply_markup=kb.dates_kb(service.service_point, lang),
    )
    await callback.answer()


@router.callback_query(F.data == "back:dates")
async def back_to_dates(callback: CallbackQuery, state: FSMContext):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    data = await state.get_data()
    service = await db.get_service(data.get("service_id"))
    if service is None:
        await callback.answer(t(lang, "restart"), show_alert=True)
        return
    await state.set_state(Booking.day)
    await callback.message.edit_text(
        t(lang, "choose_day"), reply_markup=kb.dates_kb(service.service_point, lang)
    )
    await callback.answer()


@router.callback_query(Booking.day, F.data.startswith("day:"))
async def choose_day(callback: CallbackQuery, state: FSMContext):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    data = await state.get_data()
    service = await db.get_service(data.get("service_id"))
    if service is None:
        await callback.answer(t(lang, "restart"), show_alert=True)
        return
    on_date = date.fromisoformat(callback.data.removeprefix("day:"))
    slots = await db.get_slots(service, on_date)
    if not slots:
        await callback.answer(t(lang, "no_slots"), show_alert=True)
        return
    await state.update_data(day=on_date.isoformat())
    await state.set_state(Booking.slot_time)
    await callback.message.edit_text(
        t(lang, "free_time", service=svc_name(service, lang), date=f"{on_date:%d.%m.%Y}"),
        reply_markup=kb.slots_kb(slots, lang),
    )
    await callback.answer()


@router.callback_query(Booking.slot_time, F.data.startswith("tm:"))
async def choose_time(callback: CallbackQuery, state: FSMContext):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    data = await state.get_data()
    service = await db.get_service(data.get("service_id"))
    if service is None:
        await callback.answer(t(lang, "restart"), show_alert=True)
        return
    time_str = callback.data.removeprefix("tm:")
    await state.update_data(slot_time=time_str)
    await state.set_state(Booking.confirm)
    price = ""
    if service.price:
        price = t(lang, "price_line", price=f"{int(service.price):,}".replace(",", " "))
    await callback.message.edit_text(
        t(
            lang, "check_booking",
            service=svc_name(service, lang),
            date=f"{date.fromisoformat(data['day']):%d.%m.%Y}",
            time=time_str,
            duration=service.duration_minutes,
            price=price,
        ),
        reply_markup=kb.confirm_kb(lang),
    )
    await callback.answer()


@router.callback_query(Booking.confirm, F.data == "ok:yes")
async def confirm_booking(callback: CallbackQuery, state: FSMContext):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    data = await state.get_data()
    service = await db.get_service(data.get("service_id"))
    if service is None:
        await callback.answer(t(lang, "restart"), show_alert=True)
        return
    tz = ZoneInfo(service.service_point.timezone)
    start_time = datetime.combine(
        date.fromisoformat(data["day"]),
        datetime.strptime(data["slot_time"], "%H:%M").time(),
        tzinfo=tz,
    )
    try:
        appt = await db.book_appointment(client, service, start_time)
    except SlotTakenError:
        await state.set_state(Booking.day)
        await callback.message.edit_text(
            t(lang, "slot_taken_retry"),
            reply_markup=kb.dates_kb(service.service_point, lang),
        )
        await callback.answer()
        return
    except BookingError:
        await state.set_state(Booking.day)
        await callback.message.edit_text(
            t(lang, "booking_failed_retry"),
            reply_markup=kb.dates_kb(service.service_point, lang),
        )
        await callback.answer()
        return
    await state.clear()
    await callback.message.edit_text(
        t(
            lang, "booked",
            service=svc_name(service, lang),
            date=f"{start_time:%d.%m.%Y}",
            time=f"{start_time:%H:%M}",
            bay=appt.bay.name,
            btn_my=t(lang, "btn_my"),
        )
    )
    # Адрес и точка на карте, чтобы клиент построил маршрут в один тап
    sp = service.service_point
    if sp.address:
        await callback.message.answer(t(lang, "our_address", address=sp.address))
    if sp.latitude is not None and sp.longitude is not None:
        await callback.message.answer_location(
            latitude=float(sp.latitude), longitude=float(sp.longitude)
        )
    await callback.answer(t(lang, "booking_created_toast"))


@router.callback_query(Booking.confirm, F.data == "ok:no")
async def decline_booking(callback: CallbackQuery, state: FSMContext):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(t(client.language, "booking_declined"))
    await callback.answer()


# ---------- мои записи ----------

@router.message(F.text.in_(btn_texts("btn_my")))
async def my_appointments(message: Message):
    client, _ = await db.get_or_create_client(message.from_user.id)
    lang = client.language
    appointments = await db.get_my_appointments(client)
    if not appointments:
        await message.answer(t(lang, "no_appointments"))
        return
    sp = await db.get_service_point()
    tz = ZoneInfo(sp.timezone) if sp else None
    lines = [t(lang, "my_header")]
    for a in appointments:
        a.start_time_local = a.start_time.astimezone(tz) if tz else a.start_time
        lines.append(
            f"• {a.start_time_local:%d.%m.%Y %H:%M} — {svc_name(a.service, lang)} ({a.bay.name})"
        )
    await message.answer(
        "\n".join(lines), reply_markup=kb.my_appointments_kb(appointments, lang)
    )


@router.callback_query(F.data.startswith("cxl:"))
async def cancel_appointment_cb(callback: CallbackQuery):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    try:
        appt = await db.cancel_my_appointment(callback.data.removeprefix("cxl:"), client)
    except BookingError as exc:
        await callback.answer(str(exc), show_alert=True)
        return
    if appt is None:
        await callback.answer(t(lang, "appt_not_found"), show_alert=True)
        return
    await callback.message.edit_text(
        t(lang, "appt_cancelled", service=svc_name(appt.service, lang))
    )
    await callback.answer(t(lang, "cancelled_toast"))


# ---------- fallback ----------

@router.message()
async def fallback(message: Message):
    client, _ = await db.get_or_create_client(message.from_user.id)
    lang = client.language
    await message.answer(t(lang, "fallback"), reply_markup=kb.main_menu(lang))
