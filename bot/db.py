"""
Асинхронные обёртки над Django ORM и сервисным слоем для бота.
Бот работает с БД напрямую через core.services — инварианты в одном месте,
без лишнего HTTP-слоя.
"""
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from asgiref.sync import sync_to_async
from django.db import transaction

from core.models import Appointment, Bay, Client, Service, ServiceManager, ServicePoint
from core.services import appointments as appt_service
from core.services.notifications import send_now
from core.services.slots import get_available_slots

APPT_RELATED = ("client", "service", "bay", "service__service_point")


@sync_to_async
def get_or_create_client(telegram_id: int) -> tuple[Client, bool]:
    return Client.objects.get_or_create(telegram_id=telegram_id)


@sync_to_async
def update_client(client_id, **fields) -> None:
    Client.objects.filter(pk=client_id).update(**fields)


@sync_to_async
def get_service_point() -> ServicePoint | None:
    return ServicePoint.objects.filter(is_active=True).first()


@sync_to_async
def get_active_services() -> list[Service]:
    return list(Service.objects.filter(is_active=True).select_related("service_point"))


@sync_to_async
def get_service(service_id) -> Service | None:
    return Service.objects.filter(pk=service_id).select_related("service_point").first()


@sync_to_async
def get_slots(service: Service, on_date: date):
    return get_available_slots(service, on_date)


@sync_to_async
def book_appointment(client: Client, service: Service, start_time: datetime) -> Appointment:
    appt = appt_service.create_appointment(
        client=client,
        service=service,
        start_time=start_time,
        source=Appointment.Source.TELEGRAM,
    )
    # подтягиваем связи для отображения без ленивых запросов в async-контексте
    return Appointment.objects.select_related("service", "bay").get(pk=appt.pk)


@sync_to_async
def get_my_appointments(client: Client) -> list[Appointment]:
    from django.utils import timezone

    return list(
        Appointment.objects.filter(
            client=client,
            status__in=Appointment.ACTIVE_STATUSES,
            start_time__gte=timezone.now(),
        )
        .select_related("service", "bay")
        .order_by("start_time")
    )


@sync_to_async
def cancel_my_appointment(appointment_id, client: Client) -> Appointment | None:
    appt = (
        Appointment.objects.select_related("service")
        .filter(pk=appointment_id, client=client)
        .first()
    )
    if appt is None:
        return None
    return appt_service.cancel_appointment(appt)


# ---------- режим мастера ----------

@sync_to_async
def get_manager(telegram_id: int) -> ServiceManager | None:
    """Роль пользователя: мастер активного сервиса или None (клиент)."""
    return (
        ServiceManager.objects.select_related("service_point")
        .filter(telegram_id=telegram_id, is_active=True, service_point__is_active=True)
        .first()
    )


def _day_bounds(sp: ServicePoint, on_date: date) -> tuple[datetime, datetime]:
    tz = ZoneInfo(sp.timezone)
    start = datetime.combine(on_date, time.min, tzinfo=tz)
    return start, start + timedelta(days=1)


@sync_to_async
def get_day_appointments(sp: ServicePoint, on_date: date) -> list[Appointment]:
    start, end = _day_bounds(sp, on_date)
    return list(
        Appointment.objects.filter(
            bay__service_point=sp, start_time__gte=start, start_time__lt=end
        )
        .select_related(*APPT_RELATED)
        .order_by("start_time")
    )


@sync_to_async
def get_sp_appointment(appointment_id, sp: ServicePoint) -> Appointment | None:
    """Запись строго своего сервиса — мастер не достанет чужую."""
    return (
        Appointment.objects.filter(pk=appointment_id, bay__service_point=sp)
        .select_related(*APPT_RELATED)
        .first()
    )


