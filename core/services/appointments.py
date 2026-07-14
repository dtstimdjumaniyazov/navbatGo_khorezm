"""
Операции с записями. Все инварианты enforce'ятся здесь (и дублируются
exclusion-констрейнтом в БД на случай гонки параллельных запросов).
"""
from datetime import datetime, timedelta

from django.db import IntegrityError, transaction
from django.db.models import F
from django.utils import timezone

from core.models import Appointment, Bay, Client, Notification, Service
from core.services.notifications import cancel_pending_notifications, schedule_reminder
from core.services.slots import is_within_work_hours


class BookingError(Exception):
    """Ошибка бронирования с человекочитаемым сообщением."""


class SlotTakenError(BookingError):
    """Слот уже занят (в т.ч. проигранная гонка за слот)."""


class ClientDoubleBookingError(BookingError):
    """У клиента уже есть активная запись на это время (в этом или другом сервисе)."""


def _find_free_bay(service: Service, start: datetime, end: datetime, bay: Bay | None) -> Bay:
    """Вернуть свободный пост на интервал. Если bay задан — проверить именно его."""
    candidates = [bay] if bay else list(
        Bay.objects.filter(service_point=service.service_point, is_active=True)
    )
    for candidate in candidates:
        overlap = (
            Appointment.objects.select_for_update()
            .filter(
                bay=candidate,
                status__in=Appointment.ACTIVE_STATUSES,
                start_time__lt=end,
                estimated_end_time__gt=start,
            )
            .exists()
        )
        if not overlap:
            return candidate
    raise SlotTakenError("Это время уже занято, выберите другой слот.")


@transaction.atomic
def create_appointment(
    *,
    client: Client,
    service: Service,
    start_time: datetime,
    bay: Bay | None = None,
    source: str = Appointment.Source.TELEGRAM,
    note: str = "",
    car_details: str = "",
    duration_minutes: int | None = None,
) -> Appointment:
    """
    Создать запись с проверкой всех инвариантов:
    рабочие часы, свободный пост, estimated_end = start + duration + buffer.
    Пост выбирается автоматически (первый свободный), если не указан явно.
    duration_minutes переопределяет длительность услуги (мастер может задать
    своё время, актуально для flexible-услуг).
    """
    sp = service.service_point
    if start_time < timezone.now():
        raise BookingError("Нельзя записаться на прошедшее время.")

    # Длительность работ храним в записи отдельно от буфера: история остаётся
    # корректной, даже если сервис потом поменяет slot_buffer_minutes
    duration = duration_minutes if duration_minutes is not None else service.duration_minutes
    end_time = start_time + timedelta(minutes=duration + sp.slot_buffer_minutes)
    if not is_within_work_hours(sp, start_time, end_time):
        raise BookingError("Время выходит за рамки рабочих часов сервиса.")

    # Один клиент не может быть одновременно записан в двух местах (в т.ч. на
    # разные сервисы) — раньше это никак не проверялось и позволяло записаться
    # на одно и то же время сразу в двух автосервисах.
    client_conflict = (
        Appointment.objects.select_for_update()
        .filter(
            client=client,
            status__in=Appointment.ACTIVE_STATUSES,
            start_time__lt=end_time,
            estimated_end_time__gt=start_time,
        )
        .exists()
    )
    if client_conflict:
        raise ClientDoubleBookingError(
            "У вас уже есть запись на это время в другом месте."
        )

    chosen_bay = _find_free_bay(service, start_time, end_time, bay)
    try:
        appt = Appointment.objects.create(
            client=client,
            service=service,
            bay=chosen_bay,
            start_time=start_time,
            duration_minutes=duration,
            estimated_end_time=end_time,
            source=source,
            note=note,
            car_details=car_details,
        )
    except IntegrityError as exc:
        # Гонка: кто-то занял слот (или тот же клиент параллельным запросом
        # успел записаться на пересекающееся время) между проверкой и вставкой
        raise SlotTakenError("Это время только что заняли, выберите другой слот.") from exc
    schedule_reminder(appt)
    return appt


