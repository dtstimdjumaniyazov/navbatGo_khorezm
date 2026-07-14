"""
График работы сервиса: базовые часы (work_days + work_start/work_end)
плюс переопределения по дням недели (WorkingHours: другие часы / выходной).
Единая точка правды для слотов, бота и клиентских интерфейсов.
"""
from datetime import time

from core.models import ServicePoint


def day_hours(sp: ServicePoint, weekday: int) -> tuple[time, time] | None:
    """Часы работы в день недели (0=Пн … 6=Вс); None — выходной."""
    override = next(
        (wh for wh in sp.working_hours.all() if wh.weekday == weekday), None
    )
    if override is not None:
        if override.is_closed or not (override.work_start and override.work_end):
            return None
        return override.work_start, override.work_end
    if weekday in sp.work_days:
        return sp.work_start, sp.work_end
    return None


def week_schedule(sp: ServicePoint) -> list[dict]:
    """
    Неделя целиком для витрин: [{weekday, start, end}] × 7,
    start/end = None — выходной. Время строками «HH:MM».
    """
    result = []
    for weekday in range(7):
        hours = day_hours(sp, weekday)
        result.append({
            "weekday": weekday,
            "start": hours[0].strftime("%H:%M") if hours else None,
            "end": hours[1].strftime("%H:%M") if hours else None,
        })
    return result
