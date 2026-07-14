"""
Планирование уведомлений. Отложенная отправка — команда
send_due_notifications (по cron), немедленная — send_now() (сдвиг очереди).
Каждый клиент сам выбирает канал получения — Telegram или push в
приложении (Client.notification_channel) — здесь текст один и тот же,
меняется только способ доставки.
"""
import asyncio
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.models import Appointment, NotificationChannel, Notification


def schedule_reminder(appointment: Appointment) -> Notification | None:
    """
    Запланировать напоминание за reminder_hours_before до начала.
    Не создаётся, если клиенту некуда его доставить (не привязан Telegram и
    нет push-токена — например, записан мастером «с улицы») или окно
    напоминания уже прошло (клиент записался ближе, чем за N часов).
    """
    if not appointment.client.telegram_id and not appointment.client.push_token:
        return None
    sp = appointment.service.service_point
    scheduled_for = appointment.start_time - timedelta(hours=sp.reminder_hours_before)
    if scheduled_for <= timezone.now():
        return None
    return Notification.objects.create(
        appointment=appointment,
        notification_type=Notification.Type.REMINDER,
        scheduled_for=scheduled_for,
    )


def cancel_pending_notifications(appointment: Appointment) -> int:
    """Погасить неотправленные уведомления записи (при отмене/no_show)."""
    return appointment.notifications.filter(
        status=Notification.Status.PENDING
    ).update(status=Notification.Status.CANCELLED)


def client_channel_ready(client) -> bool:
    """Есть ли у клиента способ доставки на выбранном им канале."""
    if client.notification_channel == NotificationChannel.PUSH:
        return bool(client.push_token)
    return bool(client.telegram_id)


def dispatch_batch(prepared: list[tuple[Notification, str]]) -> dict:
    """
    Разослать уже подготовленные (Notification, текст) по каналу получателя:
    Telegram — одним batch-запросом (как раньше), push — по одному через Expo.
    Notification.status к этому моменту уже оптимистично выставлен в SENT
    вызывающей стороной (см. send_now/send_due_notifications); при ошибке
    откатывается в FAILED. Возвращает {'sent', 'failed'}.
    """
    from bot import notify  # ленивый импорт: core не тянет aiogram без нужды
    from core.services.push import send_push

    telegram_batch: list[tuple[str, int, str]] = []
    push_items: list[tuple[Notification, str, str]] = []
    for n, text in prepared:
        client = n.appointment.client
        if client.notification_channel == NotificationChannel.PUSH:
            push_items.append((n, client.push_token, text))
        else:
            telegram_batch.append((str(n.pk), client.telegram_id, text))

    sent = failed = 0
    if telegram_batch:
        results = asyncio.run(notify.deliver(telegram_batch))
        for nid, error in results.items():
            if error:
                Notification.objects.filter(pk=nid).update(
                    status=Notification.Status.FAILED, sent_at=None
                )
                failed += 1
            else:
                sent += 1
    for n, token, text in push_items:
        if send_push(token, title="NavbatGo", body=text):
            sent += 1
        else:
            Notification.objects.filter(pk=n.pk).update(
                status=Notification.Status.FAILED, sent_at=None
            )
            failed += 1
    return {"sent": sent, "failed": failed}


def send_now(notifications: list[Notification]) -> dict:
    """
    Немедленная отправка (сдвиг очереди — клиент должен узнать сразу).
    Та же дисциплина, что в send_due_notifications: пометка sent до отправки,
    ошибка одного сообщения не мешает остальным. Возвращает {'sent', 'failed'}.
    Вызывать после коммита транзакции, создавшей уведомления.
    """
    from bot import notify  # ленивый импорт: core не тянет aiogram без нужды

    if not notifications:
        return {"sent": 0, "failed": 0}
    if not settings.BOT_TOKEN:
        Notification.objects.filter(pk__in=[n.pk for n in notifications]).update(
            status=Notification.Status.FAILED
        )
        return {"sent": 0, "failed": len(notifications)}

    now = timezone.now()
    prepared: list[tuple[Notification, str]] = []
    failed = 0
    for n in notifications:
        # build_text читает связи — подгружаем одним запросом на уведомление
        n = Notification.objects.select_related(
            "appointment__client", "appointment__service__service_point"
        ).get(pk=n.pk)
        text = notify.build_text(n)
        if text is None or not client_channel_ready(n.appointment.client):
            n.status = Notification.Status.FAILED
            n.save(update_fields=["status", "updated_at"])
            failed += 1
            continue
        n.status = Notification.Status.SENT
        n.sent_at = now
        n.save(update_fields=["status", "sent_at", "updated_at"])
        prepared.append((n, text))

    result = dispatch_batch(prepared) if prepared else {"sent": 0, "failed": 0}
    result["failed"] += failed
    return result
