"""
Отправка созревших уведомлений: python manage.py send_due_notifications

Запускается по cron раз в 2–5 минут. Идемпотентна и безопасна при
параллельном запуске:
- строки выбираются с select_for_update(skip_locked=True) — второй
  одновременный запуск просто пропустит уже захваченные;
- уведомление помечается sent ДО фактической отправки (при ошибке
  откатывается в failed). Это осознанный выбор: при аварии между коммитом
  и отправкой напоминание может потеряться, но НЕ может уйти дважды.
"""
import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Appointment, Notification

BATCH_LIMIT = 200  # за один прогон; следующий cron-запуск доберёт остальное


class Command(BaseCommand):
    help = "Отправляет уведомления со status=pending и scheduled_for <= now"

    def handle(self, *args, **options):
        if not settings.BOT_TOKEN:
            raise CommandError("BOT_TOKEN не задан в .env — отправка невозможна.")
        from bot import notify  # импорт здесь, чтобы команда падала понятной ошибкой выше

        now = timezone.now()
        batch: list[tuple[Notification, int, str]] = []

        with transaction.atomic():
            due = list(
                Notification.objects.select_for_update(skip_locked=True, of=("self",))
                .select_related(
                    "appointment__client",
                    "appointment__service__service_point",
                )
                .filter(status=Notification.Status.PENDING, scheduled_for__lte=now)
                .order_by("scheduled_for")[:BATCH_LIMIT]
            )
            for n in due:
                appt = n.appointment
                # Запись уже отменена/завершена — напоминать не о чем
                if appt.status not in Appointment.ACTIVE_STATUSES:
                    n.status = Notification.Status.CANCELLED
                    n.save(update_fields=["status", "updated_at"])
                    continue
                text = notify.build_text(n)
                if not appt.client.telegram_id or text is None:
                    n.status = Notification.Status.FAILED
                    n.save(update_fields=["status", "updated_at"])
                    continue
                # Оптимистично помечаем отправленным (см. докстринг)
                n.status = Notification.Status.SENT
                n.sent_at = now
                n.save(update_fields=["status", "sent_at", "updated_at"])
                batch.append((n, appt.client.telegram_id, text))

        if not batch:
            self.stdout.write("Нет уведомлений к отправке.")
            return

        results = asyncio.run(
            notify.deliver([(str(n.id), tg_id, text) for n, tg_id, text in batch])
        )

        sent = failed = 0
        for n, _, _ in batch:
            error = results.get(str(n.id))
            if error:
                Notification.objects.filter(pk=n.pk).update(
                    status=Notification.Status.FAILED, sent_at=None
                )
                failed += 1
                self.stderr.write(f"failed {n.id}: {error}")
            else:
                sent += 1

        self.stdout.write(self.style.SUCCESS(f"Отправлено: {sent}, ошибок: {failed}."))
