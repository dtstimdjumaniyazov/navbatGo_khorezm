"""
Вход через Telegram (device-code flow, как у telegram-логина на ТВ):

1. POST /api/auth/telegram/start/  → создаётся одноразовый код;
2. приложение открывает t.me/<бот>?start=login_<код>, пользователь жмёт Start;
3. бот вызывает confirm_login(код, telegram_id) — код подтверждается;
4. приложение опрашивает POST /api/auth/telegram/poll/ — после подтверждения
   получает JWT-пару и роль, код гасится (used_at) и повторно не работает.

Роль определяется по telegram_id: активный ServiceManager → мастер,
иначе — клиент (Client создаётся при первом входе, как в боте).
Пароли не нужны: Django-User создаётся автоматически (username tg_<id>,
пароль unusable) и привязывается к мастеру/клиенту.
"""
import secrets
from datetime import timedelta

from django.contrib.auth.models import User
from django.db import transaction
from django.utils import timezone

from core.models import Client, ServiceManager, TelegramLoginCode

CODE_TTL = timedelta(minutes=5)


def start_login() -> TelegramLoginCode:
    """Новый одноразовый код входа (22 url-safe символа, живёт 5 минут)."""
    return TelegramLoginCode.objects.create(
        code=secrets.token_urlsafe(16),
        expires_at=timezone.now() + CODE_TTL,
    )


def _active_manager(telegram_id: int) -> ServiceManager | None:
    return (
        ServiceManager.objects.select_related("service_point")
        .filter(
            telegram_id=telegram_id, is_active=True, service_point__is_active=True
        )
        .first()
    )


def _ensure_user(telegram_id: int, first_name: str) -> User:
    """Django-User для JWT: один на telegram_id, без пароля."""
    user, created = User.objects.get_or_create(
        username=f"tg_{telegram_id}",
        defaults={"first_name": first_name[:150]},
    )
    if created:  # вход только через Telegram — пароль не нужен
        user.set_unusable_password()
        user.save(update_fields=["password"])
    return user


def confirm_login(code: str, telegram_id: int) -> str:
    """
    Подтверждение кода из бота (пользователь нажал Start по deep-link).
    Возвращает исход для ответа в чате: ok (мастер) | ok_client | invalid.
    """
    now = timezone.now()
    with transaction.atomic():
        login = (
            TelegramLoginCode.objects.select_for_update()
            .filter(code=code, used_at=None, confirmed_at=None, expires_at__gt=now)
            .first()
        )
        if login is None:
            return "invalid"
        login.telegram_id = telegram_id
        login.confirmed_at = now
        login.save(update_fields=["telegram_id", "confirmed_at", "updated_at"])
    return "ok" if _active_manager(telegram_id) else "ok_client"


def poll_login(code: str) -> tuple[str, ServiceManager | Client] | str:
    """
    Опрос кода приложением. Возвращает:
    - "pending" — Start в боте ещё не нажат;
    - "invalid" — код не существует, истёк или уже использован;
    - ("master", ServiceManager) | ("client", Client) — вход подтверждён,
      код погашен, у объекта гарантированно есть .user для выдачи JWT.
    """
    now = timezone.now()
    with transaction.atomic():
        login = (
            TelegramLoginCode.objects.select_for_update()
            .filter(code=code, used_at=None)
            .first()
        )
        if login is None or login.expires_at <= now:
            return "invalid"
        if login.confirmed_at is None:
            return "pending"

        manager = _active_manager(login.telegram_id)
        if manager is not None:
            if manager.user is None:
                manager.user = _ensure_user(manager.telegram_id, manager.name)
                manager.save(update_fields=["user", "updated_at"])
            role, obj = "master", manager
        else:
            client, _ = Client.objects.get_or_create(telegram_id=login.telegram_id)
            if client.user is None:
                client.user = _ensure_user(login.telegram_id, client.name)
                client.save(update_fields=["user", "updated_at"])
            role, obj = "client", client

        login.used_at = now
        login.save(update_fields=["used_at", "updated_at"])
    return role, obj
