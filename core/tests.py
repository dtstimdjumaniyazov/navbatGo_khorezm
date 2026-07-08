"""Тесты ключевых инвариантов: слоты, пересечения, статусы, уведомления."""
from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone as dj_tz

from core.models import (
    Appointment,
    Bay,
    Client,
    Notification,
    Service,
    ServiceManager,
    ServicePoint,
)
from core.services.appointments import (
    BookingError,
    ShiftRequired,
    SlotTakenError,
    cancel_appointment,
    create_appointment,
    extend_appointment,
    mark_no_show,
    shift_queue,
    start_appointment,
)
from core.services.slots import get_available_slots

TZ = ZoneInfo("Asia/Tashkent")


def next_workday(days_ahead: int = 1) -> date:
    """Ближайший будний день (пн–сб) не раньше, чем через days_ahead."""
    d = dj_tz.now().astimezone(TZ).date() + timedelta(days=days_ahead)
    while d.weekday() == 6:  # вс — выходной в тестовом сервисе
        d += timedelta(days=1)
    return d


class BaseSetup(TestCase):
    def setUp(self):
        self.sp = ServicePoint.objects.create(
            name="Тестовый сервис",
            timezone="Asia/Tashkent",
            work_start=time(9, 0),
            work_end=time(18, 0),
            work_days=[0, 1, 2, 3, 4, 5],
            slot_buffer_minutes=10,
        )
        self.bay1 = Bay.objects.create(service_point=self.sp, name="Пост 1")
        self.bay2 = Bay.objects.create(service_point=self.sp, name="Пост 2")
        self.service = Service.objects.create(
            service_point=self.sp, name="Шиномонтаж",
            service_type="fixed", duration_minutes=30,
        )
        self.client_obj = Client.objects.create(telegram_id=111, name="Тест")
        self.day = next_workday()

    def dt(self, hour, minute=0):
        return datetime.combine(self.day, time(hour, minute), tzinfo=TZ)


class SlotTests(BaseSetup):
    def test_slots_generated_for_workday(self):
        slots = get_available_slots(self.service, self.day)
        self.assertTrue(slots)
        # первый слот — в начало рабочего дня, оба поста свободны
        self.assertEqual(slots[0].start, self.dt(9))
        self.assertEqual(len(slots[0].bay_ids), 2)
        # слот 30 + буфер 10 = 40 мин не должен выходить за 18:00
        self.assertTrue(all(s.end <= self.dt(18) for s in slots))

    def test_no_slots_on_day_off(self):
        d = self.day
        while d.weekday() != 6:  # воскресенье
            d += timedelta(days=1)
        self.assertEqual(get_available_slots(self.service, d), [])

    def test_busy_bay_excluded_but_second_bay_free(self):
        create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(9),
            bay=self.bay1,
        )
        slots = get_available_slots(self.service, self.day)
        first = slots[0]
        self.assertEqual(first.start, self.dt(9))
        self.assertEqual(first.bay_ids, [self.bay2.id])

    def test_both_bays_busy_slot_disappears(self):
        create_appointment(client=self.client_obj, service=self.service,
                           start_time=self.dt(9), bay=self.bay1)
        create_appointment(client=self.client_obj, service=self.service,
                           start_time=self.dt(9), bay=self.bay2)
        slots = get_available_slots(self.service, self.day)
        # 9:00 и 9:30 заняты/пересекаются (запись 9:00–9:40), первый свободный — 10:00
        self.assertEqual(slots[0].start, self.dt(10))


