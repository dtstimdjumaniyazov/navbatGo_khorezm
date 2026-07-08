"""Точка входа бота. Запускается через: python manage.py runbot"""
import logging

from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.types import BotCommand, BotCommandScopeChat, BotCommandScopeDefault
from asgiref.sync import sync_to_async
from django.conf import settings

from bot.handlers import router
from bot.master import master_router

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@sync_to_async
def _manager_ids() -> list[int]:
    from core.models import ServiceManager

    return list(
        ServiceManager.objects.filter(is_active=True).values_list("telegram_id", flat=True)
    )


async def _setup_commands(bot: Bot):
    """Подсказки команд в меню Telegram: клиентам RU/UZ, мастерам — свой набор."""
    client_ru = [
        BotCommand(command="start", description="Главное меню"),
        BotCommand(command="language", description="Выбрать язык / Тилни танлаш"),
    ]
    client_uz = [
        BotCommand(command="start", description="Асосий меню"),
        BotCommand(command="language", description="Тилни танлаш / Выбрать язык"),
    ]
    await bot.set_my_commands(client_ru, scope=BotCommandScopeDefault())
    # Подсказки для клиентов с узбекским языком интерфейса Telegram
    await bot.set_my_commands(client_uz, scope=BotCommandScopeDefault(), language_code="uz")

    master_cmds = [
        BotCommand(command="menu", description="Меню мастера"),
        BotCommand(command="start", description="Меню мастера"),
    ]
    for telegram_id in await _manager_ids():
        try:
            await bot.set_my_commands(
                master_cmds, scope=BotCommandScopeChat(chat_id=telegram_id)
            )
        except Exception as exc:  # мастер ещё ни разу не писал боту — чата нет
            logger.warning("Команды мастеру %s не выставлены: %s", telegram_id, exc)


async def run_bot():
    if not settings.BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан в .env — получите токен у @BotFather.")
    bot = Bot(token=settings.BOT_TOKEN, default=DefaultBotProperties(parse_mode=None))
    dp = Dispatcher()
    # Мастер-роутер ПЕРВЫМ: его фильтр забирает апдейты мастеров целиком,
    # клиентский роутер их не видит (и наоборот)
    dp.include_router(master_router)
    dp.include_router(router)
    await bot.delete_webhook(drop_pending_updates=True)
    await _setup_commands(bot)
    await dp.start_polling(bot)
