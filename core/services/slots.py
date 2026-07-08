"""
Расчёт свободных слотов.

Слоты строятся ПО КАЖДОМУ активному посту (Bay): кандидаты идут по сетке
SLOT_STEP_MINUTES в пределах рабочих часов; кандидат подходит, если интервал
[start, start + duration + buffer) не пересекает ни одну активную запись поста.
"""
from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime, time, timedelta
from zoneinfo import ZoneInfo

from django.conf import settings
from django.utils import timezone

from core.models import Appointment, Bay, Service, ServicePoint


@dataclass
class Slot:
    start: datetime                 # aware, в TZ сервиса
    end: datetime                   # start + duration + buffer
    bay_ids: list = field(default_factory=list)  # посты, свободные на это время


def slot_duration(service: Service, service_point: ServicePoint) -> timedelta:
    """Полная длина слота: услуга + буфер между записями."""
    return timedelta(minutes=service.duration_minutes + service_point.slot_buffer_minutes)


def _busy_intervals_by_bay(service_point: ServicePoint, day_start: datetime, day_end: datetime) -> dict:
    """Занятые интервалы активных записей за день, сгруппированные по постам."""
    busy: dict = {}
    qs = (
        Appointment.objects.filter(
            bay__service_point=service_point,
            status__in=Appointment.ACTIVE_STATUSES,
            start_time__lt=day_end,
            estimated_end_time__gt=day_start,
        )
        .values_list("bay_id", "start_time", "estimated_end_time")
    )
    for bay_id, start, end in qs:
        busy.setdefault(bay_id, []).append((start, end))
    return busy


def get_available_slots(service: Service, on_date: date_cls) -> list[Slot]:
    """Свободные слоты на дату для услуги. Пустой список, если день нерабочий."""
    sp = service.service_point
    if on_date.weekday() not in sp.work_days:
        return []

    tz = ZoneInfo(sp.timezone)
    day_start = datetime.combine(on_date, sp.work_start, tzinfo=tz)
    day_end = datetime.combine(on_date, sp.work_end, tzinfo=tz)
    total = slot_duration(service, sp)
    step = timedelta(minutes=settings.SLOT_STEP_MINUTES)

    # На сегодня не предлагаем прошедшее время: округляем "сейчас" вверх до сетки
    now = timezone.now().astimezone(tz)
    first_start = day_start
    if now > day_start:
        overshoot = (now - day_start) % step
        first_start = now + (step - overshoot if overshoot else timedelta())

    bays = list(Bay.objects.filter(service_point=sp, is_active=True))
    if not bays:
        return []
    busy = _busy_intervals_by_bay(sp, day_start, day_end)

    slots: list[Slot] = []
    t = first_start
    while t + total <= day_end:
        free_bay_ids = [
            bay.id
            for bay in bays
            if not any(bs < t + total and be > t for bs, be in busy.get(bay.id, []))
        ]
        if free_bay_ids:
            slots.append(Slot(start=t, end=t + total, bay_ids=free_bay_ids))
        t += step
    return slots


def is_within_work_hours(service_point: ServicePoint, start: datetime, end: datetime) -> bool:
    """Проверка инварианта: слот целиком внутри рабочего дня и в рабочий день недели."""
    tz = ZoneInfo(service_point.timezone)
    local_start = start.astimezone(tz)
    local_end = end.astimezone(tz)
    if local_start.weekday() not in service_point.work_days:
        return False
    if local_start.date() != local_end.date() and local_end.time() != time(0, 0):
        return False  # слот не должен переваливать через полночь
    day_open = datetime.combine(local_start.date(), service_point.work_start, tzinfo=tz)
    day_close = datetime.combine(local_start.date(), service_point.work_end, tzinfo=tz)
    return day_open <= local_start and local_end <= day_close