class BookingTests(BaseSetup):
    def test_estimated_end_includes_buffer(self):
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(10)
        )
        self.assertEqual(appt.estimated_end_time, self.dt(10, 40))

    def test_cannot_double_book_same_bay(self):
        create_appointment(client=self.client_obj, service=self.service,
                           start_time=self.dt(10), bay=self.bay1)
        with self.assertRaises(SlotTakenError):
            create_appointment(client=self.client_obj, service=self.service,
                               start_time=self.dt(10, 20), bay=self.bay1)

    def test_auto_picks_free_bay(self):
        a1 = create_appointment(client=self.client_obj, service=self.service,
                                start_time=self.dt(10))
        a2 = create_appointment(client=self.client_obj, service=self.service,
                                start_time=self.dt(10))
        self.assertNotEqual(a1.bay_id, a2.bay_id)

    def test_outside_work_hours_rejected(self):
        with self.assertRaises(BookingError):
            create_appointment(client=self.client_obj, service=self.service,
                               start_time=self.dt(17, 45))  # конец 18:25 > 18:00

    def test_db_constraint_blocks_overlap(self):
        """Exclusion-констрейнт в БД — последний рубеж при гонке."""
        create_appointment(client=self.client_obj, service=self.service,
                           start_time=self.dt(11), bay=self.bay1)
        with self.assertRaises(IntegrityError), transaction.atomic():
            Appointment.objects.create(
                client=self.client_obj, service=self.service, bay=self.bay1,
                start_time=self.dt(11, 15),
                estimated_end_time=self.dt(11, 55),
            )

    def test_cancelled_frees_slot(self):
        appt = create_appointment(client=self.client_obj, service=self.service,
                                  start_time=self.dt(12), bay=self.bay1)
        cancel_appointment(appt)
        # после отмены слот снова доступен на том же посту
        create_appointment(client=self.client_obj, service=self.service,
                           start_time=self.dt(12), bay=self.bay1)


class StatusTests(BaseSetup):
    def test_no_show_increments_counter(self):
        appt = create_appointment(client=self.client_obj, service=self.service,
                                  start_time=self.dt(13))
        mark_no_show(appt)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.no_show_count, 1)
        self.assertEqual(appt.status, Appointment.Status.NO_SHOW)


async def _fake_deliver_ok(batch):
    return {nid: None for nid, _, _ in batch}


async def _fake_deliver_fail(batch):
    return {nid: "Forbidden: bot was blocked by the user" for nid, _, _ in batch}


@override_settings(BOT_TOKEN="123:test")
class ReminderTests(BaseSetup):
    """Часть A этапа 3: напоминания за N часов."""

    def make_appt(self, hour=10):
        return create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(hour)
        )

    def test_reminder_created_on_booking(self):
        appt = self.make_appt()
        n = Notification.objects.get(appointment=appt)
        self.assertEqual(n.notification_type, Notification.Type.REMINDER)
        self.assertEqual(n.status, Notification.Status.PENDING)
        # за reminder_hours_before (по умолчанию 3) до начала
        self.assertEqual(n.scheduled_for, appt.start_time - timedelta(hours=3))

    def test_no_reminder_without_telegram(self):
        street_client = Client.objects.create(name="С улицы", phone="+998900000009")
        appt = create_appointment(
            client=street_client, service=self.service, start_time=self.dt(11)
        )
        self.assertFalse(Notification.objects.filter(appointment=appt).exists())

    def test_no_reminder_if_window_passed(self):
        # Окно напоминания уже прошло (клиент записался ближе, чем за N часов)
        self.sp.reminder_hours_before = 1000
        self.sp.save()
        appt = self.make_appt()
        self.assertFalse(Notification.objects.filter(appointment=appt).exists())

    def test_cancel_appointment_cancels_reminder(self):
        appt = self.make_appt()
        cancel_appointment(appt)
        n = Notification.objects.get(appointment=appt)
        self.assertEqual(n.status, Notification.Status.CANCELLED)

    def test_no_show_cancels_reminder(self):
        appt = self.make_appt()
        mark_no_show(appt)
        n = Notification.objects.get(appointment=appt)
        self.assertEqual(n.status, Notification.Status.CANCELLED)

    def _make_due(self):
        """Запись + напоминание, у которого время отправки уже наступило."""
        appt = self.make_appt()
        n = Notification.objects.get(appointment=appt)
        n.scheduled_for = dj_tz.now() - timedelta(minutes=1)
        n.save(update_fields=["scheduled_for"])
        return appt, n

    def test_send_command_marks_sent(self):
        _, n = self._make_due()
        with patch("bot.notify.deliver", side_effect=_fake_deliver_ok):
            call_command("send_due_notifications")
        n.refresh_from_db()
        self.assertEqual(n.status, Notification.Status.SENT)
        self.assertIsNotNone(n.sent_at)

    def test_send_command_idempotent(self):
        self._make_due()
        with patch("bot.notify.deliver", side_effect=_fake_deliver_ok) as mock1:
            call_command("send_due_notifications")
        self.assertEqual(mock1.call_count, 1)
        # Повторный запуск не шлёт ничего второй раз
        with patch("bot.notify.deliver", side_effect=_fake_deliver_ok) as mock2:
            call_command("send_due_notifications")
        self.assertEqual(mock2.call_count, 0)

    def test_send_command_marks_failed_on_error(self):
        _, n = self._make_due()
        with patch("bot.notify.deliver", side_effect=_fake_deliver_fail):
            call_command("send_due_notifications")
        n.refresh_from_db()
        self.assertEqual(n.status, Notification.Status.FAILED)
        self.assertIsNone(n.sent_at)

    def test_send_command_skips_inactive_appointment(self):
        # Гонка: запись отменили, а напоминание осталось pending
        appt, n = self._make_due()
        Appointment.objects.filter(pk=appt.pk).update(status=Appointment.Status.CANCELLED)
        with patch("bot.notify.deliver", side_effect=_fake_deliver_ok) as mock:
            call_command("send_due_notifications")
        self.assertEqual(mock.call_count, 0)
        n.refresh_from_db()
        self.assertEqual(n.status, Notification.Status.CANCELLED)

    def test_reminder_text_localized(self):
        from bot.notify import build_text

        appt, n = self._make_due()
        self.sp.address = "Ургенч, ул. Хонка 12"
        self.sp.save()
        n = Notification.objects.select_related(
            "appointment__client", "appointment__service__service_point"
        ).get(pk=n.pk)
        self.assertIn("Напоминаем", build_text(n))
        Client.objects.filter(pk=self.client_obj.pk).update(language="uz")
        n = Notification.objects.select_related(
            "appointment__client", "appointment__service__service_point"
        ).get(pk=n.pk)
        text = build_text(n)
        self.assertIn("Эслатма", text)
        self.assertIn("Манзил", text)


