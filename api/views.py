from datetime import datetime

from django.conf import settings
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import AllowAny, BasePermission
from rest_framework.response import Response
from rest_framework.throttling import ScopedRateThrottle
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from api.serializers import (
    AppointmentCreateSerializer,
    AppointmentSerializer,
    BaySerializer,
    ClientSerializer,
    ManagerMediaCreateSerializer,
    ManagerProfileSerializer,
    MyBookingSerializer,
    PublicProfileSerializer,
    ServiceMediaSerializer,
    ServicePointSerializer,
    ServiceSerializer,
    SlotSerializer,
)
from core.models import (
    Appointment,
    Bay,
    Client,
    NotificationChannel,
    Service,
    ServiceManager,
    ServicePoint,
    ServicePointMedia,
)
from core.services import appointments as appt_service
from core.services import telegram_auth
from core.services.clients import get_or_create_walkin_client, normalize_phone
from core.services.master_notify import notify_masters_cancelled, notify_masters_new
from core.services.notifications import send_now
from core.services.slots import get_available_slots


class IsManager(BasePermission):
    """Служебные API (записи, услуги, посты) — только мастерам и админам."""

    message = "Доступно только мастерам сервиса."

    def has_permission(self, request, view):
        user = request.user
        if not (user and user.is_authenticated):
            return False
        return user.is_staff or ServiceManager.objects.filter(
            user=user, is_active=True
        ).exists()


