from rest_framework import serializers

from core.models import Appointment, Bay, Client, Service, ServicePoint


class ServicePointSerializer(serializers.ModelSerializer):
    class Meta:
        model = ServicePoint
        fields = (
            "id", "name", "address", "latitude", "longitude",
            "timezone", "work_start", "work_end", "work_days",
            "slot_buffer_minutes", "reminder_hours_before", "is_active",
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
    service_type = serializers.CharField(source="service.service_type", read_only=True)
    bay_name = serializers.CharField(source="bay.name", read_only=True)

    class Meta:
        model = Appointment
        fields = (
            "id", "client", "client_name", "client_phone",
            "service", "service_name", "service_type", "bay", "bay_name",
            "start_time", "estimated_end_time", "actual_start", "actual_end",
            "status", "source", "car_details", "note", "created_at",
        )
        # Через PATCH редактируются только car_details и note; время/пост/статус
        # меняются через сервисный слой (инварианты), статус — см. partial_update
        read_only_fields = (
            "client", "service", "bay", "start_time", "estimated_end_time",
            "actual_start", "actual_end", "status", "source",
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
