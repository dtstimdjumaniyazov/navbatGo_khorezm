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
from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from core.models import Appointment, Notification
from core.services.notifications import client_channel_ready, dispatch_batch

BATCH_LIMIT = 200  # за один прогон; следующий cron-запуск доберёт остальное


class Command(BaseCommand):
    help = "Отправляет уведомления со status=pending и scheduled_for <= now"

    def handle(self, *args, **options):
        if not settings.BOT_TOKEN:
            raise CommandError("BOT_TOKEN не задан в .env — отправка невозможна.")
        from bot import notify  # импорт здесь, чтобы команда падала понятной ошибкой выше

        now = timezone.now()
        prepared: list[tuple[Notification, str]] = []

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
                if text is None or not client_channel_ready(appt.client):
                    n.status = Notification.Status.FAILED
                    n.save(update_fields=["status", "updated_at"])
                    continue
                # Оптимистично помечаем отправленным (см. докстринг)
                n.status = Notification.Status.SENT
                n.sent_at = now
                n.save(update_fields=["status", "sent_at", "updated_at"])
                prepared.append((n, text))

        if not prepared:
            self.stdout.write("Нет уведомлений к отправке.")
            return

        result = dispatch_batch(prepared)
        self.stdout.write(
            self.style.SUCCESS(f"Отправлено: {result['sent']}, ошибок: {result['failed']}.")
        )
