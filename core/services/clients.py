"""Работа с клиентами: нормализация телефона и дедупликация «уличных» клиентов."""
import re

from core.models import Client


def normalize_phone(raw: str) -> str:
    """
    «+998 (91) 234-56-78» → «+998912345678»: остаются цифры и ведущий «+».
    Пустая строка, если цифр нет.
    """
    digits = re.sub(r"\D", "", raw or "")
    if not digits:
        return ""
    return ("+" if raw.strip().startswith("+") else "") + digits


def get_or_create_walkin_client(name: str, phone: str) -> Client:
    """
    Клиент «с улицы» (без Telegram): перед созданием ищем существующего
    по нормализованному телефону, чтобы постоянный клиент не превращался
    в стопку дублей, а его no_show_count не размазывался.
    """
    phone_norm = normalize_phone(phone)
    if phone_norm:
        client = Client.objects.filter(phone=phone_norm).order_by("created_at").first()
        if client is not None:
            if name and not client.name:
                client.name = name
                client.save(update_fields=["name", "updated_at"])
            return client
    return Client.objects.create(name=name, phone=phone_norm)
