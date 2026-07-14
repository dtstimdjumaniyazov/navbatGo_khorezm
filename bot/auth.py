"""
Подтверждение входа в приложение/сайт по deep-link
t.me/<бот>?start=login_<код>. Роутер подключается ПЕРВЫМ (до мастера и
клиента), иначе их обработчики /start перехватят команду.
"""
from aiogram import F, Router
from aiogram.filters import CommandObject, CommandStart
from aiogram.types import Message
from asgiref.sync import sync_to_async

from bot import db
from bot.i18n import t
from core.services import telegram_auth

login_router = Router(name="login")

# Тексты мастеру — RU (общая договорённость), клиенту — на его языке
REPLIES = {
    "ok": "✅ Вход подтверждён. Вернитесь в приложение NavbatGo.",
    "invalid": "Код входа недействителен или истёк. Запросите вход в приложении заново.",
}


@login_router.message(CommandStart(deep_link=True, magic=F.args.startswith("login_")))
async def confirm_app_login(message: Message, command: CommandObject):
    code = (command.args or "").removeprefix("login_")
    outcome = await sync_to_async(telegram_auth.confirm_login)(
        code, message.from_user.id
    )
    if outcome == "ok_client":
        client, _ = await db.get_or_create_client(message.from_user.id)
        await message.answer(t(client.language, "login_confirmed"))
        return
    await message.answer(REPLIES[outcome])