@override_settings(BOT_TOKEN="123:test")
class OverrunTests(BaseSetup):
    """Часть B этапа 3: продление и сдвиг очереди. Слот = 30 мин + 10 буфер."""

    def setUp(self):
        super().setUp()
        self.street = Client.objects.create(name="Без телеграма", phone="+998900000002")
        # A — на посту (in_progress) 10:00–10:40
        self.a = create_appointment(client=self.client_obj, service=self.service,
                                    start_time=self.dt(10), bay=self.bay1)
        start_appointment(self.a)
        # B и C — впритык следом на том же посту
        self.b = create_appointment(client=self.client_obj, service=self.service,
                                    start_time=self.dt(10, 40), bay=self.bay1)
        self.c = create_appointment(client=self.street, service=self.service,
                                    start_time=self.dt(11, 20), bay=self.bay1)
        # D — другой пост, трогать нельзя
        self.d = create_appointment(client=self.client_obj, service=self.service,
                                    start_time=self.dt(10, 40), bay=self.bay2)

    def test_extend_without_conflict(self):
        # Освобождаем место за A
        cancel_appointment(self.b)
        cancel_appointment(self.c)
        extend_appointment(self.a, 30)
        self.a.refresh_from_db()
        self.assertEqual(self.a.estimated_end_time, self.dt(11, 10))

    def test_extend_conflict_raises_shift_required(self):
        with self.assertRaises(ShiftRequired) as ctx:
            extend_appointment(self.a, 30)  # наезд на B (10:40)
        self.assertEqual(ctx.exception.conflicts, 1)

    def test_extend_requires_in_progress(self):
        with self.assertRaises(BookingError):
            extend_appointment(self.b, 30)  # B ещё scheduled

    def test_shift_moves_only_subsequent_on_same_bay(self):
        shifted, _ = shift_queue(self.a, 30)
        self.assertEqual({s.pk for s in shifted}, {self.b.pk, self.c.pk})
        self.b.refresh_from_db(); self.c.refresh_from_db()
        self.a.refresh_from_db(); self.d.refresh_from_db()
        # B и C уехали на +30 (впритык — проверяет порядок обновления с конца)
        self.assertEqual(self.b.start_time, self.dt(11, 10))
        self.assertEqual(self.c.start_time, self.dt(11, 50))
        # A (на посту) и D (другой пост) не тронуты
        self.assertEqual(self.a.start_time, self.dt(10))
        self.assertEqual(self.d.start_time, self.dt(10, 40))

    def test_shift_skips_finished_and_cancelled(self):
        cancel_appointment(self.c)
        shifted, _ = shift_queue(self.a, 15)
        self.assertEqual([s.pk for s in shifted], [self.b.pk])
        self.c.refresh_from_db()
        self.assertEqual(self.c.start_time, self.dt(11, 20))  # отменённая на месте

    def test_shift_creates_notifications_and_moves_reminders(self):
        reminder_b = Notification.objects.get(
            appointment=self.b, notification_type=Notification.Type.REMINDER
        )
        old_scheduled = reminder_b.scheduled_for
        _, notifications = shift_queue(self.a, 30)
        # shifted-уведомление только у B (у клиента C нет Telegram)
        self.assertEqual(len(notifications), 1)
        self.assertEqual(notifications[0].appointment_id, self.b.pk)
        self.assertEqual(notifications[0].notification_type, Notification.Type.SHIFTED)
        # напоминание B уехало вместе с записью
        reminder_b.refresh_from_db()
        self.assertEqual(reminder_b.scheduled_for, old_scheduled + timedelta(minutes=30))

    def test_shift_backwards_rejected(self):
        with self.assertRaises(BookingError):
            shift_queue(self.a, -15)

    def test_extend_api_returns_needs_shift(self):
        resp = self.client.post(
            f"/api/appointments/{self.a.id}/extend/",
            {"extra_minutes": 30},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 409)
        body = resp.json()
        self.assertTrue(body["needs_shift"])
        self.assertEqual(body["conflicts"], 1)

    def test_shift_queue_api_shifts_and_notifies(self):
        with patch("bot.notify.deliver", side_effect=_fake_deliver_ok):
            resp = self.client.post(
                f"/api/appointments/{self.a.id}/shift_queue/",
                {"minutes": 30},
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        body = resp.json()
        self.assertEqual(body["shifted_count"], 2)
        self.assertEqual(body["notified"], 1)      # только клиент с Telegram
        self.assertEqual(body["notify_failed"], 0)
        n = Notification.objects.get(notification_type=Notification.Type.SHIFTED)
        self.assertEqual(n.status, Notification.Status.SENT)

    def test_shifted_text_contains_new_time(self):
        from bot.notify import build_text

        shift_queue(self.a, 30)
        n = Notification.objects.select_related(
            "appointment__client", "appointment__service__service_point"
        ).get(notification_type=Notification.Type.SHIFTED)
        text = build_text(n)
        self.assertIn("11:10", text)  # новое время B, не старое 10:40


class MasterRoleTests(BaseSetup):
    """Определение роли мастера для Telegram-бота."""

    def test_manager_resolved_by_telegram_id(self):
        from asgiref.sync import async_to_sync

        from bot.db import get_manager

        ServiceManager.objects.create(
            service_point=self.sp, telegram_id=555, name="Мастер"
        )
        mgr = async_to_sync(get_manager)(555)
        self.assertIsNotNone(mgr)
        self.assertEqual(mgr.service_point_id, self.sp.pk)
        # чужой/неизвестный id — клиентский режим
        self.assertIsNone(async_to_sync(get_manager)(777))

    def test_inactive_manager_ignored(self):
        from asgiref.sync import async_to_sync

        from bot.db import get_manager

        ServiceManager.objects.create(
            service_point=self.sp, telegram_id=556, is_active=False
        )
        self.assertIsNone(async_to_sync(get_manager)(556))

    def test_master_cannot_reach_foreign_appointment(self):
        from asgiref.sync import async_to_sync

        from bot.db import get_sp_appointment

        other_sp = ServicePoint.objects.create(
            name="Чужой сервис", timezone="Asia/Tashkent",
            work_start=time(9, 0), work_end=time(18, 0),
            work_days=[0, 1, 2, 3, 4, 5],
        )
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(10)
        )
        # запись нашего сервиса не видна из контекста чужого
        self.assertIsNone(async_to_sync(get_sp_appointment)(appt.id, other_sp))
        self.assertIsNotNone(async_to_sync(get_sp_appointment)(appt.id, self.sp))


