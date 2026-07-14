"""Хендлеры бота: выбор языка, регистрация, запись на слот, мои записи, отмена."""
from datetime import date, datetime
from zoneinfo import ZoneInfo

from aiogram import F, Router
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    CallbackQuery,
    FSInputFile,
    InputMediaPhoto,
    Message,
    ReplyKeyboardRemove,
)
from django.conf import settings

from bot import db, keyboards as kb
from bot.i18n import LANGS, btn_texts, legal_urls, loc, sp_address, svc_name, t
from core.services.appointments import BookingError, SlotTakenError
from core.services.clients import normalize_phone

router = Router()


async def notify_masters(bot, service_point, key: str, **params) -> None:
    """
    Сообщить мастерам сервиса о событии (новая запись / отмена клиентом) —
    каждому на его языке и выбранном им канале (Telegram или push). Ошибка
    доставки одному мастеру не мешает остальным и не ломает сценарий клиента.
    """
    import asyncio

    from core.models import NotificationChannel
    from core.services.push import send_push

    for tg_id, m_lang, channel, push_token in await db.get_manager_notify_targets(service_point):
        text = t(m_lang or "ru", key, **params)
        if channel == NotificationChannel.PUSH:
            if push_token:
                await asyncio.to_thread(send_push, push_token, "NavbatGo", text)
            continue
        try:
            await bot.send_message(tg_id, text)
        except Exception:  # noqa: BLE001
            pass


class Registration(StatesGroup):
    language = State()
    name = State()
    phone = State()


class Booking(StatesGroup):
    service_point = State()  # выбор автосервиса (когда их больше одного)
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


@router.message(F.text.in_(btn_texts("btn_partner")))
async def become_partner(message: Message):
    client, _ = await db.get_or_create_client(message.from_user.id)
    lang = client.language
    if not settings.PARTNER_CONTACT_USERNAME:
        await message.answer(t(lang, "partner_not_configured"))
        return
    url = f"https://t.me/{settings.PARTNER_CONTACT_USERNAME}"
    await message.answer(t(lang, "partner_contact_msg", url=url))


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
        await db.update_client(
            client.id, phone=normalize_phone(message.contact.phone_number)[:32]
        )
    elif message.text and message.text not in btn_texts("btn_skip"):
        await db.update_client(client.id, phone=normalize_phone(message.text)[:32])
    await state.clear()
    await message.answer(t(lang, "registered"), reply_markup=kb.main_menu(lang))
    await message.answer(t(lang, "onboard_msg"))
    urls = legal_urls(lang)
    await message.answer(t(lang, "legal_links", oferta=urls["oferta"], privacy=urls["privacy"]))


# ---------- запись: сервис → услуга → дата → время → подтверждение ----------

async def _show_services(target: Message, state: FSMContext, sp, lang: str, edit: bool):
    """Список услуг выбранного сервиса (общий шаг обоих путей входа в запись)."""
    services = await db.get_active_services(sp)
    if not services:
        text = t(lang, "no_services")
        await (target.edit_text(text) if edit else target.answer(text))
        return
    await state.update_data(sp_id=str(sp.id))
    await state.set_state(Booking.service)
    text = t(lang, "choose_service")
    markup = kb.services_kb(services, lang)
    if edit:
        await target.edit_text(text, reply_markup=markup)
    else:
        await target.answer(text, reply_markup=markup)


@router.message(F.text.in_(btn_texts("btn_book")))
async def start_booking(message: Message, state: FSMContext):
    client, _ = await db.get_or_create_client(message.from_user.id)
    lang = client.language
    points = await db.get_service_points()
    if not points:
        await message.answer(t(lang, "no_services"))
        return
    if len(points) == 1:  # сервис один — не спрашиваем лишнего
        await _show_services(message, state, points[0], lang, edit=False)
        return
    await state.set_state(Booking.service_point)
    await message.answer(
        t(lang, "choose_point"), reply_markup=kb.service_points_kb(points, "bsp")
    )


@router.callback_query(Booking.service_point, F.data.startswith("bsp:"))
async def booking_choose_point(callback: CallbackQuery, state: FSMContext):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    sp = await db.get_service_point(callback.data.removeprefix("bsp:"))
    if sp is None:
        await callback.answer(t(lang, "restart"), show_alert=True)
        return
    await _show_services(callback.message, state, sp, lang, edit=True)
    await callback.answer()


