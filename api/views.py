from datetime import datetime

from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    BaySerializer,
    ClientSerializer,
    ServicePointSerializer,
    ServiceSerializer,
    SlotSerializer,
)
from core.models import Appointment, Bay, Client, Service, ServicePoint
from core.services import appointments as appt_service
from core.services.notifications import send_now
from core.services.slots import get_available_slots


class ServicePointViewSet(viewsets.ModelViewSet):
    queryset = ServicePoint.objects.all()
    serializer_class = ServicePointSerializer


class BayViewSet(viewsets.ModelViewSet):
    queryset = Bay.objects.all()
    serializer_class = BaySerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("active") == "1":
            qs = qs.filter(is_active=True)
        return qs


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.query_params.get("active") == "1":
            qs = qs.filter(is_active=True)
        return qs


class ClientViewSet(viewsets.ModelViewSet):
    queryset = Client.objects.all()
    serializer_class = ClientSerializer


class SlotsView(APIView):
    """GET /api/slots/?service=<uuid>&date=YYYY-MM-DD — свободные слоты по постам."""

    def get(self, request):
        service_id = request.query_params.get("service")
        date_str = request.query_params.get("date")
        if not service_id or not date_str:
            return Response(
                {"detail": "Обязательные параметры: service, date (YYYY-MM-DD)."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            service = Service.objects.get(pk=service_id, is_active=True)
        except (Service.DoesNotExist, ValueError):
            return Response({"detail": "Услуга не найдена."}, status=status.HTTP_404_NOT_FOUND)
        try:
            on_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response({"detail": "Неверный формат даты."}, status=status.HTTP_400_BAD_REQUEST)

        slots = get_available_slots(service, on_date)
        return Response(SlotSerializer(slots, many=True).data)


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    CRUD записей + действия мастера:
    POST /appointments/{id}/start|finish|no_show|cancel|confirm/
    Фильтры списка: ?date=YYYY-MM-DD, ?status=..., ?bay=<uuid>
    """
    queryset = Appointment.objects.select_related("client", "service", "bay")
    serializer_class = AppointmentSerializer
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        qs = super().get_queryset()
        params = self.request.query_params
        if date_str := params.get("date"):
            try:
                on_date = datetime.strptime(date_str, "%Y-%m-%d").date()
            except ValueError:
                return qs.none()
            # день в TZ по умолчанию (TZ сервиса совпадает с settings.TIME_ZONE)
            tz = timezone.get_default_timezone()
            day_start = datetime.combine(on_date, datetime.min.time(), tzinfo=tz)
            day_end = datetime.combine(on_date, datetime.max.time(), tzinfo=tz)
            qs = qs.filter(start_time__range=(day_start, day_end))
        if status_param := params.get("status"):
            qs = qs.filter(status=status_param)
        if bay := params.get("bay"):
            qs = qs.filter(bay_id=bay)
        return qs

    def create(self, request, *args, **kwargs):
        serializer = AppointmentCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        client = data.get("client")
        if client is None:
            # Клиент «с улицы»: мастер добавляет вручную, telegram_id отсутствует
            client = Client.objects.create(
                name=data.get("client_name", ""), phone=data.get("client_phone", "")
            )
        try:
            appt = appt_service.create_appointment(
                client=client,
                service=data["service"],
                start_time=data["start_time"],
                bay=data.get("bay"),
                source=data["source"],
                note=data.get("note", ""),
                car_details=data.get("car_details", ""),
                duration_minutes=data.get("duration_minutes"),
            )
        except appt_service.BookingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AppointmentSerializer(appt).data, status=status.HTTP_201_CREATED)

    # Смена статуса через PATCH {"status": "..."} — переходы идут через сервисный
    # слой (инкремент неявок, actual_start/actual_end), а не прямой записью в поле
    STATUS_TRANSITIONS = {
        Appointment.Status.CONFIRMED: appt_service.confirm_appointment,
        Appointment.Status.IN_PROGRESS: appt_service.start_appointment,
        Appointment.Status.DONE: appt_service.finish_appointment,
        Appointment.Status.NO_SHOW: appt_service.mark_no_show,
        Appointment.Status.CANCELLED: appt_service.cancel_appointment,
    }

    def partial_update(self, request, *args, **kwargs):
        appt = self.get_object()
        new_status = request.data.get("status")
        if new_status and new_status != appt.status:
            func = self.STATUS_TRANSITIONS.get(new_status)
            if func is None:
                return Response(
                    {"detail": f"Недопустимый статус: {new_status}."},
                    status=status.HTTP_400_BAD_REQUEST,
                )
            try:
                appt = func(appt)
            except appt_service.BookingError as exc:
                return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        serializer = self.get_serializer(appt, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)

    def _transition(self, request, pk, func, **kwargs):
        appt = self.get_object()
        try:
            appt = func(appt, **kwargs)
        except appt_service.BookingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AppointmentSerializer(appt).data)

    @action(detail=True, methods=["post"])
    def start(self, request, pk=None):
        return self._transition(request, pk, appt_service.start_appointment)

    @action(detail=True, methods=["post"])
    def finish(self, request, pk=None):
        return self._transition(request, pk, appt_service.finish_appointment)

    @action(detail=True, methods=["post"])
    def no_show(self, request, pk=None):
        return self._transition(request, pk, appt_service.mark_no_show)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        return self._transition(request, pk, appt_service.cancel_appointment)

    @action(detail=True, methods=["post"])
    def confirm(self, request, pk=None):
        return self._transition(request, pk, appt_service.confirm_appointment)

    @action(detail=True, methods=["post"])
    def extend(self, request, pk=None):
        """
        Продлить in_progress-запись: {"extra_minutes": 30}.
        409 + needs_shift=true, если продление наезжает на следующие записи
        поста — тогда мастеру предлагается shift_queue.
        """
        try:
            extra = int(request.data.get("extra_minutes", 0))
        except (TypeError, ValueError):
            extra = 0
        if extra <= 0:
            return Response(
                {"detail": "extra_minutes должен быть положительным числом."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        appt = self.get_object()
        try:
            appt = appt_service.extend_appointment(appt, extra_minutes=extra)
        except appt_service.ShiftRequired as exc:
            return Response(
                {"detail": str(exc), "needs_shift": True, "conflicts": exc.conflicts},
                status=status.HTTP_409_CONFLICT,
            )
        except appt_service.BookingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        return Response(AppointmentSerializer(appt).data)

    @action(detail=True, methods=["post"], url_path="shift_queue")
    def shift_queue(self, request, pk=None):
        """
        Сдвинуть очередь поста: {"minutes": 30}.
        Сдвигает все последующие scheduled/confirmed записи этого поста
        на +X минут и сразу шлёт клиентам shifted-уведомления в Telegram.
        """
        try:
            minutes = int(request.data.get("minutes", 0))
        except (TypeError, ValueError):
            minutes = 0
        if minutes <= 0:
            return Response(
                {"detail": "minutes должен быть положительным числом."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        appt = self.get_object()
        try:
            shifted, notifications = appt_service.shift_queue(appt, minutes)
        except appt_service.BookingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        # Отправка после коммита сдвига: сдвиг не откатится из-за проблем Telegram
        delivery = send_now(notifications)
        return Response({
            "shifted_count": len(shifted),
            "appointments": AppointmentSerializer(shifted, many=True).data,
            "notified": delivery["sent"],
            "notify_failed": delivery["failed"],
        })