class TelegramLoginStartView(APIView):
    """
    Начало входа через Telegram: выдаёт одноразовый код и deep-link на бота.
    Приложение открывает ссылку, пользователь жмёт Start — бот подтверждает код.
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "telegram_login"

    def post(self, request):
        login = telegram_auth.start_login()
        deep_link = (
            f"https://t.me/{settings.BOT_USERNAME}?start=login_{login.code}"
            if settings.BOT_USERNAME
            else None
        )
        return Response({
            "code": login.code,
            "deep_link": deep_link,
            "expires_in": int(telegram_auth.CODE_TTL.total_seconds()),
        })


class TelegramLoginPollView(APIView):
    """
    Опрос кода входа: {"code": "..."}. Пока Start не нажат — {"status": "pending"};
    после подтверждения — JWT-пара (один раз, код гасится).
    """

    permission_classes = [AllowAny]
    throttle_classes = [ScopedRateThrottle]
    throttle_scope = "telegram_login"

    def post(self, request):
        code = str(request.data.get("code", ""))
        if not code:
            return Response({"detail": "Не передан code."}, status=400)
        result = telegram_auth.poll_login(code)
        if result == "pending":
            return Response({"status": "pending"})
        if result == "invalid":
            return Response(
                {"status": "invalid", "detail": "Код недействителен или истёк."},
                status=status.HTTP_404_NOT_FOUND,
            )
        role, obj = result
        refresh = RefreshToken.for_user(obj.user)
        payload = {
            "status": "ok",
            "role": role,
            "access": str(refresh.access_token),
            "refresh": str(refresh),
        }
        if role == "master":
            payload["manager"] = {
                "name": obj.name,
                "role": obj.role,
                "language": obj.language,
                "service_point": str(obj.service_point_id),
                "service_point_name": obj.service_point.name,
            }
        else:
            payload["client"] = {
                "id": str(obj.id),
                "name": obj.name,
                "phone": obj.phone,
                "language": obj.language,
            }
        return Response(payload)


class MeView(APIView):
    """Кто вошёл: мастер (manager) или клиент (client) — роль для приложений."""

    def get(self, request):
        manager = (
            ServiceManager.objects.select_related("service_point")
            .filter(user=request.user, is_active=True)
            .first()
        )
        client = None
        if manager is None:
            client = Client.objects.filter(user=request.user).first()
        return Response({
            "username": request.user.username,
            "manager": (
                {
                    "name": manager.name,
                    "role": manager.role,
                    "language": manager.language,
                    "service_point": str(manager.service_point_id),
                    "service_point_name": manager.service_point.name,
                    "notification_channel": manager.notification_channel,
                }
                if manager
                else None
            ),
            "client": (
                {
                    "id": str(client.id),
                    "name": client.name,
                    "phone": client.phone,
                    "language": client.language,
                    "notification_channel": client.notification_channel,
                }
                if client
                else None
            ),
        })


def _scope_to_manager(request, qs, field: str):
    """
    Ограничить queryset собственным сервисом мастера — иначе любой
    авторизованный мастер видел бы посты/услуги/записи ЧУЖИХ сервисов
    (найденный баг: в «Новой записи» показывались посты соседнего автосервиса).
    Staff (Django admin) видит всё без ограничения.
    """
    if request.user.is_staff:
        return qs
    manager = _get_manager(request)
    if manager is None:
        return qs.none()
    return qs.filter(**{field: manager.service_point_id}).distinct()


def _get_manager(request) -> ServiceManager | None:
    return (
        ServiceManager.objects.select_related("service_point")
        .filter(user=request.user, is_active=True)
        .first()
    )


class MyProfileView(APIView):
    """Профиль текущего мастера: GET — посмотреть, PATCH — изменить (+аватар)."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]

    def get(self, request):
        manager = _get_manager(request)
        if manager is None:
            return Response({"detail": "Профиль мастера не найден."}, status=404)
        return Response(ManagerProfileSerializer(manager, context={"request": request}).data)

    def patch(self, request):
        manager = _get_manager(request)
        if manager is None:
            return Response({"detail": "Профиль мастера не найден."}, status=404)
        serializer = ManagerProfileSerializer(
            manager, data=request.data, partial=True, context={"request": request}
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class MyMediaView(APIView):
    """Галерея СВОЕГО сервиса: POST — добавить фото (multipart) или видео-ссылку."""

    parser_classes = [MultiPartParser, FormParser, JSONParser]
    MAX_ITEMS = 30

    def post(self, request):
        manager = _get_manager(request)
        if manager is None:
            return Response({"detail": "Профиль мастера не найден."}, status=404)
        sp = manager.service_point
        if sp.media.count() >= self.MAX_ITEMS:
            return Response(
                {"detail": f"В галерее максимум {self.MAX_ITEMS} элементов."}, status=400
            )
        serializer = ManagerMediaCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data
        is_video = bool(data.get("video_url"))
        if is_video and sp.media.filter(media_type=ServicePointMedia.MediaType.VIDEO).exists():
            return Response(
                {"detail": "Видео уже добавлено — удалите текущее, чтобы заменить его на другое."},
                status=400,
            )
        item = ServicePointMedia.objects.create(
            service_point=sp,
            media_type=(
                ServicePointMedia.MediaType.PHOTO if data.get("image")
                else ServicePointMedia.MediaType.VIDEO
            ),
            image=data.get("image"),
            video_url=data.get("video_url", ""),
            caption=data.get("caption", ""),
            order=data.get("order", 0),
        )
        return Response(
            ServiceMediaSerializer(item, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class MyMediaDetailView(APIView):
    """Удаление элемента галереи своего сервиса (вместе с файлом)."""

    def delete(self, request, pk):
        manager = _get_manager(request)
        if manager is None:
            return Response({"detail": "Профиль мастера не найден."}, status=404)
        item = ServicePointMedia.objects.filter(
            pk=pk, service_point=manager.service_point
        ).first()
        if item is None:
            return Response({"detail": "Элемент не найден."}, status=404)
        if item.image:
            item.image.delete(save=False)
        item.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class PublicProfileView(APIView):
    """
    Публичная витрина сервиса — без аутентификации: клиенты (сайт, приложение,
    бот) видят описание, адрес, галерею, мастеров и услуги. Только чтение.
    """

    permission_classes = [AllowAny]

    def get(self, request, pk):
        sp = ServicePoint.objects.filter(pk=pk, is_active=True).first()
        if sp is None:
            return Response({"detail": "Сервис не найден."}, status=404)
        return Response(PublicProfileSerializer(sp, context={"request": request}).data)


class PublicServicePointListView(APIView):
    """Каталог активных сервисов — стартовая страница клиента."""

    permission_classes = [AllowAny]

    def get(self, request):
        qs = (
            ServicePoint.objects.filter(is_active=True)
            .order_by("name")
            .prefetch_related("media", "managers", "services")
        )
        return Response(
            PublicProfileSerializer(qs, many=True, context={"request": request}).data
        )


def _get_client(request) -> Client | None:
    return Client.objects.filter(user=request.user).first()


class MySettingsView(APIView):
    """Настройки клиента: канал уведомлений (Telegram/push), меняется в любой момент."""

    def get(self, request):
        client = _get_client(request)
        if client is None:
            return Response({"detail": "Профиль клиента не найден."}, status=404)
        return Response({"notification_channel": client.notification_channel})

    def patch(self, request):
        client = _get_client(request)
        if client is None:
            return Response({"detail": "Профиль клиента не найден."}, status=404)
        channel = request.data.get("notification_channel")
        if channel not in NotificationChannel.values:
            return Response({"detail": "Некорректный канал уведомлений."}, status=400)
        client.notification_channel = channel
        client.save(update_fields=["notification_channel", "updated_at"])
        return Response({"notification_channel": client.notification_channel})


class RegisterPushTokenView(APIView):
    """Сохранить Expo push-токен текущего пользователя (клиент или мастер)."""

    def post(self, request):
        token = (request.data.get("token") or "").strip()
        if not token:
            return Response({"detail": "Токен обязателен."}, status=400)
        manager = _get_manager(request)
        if manager is not None:
            manager.push_token = token
            manager.save(update_fields=["push_token", "updated_at"])
            return Response({"status": "ok"})
        client = _get_client(request)
        if client is not None:
            client.push_token = token
            client.save(update_fields=["push_token", "updated_at"])
            return Response({"status": "ok"})
        return Response({"detail": "Профиль не найден."}, status=404)


class MyAppointmentsView(APIView):
    """Клиент: список своих активных записей (GET) и новая запись (POST)."""

    def get(self, request):
        client = _get_client(request)
        if client is None:
            return Response({"detail": "Профиль клиента не найден."}, status=404)
        qs = (
            Appointment.objects.filter(
                client=client,
                status__in=Appointment.ACTIVE_STATUSES,
                start_time__gte=timezone.now(),
            )
            .select_related("client", "service__service_point", "bay")
            .order_by("start_time")
        )
        return Response(AppointmentSerializer(qs, many=True).data)

    def post(self, request):
        client = _get_client(request)
        if client is None:
            return Response({"detail": "Профиль клиента не найден."}, status=404)
        serializer = MyBookingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Имя/телефон из формы обновляют профиль клиента (первый вход с сайта)
        updates = {}
        if data.get("name", "").strip():
            updates["name"] = data["name"].strip()
        if data.get("phone", "").strip():
            updates["phone"] = normalize_phone(data["phone"])[:32]
        if updates:
            for field, value in updates.items():
                setattr(client, field, value)
            client.save(update_fields=[*updates, "updated_at"])

        try:
            appt = appt_service.create_appointment(
                client=client,
                service=data["service"],
                start_time=data["start_time"],
                source=Appointment.Source.APP,
                car_details=data.get("car_details", ""),
            )
        except appt_service.BookingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        notify_masters_new(appt)
        return Response(AppointmentSerializer(appt).data, status=status.HTTP_201_CREATED)


class MyAppointmentCancelView(APIView):
    """Клиент отменяет СВОЮ запись; мастера узнают в Telegram."""

    def post(self, request, pk):
        client = _get_client(request)
        if client is None:
            return Response({"detail": "Профиль клиента не найден."}, status=404)
        appt = (
            Appointment.objects.filter(pk=pk, client=client)
            .select_related("client", "service__service_point", "bay")
            .first()
        )
        if appt is None:
            return Response({"detail": "Запись не найдена."}, status=404)
        try:
            appt_service.cancel_appointment(appt)
        except appt_service.BookingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        notify_masters_cancelled(appt)
        return Response(AppointmentSerializer(appt).data)


class ServicePointViewSet(viewsets.ModelViewSet):
    queryset = ServicePoint.objects.all()
    serializer_class = ServicePointSerializer
    permission_classes = [IsManager]

    def get_queryset(self):
        return _scope_to_manager(self.request, super().get_queryset(), "id")

    def update(self, request, *args, **kwargs):
        # Менять настройки (напоминания, описание, Instagram) может только
        # мастер этого сервиса — не соседнего
        manager = _get_manager(request)
        if manager is None or str(manager.service_point_id) != str(kwargs.get("pk")):
            return Response({"detail": "Можно менять только свой сервис."}, status=403)
        return super().update(request, *args, **kwargs)


class BayViewSet(viewsets.ModelViewSet):
    queryset = Bay.objects.all()
    serializer_class = BaySerializer
    permission_classes = [IsManager]

    def get_queryset(self):
        qs = _scope_to_manager(self.request, super().get_queryset(), "service_point")
        if self.request.query_params.get("active") == "1":
            qs = qs.filter(is_active=True)
        return qs


class ServiceViewSet(viewsets.ModelViewSet):
    queryset = Service.objects.all()
    serializer_class = ServiceSerializer
    permission_classes = [IsManager]

    def get_queryset(self):
        qs = _scope_to_manager(self.request, super().get_queryset(), "service_point")
        if self.request.query_params.get("active") == "1":
            qs = qs.filter(is_active=True)
        return qs


class ClientViewSet(viewsets.ModelViewSet):
    """
    Клиенты не привязаны к одному сервису (могут записываться в разные) —
    мастеру показываем только тех, кто хоть раз записывался к нему.
    """

    queryset = Client.objects.all()
    serializer_class = ClientSerializer
    permission_classes = [IsManager]

    def get_queryset(self):
        return _scope_to_manager(
            self.request, super().get_queryset(), "appointments__bay__service_point"
        )


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

        # Мастер видит все слоты своего сервиса (клиент уже на месте — запись
        # «с улицы»); чужой сервис ему недоступен — только staff видит любой.
        # Клиенту (бот/приложение/сайт) слот ближе min_lead_minutes не предлагаем.
        manager = _get_manager(request)
        if manager is not None and not request.user.is_staff:
            if service.service_point_id != manager.service_point_id:
                return Response({"detail": "Услуга не найдена."}, status=status.HTTP_404_NOT_FOUND)
        is_master = request.user.is_staff or manager is not None
        slots = get_available_slots(service, on_date, apply_lead_time=not is_master)
        return Response(SlotSerializer(slots, many=True).data)


class AppointmentViewSet(viewsets.ModelViewSet):
    """
    CRUD записей + действия мастера:
    POST /appointments/{id}/start|finish|no_show|cancel|confirm/
    Фильтры списка: ?date=YYYY-MM-DD, ?status=..., ?bay=<uuid>
    """
    queryset = Appointment.objects.select_related("client", "service__service_point", "bay")
    serializer_class = AppointmentSerializer
    permission_classes = [IsManager]
    http_method_names = ["get", "post", "patch", "delete"]

    def get_queryset(self):
        qs = _scope_to_manager(self.request, super().get_queryset(), "bay__service_point")
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

        # Услуга/пост должны принадлежать сервису самого мастера — иначе
        # можно было записать клиента на чужой пост чужой услугой (тот баг)
        manager = _get_manager(request)
        if manager is not None and not request.user.is_staff:
            own_sp = manager.service_point_id
            if data["service"].service_point_id != own_sp:
                return Response({"detail": "Услуга не найдена."}, status=status.HTTP_404_NOT_FOUND)
            bay = data.get("bay")
            if bay is not None and bay.service_point_id != own_sp:
                return Response({"detail": "Пост не найден."}, status=status.HTTP_404_NOT_FOUND)

        client = data.get("client")
        if client is None:
            # Клиент «с улицы»: ищется по телефону (дедуп) или создаётся новый
            client = get_or_create_walkin_client(
                data.get("client_name", ""), data.get("client_phone", "")
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
                if new_status == Appointment.Status.CANCELLED:
                    # Отмена мастером — причина обязательна, клиент узнаёт в Telegram
                    reason = request.data.get("reason", "")
                    appt, notifications = appt_service.cancel_by_master(appt, reason)
                    send_now(notifications)
                else:
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
        """Отмена мастером: причина обязательна, клиенту с Telegram сразу уходит уведомление."""
        appt = self.get_object()
        reason = request.data.get("reason", "")
        try:
            appt, notifications = appt_service.cancel_by_master(appt, reason)
        except appt_service.BookingError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_409_CONFLICT)
        send_now(notifications)
        return Response(AppointmentSerializer(appt).data)

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