class WalkInTests(BaseSetup):
    """«Записать с улицы» из мастер-бота."""

    def test_walkin_creates_client_and_manual_appointment(self):
        from asgiref.sync import async_to_sync

        from bot.db import master_create_walkin

        appt = async_to_sync(master_create_walkin)(
            self.sp, str(self.bay1.id), str(self.service.id),
            self.dt(15), "Бахтиёр", "+998901112244",
        )
        self.assertEqual(appt.source, Appointment.Source.MANUAL)
        self.assertEqual(appt.client.name, "Бахтиёр")
        self.assertIsNone(appt.client.telegram_id)
        # напоминание клиенту без Telegram не создаётся
        self.assertFalse(Notification.objects.filter(appointment=appt).exists())

    def test_walkin_slot_taken_leaves_no_orphan_client(self):
        from asgiref.sync import async_to_sync

        from bot.db import master_create_walkin

        create_appointment(client=self.client_obj, service=self.service,
                           start_time=self.dt(15), bay=self.bay1)
        clients_before = Client.objects.count()
        with self.assertRaises(SlotTakenError):
            async_to_sync(master_create_walkin)(
                self.sp, str(self.bay1.id), str(self.service.id),
                self.dt(15), "Никто", "",
            )
        self.assertEqual(Client.objects.count(), clients_before)


