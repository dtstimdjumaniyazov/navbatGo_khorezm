"""
Планирование уведомлений. Отложенная отправка — команда
send_due_notifications (по cron), немедленная — send_now() (сдвиг очереди).
"""
import asyncio
from datetime import timedelta

from django.conf import settings
from django.utils import timezone

from core.models import Appointment, Notification


def schedule_reminder(appointment: Appointment) -> Notification | None:
    """
    Запланировать напоминание за reminder_hours_before до начала.
    Не создаётся, если у клиента нет Telegram (записан мастером «с улицы»)
    или окно напоминания уже прошло (клиент записался ближе, чем за N часов —
    напоминать сразу после записи бессмысленно).
    """
    if not appointment.client.telegram_id:
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
    batch: list[tuple[str, int, str]] = []
    failed = 0
    for n in notifications:
        # build_text читает связи — подгружаем одним запросом на уведомление
        n = Notification.objects.select_related(
            "appointment__client", "appointment__service__service_point"
        ).get(pk=n.pk)
        text = notify.build_text(n)
        if text is None or not n.appointment.client.telegram_id:
            n.status = Notification.Status.FAILED
            n.save(update_fields=["status", "updated_at"])
            failed += 1
            continue
        n.status = Notification.Status.SENT
        n.sent_at = now
        n.save(update_fields=["status", "sent_at", "updated_at"])
        batch.append((str(n.pk), n.appointment.client.telegram_id, text))

    sent = 0
    if batch:
        results = asyncio.run(notify.deliver(batch))
        for nid, error in results.items():
            if error:
                Notification.objects.filter(pk=nid).update(
                    status=Notification.Status.FAILED, sent_at=None
                )
                failed += 1
            else:
                sent += 1
    return {"sent": sent, "failed": failed}
