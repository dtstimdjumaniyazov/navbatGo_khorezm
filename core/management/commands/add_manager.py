"""Назначить мастера сервиса: python manage.py add_manager <telegram_id> [--name "Имя"]"""
from django.core.management.base import BaseCommand, CommandError

from core.models import ServiceManager, ServicePoint


class Command(BaseCommand):
    help = "Привязывает telegram_id мастера к первому активному автосервису"

    def add_arguments(self, parser):
        parser.add_argument("telegram_id", type=int)
        parser.add_argument("--name", default="")

    def handle(self, *args, **options):
        sp = ServicePoint.objects.filter(is_active=True).first()
        if sp is None:
            raise CommandError("Нет активного автосервиса — создайте его в админке.")
        manager, created = ServiceManager.objects.get_or_create(
            service_point=sp,
            telegram_id=options["telegram_id"],
            defaults={"name": options["name"]},
        )
        if created:
            self.stdout.write(self.style.SUCCESS(
                f"Мастер {options['telegram_id']} назначен владельцем «{sp.name}»."
            ))
        else:
            self.stdout.write("Такой мастер уже есть у этого сервиса.")
