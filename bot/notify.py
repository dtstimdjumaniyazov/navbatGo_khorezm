"""
Единый модуль отправки уведомлений в Telegram.
Используется командой send_due_notifications (напоминания по cron)
и сдвигом очереди (этап 3, часть B). Тексты — в bot/i18n.py.
"""
import logging
from zoneinfo import ZoneInfo

from aiogram import Bot
from django.conf import settings
from django.utils import timezone

from bot.i18n import svc_name, t
from core.models import Notification

logger = logging.getLogger(__name__)


def build_text(notification: Notification) -> str | None:
    """Текст уведомления на языке клиента. None — неизвестный тип."""
    appt = notification.appointment
    lang = appt.client.language
    sp = appt.service.service_point
    tz = ZoneInfo(sp.timezone)
    local = appt.start_time.astimezone(tz)

    if local.date() == timezone.now().astimezone(tz).date():
        when = t(lang, "when_today", time=f"{local:%H:%M}")
    else:
        when = t(lang, "when_date", date=f"{local:%d.%m}", time=f"{local:%H:%M}")
    service = svc_name(appt.service, lang)

    if notification.notification_type == Notification.Type.REMINDER:
        address = t(lang, "notif_address", address=sp.address) if sp.address else ""
        return t(lang, "notif_reminder", service=service, when=when, address=address)
    if notification.notification_type == Notification.Type.SHIFTED:
        return t(lang, "notif_shifted", service=service, when=when)
    return None


async def deliver(batch: list[tuple[str, int, str]]) -> dict[str, str | None]:
    """
    Отправить пачку сообщений: [(notification_id, telegram_id, text), ...].
    Возвращает {notification_id: None при успехе | текст ошибки}.
    Ошибка одного сообщения (клиент заблокировал бота, чат недоступен)
    не прерывает отправку остальных.
    """
    results: dict[str, str | None] = {}
    bot = Bot(token=settings.BOT_TOKEN)
    try:
        for notification_id, telegram_id, text in batch:
            try:
                await bot.send_message(telegram_id, text)
                results[notification_id] = None
            except Exception as exc:  # noqa: BLE001 — любая ошибка = failed, идём дальше
                logger.warning("Не отправлено %s (tg %s): %s", notification_id, telegram_id, exc)
                results[notification_id] = str(exc)
    finally:
        await bot.session.close()
    return results
