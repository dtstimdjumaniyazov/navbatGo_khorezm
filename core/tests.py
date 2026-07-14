"""Тесты ключевых инвариантов: слоты, пересечения, статусы, уведомления."""
from datetime import date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

from django.core.management import call_command
from django.db import IntegrityError, transaction
from django.test import TestCase, override_settings
from django.utils import timezone as dj_tz

import tempfile

from core.models import (
    Appointment,
    Bay,
    Client,
    Notification,
    NotificationChannel,
    Service,
    ServiceManager,
    ServicePoint,
    ServicePointMedia,
)

# 1×1 GIF для тестов загрузки изображений
TINY_GIF = (
    b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00ccc,\x00\x00\x00\x00"
    b"\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
)
from core.services.appointments import (
    BookingError,
    ShiftRequired,
    SlotTakenError,
    cancel_appointment,
    cancel_by_master,
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
        from django.contrib.auth.models import User

        # is_staff: служебные API закрыты пермишном IsManager (мастер или staff)
        self.user = User.objects.create_user(
            "master1", password="test-pass-123", is_staff=True
        )
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
        other_client = Client.objects.create(telegram_id=112, name="Другой клиент")
        create_appointment(client=self.client_obj, service=self.service,
                           start_time=self.dt(9), bay=self.bay1)
        create_appointment(client=other_client, service=self.service,
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
        other_client = Client.objects.create(telegram_id=113, name="Другой клиент")
        create_appointment(client=self.client_obj, service=self.service,
                           start_time=self.dt(10), bay=self.bay1)
        with self.assertRaises(SlotTakenError):
            create_appointment(client=other_client, service=self.service,
                               start_time=self.dt(10, 20), bay=self.bay1)

    def test_auto_picks_free_bay(self):
        other_client = Client.objects.create(telegram_id=114, name="Другой клиент")
        a1 = create_appointment(client=self.client_obj, service=self.service,
                                start_time=self.dt(10))
        a2 = create_appointment(client=other_client, service=self.service,
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
        self.client.force_login(self.user)
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
        # D — другой пост, трогать нельзя (свой клиент: тот же не может быть
        # одновременно на двух постах — см. excl_overlapping_client_appts)
        self.d = create_appointment(client=self.street, service=self.service,
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


class AuthTests(BaseSetup):
    """JWT-аутентификация: API закрыт, вход по логину/паролю."""

    def test_api_requires_auth(self):
        resp = self.client.get("/api/services/")
        self.assertEqual(resp.status_code, 401)

    def test_login_returns_tokens_and_they_work(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "master1", "password": "test-pass-123"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        tokens = resp.json()
        self.assertIn("access", tokens)
        self.assertIn("refresh", tokens)
        resp = self.client.get(
            "/api/services/", headers={"Authorization": f"Bearer {tokens['access']}"}
        )
        self.assertEqual(resp.status_code, 200)

    def test_wrong_password_rejected(self):
        resp = self.client.post(
            "/api/auth/login/",
            {"username": "master1", "password": "wrong"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 401)

    def test_me_returns_manager_profile(self):
        ServiceManager.objects.create(
            service_point=self.sp, telegram_id=901, name="Мастер", user=self.user
        )
        self.client.force_login(self.user)
        resp = self.client.get("/api/auth/me/")
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertEqual(data["username"], "master1")
        self.assertEqual(data["manager"]["service_point"], str(self.sp.id))


@override_settings(MEDIA_ROOT=tempfile.mkdtemp(prefix="navbatgo_test_media_"))
class ProfileTests(BaseSetup):
    """Профили мастеров: свой кабинет + публичная витрина."""

    def setUp(self):
        super().setUp()
        self.manager = ServiceManager.objects.create(
            service_point=self.sp, telegram_id=902, name="Мастер Ака", user=self.user
        )
        self.client.force_login(self.user)

    def _photo(self, name="work.gif"):
        from django.core.files.uploadedfile import SimpleUploadedFile

        return SimpleUploadedFile(name, TINY_GIF, content_type="image/gif")

    def test_patch_profile_bio_and_avatar(self):
        resp = self.client.patch(
            "/api/profile/",
            {"bio": "Чиню ходовую 10 лет", "experience_years": 10},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["bio"], "Чиню ходовую 10 лет")
        # аватар — multipart (для PATCH тест-клиент требует ручной кодировки)
        from django.test.client import BOUNDARY, MULTIPART_CONTENT, encode_multipart

        resp = self.client.patch(
            "/api/profile/",
            encode_multipart(BOUNDARY, {"avatar": self._photo("me.gif")}),
            content_type=MULTIPART_CONTENT,
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertIn("avatars/", resp.json()["avatar"])

    def test_profile_404_for_non_manager_user(self):
        from django.contrib.auth.models import User

        plain = User.objects.create_user("plain", password="x12345678")
        self.client.force_login(plain)
        self.assertEqual(self.client.get("/api/profile/").status_code, 404)

    def test_add_photo_and_video_to_gallery(self):
        resp = self.client.post("/api/profile/media/", {"image": self._photo()})
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["media_type"], "photo")
        resp = self.client.post(
            "/api/profile/media/",
            {"video_url": "https://youtu.be/dQw4w9WgXcQ", "caption": "Наш бокс"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["media_type"], "video")
        # галерея видна в профиле
        media = self.client.get("/api/profile/").json()["media"]
        self.assertEqual(len(media), 2)

    def test_video_must_be_youtube(self):
        resp = self.client.post(
            "/api/profile/media/",
            {"video_url": "https://vimeo.com/12345"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_photo_xor_video_required(self):
        resp = self.client.post("/api/profile/media/", {}, content_type="application/json")
        self.assertEqual(resp.status_code, 400)

    def test_only_one_video_allowed(self):
        resp = self.client.post(
            "/api/profile/media/",
            {"video_url": "https://youtu.be/aaaaaaaaaaa"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        resp = self.client.post(
            "/api/profile/media/",
            {"video_url": "https://youtu.be/bbbbbbbbbbb"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(
            ServicePointMedia.objects.filter(
                service_point=self.sp, media_type="video"
            ).count(),
            1,
        )

    def test_multiple_photos_still_allowed(self):
        for name in ("a.gif", "b.gif", "c.gif"):
            resp = self.client.post("/api/profile/media/", {"image": self._photo(name)})
            self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(
            ServicePointMedia.objects.filter(
                service_point=self.sp, media_type="photo"
            ).count(),
            3,
        )

    def test_delete_own_service_media_only(self):
        """Галерея принадлежит сервису: чужой сервис недоступен, свой — да."""
        mine = ServicePointMedia.objects.create(
            service_point=self.sp, media_type="video", video_url="https://youtu.be/x"
        )
        other_sp = ServicePoint.objects.create(
            name="Чужой сервис", work_start=time(9), work_end=time(18), work_days=[0],
        )
        foreign = ServicePointMedia.objects.create(
            service_point=other_sp, media_type="video", video_url="https://youtu.be/y"
        )
        self.assertEqual(
            self.client.delete(f"/api/profile/media/{foreign.pk}/").status_code, 404
        )
        self.assertEqual(
            self.client.delete(f"/api/profile/media/{mine.pk}/").status_code, 204
        )
        self.assertFalse(ServicePointMedia.objects.filter(pk=mine.pk).exists())

    def test_public_profile_without_auth(self):
        self.manager.bio = "Опытный мастер"
        self.manager.save()
        ServicePointMedia.objects.create(
            service_point=self.sp, media_type="video", video_url="https://youtu.be/z"
        )
        self.client.logout()
        resp = self.client.get(f"/api/public/service-points/{self.sp.pk}/")
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        # галерея — на уровне сервиса, у мастеров — только личные карточки
        self.assertEqual(len(data["media"]), 1)
        self.assertEqual(len(data["managers"]), 1)
        self.assertEqual(data["managers"][0]["bio"], "Опытный мастер")
        self.assertNotIn("media", data["managers"][0])


class ApiTests(BaseSetup):
    """API панели мастера: создание с car_details/длительностью, PATCH статуса."""

    def setUp(self):
        super().setUp()
        self.client.force_login(self.user)

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


class MasterCancelNotificationTests(BaseSetup):
    """Отмена мастером: клиент с Telegram сразу получает уведомление."""

    def test_cancel_by_master_creates_notification(self):
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(11)
        )
        reminder = appt.notifications.filter(
            notification_type=Notification.Type.REMINDER
        ).first()
        appt, notifs = cancel_by_master(appt, "Сломался подъёмник")
        self.assertEqual(appt.status, Appointment.Status.CANCELLED)
        self.assertEqual(appt.cancelled_by, Appointment.CancelledBy.MASTER)
        self.assertEqual(appt.cancel_reason, "Сломался подъёмник")
        self.assertEqual(len(notifs), 1)
        self.assertEqual(notifs[0].notification_type, Notification.Type.CANCELLED)
        self.assertEqual(notifs[0].status, Notification.Status.PENDING)
        if reminder is not None:  # напоминание гасится, а не уезжает клиенту
            reminder.refresh_from_db()
            self.assertEqual(reminder.status, Notification.Status.CANCELLED)

    def test_cancel_by_master_requires_reason(self):
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(11, 30)
        )
        with self.assertRaises(BookingError):
            cancel_by_master(appt, "   ")
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.SCHEDULED)

    def test_client_cancel_does_not_set_master_reason(self):
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(11, 45)
        )
        cancel_appointment(appt)
        self.assertEqual(appt.cancelled_by, Appointment.CancelledBy.CLIENT)
        self.assertEqual(appt.cancel_reason, "")

    def test_street_client_gets_no_notification(self):
        street = Client.objects.create(name="Клиент с улицы")
        appt = create_appointment(
            client=street, service=self.service, start_time=self.dt(12)
        )
        _, notifs = cancel_by_master(appt, "Мастер заболел")
        self.assertEqual(notifs, [])
        self.assertFalse(
            appt.notifications.filter(
                notification_type=Notification.Type.CANCELLED
            ).exists()
        )

    def test_cancelled_text_localized(self):
        from bot.notify import build_text

        self.client_obj.language = "uz"
        self.client_obj.save(update_fields=["language"])
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(13)
        )
        _, notifs = cancel_by_master(appt, "Мастер заболел")
        n = Notification.objects.select_related(
            "appointment__client", "appointment__service__service_point"
        ).get(pk=notifs[0].pk)
        text = build_text(n)
        self.assertIn("бекор қилинди", text)
        self.assertIn(self.service.name, text)
        self.assertIn("Мастер заболел", text)

    def test_cancelled_text_includes_reason(self):
        from bot.notify import build_text

        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(13, 30)
        )
        _, notifs = cancel_by_master(appt, "Сломался подъёмник")
        n = Notification.objects.select_related(
            "appointment__client", "appointment__service__service_point"
        ).get(pk=notifs[0].pk)
        text = build_text(n)
        self.assertIn("Сломался подъёмник", text)

    def test_api_cancel_sends_notification(self):
        from unittest.mock import AsyncMock

        self.client.force_login(self.user)
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(14)
        )
        with patch("bot.notify.deliver", new_callable=AsyncMock) as mock_deliver:
            mock_deliver.side_effect = lambda batch: {nid: None for nid, _tg, _txt in batch}
            resp = self.client.post(
                f"/api/appointments/{appt.id}/cancel/",
                {"reason": "Мастер заболел"},
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        n = appt.notifications.get(notification_type=Notification.Type.CANCELLED)
        self.assertEqual(n.status, Notification.Status.SENT)
        mock_deliver.assert_called_once()

    def test_api_cancel_requires_reason(self):
        self.client.force_login(self.user)
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(15)
        )
        resp = self.client.post(f"/api/appointments/{appt.id}/cancel/")
        self.assertEqual(resp.status_code, 409, resp.content)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.SCHEDULED)


class LeadTimeTests(BaseSetup):
    """
    min_lead_minutes: клиент не видит слоты ближе N минут от «сейчас»;
    мастер (запись «с улицы») видит все слоты — буфер его не касается.
    """

    def test_lead_time_pushes_first_slot(self):
        self.sp.min_lead_minutes = 60
        self.sp.save(update_fields=["min_lead_minutes"])
        with patch("core.services.slots.timezone.now", return_value=self.dt(13, 37)):
            slots = get_available_slots(self.service, self.day)
        # 13:37 + 60 мин = 14:37 → округление вверх до сетки (шаг 30 мин от 9:00) = 15:00
        self.assertEqual(slots[0].start, self.dt(15, 0))

    def test_apply_lead_time_false_bypasses_buffer(self):
        self.sp.min_lead_minutes = 60
        self.sp.save(update_fields=["min_lead_minutes"])
        with patch("core.services.slots.timezone.now", return_value=self.dt(13, 37)):
            slots = get_available_slots(self.service, self.day, apply_lead_time=False)
        # без буфера — обычное округление «сейчас» вверх до сетки: 14:00
        self.assertEqual(slots[0].start, self.dt(14, 0))

    def test_zero_lead_time_behaves_like_before(self):
        self.sp.min_lead_minutes = 0
        self.sp.save(update_fields=["min_lead_minutes"])
        with patch("core.services.slots.timezone.now", return_value=self.dt(13, 37)):
            slots = get_available_slots(self.service, self.day)
        self.assertEqual(slots[0].start, self.dt(14, 0))

    def test_slots_api_respects_role(self):
        """Клиент — с буфером, мастер — без буфера, через /api/slots/."""
        from django.contrib.auth.models import User

        self.sp.min_lead_minutes = 60
        self.sp.save(update_fields=["min_lead_minutes"])
        client_user = User.objects.create_user("tg_555")
        Client.objects.create(telegram_id=555, user=client_user)

        url = f"/api/slots/?service={self.service.id}&date={self.day.isoformat()}"
        with patch("core.services.slots.timezone.now", return_value=self.dt(13, 37)):
            self.client.force_login(client_user)
            client_resp = self.client.get(url).json()
            self.client.logout()
            self.client.force_login(self.user)  # мастер (is_staff)
            master_resp = self.client.get(url).json()

        self.assertEqual(client_resp[0]["start"][11:16], "15:00")
        self.assertEqual(master_resp[0]["start"][11:16], "14:00")


class WorkingHoursTests(BaseSetup):
    """Переопределения графика по дням: другие часы, выходной, витрина."""

    def _override(self, weekday, **kwargs):
        from core.models import WorkingHours

        return WorkingHours.objects.create(
            service_point=self.sp, weekday=weekday, **kwargs
        )

    def test_override_shortens_day(self):
        from datetime import time as t_

        # В день записи сервис работает только до 14:00
        self._override(self.day.weekday(), work_start=t_(9), work_end=t_(14))
        slots = get_available_slots(self.service, self.day)
        self.assertTrue(slots)
        self.assertTrue(all(s.end <= self.dt(14) for s in slots))
        with self.assertRaises(BookingError):
            create_appointment(
                client=self.client_obj, service=self.service, start_time=self.dt(15)
            )

    def test_override_closes_day(self):
        self._override(self.day.weekday(), is_closed=True)
        self.assertEqual(get_available_slots(self.service, self.day), [])
        with self.assertRaises(BookingError):
            create_appointment(
                client=self.client_obj, service=self.service, start_time=self.dt(10)
            )

    def test_week_schedule_merges_base_and_overrides(self):
        from datetime import time as t_

        from core.services.schedule import week_schedule

        self._override(3, work_start=t_(9), work_end=t_(14))  # чт короче
        self._override(5, is_closed=True)  # сб выходной, хотя в work_days есть
        schedule = week_schedule(self.sp)
        self.assertEqual(schedule[0]["start"], "09:00")  # пн — базовый график
        self.assertEqual(schedule[0]["end"], "18:00")
        self.assertEqual(schedule[3]["end"], "14:00")   # переопределение часов
        self.assertIsNone(schedule[5]["start"])          # переопределение-выходной
        self.assertIsNone(schedule[6]["start"])          # вс — не в work_days

    def test_schedule_in_public_profile(self):
        resp = self.client.get(f"/api/public/service-points/{self.sp.pk}/")
        data = resp.json()
        self.assertEqual(len(data["schedule"]), 7)
        self.assertEqual(data["schedule"][0]["start"], "09:00")


class TelegramLoginTests(BaseSetup):
    """Вход через Telegram: start → подтверждение в боте → poll → JWT."""

    MASTER_TG = 555001

    def setUp(self):
        super().setUp()
        self.manager = ServiceManager.objects.create(
            service_point=self.sp, telegram_id=self.MASTER_TG, name="Мастер"
        )

    def _start(self) -> str:
        resp = self.client.post("/api/auth/telegram/start/")
        self.assertEqual(resp.status_code, 200, resp.content)
        return resp.json()["code"]

    def _poll(self, code):
        return self.client.post(
            "/api/auth/telegram/poll/", {"code": code}, content_type="application/json"
        )

    def test_full_flow_issues_working_jwt(self):
        from core.services.telegram_auth import confirm_login

        code = self._start()
        # до Start в боте — pending
        self.assertEqual(self._poll(code).json()["status"], "pending")
        self.assertEqual(confirm_login(code, self.MASTER_TG), "ok")
        resp = self._poll(code)
        data = resp.json()
        self.assertEqual(data["status"], "ok", data)
        self.assertEqual(data["manager"]["service_point"], str(self.sp.id))
        # токен рабочий
        resp = self.client.get(
            "/api/services/", headers={"Authorization": f"Bearer {data['access']}"}
        )
        self.assertEqual(resp.status_code, 200)
        # User создан и привязан к мастеру, пароль не задан
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.user.username, f"tg_{self.MASTER_TG}")
        self.assertFalse(self.manager.user.has_usable_password())

    def test_code_is_single_use(self):
        from core.services.telegram_auth import confirm_login

        code = self._start()
        confirm_login(code, self.MASTER_TG)
        self.assertEqual(self._poll(code).json()["status"], "ok")
        self.assertEqual(self._poll(code).status_code, 404)  # повторно — погашен

    def test_non_manager_logs_in_as_client(self):
        """Обычный telegram-пользователь входит как клиент (создаётся Client)."""
        from core.services.telegram_auth import confirm_login

        code = self._start()
        self.assertEqual(confirm_login(code, 777000), "ok_client")
        data = self._poll(code).json()
        self.assertEqual(data["status"], "ok", data)
        self.assertEqual(data["role"], "client")
        self.assertEqual(data["client"]["name"], "")
        created = Client.objects.get(telegram_id=777000)
        self.assertEqual(created.user.username, "tg_777000")
        # токен рабочий и роль видна в /auth/me/
        resp = self.client.get(
            "/api/auth/me/", headers={"Authorization": f"Bearer {data['access']}"}
        )
        self.assertIsNone(resp.json()["manager"])
        self.assertEqual(resp.json()["client"]["id"], str(created.id))

    def test_expired_code_invalid(self):
        from core.models import TelegramLoginCode
        from core.services.telegram_auth import confirm_login

        code = self._start()
        TelegramLoginCode.objects.filter(code=code).update(
            expires_at=dj_tz.now() - timedelta(seconds=1)
        )
        self.assertEqual(confirm_login(code, self.MASTER_TG), "invalid")
        self.assertEqual(self._poll(code).status_code, 404)

    def test_existing_panel_user_reused(self):
        """У мастера уже есть логин панели — telegram-вход не плодит второго User."""
        self.manager.user = self.user
        self.manager.save(update_fields=["user"])
        from core.services.telegram_auth import confirm_login

        code = self._start()
        confirm_login(code, self.MASTER_TG)
        data = self._poll(code).json()
        self.assertEqual(data["status"], "ok")
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.user, self.user)
        self.assertTrue(self.manager.user.has_usable_password())  # пароль жив


class ClientApiTests(BaseSetup):
    """Клиент в приложении/на сайте: каталог, свои записи, запрет служебных API."""

    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User

        self.client_user = User.objects.create_user("tg_111")
        self.client_obj.user = self.client_user
        self.client_obj.save(update_fields=["user"])
        self.client.force_login(self.client_user)

    def test_catalog_is_public(self):
        self.client.logout()
        resp = self.client.get("/api/public/service-points/")
        self.assertEqual(resp.status_code, 200, resp.content)
        data = resp.json()
        self.assertEqual(len(data), 1)
        self.assertEqual(data[0]["name"], "Тестовый сервис")
        self.assertEqual(len(data[0]["services"]), 1)  # услуги видны для записи

    def test_client_books_lists_and_cancels(self):
        from unittest.mock import AsyncMock

        with patch("bot.notify.deliver", new_callable=AsyncMock) as mock_deliver:
            mock_deliver.side_effect = lambda batch: {nid: None for nid, *_ in batch}
            resp = self.client.post(
                "/api/my/appointments/",
                {
                    "service": str(self.service.id),
                    "start_time": self.dt(10).isoformat(),
                    "name": "Жасур",
                    "phone": "+998 90 123-45-67",
                },
                content_type="application/json",
            )
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(resp.json()["source"], "app")
        # имя/телефон из формы обновили профиль (телефон нормализован)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.name, "Жасур")
        self.assertEqual(self.client_obj.phone, "+998901234567")

        listed = self.client.get("/api/my/appointments/").json()
        self.assertEqual(len(listed), 1)

        with patch("bot.notify.deliver", new_callable=AsyncMock) as mock_deliver:
            mock_deliver.side_effect = lambda batch: {nid: None for nid, *_ in batch}
            resp = self.client.post(
                f"/api/my/appointments/{listed[0]['id']}/cancel/"
            )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["status"], "cancelled")
        self.assertEqual(self.client.get("/api/my/appointments/").json(), [])

    def test_client_cannot_cancel_foreign_appointment(self):
        other = Client.objects.create(telegram_id=222)
        appt = create_appointment(
            client=other, service=self.service, start_time=self.dt(15)
        )
        resp = self.client.post(f"/api/my/appointments/{appt.id}/cancel/")
        self.assertEqual(resp.status_code, 404)
        appt.refresh_from_db()
        self.assertEqual(appt.status, Appointment.Status.SCHEDULED)

    def test_master_api_forbidden_for_client(self):
        for url in (
            "/api/appointments/", "/api/services/", "/api/bays/",
            "/api/clients/", "/api/service-points/",
        ):
            self.assertEqual(self.client.get(url).status_code, 403, url)

    def test_slots_available_to_client(self):
        resp = self.client.get(
            f"/api/slots/?service={self.service.id}&date={self.day.isoformat()}"
        )
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.json())


class WalkinDedupTests(BaseSetup):
    """Дедупликация «уличных» клиентов по нормализованному телефону."""

    def test_phone_normalization(self):
        from core.services.clients import normalize_phone

        self.assertEqual(normalize_phone("+998 (91) 234-56-78"), "+998912345678")
        self.assertEqual(normalize_phone("91 234 56 78"), "912345678")
        self.assertEqual(normalize_phone("  "), "")

    def test_same_phone_reuses_client(self):
        from core.services.clients import get_or_create_walkin_client

        c1 = get_or_create_walkin_client("Аваз", "+998 91 234-56-78")
        c2 = get_or_create_walkin_client("", "+998912345678")
        self.assertEqual(c1.pk, c2.pk)
        self.assertEqual(Client.objects.filter(phone="+998912345678").count(), 1)

    def test_blank_phone_always_creates_new(self):
        from core.services.clients import get_or_create_walkin_client

        c1 = get_or_create_walkin_client("Первый", "")
        c2 = get_or_create_walkin_client("Второй", "")
        self.assertNotEqual(c1.pk, c2.pk)

    def test_api_create_dedups_by_phone(self):
        self.client.force_login(self.user)
        payload = {
            "client_name": "Аваз", "client_phone": "+998 91 111-22-33",
            "service": str(self.service.id), "start_time": self.dt(10).isoformat(),
        }
        resp = self.client.post("/api/appointments/", payload, content_type="application/json")
        self.assertEqual(resp.status_code, 201, resp.content)
        # тот же номер в другом написании → тот же клиент, дубль не создаётся
        payload["start_time"] = self.dt(14).isoformat()
        payload["client_phone"] = "+998 (91) 111 22 33"
        resp = self.client.post("/api/appointments/", payload, content_type="application/json")
        self.assertEqual(resp.status_code, 201, resp.content)
        self.assertEqual(Client.objects.filter(phone="+998911112233").count(), 1)


class DurationFieldTests(BaseSetup):
    """duration_minutes хранится в записи; буфер живёт отдельно."""

    def test_duration_saved_from_service(self):
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(10)
        )
        self.assertEqual(appt.duration_minutes, 30)
        self.assertEqual(appt.estimated_end_time, self.dt(10, 40))  # +буфер 10

    def test_duration_override_saved(self):
        appt = create_appointment(
            client=self.client_obj, service=self.service,
            start_time=self.dt(10), duration_minutes=45,
        )
        self.assertEqual(appt.duration_minutes, 45)
        self.assertEqual(appt.estimated_end_time, self.dt(10, 55))

    def test_extend_updates_duration(self):
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(10)
        )
        start_appointment(appt)
        extend_appointment(appt, extra_minutes=20)
        appt.refresh_from_db()
        self.assertEqual(appt.duration_minutes, 50)


