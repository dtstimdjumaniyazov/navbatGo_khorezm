from rest_framework import serializers

from core.models import (
    Appointment,
    Bay,
    Client,
    Service,
    ServiceManager,
    ServicePoint,
    ServicePointMedia,
)
from core.services.schedule import week_schedule


class ServicePointSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePoint
        fields = (
            "id", "name", "description", "description_uz", "address", "address_uz",
            "latitude", "longitude",
            "timezone", "work_start", "work_end", "work_days",
            "slot_buffer_minutes", "reminder_hours_before", "min_lead_minutes",
            "instagram", "is_active",
        )


MAX_IMAGE_MB = 10


class ServiceMediaSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePointMedia
        fields = ("id", "media_type", "image", "video_url", "caption", "order")
        read_only_fields = ("media_type",)


class ManagerMediaCreateSerializer(serializers.Serializer):
    """Один элемент галереи сервиса: либо фото (файл), либо ссылка на YouTube."""

    image = serializers.ImageField(required=False)
    video_url = serializers.URLField(required=False, allow_blank=True)
    caption = serializers.CharField(required=False, allow_blank=True, max_length=200, default="")
    order = serializers.IntegerField(required=False, default=0, min_value=0)

    def validate(self, attrs):
        image = attrs.get("image")
        video_url = attrs.get("video_url", "")
        if bool(image) == bool(video_url):
            raise serializers.ValidationError(
                "Передайте либо image (фото), либо video_url (YouTube) — ровно одно."
            )
        if image and image.size > MAX_IMAGE_MB * 1024 * 1024:
            raise serializers.ValidationError(f"Фото больше {MAX_IMAGE_MB} МБ.")
        if video_url and not ("youtube.com/" in video_url or "youtu.be/" in video_url):
            raise serializers.ValidationError("Видео принимаются только ссылками на YouTube.")
        return attrs


class ManagerProfileSerializer(serializers.ModelSerializer):
    """
    Профиль мастера: личные поля + галерея ЕГО СЕРВИСА (только чтение —
    галерея общая для точки, редактируется через /profile/media/).
    """

    media = ServiceMediaSerializer(source="service_point.media", many=True, read_only=True)
    service_point_name = serializers.CharField(source="service_point.name", read_only=True)

    class Meta:
        model = ServiceManager
        fields = (
            "id", "name", "bio", "bio_uz", "experience_years", "avatar",
            "language", "role", "service_point", "service_point_name", "media",
            "notification_channel",
        )
        read_only_fields = ("role", "service_point")

    def validate_avatar(self, value):
        if value and value.size > MAX_IMAGE_MB * 1024 * 1024:
            raise serializers.ValidationError(f"Фото больше {MAX_IMAGE_MB} МБ.")
        return value


class PublicManagerSerializer(serializers.ModelSerializer):
    """Карточка мастера в витрине: только личное, без галереи сервиса."""

    class Meta:
        model = ServiceManager
        fields = ("id", "name", "bio", "bio_uz", "experience_years", "avatar", "role")


class PublicServiceSerializer(serializers.ModelSerializer):
    """Услуга в витрине — клиент выбирает, на что записаться."""

    class Meta:
        model = Service
        fields = ("id", "name", "name_uz", "service_type", "duration_minutes", "price")


class PublicProfileSerializer(serializers.ModelSerializer):
    """Публичная витрина сервиса: описание, адрес, галерея, мастера, услуги."""

    media = ServiceMediaSerializer(many=True, read_only=True)
    managers = serializers.SerializerMethodField()
    services = serializers.SerializerMethodField()
    # Итоговый график по дням (база + переопределения): [{weekday, start, end}]
    schedule = serializers.SerializerMethodField()

    class Meta:
        model = ServicePoint
        fields = (
            "id", "name", "description", "description_uz", "address", "address_uz",
            "latitude", "longitude",
            "instagram", "work_start", "work_end", "work_days", "schedule",
            "media", "managers", "services",
        )

    def get_schedule(self, sp):
        return week_schedule(sp)

    def get_managers(self, sp):
        qs = sp.managers.filter(is_active=True)
        return PublicManagerSerializer(qs, many=True, context=self.context).data

    def get_services(self, sp):
        qs = sp.services.filter(is_active=True).order_by("name")
        return PublicServiceSerializer(qs, many=True).data