class ApiTests(BaseSetup):
    """API панели мастера: создание с car_details/длительностью, PATCH статуса."""

    def test_create_with_car_details_and_duration_override(self):
        resp = self.client.post(
            "/api/appointments/",
            {
                "client_name": "Рустам",
                "client_phone": "+998901112233",
                "service": str(self.service.id),
                "start_time": self.dt(10).isoformat(),
                "car_details": "Kia K5",
                "duration_minutes": 50,  # вместо 30 у услуги
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        data = resp.json()
        self.assertEqual(data["car_details"], "Kia K5")
        self.assertEqual(data["service_type"], "fixed")
        # 50 мин + буфер 10 = конец в 11:00
        appt = Appointment.objects.get(pk=data["id"])
        self.assertEqual(appt.estimated_end_time, self.dt(11))

    def test_patch_status_no_show_increments_counter(self):
        appt = create_appointment(client=self.client_obj, service=self.service,
                                  start_time=self.dt(14))
        resp = self.client.patch(
            f"/api/appointments/{appt.id}/",
            {"status": "no_show"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["status"], "no_show")
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.no_show_count, 1)

    def test_patch_invalid_transition_rejected(self):
        appt = create_appointment(client=self.client_obj, service=self.service,
                                  start_time=self.dt(15))
        # scheduled → done без in_progress — недопустимо
        resp = self.client.patch(
            f"/api/appointments/{appt.id}/",
            {"status": "done"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 409)

    def test_patch_cannot_move_appointment_directly(self):
        """start_time через PATCH игнорируется — перенос только через сервисный слой."""
        appt = create_appointment(client=self.client_obj, service=self.service,
                                  start_time=self.dt(16))
        resp = self.client.patch(
            f"/api/appointments/{appt.id}/",
            {"start_time": self.dt(9).isoformat(), "note": "попытка сдвига"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        appt.refresh_from_db()
        self.assertEqual(appt.start_time, self.dt(16))  # не изменилось
        self.assertEqual(appt.note, "попытка сдвига")   # а note — да

    def test_bays_active_filter(self):
        Bay.objects.create(service_point=self.sp, name="Сломанный", is_active=False)
        resp = self.client.get("/api/bays/?active=1")
        names = [b["name"] for b in resp.json()]
        self.assertNotIn("Сломанный", names)
        self.assertEqual(len(names), 2)