class ServicePointSettingsTests(BaseSetup):
    """Настройки сервиса через API: Instagram, напоминания, чужой сервис — нельзя."""

    def setUp(self):
        super().setUp()
        self.manager = ServiceManager.objects.create(
            service_point=self.sp, telegram_id=903, name="Мастер", user=self.user
        )
        self.client.force_login(self.user)

    def test_patch_instagram_and_reminder(self):
        resp = self.client.patch(
            f"/api/service-points/{self.sp.id}/",
            {"instagram": "https://instagram.com/navbatgo", "reminder_hours_before": 2},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.sp.refresh_from_db()
        self.assertEqual(self.sp.instagram, "https://instagram.com/navbatgo")
        self.assertEqual(self.sp.reminder_hours_before, 2)

    def test_instagram_visible_in_public_profile(self):
        self.sp.instagram = "https://instagram.com/navbatgo"
        self.sp.save(update_fields=["instagram"])
        self.client.logout()
        resp = self.client.get(f"/api/public/service-points/{self.sp.id}/")
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()["instagram"], "https://instagram.com/navbatgo")

    def test_cannot_patch_foreign_service_point(self):
        other = ServicePoint.objects.create(
            name="Чужой сервис", work_start=time(9), work_end=time(18), work_days=[0],
        )
        resp = self.client.patch(
            f"/api/service-points/{other.id}/",
            {"instagram": "https://instagram.com/hack"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 403)

    # ---------- график по дням (WorkingHours) ----------

    def test_patch_working_hours_creates_overrides(self):
        resp = self.client.patch(
            f"/api/service-points/{self.sp.id}/",
            {
                "working_hours": [
                    {"weekday": 1, "is_closed": True, "work_start": None, "work_end": None},
                    {"weekday": 2, "is_closed": False, "work_start": "10:00", "work_end": "15:00"},
                ]
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        rows = {h.weekday: h for h in self.sp.working_hours.all()}
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[1].is_closed)
        self.assertEqual(str(rows[2].work_start), "10:00:00")
        self.assertEqual(str(rows[2].work_end), "15:00:00")

    def test_working_hours_override_affects_available_slots(self):
        # Вторник (weekday=1) обычно рабочий (BaseSetup: work_days=[0..5]) — закрываем его
        resp = self.client.patch(
            f"/api/service-points/{self.sp.id}/",
            {"working_hours": [{"weekday": 1, "is_closed": True, "work_start": None, "work_end": None}]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        tuesday = self.day
        while tuesday.weekday() != 1:
            tuesday += timedelta(days=1)
        self.assertEqual(get_available_slots(self.service, tuesday), [])

    def test_patch_working_hours_replaces_previous_set(self):
        self.client.patch(
            f"/api/service-points/{self.sp.id}/",
            {"working_hours": [{"weekday": 1, "is_closed": True, "work_start": None, "work_end": None}]},
            content_type="application/json",
        )
        resp = self.client.patch(
            f"/api/service-points/{self.sp.id}/",
            {"working_hours": [{"weekday": 3, "is_closed": True, "work_start": None, "work_end": None}]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        weekdays = list(self.sp.working_hours.values_list("weekday", flat=True))
        self.assertEqual(weekdays, [3])  # запись за вторник заменена, не накоплена

    def test_working_hours_rejects_missing_time_when_open(self):
        resp = self.client.patch(
            f"/api/service-points/{self.sp.id}/",
            {"working_hours": [{"weekday": 1, "is_closed": False, "work_start": None, "work_end": None}]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_working_hours_rejects_end_before_start(self):
        resp = self.client.patch(
            f"/api/service-points/{self.sp.id}/",
            {"working_hours": [{"weekday": 1, "is_closed": False, "work_start": "18:00", "work_end": "09:00"}]},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    def test_working_hours_rejects_duplicate_weekday(self):
        resp = self.client.patch(
            f"/api/service-points/{self.sp.id}/",
            {
                "working_hours": [
                    {"weekday": 1, "is_closed": True, "work_start": None, "work_end": None},
                    {"weekday": 1, "is_closed": True, "work_start": None, "work_end": None},
                ]
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)


class TenantIsolationTests(BaseSetup):
    """
    Мастер видит и может изменять только данные СВОЕГО сервиса.
    Баг: в «Новой записи» выпадающие списки постов/услуг показывали
    данные ЧУЖОГО автосервиса — можно было записать клиента на чужой пост.
    """

    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User

        # Отдельный НЕ-staff пользователь: self.user из BaseSetup — is_staff=True
        # и обходит любое ограничение по своему сервису, для этих тестов не годится
        self.master_user = User.objects.create_user("master_own", password="x12345678")
        self.manager = ServiceManager.objects.create(
            service_point=self.sp, telegram_id=904, name="Мастер", user=self.master_user
        )
        self.other_sp = ServicePoint.objects.create(
            name="Чужой сервис", work_start=time(9), work_end=time(18),
            work_days=[0, 1, 2, 3, 4, 5],
        )
        self.other_bay = Bay.objects.create(service_point=self.other_sp, name="Чужой пост")
        self.other_service = Service.objects.create(
            service_point=self.other_sp, name="Чужая услуга",
            service_type="fixed", duration_minutes=30,
        )
        self.client.force_login(self.master_user)

    def test_bays_list_excludes_foreign(self):
        names = [b["name"] for b in self.client.get("/api/bays/").json()]
        self.assertIn(self.bay1.name, names)
        self.assertNotIn(self.other_bay.name, names)

    def test_services_list_excludes_foreign(self):
        names = [s["name"] for s in self.client.get("/api/services/").json()]
        self.assertIn(self.service.name, names)
        self.assertNotIn(self.other_service.name, names)

    def test_cannot_retrieve_foreign_bay(self):
        resp = self.client.get(f"/api/bays/{self.other_bay.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_cannot_retrieve_foreign_service(self):
        resp = self.client.get(f"/api/services/{self.other_service.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_appointments_list_excludes_foreign(self):
        own_appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(10)
        )
        other_client = Client.objects.create(telegram_id=222)
        foreign_appt = create_appointment(
            client=other_client, service=self.other_service,
            bay=self.other_bay, start_time=self.dt(10),
        )
        ids = [a["id"] for a in self.client.get("/api/appointments/").json()]
        self.assertIn(str(own_appt.id), ids)
        self.assertNotIn(str(foreign_appt.id), ids)

    def test_cannot_retrieve_foreign_appointment(self):
        other_client = Client.objects.create(telegram_id=223)
        foreign_appt = create_appointment(
            client=other_client, service=self.other_service,
            bay=self.other_bay, start_time=self.dt(10),
        )
        resp = self.client.get(f"/api/appointments/{foreign_appt.id}/")
        self.assertEqual(resp.status_code, 404)

    def test_cannot_create_appointment_with_foreign_service(self):
        resp = self.client.post(
            "/api/appointments/",
            {
                "client_name": "Тест", "client_phone": "+998900000000",
                "service": str(self.other_service.id),
                "start_time": self.dt(10).isoformat(),
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(Appointment.objects.filter(service=self.other_service).exists())

    def test_cannot_create_appointment_with_own_service_foreign_bay(self):
        """Ровно баг со скриншота: своя услуга, но чужой пост в выпадающем списке."""
        resp = self.client.post(
            "/api/appointments/",
            {
                "client_name": "Тест", "client_phone": "+998900000001",
                "service": str(self.service.id),
                "bay": str(self.other_bay.id),
                "start_time": self.dt(11).isoformat(),
            },
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)
        self.assertFalse(Appointment.objects.filter(bay=self.other_bay).exists())

    def test_clients_list_excludes_those_who_never_booked_here(self):
        other_client = Client.objects.create(telegram_id=224, name="Чужой клиент")
        create_appointment(
            client=other_client, service=self.other_service,
            bay=self.other_bay, start_time=self.dt(10),
        )
        create_appointment(client=self.client_obj, service=self.service, start_time=self.dt(11))
        ids = [c["id"] for c in self.client.get("/api/clients/").json()]
        self.assertIn(str(self.client_obj.id), ids)
        self.assertNotIn(str(other_client.id), ids)

    def test_slots_view_rejects_foreign_service_for_master(self):
        resp = self.client.get(
            f"/api/slots/?service={self.other_service.id}&date={self.day.isoformat()}"
        )
        self.assertEqual(resp.status_code, 404)

    def test_slots_view_allows_own_service(self):
        resp = self.client.get(
            f"/api/slots/?service={self.service.id}&date={self.day.isoformat()}"
        )
        self.assertEqual(resp.status_code, 200)

    def test_staff_sees_everything(self):
        """is_staff (Django admin) — без ограничения по сервису, как и раньше."""
        self.client.force_login(self.user)  # self.user из BaseSetup: is_staff=True
        names = [b["name"] for b in self.client.get("/api/bays/").json()]
        self.assertIn(self.other_bay.name, names)


class PushNotificationTests(BaseSetup):
    """
    Канал уведомлений (Telegram/push) выбирается клиентом/мастером и
    переключается в любой момент — см. Client.notification_channel /
    ServiceManager.notification_channel и core/services/push.py.
    """

    def setUp(self):
        super().setUp()
        from django.contrib.auth.models import User

        self.manager = ServiceManager.objects.create(
            service_point=self.sp, telegram_id=902, name="Мастер", user=self.user
        )
        self.client_user = User.objects.create_user("tg_111")
        self.client_obj.user = self.client_user
        self.client_obj.save(update_fields=["user"])

    # ---------- client_channel_ready ----------

    def test_channel_ready_telegram(self):
        from core.services.notifications import client_channel_ready

        self.client_obj.notification_channel = NotificationChannel.TELEGRAM
        self.client_obj.telegram_id = None
        self.assertFalse(client_channel_ready(self.client_obj))
        self.client_obj.telegram_id = 111
        self.assertTrue(client_channel_ready(self.client_obj))

    def test_channel_ready_push(self):
        from core.services.notifications import client_channel_ready

        self.client_obj.notification_channel = NotificationChannel.PUSH
        self.client_obj.push_token = ""
        self.assertFalse(client_channel_ready(self.client_obj))
        self.client_obj.push_token = "ExponentPushToken[xxx]"
        self.assertTrue(client_channel_ready(self.client_obj))

    # ---------- dispatch_batch маршрутизирует по каналу ----------

    def test_dispatch_batch_routes_push_client_to_push_not_telegram(self):
        from unittest.mock import AsyncMock

        from core.services.notifications import dispatch_batch

        self.client_obj.notification_channel = NotificationChannel.PUSH
        self.client_obj.push_token = "ExponentPushToken[xxx]"
        self.client_obj.save(update_fields=["notification_channel", "push_token"])
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(10)
        )
        n = Notification.objects.create(
            appointment=appt, notification_type=Notification.Type.REMINDER,
            scheduled_for=dj_tz.now(),
        )
        n = Notification.objects.select_related(
            "appointment__client", "appointment__service__service_point"
        ).get(pk=n.pk)
        with patch("bot.notify.deliver", new_callable=AsyncMock) as mock_deliver, \
             patch("core.services.push.send_push", return_value=True) as mock_push:
            result = dispatch_batch([(n, "текст напоминания")])
        mock_push.assert_called_once_with(
            "ExponentPushToken[xxx]", title="NavbatGo", body="текст напоминания"
        )
        mock_deliver.assert_not_called()
        self.assertEqual(result, {"sent": 1, "failed": 0})

    def test_dispatch_batch_routes_telegram_client_to_deliver(self):
        from unittest.mock import AsyncMock

        from core.services.notifications import dispatch_batch

        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(11)
        )
        n = Notification.objects.create(
            appointment=appt, notification_type=Notification.Type.REMINDER,
            scheduled_for=dj_tz.now(),
        )
        n = Notification.objects.select_related(
            "appointment__client", "appointment__service__service_point"
        ).get(pk=n.pk)
        with patch("bot.notify.deliver", new_callable=AsyncMock) as mock_deliver, \
             patch("core.services.push.send_push") as mock_push:
            mock_deliver.return_value = {str(n.pk): None}
            result = dispatch_batch([(n, "текст напоминания")])
        mock_deliver.assert_called_once()
        mock_push.assert_not_called()
        self.assertEqual(result, {"sent": 1, "failed": 0})

    # ---------- API: настройки клиента ----------

    def test_client_can_read_and_update_notification_channel(self):
        self.client.force_login(self.client_user)
        resp = self.client.get("/api/my/settings/")
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["notification_channel"], "telegram")

        resp = self.client.patch(
            "/api/my/settings/", {"notification_channel": "push"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["notification_channel"], "push")
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.notification_channel, "push")

    def test_client_settings_rejects_invalid_channel(self):
        self.client.force_login(self.client_user)
        resp = self.client.patch(
            "/api/my/settings/", {"notification_channel": "carrier_pigeon"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 400)

    # ---------- API: профиль мастера ----------

    def test_manager_can_update_notification_channel_via_profile(self):
        self.client.force_login(self.user)
        resp = self.client.patch(
            "/api/profile/", {"notification_channel": "push"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.assertEqual(resp.json()["notification_channel"], "push")
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.notification_channel, "push")

    # ---------- API: регистрация push-токена ----------

    def test_client_can_register_push_token(self):
        self.client.force_login(self.client_user)
        resp = self.client.post(
            "/api/notifications/push-token/", {"token": "ExponentPushToken[abc]"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.client_obj.refresh_from_db()
        self.assertEqual(self.client_obj.push_token, "ExponentPushToken[abc]")

    def test_manager_can_register_push_token(self):
        self.client.force_login(self.user)
        resp = self.client.post(
            "/api/notifications/push-token/", {"token": "ExponentPushToken[def]"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200, resp.content)
        self.manager.refresh_from_db()
        self.assertEqual(self.manager.push_token, "ExponentPushToken[def]")

    def test_register_push_token_requires_profile(self):
        from django.contrib.auth.models import User

        stray = User.objects.create_user("nobody")
        self.client.force_login(stray)
        resp = self.client.post(
            "/api/notifications/push-token/", {"token": "x"},
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 404)

    # ---------- мастера получают события на своём канале ----------

    def test_master_notify_uses_push_for_push_channel_manager(self):
        self.manager.notification_channel = NotificationChannel.PUSH
        self.manager.push_token = "ExponentPushToken[master]"
        self.manager.save(update_fields=["notification_channel", "push_token"])
        appt = create_appointment(
            client=self.client_obj, service=self.service, start_time=self.dt(12)
        )
        from core.services.master_notify import notify_masters_new

        with patch("core.services.push.send_push", return_value=True) as mock_push:
            notify_masters_new(appt)
        mock_push.assert_called_once()
        self.assertEqual(mock_push.call_args.args[0], "ExponentPushToken[master]")