class MyBookingSerializer(serializers.Serializer):
    """Запись клиента за себя (приложение/сайт). Имя/телефон обновляют профиль."""

    service = serializers.PrimaryKeyRelatedField(
        queryset=Service.objects.filter(is_active=True)
    )
    start_time = serializers.DateTimeField()
    name = serializers.CharField(required=False, allow_blank=True, max_length=200)
    phone = serializers.CharField(required=False, allow_blank=True, max_length=32)
    car_details = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=120
    )


class BaySerializer(serializers.ModelSerializer):
    class Meta:
        model = Bay
        fields = ("id", "service_point", "name", "is_active")


class ServiceSerializer(serializers.ModelSerializer):
    class Meta:
        model = Service
        fields = (
            "id", "service_point", "name", "service_type",
            "duration_minutes", "price", "is_active",
        )


class ClientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Client
        fields = ("id", "telegram_id", "name", "phone", "no_show_count")
        read_only_fields = ("no_show_count",)


class AppointmentSerializer(serializers.ModelSerializer):
    client_name = serializers.CharField(source="client.name", read_only=True)
    client_phone = serializers.CharField(source="client.phone", read_only=True)
    service_name = serializers.CharField(source="service.name", read_only=True)
    service_name_uz = serializers.CharField(source="service.name_uz", read_only=True)
    service_type = serializers.CharField(source="service.service_type", read_only=True)
    bay_name = serializers.CharField(source="bay.name", read_only=True)
    client_no_show_count = serializers.IntegerField(source="client.no_show_count", read_only=True)
    service_point_name = serializers.CharField(source="service.service_point.name", read_only=True)
    service_point_address = serializers.CharField(source="service.service_point.address", read_only=True)
    service_point_address_uz = serializers.CharField(
        source="service.service_point.address_uz", read_only=True
    )

    class Meta:
        model = Appointment
        fields = (
            "id", "client", "client_name", "client_phone", "client_no_show_count",
            "service", "service_name", "service_name_uz", "service_type", "bay", "bay_name",
            "service_point_name", "service_point_address", "service_point_address_uz",
            "start_time", "duration_minutes", "estimated_end_time",
            "actual_start", "actual_end",
            "status", "source", "car_details", "note", "created_at",
            "cancelled_by", "cancel_reason",
        )
        # Через PATCH редактируются только car_details и note; время/пост/статус
        # меняются через сервисный слой (инварианты), статус — см. partial_update
        read_only_fields = (
            "client", "service", "bay", "start_time", "duration_minutes",
            "estimated_end_time", "actual_start", "actual_end", "status", "source",
            "cancelled_by", "cancel_reason",
        )


class AppointmentCreateSerializer(serializers.Serializer):
    """
    Создание записи. Либо client (id существующего), либо client_name/client_phone —
    для клиента «с улицы», которого мастер добавляет вручную.
    bay опционален: если не указан, система сама выберет свободный пост.
    """
    client = serializers.PrimaryKeyRelatedField(
        queryset=Client.objects.all(), required=False, allow_null=True
    )
    client_name = serializers.CharField(required=False, allow_blank=True)
    client_phone = serializers.CharField(required=False, allow_blank=True)
    service = serializers.PrimaryKeyRelatedField(queryset=Service.objects.filter(is_active=True))
    bay = serializers.PrimaryKeyRelatedField(
        queryset=Bay.objects.filter(is_active=True), required=False, allow_null=True
    )
    start_time = serializers.DateTimeField()
    # Переопределение длительности услуги (мин); по умолчанию берётся из услуги
    duration_minutes = serializers.IntegerField(required=False, min_value=5, max_value=600)
    car_details = serializers.CharField(
        required=False, allow_blank=True, default="", max_length=120
    )
    source = serializers.ChoiceField(
        choices=Appointment.Source.choices, default=Appointment.Source.MANUAL
    )
    note = serializers.CharField(required=False, allow_blank=True, default="")

    def validate(self, attrs):
        if not attrs.get("client") and not (attrs.get("client_name") or attrs.get("client_phone")):
            raise serializers.ValidationError(
                "Укажите client (id) или client_name/client_phone для нового клиента."
            )
        return attrs


class SlotSerializer(serializers.Serializer):
    start = serializers.DateTimeField()
    end = serializers.DateTimeField()
    bay_ids = serializers.ListField(child=serializers.UUIDField())
