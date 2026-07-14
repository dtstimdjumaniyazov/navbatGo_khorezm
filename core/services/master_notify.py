"""
Мгновенные уведомления мастерам о действиях клиентов из приложения/сайта
(новая запись, отмена). Для бронирований через бота то же самое делает
bot/handlers.notify_masters — там уже есть живой bot. Каждый мастер сам
выбирает канал — Telegram или push (ServiceManager.notification_channel).

Шлём напрямую, без очереди Notification: получатель — мастер, а очередь
спроектирована под клиентские уведомления. Ошибки доставки не ломают
сценарий клиента (каждое сообщение отправляется независимо от остальных).
"""
import asyncio
import logging
from zoneinfo import ZoneInfo

from django.conf import settings

from core.models import Appointment, NotificationChannel, ServiceManager

logger = logging.getLogger(__name__)


def _send_to_masters(appt: Appointment, key: str, **params) -> None:
    """Разослать событие мастерам сервиса — каждому на его языке и канале."""
    from bot.i18n import t

    sp = appt.service.service_point
    targets = list(
        ServiceManager.objects.filter(service_point=sp, is_active=True).values_list(
            "telegram_id", "language", "notification_channel", "push_token"
        )
    )
    if not targets:
        return

    telegram_batch = []
    push_targets = []
    for tg_id, lang, channel, push_token in targets:
        text = t(lang or "ru", key, **params)
        if channel == NotificationChannel.PUSH:
            if push_token:
                push_targets.append((push_token, text))
        elif tg_id:
            telegram_batch.append((f"master-{tg_id}", tg_id, text))

    if telegram_batch and settings.BOT_TOKEN:
        from bot import notify  # ленивый импорт: core не тянет aiogram без нужды

        try:
            asyncio.run(notify.deliver(telegram_batch))
        except Exception as exc:  # noqa: BLE001 — уведомление не должно ломать запись
            logger.warning("Уведомление мастерам не отправлено: %s", exc)

    if push_targets:
        from core.services.push import send_push

        for token, text in push_targets:
            send_push(token, title="NavbatGo", body=text)


def _when(appt: Appointment) -> str:
    tz = ZoneInfo(appt.service.service_point.timezone)
    return f"{appt.start_time.astimezone(tz):%d.%m %H:%M}"


def notify_masters_new(appt: Appointment) -> None:
    _send_to_masters(
        appt, "m_notif_new",
        when=_when(appt),
        service=appt.service.name,
        client=appt.client.name or "Без имени",
        phone=f" · {appt.client.phone}" if appt.client.phone else "",
        bay=appt.bay.name,
    )


def notify_masters_cancelled(appt: Appointment) -> None:
    _send_to_masters(
        appt, "m_notif_client_cancelled",
        when=_when(appt),
        service=appt.service.name,
        client=appt.client.name or "Без имени",
    )