@router.callback_query(F.data == "back:points")
async def back_to_points(callback: CallbackQuery, state: FSMContext):
    """«Назад» из списка услуг: к выбору сервиса или отмена записи."""
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    points = await db.get_service_points()
    if len(points) > 1:
        await state.set_state(Booking.service_point)
        await callback.message.edit_text(
            t(lang, "choose_point"), reply_markup=kb.service_points_kb(points, "bsp")
        )
    else:
        await state.clear()
        await callback.message.edit_text(t(lang, "booking_declined"))
    await callback.answer()


@router.callback_query(F.data == "back:services")
async def back_to_services(callback: CallbackQuery, state: FSMContext):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    data = await state.get_data()
    sp = await db.get_service_point(data.get("sp_id"))
    if sp is None:
        await callback.answer(t(lang, "restart"), show_alert=True)
        return
    await _show_services(callback.message, state, sp, lang, edit=True)
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
    schedule = await db.get_week_schedule(service.service_point)
    await callback.message.edit_text(
        t(lang, "service_line", name=svc_name(service, lang)) + hint + "\n\n" + t(lang, "choose_day"),
        reply_markup=kb.dates_kb(service.service_point, lang, schedule),
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
    schedule = await db.get_week_schedule(service.service_point)
    await callback.message.edit_text(
        t(lang, "choose_day"),
        reply_markup=kb.dates_kb(service.service_point, lang, schedule),
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
            reply_markup=kb.dates_kb(
                service.service_point, lang, await db.get_week_schedule(service.service_point)
            ),
        )
        await callback.answer()
        return
    except BookingError:
        await state.set_state(Booking.day)
        await callback.message.edit_text(
            t(lang, "booking_failed_retry"),
            reply_markup=kb.dates_kb(
                service.service_point, lang, await db.get_week_schedule(service.service_point)
            ),
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
    # Адрес и точка на карте одним сообщением (venue) — маршрут в один тап
    sp = service.service_point
    sp_address = loc(lang, sp.address, sp.address_uz)
    if sp.latitude is not None and sp.longitude is not None:
        await callback.message.answer_venue(
            latitude=float(sp.latitude),
            longitude=float(sp.longitude),
            title=sp.name,
            address=sp_address or sp.name,
        )
    elif sp_address:
        await callback.message.answer(t(lang, "our_address", address=sp_address))
    # Мастера узнают о новой записи сразу — каждый на своём языке
    await notify_masters(
        callback.bot,
        sp,
        "m_notif_new",
        when=f"{start_time:%d.%m %H:%M}",
        service=service.name,
        client=client.name or "Без имени",
        phone=f" · {client.phone}" if client.phone else "",
        bay=appt.bay.name,
    )
    await callback.answer(t(lang, "booking_created_toast"))


@router.callback_query(Booking.confirm, F.data == "ok:no")
async def decline_booking(callback: CallbackQuery, state: FSMContext):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    await state.clear()
    await callback.message.edit_text(t(client.language, "booking_declined"))
    await callback.answer()


# ---------- о сервисе (витрина для клиентов) ----------

@router.message(F.text.in_(btn_texts("btn_about")))
async def about_service(message: Message):
    client, _ = await db.get_or_create_client(message.from_user.id)
    lang = client.language
    points = await db.get_service_points()
    if not points:
        await message.answer(t(lang, "no_services"))
        return
    if len(points) == 1:
        await _send_service_profile(message, points[0], lang)
        return
    await message.answer(
        t(lang, "choose_point"), reply_markup=kb.service_points_kb(points, "absp")
    )


@router.callback_query(F.data.startswith("absp:"))
async def about_point(callback: CallbackQuery):
    client, _ = await db.get_or_create_client(callback.from_user.id)
    lang = client.language
    sp = await db.get_service_point(callback.data.removeprefix("absp:"))
    if sp is None:
        await callback.answer(t(lang, "restart"), show_alert=True)
        return
    await _send_service_profile(callback.message, sp, lang)
    await callback.answer()


async def _send_service_profile(message: Message, sp, lang: str):
    from bot.i18n import weekdays as wd

    profile = await db.get_service_profile(sp)
    desc = loc(lang, sp.description, sp.description_uz)
    address = loc(lang, sp.address, sp.address_uz)
    header = f"🔧 {sp.name}" + (f"\n\n{desc}" if desc else "")

    # 1) Фото сервиса альбомом; описание — подписью к первому фото.
    #    Нет фото — описание обычным сообщением.
    sent_header = False
    if profile["gallery"]:
        media = [
            InputMediaPhoto(
                media=FSInputFile(item["path"]),
                caption=header[:1024] if i == 0 else (item["caption"] or None),
            )
            for i, item in enumerate(profile["gallery"][:6])
        ]
        try:
            await message.answer_media_group(media)
            sent_header = True
        except Exception:  # noqa: BLE001 — галерея не должна ломать витрину
            pass
    if not sent_header:
        await message.answer(header)

    # 2) Адрес одним сообщением вместе с точкой на карте (venue);
    #    без координат — просто текстом
    if sp.latitude is not None and sp.longitude is not None:
        await message.answer_venue(
            latitude=float(sp.latitude),
            longitude=float(sp.longitude),
            title=sp.name,
            address=address or sp.name,
        )
    elif address:
        await message.answer(t(lang, "our_address", address=address))

    # 3) График по дням + Instagram
    schedule = await db.get_week_schedule(sp)
    day_names = wd(lang)
    hours_lines = [t(lang, "about_hours")]
    for entry in schedule:
        name = day_names[entry["weekday"]]
        if entry["start"] is None:
            hours_lines.append(f"{name}: {t(lang, 'closed_day')}")
        else:
            hours_lines.append(f"{name}: {entry['start']}–{entry['end']}")
    if sp.instagram:
        hours_lines.append(f"\n📸 Instagram: {sp.instagram}")
    await message.answer("\n".join(hours_lines))

    # 4) Видео работ
    if profile["videos"]:
        await message.answer(
            t(lang, "about_videos") + "\n" + "\n".join(profile["videos"][:5])
        )

    # 5) Карточки мастеров
    for m in profile["managers"]:
        bio = loc(lang, m["bio"], m["bio_uz"])
        parts = [
            m["name"],
            t(lang, "about_exp", years=m["experience_years"])
            if m["experience_years"] else "",
            t(lang, "about_bio", bio=bio) if bio else "",
        ]
        caption = "\n".join(p for p in parts if p)
        if m["avatar_path"]:
            try:
                await message.answer_photo(
                    FSInputFile(m["avatar_path"]), caption=caption[:1024]
                )
                continue
            except Exception:  # noqa: BLE001 — файл удалён/битый, покажем текст
                pass
        if caption:
            await message.answer(caption)


# ---------- мои записи ----------

@router.message(F.text.in_(btn_texts("btn_my")))
async def my_appointments(message: Message):
    client, _ = await db.get_or_create_client(message.from_user.id)
    lang = client.language
    appointments = await db.get_my_appointments(client)
    if not appointments:
        await message.answer(t(lang, "no_appointments"))
        return
    lines = [t(lang, "my_header")]
    for a in appointments:
        # время каждой записи — в поясе её сервиса (сервисов может быть несколько)
        sp = a.service.service_point
        tz = ZoneInfo(sp.timezone)
        a.start_time_local = a.start_time.astimezone(tz)
        address = sp_address(sp, lang)
        lines.append(
            f"• {a.start_time_local:%d.%m.%Y %H:%M} — {svc_name(a.service, lang)} ({a.bay.name})\n"
            f"  🔧 {sp.name}" + (f" · 📍 {address}" if address else "")
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
    # Мастера узнают об отмене сразу — слот освободился
    sp = appt.service.service_point
    local_start = appt.start_time.astimezone(ZoneInfo(sp.timezone))
    await notify_masters(
        callback.bot,
        sp,
        "m_notif_client_cancelled",
        when=f"{local_start:%d.%m %H:%M}",
        service=appt.service.name,
        client=client.name or "Без имени",
    )
    await callback.answer(t(lang, "cancelled_toast"))


# ---------- fallback ----------

@router.message()
async def fallback(message: Message):
    client, _ = await db.get_or_create_client(message.from_user.id)
    lang = client.language
    await message.answer(t(lang, "fallback"), reply_markup=kb.main_menu(lang))