@sync_to_async
def get_current_appointment(sp: ServicePoint) -> Appointment | None:
    """Текущая (in_progress) или ближайшая будущая активная запись."""
    from django.utils import timezone

    qs = Appointment.objects.filter(bay__service_point=sp).select_related(*APPT_RELATED)
    current = (
        qs.filter(status=Appointment.Status.IN_PROGRESS).order_by("start_time").first()
    )
    if current:
        return current
    return (
        qs.filter(
            status__in=(Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED),
            start_time__gte=timezone.now(),
        )
        .order_by("start_time")
        .first()
    )


MASTER_ACTIONS = {
    "start": appt_service.start_appointment,
    "finish": appt_service.finish_appointment,
    "noshow": appt_service.mark_no_show,
    "cancel": appt_service.cancel_appointment,
}


@sync_to_async
def master_action(appointment_id, sp: ServicePoint, action: str) -> Appointment | None:
    """Переход статуса через сервисный слой (инварианты те же, что в панели)."""
    appt = (
        Appointment.objects.filter(pk=appointment_id, bay__service_point=sp)
        .select_related(*APPT_RELATED)
        .first()
    )
    if appt is None:
        return None
    MASTER_ACTIONS[action](appt)  # BookingError пробрасывается наверх
    return appt


@sync_to_async
def master_extend(appointment_id, sp: ServicePoint, minutes: int) -> Appointment | None:
    appt = (
        Appointment.objects.filter(pk=appointment_id, bay__service_point=sp)
        .select_related(*APPT_RELATED)
        .first()
    )
    if appt is None:
        return None
    return appt_service.extend_appointment(appt, extra_minutes=minutes)


@sync_to_async
def count_shift_targets(appt: Appointment) -> int:
    """Сколько записей уедет при сдвиге очереди от этой записи."""
    return (
        Appointment.objects.filter(
            bay=appt.bay,
            status__in=(Appointment.Status.SCHEDULED, Appointment.Status.CONFIRMED),
            start_time__gte=appt.start_time,
        )
        .exclude(pk=appt.pk)
        .count()
    )


@sync_to_async
def get_active_bays(sp: ServicePoint) -> list[Bay]:
    return list(Bay.objects.filter(service_point=sp, is_active=True))


@sync_to_async
def get_sp_service(service_id, sp: ServicePoint) -> Service | None:
    return (
        Service.objects.filter(pk=service_id, service_point=sp, is_active=True)
        .select_related("service_point")
        .first()
    )


@sync_to_async
def master_create_walkin(
    sp: ServicePoint, bay_id, service_id, start_time: datetime, name: str, phone: str
) -> Appointment:
    """
    Клиент «с улицы»: новый Client без telegram_id + запись source=manual
    через тот же create_appointment (непересечение, рабочие часы — те же).
    Транзакция: при занятом слоте клиент-сирота не остаётся.
    """
    with transaction.atomic():
        bay = Bay.objects.filter(pk=bay_id, service_point=sp, is_active=True).first()
        service = (
            Service.objects.filter(pk=service_id, service_point=sp, is_active=True)
            .select_related("service_point")
            .first()
        )
        if bay is None or service is None:
            raise appt_service.BookingError("Пост или услуга не найдены.")
        client = Client.objects.create(name=name, phone=phone)
        appt = appt_service.create_appointment(
            client=client,
            service=service,
            bay=bay,
            start_time=start_time,
            source=Appointment.Source.MANUAL,
        )
    return Appointment.objects.select_related(*APPT_RELATED).get(pk=appt.pk)


@sync_to_async
def master_shift(appointment_id, sp: ServicePoint, minutes: int) -> dict | None:
    """Сдвиг очереди + немедленная рассылка shifted-уведомлений."""
    appt = Appointment.objects.filter(pk=appointment_id, bay__service_point=sp).first()
    if appt is None:
        return None
    shifted, notifications = appt_service.shift_queue(appt, minutes)
    delivery = send_now(notifications)
    return {"shifted": len(shifted), **delivery}
