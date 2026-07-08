from django.contrib import admin

from core.models import (
    Appointment,
    Bay,
    Client,
    Notification,
    Service,
    ServiceManager,
    ServicePoint,
)


@admin.register(ServiceManager)
class ServiceManagerAdmin(admin.ModelAdmin):
    list_display = ("name", "telegram_id", "service_point", "role", "is_active")
    list_filter = ("service_point", "role", "is_active")


@admin.register(ServicePoint)
class ServicePointAdmin(admin.ModelAdmin):
    list_display = ("name", "address", "work_start", "work_end", "slot_buffer_minutes", "is_active")
    fields = (
        "name", "address", "latitude", "longitude", "timezone",
        "work_start", "work_end", "work_days",
        "slot_buffer_minutes", "reminder_hours_before", "is_active",
    )


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
    list_display = ("name", "phone", "telegram_id", "no_show_count")
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
