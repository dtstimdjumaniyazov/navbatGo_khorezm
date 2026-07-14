from django.contrib import admin
from django.db.models import Count, Q

from core.models import (
    Appointment,
    Bay,
    Client,
    Notification,
    Service,
    ServiceManager,
    ServicePoint,
    ServicePointMedia,
    WorkingHours,
)


class ServicePointMediaInline(admin.TabularInline):
    model = ServicePointMedia
    extra = 0
    fields = ("media_type", "image", "video_url", "caption", "order")


class WorkingHoursInline(admin.TabularInline):
    """Переопределения графика: другие часы дня или выходной."""

    model = WorkingHours
    extra = 0
    fields = ("weekday", "is_closed", "work_start", "work_end")


@admin.register(ServiceManager)
class ServiceManagerAdmin(admin.ModelAdmin):
    list_display = (
        "name", "telegram_id", "service_point", "role", "notification_channel", "is_active",
    )
    list_filter = ("service_point", "role", "notification_channel", "is_active")


@admin.register(ServicePoint)
class ServicePointAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "work_start", "work_end", "slot_buffer_minutes", "is_active")
    fields = (
        "name", "description", "description_uz", "address", "address_uz",
        "latitude", "longitude", "timezone",
        "work_start", "work_end", "work_days",
        "slot_buffer_minutes", "reminder_hours_before", "min_lead_minutes",
        "instagram", "is_active",
    )
    inlines = [WorkingHoursInline, ServicePointMediaInline]

    # Метрика качества (пока только для суперпользователя): доля отменённых
    # записей и разбивка по тому, кто отменил — сервис или сам клиент.
    def cancellation_rate(self, obj):
        agg = Appointment.objects.filter(service__service_point=obj).aggregate(
            total=Count("id"),
            cancelled=Count("id", filter=Q(status=Appointment.Status.CANCELLED)),
            by_master=Count(
                "id",
                filter=Q(
                    status=Appointment.Status.CANCELLED,
                    cancelled_by=Appointment.CancelledBy.MASTER,
                ),
            ),
            by_client=Count(
                "id",
                filter=Q(
                    status=Appointment.Status.CANCELLED,
                    cancelled_by=Appointment.CancelledBy.CLIENT,
                ),
            ),
        )
        total = agg["total"] or 0
        if total == 0:
            return "—"
        rate = agg["cancelled"] / total * 100
        return (
            f"{rate:.0f}% ({agg['cancelled']}/{total}) · "
            f"сервис: {agg['by_master']}, клиент: {agg['by_client']}"
        )

    cancellation_rate.short_description = "Отмены"

    def get_list_display(self, request):
        if request.user.is_superuser:
            return (*self.list_display, "cancellation_rate")
        return self.list_display

    def get_fields(self, request, obj=None):
        fields = super().get_fields(request, obj)
        if obj is not None and request.user.is_superuser:
            return (*fields, "cancellation_rate")
        return fields

    def get_readonly_fields(self, request, obj=None):
        if obj is not None and request.user.is_superuser:
            return (*self.readonly_fields, "cancellation_rate")
        return self.readonly_fields


@admin.register(Bay)
class BayAdmin(admin.ModelAdmin):
    list_display = ("name", "service_point", "is_active")
    list_filter = ("service_point", "is_active")


@admin.register(Service)
class ServiceAdmin(admin.ModelAdmin):
    list_display = ("name", "name_uz", "service_type", "duration_minutes", "price", "is_active")
    list_filter = ("service_type", "is_active")


@admin.register(Client)
class ClientAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "telegram_id", "no_show_count", "notification_channel")
    list_filter = ("notification_channel",)
    search_fields = ("name", "phone")


@admin.register(Appointment)
class AppointmentAdmin(admin.ModelAdmin):
    list_display = ("start_time", "client", "service", "bay", "status", "source")
    list_filter = ("status", "bay", "source")
    date_hierarchy = "start_time"


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ("notification_type", "appointment", "scheduled_for", "status")
    list_filter = ("notification_type", "status")
