"""Заполнение БД демо-данными для первого запуска: python manage.py seed_demo"""
from datetime import time

from django.core.management.base import BaseCommand

from core.models import Bay, Service, ServicePoint


class Command(BaseCommand):
    help = "Создаёт демо-автосервис с постами и услугами (идемпотентно)"

    def handle(self, *args, **options):
        sp, created = ServicePoint.objects.get_or_create(
            name="Автосервис Ургенч",
            defaults={
                "timezone": "Asia/Tashkent",
                "work_start": time(9, 0),
                "work_end": time(19, 0),
                "work_days": [0, 1, 2, 3, 4, 5],  # пн–сб
                "slot_buffer_minutes": 10,
                "reminder_hours_before": 3,
            },
        )
        if not created:
            self.stdout.write("Автосервис уже существует, пропускаю.")
            return

        for bay_name in ("Пост 1", "Пост 2"):
            Bay.objects.create(service_point=sp, name=bay_name)

        services = [
            ("Шиномонтаж R13–R16", "Шиномонтаж R13–R16", "fixed", 30, 150000),
            ("Шиномонтаж R17+", "Шиномонтаж R17+", "fixed", 45, 200000),
            ("Замена масла", "Мой алмаштириш", "fixed", 30, 80000),
            ("Развал-схождение", "Развал-схождение", "fixed", 60, 250000),
            ("Диагностика подвески", "Подвеска диагностикаси", "flexible", 40, 100000),
            ("Ремонт (осмотр)", "Таъмирлаш (кўрик)", "flexible", 60, None),
        ]
        for name, name_uz, stype, minutes, price in services:
            Service.objects.create(
                service_point=sp,
                name=name,
                name_uz=name_uz,
                service_type=stype,
                duration_minutes=minutes,
                price=price,
            )
        self.stdout.write(self.style.SUCCESS(
            f"Создан «{sp.name}»: 2 поста, {len(services)} услуг, 09:00–19:00 пн–сб."
        ))