class InvalidTransition(BookingError):
    """Недопустимый переход статуса."""


def _require_status(appt: Appointment, allowed: tuple):
    if appt.status not in allowed:
        raise InvalidTransition(
            f"Действие недоступно для записи в статусе «{appt.get_status_display()}»."
        )


def start_appointment(appt: Appointment) -> Appointment:
    """Мастер: «начал» — машина заехала на пост."""
    _require_status(appt, (Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED))
    appt.status = Appointment.Status.IN_PROGRESS
    appt.actual_start = timezone.now()
    appt.save(update_fields=["status", "actual_start", "updated_at"])
    return appt


def finish_appointment(appt: Appointment) -> Appointment:
    """Мастер: «закончил» — пост освобождается независимо от estimated_end_time."""
    _require_status(appt, (Appointment.Status.IN_PROGRESS,))
    appt.status = Appointment.Status.DONE
    appt.actual_end = timezone.now()
    appt.save(update_fields=["status", "actual_end", "updated_at"])
    return appt


@transaction.atomic
def mark_no_show(appt: Appointment) -> Appointment:
    """Мастер: «не приехал». Инкрементирует счётчик неявок клиента."""
    _require_status(appt, (Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED))
    appt.status = Appointment.Status.NO_SHOW
    appt.save(update_fields=["status", "updated_at"])
    Client.objects.filter(pk=appt.client_id).update(no_show_count=F("no_show_count") + 1)
    cancel_pending_notifications(appt)
    return appt


def cancel_appointment(
    appt: Appointment, cancelled_by: str = Appointment.CancelledBy.CLIENT
) -> Appointment:
    """Отмена клиентом (бот/сайт/приложение) или мастером."""
    _require_status(appt, Appointment.ACTIVE_STATUSES)
    appt.status = Appointment.Status.CANCELLED
    appt.cancelled_by = cancelled_by
    appt.save(update_fields=["status", "cancelled_by", "updated_at"])
    cancel_pending_notifications(appt)
    return appt


@transaction.atomic
def cancel_by_master(appt: Appointment, reason: str) -> tuple[Appointment, list[Notification]]:
    """
    Отмена мастером: причина обязательна — попадает клиенту в уведомление
    и в статистику отмен (метрика качества сервиса, cancelled_by=master
    не должно засчитываться клиенту как его собственная отмена/неявка).
    Клиенту с Telegram создаётся уведомление; отправку делает вызывающая
    сторона через notifications.send_now() — после коммита транзакции.
    """
    reason = reason.strip()
    if not reason:
        raise BookingError("Укажите причину отмены.")
    cancel_appointment(appt, cancelled_by=Appointment.CancelledBy.MASTER)
    appt.cancel_reason = reason
    appt.save(update_fields=["cancel_reason", "updated_at"])
    notifications = []
    if appt.client.telegram_id:
        notifications.append(
            Notification.objects.create(
                appointment=appt,
                notification_type=Notification.Type.CANCELLED,
                scheduled_for=timezone.now(),
            )
        )
    return appt, notifications


def confirm_appointment(appt: Appointment) -> Appointment:
    """Клиент подтвердил, что приедет."""
    _require_status(appt, (Appointment.Status.SCHEDULED,))
    appt.status = Appointment.Status.CONFIRMED
    appt.save(update_fields=["status", "updated_at"])
    return appt


# ---------- Overrun (этап 3, часть B) — консервативная первая версия ----------
#
# Явные допущения v1 (уточним после реальной работы сервиса):
# - сдвиг только вперёд (задержка), не назад;
# - X минут задаёт мастер;
# - сдвигаются ВСЕ последующие scheduled/confirmed записи поста, без разбора,
#   кто из клиентов уже в пути;
# - сдвинутая запись может уехать за рабочие часы — блокировать это нельзя,
#   задержка уже случилась, мастер сам решает;
# - статус сдвинутых записей не меняем (не rescheduled): запись по-прежнему
#   занимает пост, иначе слот ошибочно освободится для новых броней.


