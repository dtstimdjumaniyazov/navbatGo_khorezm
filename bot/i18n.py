"""
Тексты бота на русском и узбекском (кириллица).
t(lang, key, **kwargs) — получить строку; svc_name(service, lang) — название услуги.
"""
from core.models import Service

TEXTS = {
    "ru": {
        "choose_language": "Тилни танланг / Выберите язык:",
        "language_saved": "Язык сохранён ✅",
        "ask_name": "Здравствуйте! Это бот записи в автосервис.\nКак вас зовут?",
        "welcome_back": "С возвращением, {name}!",
        "ask_phone": "Оставьте номер телефона, чтобы мастер мог связаться с вами:",
        "btn_send_phone": "📱 Отправить номер",
        "btn_skip": "Пропустить",
        "registered": "Готово! Теперь можно записаться. 👇",
        "btn_book": "📝 Записаться",
        "btn_my": "📋 Мои записи",
        "btn_language": "🌐 Язык · Тил",
        "no_services": "Пока нет доступных услуг, загляните позже.",
        "choose_service": "Выберите услугу:",
        "service_line": "Услуга: {name}",
        "flexible_hint": "\n\nℹ️ Длительность оценочная: это запись на осмотр, время работы может измениться.",
        "choose_day": "Выберите день:",
        "btn_back_services": "◀️ Назад к услугам",
        "btn_back_dates": "◀️ Другая дата",
        "today": "Сегодня",
        "tomorrow": "Завтра",
        "weekdays": ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"],
        "no_slots": "На этот день свободных мест нет 😔",
        "free_time": "{service}, {date}\nСвободное время:",
        "check_booking": "Проверьте запись:\n\n🔧 {service}\n📅 {date} в {time}\n⏱ ~{duration} мин{price}",
        "price_line": "\nЦена: {price} сум",
        "btn_confirm": "✅ Подтвердить",
        "btn_cancel": "❌ Отмена",
        "booked": (
            "✅ Вы записаны!\n\n🔧 {service}\n📅 {date} в {time}\n📍 {bay}\n\n"
            "Приезжайте к назначенному времени. Если планы изменятся — "
            "отмените запись в «{btn_my}»."
        ),
        "our_address": "🏠 Наш адрес: {address}",
        "booking_declined": "Запись отменена. Возвращайтесь, когда будет удобно!",
        "slot_taken_retry": "⚠️ Это время только что заняли, выберите другой слот.\n\nВыберите другой день:",
        "booking_failed_retry": "⚠️ Не получилось записаться на это время.\n\nВыберите другой день:",
        "my_header": "Ваши записи:\n",
        "no_appointments": "У вас нет активных записей.",
        "btn_cancel_appt": "❌ Отменить {date} — {service}",
        "appt_cancelled": "❌ Запись «{service}» отменена.",
        "appt_not_found": "Запись не найдена.",
        "restart": "Начните заново: /start",
        "fallback": "Выберите действие на клавиатуре ниже 👇",
        "booking_created_toast": "Запись создана!",
        "cancelled_toast": "Отменено",
        # Уведомления (напоминание, сдвиг очереди)
        "when_today": "сегодня в {time}",
        "when_date": "{date} в {time}",
        "notif_address": "\n📍 Адрес: {address}",
        "notif_reminder": "🔔 Напоминаем: вы записаны на «{service}» {when}.{address}",
        "notif_shifted": (
            "⏰ Из-за задержки в сервисе время вашей записи «{service}» изменилось. "
            "Новое время: {when}. Приносим извинения за неудобства!"
        ),
        # --- Режим мастера (пока только RU; uz возьмётся отсюда по fallback) ---
        "m_menu": "🔧 {name}\n📅 Сегодня: записей — {count}, в работе — {in_progress}",
        "m_btn_today": "📅 Сегодня",
        "m_btn_tomorrow": "Завтра ▶️",
        "m_btn_now": "⏱ Текущая запись",
        "m_btn_menu": "🏠 Меню",
        "m_day_header": "📅 {date}",
        "m_day_empty": "На {date} записей нет.",
        "m_no_current": "Сейчас нет текущих и ближайших записей.",
        "m_not_found": "Запись не найдена.",
        "m_client_line": "👤 {name}",
        "m_bay_time_line": "📍 {bay} · {date} {start}–{end}",
        "m_status_line": "Статус: {emoji} {status}",
        "m_source_line": "Источник: {source}",
        "m_source_telegram": "Telegram",
        "m_source_manual": "вручную",
        "m_btn_start": "▶️ Начал",
        "m_btn_finish": "✅ Завершил",
        "m_btn_noshow": "⚠️ Не приехал",
        "m_btn_cancel_appt": "❌ Отменить",
        "m_btn_back_day": "◀️ К списку",
        "m_btn_yes": "✅ Да",
        "m_btn_no": "◀️ Назад",
        "m_confirm_cancel": "Точно отменить запись: {client}, {time}?",
        "m_confirm_noshow": "Отметить, что {client} ({time}) не приехал? Счётчик неявок клиента вырастет.",
        "m_extend_ok": "⏱ Продлено до {time}.",
        "m_extend_conflict": (
            "⏱ Продление на +{min} мин наезжает на записи поста (затронется: {n}). "
            "Сдвинуть очередь?"
        ),
        "m_btn_extend": "⏱ +{min} мин",
        "m_btn_shift": "⏩ Сдвинуть +{min}",
        "m_shift_confirm": (
            "⏩ Сдвинуть {n} запис. на +{min} мин и уведомить клиентов в Telegram?"
        ),
        "m_shift_done": "⏩ Сдвинуто: {n}. Уведомлено: {sent}, не доставлено: {failed}.",
        "m_shift_nothing": "После этой записи на посту пусто — сдвигать нечего.",
        "m_action_done": "Готово",
        "m_fallback": "Меню мастера:",
        # --- «Записать с улицы» ---
        "m_btn_add": "➕ Записать с улицы",
        "m_add_bay": "На какой пост?",
        "m_add_service": "Какая услуга?",
        "m_add_day": "На какой день?",
        "m_add_time": "{bay}, {date} — свободное время:",
        "m_add_no_slots": "На этот день у поста «{bay}» нет свободных слотов. Выберите другой день:",
        "m_add_name": "Имя клиента? (отправьте сообщением)",
        "m_add_phone": "Телефон клиента? Отправьте номер или нажмите «Пропустить».",
        "m_btn_skip": "Пропустить",
        "m_btn_abort": "❌ Отмена",
        "m_add_done": "✅ Записано!\n\n👤 {client}\n🔧 {service}\n📍 {bay} · {date} в {time}",
        "m_add_slot_taken": "⚠️ Это время только что заняли. Выберите другое:",
        "m_add_aborted": "Добавление отменено.",
    },
    "uz": {
        "choose_language": "Тилни танланг / Выберите язык:",
        "language_saved": "Тил сақланди ✅",
        "ask_name": "Ассалому алайкум! Бу автосервисга ёзилиш боти.\nИсмингиз нима?",
        "welcome_back": "Хуш келибсиз, {name}!",
        "ask_phone": "Уста сиз билан боғланиши учун телефон рақамингизни қолдиринг:",
        "btn_send_phone": "📱 Рақамни юбориш",
        "btn_skip": "Ўтказиб юбориш",
        "registered": "Тайёр! Энди ёзилишингиз мумкин. 👇",
        "btn_book": "📝 Ёзилиш",
        "btn_my": "📋 Менинг ёзувларим",
        "btn_language": "🌐 Тил · Язык",
        "no_services": "Ҳозирча хизматлар йўқ, кейинроқ қайтиб кўринг.",
        "choose_service": "Хизматни танланг:",
        "service_line": "Хизмат: {name}",
        "flexible_hint": "\n\nℹ️ Давомийлик тахминий: бу кўрикка ёзилиш, иш вақти ўзгариши мумкин.",
        "choose_day": "Кунни танланг:",
        "btn_back_services": "◀️ Хизматларга қайтиш",
        "btn_back_dates": "◀️ Бошқа кун",
        "today": "Бугун",
        "tomorrow": "Эртага",
        "weekdays": ["Душ", "Сеш", "Чор", "Пай", "Жум", "Шан", "Якш"],
        "no_slots": "Бу кунга бўш жой йўқ 😔",
        "free_time": "{service}, {date}\nБўш вақтлар:",
        "check_booking": "Ёзувни текширинг:\n\n🔧 {service}\n📅 {date}, соат {time}\n⏱ ~{duration} дақиқа{price}",
        "price_line": "\nНархи: {price} сўм",
        "btn_confirm": "✅ Тасдиқлаш",
        "btn_cancel": "❌ Бекор қилиш",
        "booked": (
            "✅ Сиз ёзилдингиз!\n\n🔧 {service}\n📅 {date}, соат {time}\n📍 {bay}\n\n"
            "Белгиланган вақтга келинг. Режалар ўзгарса — "
            "«{btn_my}» бўлимида ёзувни бекор қилинг."
        ),
        "our_address": "🏠 Бизнинг манзил: {address}",
        "booking_declined": "Ёзув бекор қилинди. Қулай вақтда қайтиб келинг!",
        "slot_taken_retry": "⚠️ Бу вақт ҳозиргина банд қилинди, бошқа вақтни танланг.\n\nБошқа кунни танланг:",
        "booking_failed_retry": "⚠️ Бу вақтга ёзиб бўлмади.\n\nБошқа кунни танланг:",
        "my_header": "Сизнинг ёзувларингиз:\n",
        "no_appointments": "Сизда фаол ёзувлар йўқ.",
        "btn_cancel_appt": "❌ Бекор қилиш: {date} — {service}",
        "appt_cancelled": "❌ «{service}» ёзуви бекор қилинди.",
        "appt_not_found": "Ёзув топилмади.",
        "restart": "Қайтадан бошланг: /start",
        "fallback": "Қуйидаги тугмалардан бирини танланг 👇",
        "booking_created_toast": "Ёзув яратилди!",
        "cancelled_toast": "Бекор қилинди",
        "when_today": "бугун соат {time} да",
        "when_date": "{date} куни соат {time} да",
        "notif_address": "\n📍 Манзил: {address}",
        "notif_reminder": "🔔 Эслатма: сиз «{service}» хизматига {when} ёзилгансиз.{address}",
        "notif_shifted": (
            "⏰ Сервисдаги кечикиш сабабли «{service}» ёзувингиз вақти ўзгарди. "
            "Янги вақт: {when}. Ноқулайлик учун узр сўраймиз!"
        ),
    },
}

DEFAULT_LANG = "ru"
LANGS = tuple(TEXTS.keys())


def t(lang: str, key: str, **kwargs) -> str:
    """Строка на языке клиента с подстановкой параметров."""
    text = TEXTS.get(lang, TEXTS[DEFAULT_LANG]).get(key, TEXTS[DEFAULT_LANG][key])
    return text.format(**kwargs) if kwargs else text


def weekdays(lang: str) -> list[str]:
    return TEXTS.get(lang, TEXTS[DEFAULT_LANG])["weekdays"]


def svc_name(service: Service, lang: str) -> str:
    """Название услуги на языке клиента; fallback на русское, если перевода нет."""
    if lang == "uz" and service.name_uz:
        return service.name_uz
    return service.name


def btn_texts(key: str) -> set[str]:
    """Все языковые варианты кнопки — для матчинга reply-клавиатуры в хендлерах."""
    return {TEXTS[lang][key] for lang in LANGS}
