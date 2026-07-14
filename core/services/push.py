"""
Push-уведомления через Expo Push API — альтернативный канал вместо Telegram
(см. NotificationChannel / Client.notification_channel / ServiceManager.notification_channel).
Без SDK: один HTTP POST на сообщение, чтобы не тащить лишнюю зависимость.
"""
import json
import logging
import urllib.request

logger = logging.getLogger(__name__)

EXPO_PUSH_URL = "https://exp.host/--/api/v2/push/send"


def send_push(token: str, title: str, body: str) -> bool:
    """
    Отправить одно push-уведомление через Expo. True — Expo приняла сообщение
    в очередь (не гарантирует доставку на устройство — как и Telegram send_message
    не гарантирует прочтение). Ошибка не должна ломать вызывающий сценарий.
    """
    if not token:
        return False
    payload = json.dumps({
        "to": token,
        "title": title,
        "body": body,
        "sound": "default",
    }).encode("utf-8")
    req = urllib.request.Request(
        EXPO_PUSH_URL,
        data=payload,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception as exc:  # noqa: BLE001 — сбой одного push не должен ломать сценарий
        logger.warning("Push не отправлен: %s", exc)
        return False

    status = data.get("data", {}).get("status")
    if status != "ok":
        logger.warning("Push не доставлен Expo: %s", data)
        return False
    return True
