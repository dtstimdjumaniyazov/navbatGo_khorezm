"""
Тексты бота на русском и узбекском (кириллица).
t(lang, key, **kwargs) — получить строку; svc_name(service, lang) — название услуги.
"""
from core.models import Service, ServicePoint

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
        "onboard_msg": (
            "📖 Как пользоваться:\n"
            "1️⃣ Нажмите «📝 Записаться» и выберите автосервис\n"
            "2️⃣ Выберите удобную услугу и время\n"
            "3️⃣ Мы напомним о записи заранее — прямо здесь, в Telegram"
        ),
        "legal_links": "📄 Оферта: {oferta}\n🔒 Политика конфиденциальности: {privacy}",
        "btn_book": "📝 Записаться",
        "btn_my": "📋 Мои записи",
        "btn_about": "ℹ️ О сервисе",
        "btn_language": "🌐 Язык · Тил",
        "btn_partner": "🏪 Хочу подключить автосервис",
        "partner_contact_msg": "Напишите нам, и мы поможем подключить ваш автосервис к NavbatGo: {url}",
        "partner_not_configured": "Контакт для подключения автосервисов пока не настроен — попробуйте позже.",
        "choose_point": "Выберите автосервис:",
        "btn_back": "◀️ Назад",
        "login_confirmed": "✅ Вход подтверждён. Вернитесь в приложение NavbatGo.",
        "about_exp": "Стаж: {years} лет",
        "about_videos": "🎬 Видео от сервиса:",
        "about_hours": "🕒 График работы:",
        "closed_day": "выходной",
        "about_bio": "О себе: {bio}",
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
        "notif_cancelled": (
            "❌ Ваша запись на «{service}» {when} отменена сервисом. "
            "Приносим извинения — вы можете записаться на другое время."
        ),
        "notif_cancelled_reason": (
            "❌ Ваша запись на «{service}» {when} отменена сервисом.\n"
            "Причина: {reason}\n"
            "Приносим извинения — вы можете записаться на другое время."
        ),
        # --- Режим мастера (пока только RU; uz возьмётся отсюда по fallback) ---
        "m_notif_new": "🆕 Новая запись: {when} · {service} · {client}{phone} · {bay}",
        "m_notif_client_cancelled": "❌ Клиент отменил запись: {when} · {service} · {client}",
        "m_menu": "🔧 {name}\n📅 Сегодня: записей — {count}, в работе — {in_progress}",
        "m_onboard_msg": (
            "📖 Коротко о боте:\n"
            "📅 «Сегодня» — вся очередь дня и что происходит на постах сейчас\n"
            "✅ Одной кнопкой отмечайте «Начал», «Готово», «Не приехал»\n"
            "➕ «Записать с улицы» — быстро добавить клиента вручную"
        ),
        "m_btn_today": "📅 Сегодня",
        "m_btn_tomorrow": "Завтра ▶️",
        "m_btn_now": "⏱ Текущая запись",
        "m_btn_menu": "🏠 Меню",
        "m_day_header": "📅 {date}",
        "m_day_empty": "На {date} записей нет.",
        "m_no_current": "Сейчас нет текущих и ближайших записей.",
        "m_not_found": "Запись не найдена.",
        "m_client_line": "👤 {name}",
        "m_no_show_badge": "⚠️ Неявок: {n}",
        "m_bay_time_line": "📍 {bay} · {date} {start}–{end}",
        "m_status_line": "Статус: {emoji} {status}",
        "m_source_line": "Источник: {source}",
        "m_source_telegram": "Telegram",
        "m_source_manual": "вручную",
        "m_source_app": "приложение",
        "m_btn_language": "🌐 Язык · Тил",
        "m_lang_choose": "Выберите язык / Тилни танланг:",
        "m_lang_saved": "✅ Язык сохранён.",
        "m_btn_start": "▶️ Начал",
        "m_btn_finish": "✅ Завершил",
        "m_btn_noshow": "⚠️ Не приехал",
        "m_btn_cancel_appt": "❌ Отменить",
        "m_btn_back_day": "◀️ К списку",
        "m_btn_yes": "✅ Да",
        "m_btn_no": "◀️ Назад",
        "m_confirm_cancel": "Точно отменить запись: {client}, {time}?",
        "m_confirm_noshow": "Отметить, что {client} ({time}) не приехал? Счётчик неявок клиента вырастет.",
        "m_cancel_reason_prompt": "Укажите причину отмены — она уйдёт клиенту в Telegram (отправьте сообщением):",
        "m_cancel_reason_empty": "Причина не может быть пустой. Напишите, почему отменяете запись:",
        "m_cancel_aborted": "Отмена записи прервана.",
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
        "onboard_msg": (
            "📖 Қандай фойдаланиш:\n"
            "1️⃣ «📝 Ёзилиш» тугмасини босинг ва автосервисни танланг\n"
            "2️⃣ Қулай хизмат ва вақтни танланг\n"
            "3️⃣ Ёзув ҳақида олдиндан шу ерда, Telegram’да эслатамиз"
        ),
        "legal_links": "📄 Оферта: {oferta}\n🔒 Махфийлик сиёсати: {privacy}",
        "btn_book": "📝 Ёзилиш",
        "btn_my": "📋 Менинг ёзувларим",
        "btn_about": "ℹ️ Сервис ҳақида",
        "btn_language": "🌐 Тил · Язык",
        "btn_partner": "🏪 Автосервисимни улашни хоҳлайман",
        "partner_contact_msg": "Бизга ёзинг, автосервисингизни NavbatGo'га улашга ёрдам берамиз: {url}",
        "partner_not_configured": "Автосервисларни улаш учун алоқа ҳали созланмаган — кейинроқ уриниб кўринг.",
        "choose_point": "Автосервисни танланг:",
        "btn_back": "◀️ Орқага",
        "login_confirmed": "✅ Кириш тасдиқланди. NavbatGo иловасига қайтинг.",
        "about_exp": "Тажриба: {years} йил",
        "about_videos": "🎬 Сервис видеоси:",
        "about_hours": "🕒 Иш вақти:",
        "closed_day": "дам олиш",
        "about_bio": "Ўзи ҳақида: {bio}",
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
        "notif_cancelled": (
            "❌ Сизнинг «{service}» хизматига {when} ёзувингиз сервис томонидан "
            "бекор қилинди. Узр сўраймиз — бошқа вақтга ёзилишингиз мумкин."
        ),
        "notif_cancelled_reason": (
            "❌ Сизнинг «{service}» хизматига {when} ёзувингиз сервис томонидан "
            "бекор қилинди.\nСабаби: {reason}\n"
            "Узр сўраймиз — бошқа вақтга ёзилишингиз мумкин."
        ),
        # --- Режим мастера (ўзбекча) ---
        "m_notif_new": "🆕 Янги ёзув: {when} · {service} · {client}{phone} · {bay}",
        "m_notif_client_cancelled": "❌ Мижоз ёзувни бекор қилди: {when} · {service} · {client}",
        "m_menu": "🔧 {name}\n📅 Бугун: ёзувлар — {count}, ишда — {in_progress}",
        "m_onboard_msg": (
            "📖 Бот ҳақида қисқача:\n"
            "📅 «Бугун» — куннинг барча навбати ва ҳозир постларда нима бўляпти\n"
            "✅ Бир тугма билан «Бошладим», «Тайёр», «Келмади» деб белгиланг\n"
            "➕ «Кўчадан ёзиш» — мижозни қўлда тезда қўшинг"
        ),
        "m_btn_today": "📅 Бугун",
        "m_btn_tomorrow": "Эртага ▶️",
        "m_btn_now": "⏱ Жорий ёзув",
        "m_btn_menu": "🏠 Меню",
        "m_day_header": "📅 {date}",
        "m_day_empty": "{date} куни ёзувлар йўқ.",
        "m_no_current": "Ҳозир жорий ва яқин ёзувлар йўқ.",
        "m_not_found": "Ёзув топилмади.",
        "m_client_line": "👤 {name}",
        "m_no_show_badge": "⚠️ Келмаганлар: {n}",
        "m_bay_time_line": "📍 {bay} · {date} {start}–{end}",
        "m_status_line": "Ҳолат: {emoji} {status}",
        "m_source_line": "Манба: {source}",
        "m_source_telegram": "Telegram",
        "m_source_manual": "қўлда",
        "m_source_app": "илова",
        "m_btn_language": "🌐 Тил · Язык",
        "m_lang_choose": "Тилни танланг / Выберите язык:",
        "m_lang_saved": "✅ Тил сақланди.",
        "m_btn_start": "▶️ Бошладим",
        "m_btn_finish": "✅ Тугатдим",
        "m_btn_noshow": "⚠️ Келмади",
        "m_btn_cancel_appt": "❌ Бекор қилиш",
        "m_btn_back_day": "◀️ Рўйхатга",
        "m_btn_yes": "✅ Ҳа",
        "m_btn_no": "◀️ Орқага",
        "m_confirm_cancel": "Ёзув бекор қилинсинми: {client}, {time}?",
        "m_confirm_noshow": (
            "{client} ({time}) келмади деб белгилансинми? Мижознинг келмаганлар "
            "ҳисобчиси ошади."
        ),
        "m_cancel_reason_prompt": (
            "Бекор қилиш сабабини ёзинг — у мижозга Telegram орқали юборилади "
            "(хабар қилиб юборинг):"
        ),
        "m_cancel_reason_empty": "Сабаб бўш бўлиши мумкин эмас. Нима учун бекор қилаётганингизни ёзинг:",
        "m_cancel_aborted": "Ёзувни бекор қилиш тўхтатилди.",
        "m_extend_ok": "⏱ {time} гача узайтирилди.",
        "m_extend_conflict": (
            "⏱ +{min} дақиқа узайтириш пост ёзувларига тўғри келади "
            "(таъсирланади: {n}). Навбат сурилсинми?"
        ),
        "m_btn_extend": "⏱ +{min} дақ.",
        "m_btn_shift": "⏩ Суриш +{min}",
        "m_shift_confirm": (
            "⏩ {n} та ёзув +{min} дақиқага сурилиб, мижозларга Telegram орқали "
            "хабар юборилсинми?"
        ),
        "m_shift_done": "⏩ Сурилди: {n}. Хабар юборилди: {sent}, етказилмади: {failed}.",
        "m_shift_nothing": "Бу ёзувдан кейин постда бўш — суришга ҳожат йўқ.",
        "m_action_done": "Тайёр",
        "m_fallback": "Уста менюси:",
        "m_btn_add": "➕ Кўчадан ёзиш",
        "m_add_bay": "Қайси постга?",
        "m_add_service": "Қайси хизмат?",
        "m_add_day": "Қайси кунга?",
        "m_add_time": "{bay}, {date} — бўш вақт:",
        "m_add_no_slots": "Бу куни «{bay}» постида бўш вақт йўқ. Бошқа кунни танланг:",
        "m_add_name": "Мижоз исми? (хабар қилиб юборинг)",
        "m_add_phone": "Мижоз телефони? Рақам юборинг ёки «Ўтказиб юбориш»ни босинг.",
        "m_btn_skip": "Ўтказиб юбориш",
        "m_btn_abort": "❌ Бекор қилиш",
        "m_add_done": "✅ Ёзилди!\n\n👤 {client}\n🔧 {service}\n📍 {bay} · {date} соат {time}",
        "m_add_slot_taken": "⚠️ Бу вақт ҳозиргина банд бўлди. Бошқасини танланг:",
        "m_add_aborted": "Қўшиш бекор қилинди.",
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


def sp_address(sp: ServicePoint, lang: str) -> str:
    """Адрес автосервиса на языке клиента; fallback на русский, если перевода нет."""
    if lang == "uz" and sp.address_uz:
        return sp.address_uz
    return sp.address


def legal_urls(lang: str) -> dict[str, str]:
    """Ссылки на публичную оферту/политику конфиденциальности на языке клиента."""
    from django.conf import settings

    suffix = "uz/" if lang == "uz" else ""
    return {
        "oferta": f"{settings.SITE_URL}/legal/oferta/{suffix}",
        "privacy": f"{settings.SITE_URL}/legal/privacy/{suffix}",
    }


def loc(lang: str, ru_text: str, uz_text: str) -> str:
    """
    Локализованное поле данных (описание, адрес, био): uz-вариант,
    если выбран узбекский и перевод заполнен, иначе — русский.
    """
    return uz_text if lang == "uz" and uz_text else ru_text


def btn_texts(key: str) -> set[str]:
    """Все языковые варианты кнопки — для матчинга reply-клавиатуры в хендлерах."""
    return {TEXTS[lang][key] for lang in LANGS}