class ShiftRequired(BookingError):
    """Продление наезжает на следующие записи поста — нужен сдвиг очереди."""

    def __init__(self, message: str, conflicts: int):
        super().__init__(message)
        self.conflicts = conflicts


@transaction.atomic
def extend_appointment(appt: Appointment, extra_minutes: int) -> Appointment:
    """
    Продлить запись in_progress на X минут (машина задерживается на посту).
    Продлевается любая услуга — overrun случается и с fixed.
    Если новое окончание наезжает на следующие записи поста — ShiftRequired
    с количеством конфликтов: вызывающая сторона предлагает мастеру сдвиг.
    """
    _require_status(appt, (Appointment.Status.IN_PROGRESS,))
    if extra_minutes <= 0:
        raise BookingError("Продление должно быть положительным числом минут.")

    new_end = appt.estimated_end_time + timedelta(minutes=extra_minutes)
    conflicts = (
        Appointment.objects.filter(
            bay=appt.bay,
            status__in=(Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED),
            start_time__lt=new_end,
            estimated_end_time__gt=appt.estimated_end_time,
        )
        .exclude(pk=appt.pk)
        .count()
    )
    if conflicts:
        raise ShiftRequired(
            "Продление пересекается со следующими записями на этом посту — "
            "сдвиньте очередь.",
            conflicts=conflicts,
        )
    appt.estimated_end_time = new_end
    if appt.duration_minutes is not None:
        appt.duration_minutes += extra_minutes
    try:
        appt.save(update_fields=["estimated_end_time", "duration_minutes", "updated_at"])
    except IntegrityError as exc:
        # Страховка exclusion-констрейнта (гонка с параллельной записью)
        raise ShiftRequired(
            "Продление пересекается с другой записью — сдвиньте очередь.", conflicts=1
        ) from exc
    return appt


@transaction.atomic
def shift_queue(appt: Appointment, minutes: int) -> tuple[list[Appointment], list]:
    """
    Сдвинуть на +X минут все последующие scheduled/confirmed записи
    ТОГО ЖЕ поста (сама appt не сдвигается — это задержавшаяся запись).
    Каждому затронутому клиенту с Telegram создаётся Notification(shifted);
    отправку делает вызывающая сторона через notifications.send_now() —
    уже после коммита транзакции.
    Возвращает (сдвинутые записи, созданные уведомления).
    """
    if minutes <= 0:
        raise BookingError("Сдвиг возможен только вперёд, на положительное число минут.")

    delta = timedelta(minutes=minutes)
    # С конца очереди: exclusion-констрейнт проверяется на каждом UPDATE,
    # и сдвиг последней записи первым освобождает место для предыдущих
    to_shift = list(
        Appointment.objects.select_for_update()
        .select_related("client")
        .filter(
            bay=appt.bay,
            status__in=(Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED),
            start_time__gte=appt.start_time,
        )
        .exclude(pk=appt.pk)
        .order_by("-start_time")
    )
    now = timezone.now()
    notifications = []
    for a in to_shift:
        a.start_time += delta
        a.estimated_end_time += delta
        a.save(update_fields=["start_time", "estimated_end_time", "updated_at"])
        # Неотправленное напоминание едет вместе с записью (текст строится
        # при отправке из актуального start_time, менять его не нужно)
        a.notifications.filter(
            notification_type=Notification.Type.REMINDER,
            status=Notification.Status.PENDING,
        ).update(scheduled_for=F("scheduled_for") + delta)
        if a.client.telegram_id:
            notifications.append(
                Notification.objects.create(
                    appointment=a,
                    notification_type=Notification.Type.SHIFTED,
                    scheduled_for=now,
                )
            )
    # Порядок «раньше — раньше» для ответа API
    to_shift.reverse()
    return to_shift, notifications
