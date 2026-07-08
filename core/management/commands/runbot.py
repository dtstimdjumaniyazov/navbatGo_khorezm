"""Запуск Telegram-бота: python manage.py runbot"""
import asyncio

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Запускает Telegram-бота (long polling)"

    def handle(self, *args, **options):
        from bot.main import run_bot

        self.stdout.write("Запуск бота... (Ctrl+C для остановки)")
        try:
            asyncio.run(run_bot())
        except KeyboardInterrupt:
            self.stdout.write("Бот остановлен.")
