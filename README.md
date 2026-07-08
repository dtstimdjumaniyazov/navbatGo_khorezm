# navbatGo — онлайн-запись для автосервиса

Система записи и управления очередью для автосервисов/шиномонтажей.
Клиенты записываются через Telegram-бота, мастер управляет днём через API
(панель на React — этап 2).

**Стек:** Django 6 + DRF, PostgreSQL 17, aiogram 3.x, React (этап 2).

## Архитектура

- **Ресурс планирования — пост (Bay), не мастер.** Слоты считаются по каждому
  посту; несколько машин обслуживаются одновременно.
- **Два типа услуг:** `fixed` (жёсткий слот) и `flexible` (запись на осмотр,
  длительность оценочная, можно продлить).
- **Защита от двойной записи двухуровневая:** проверка в сервисном слое
  (`core/services/appointments.py`) + exclusion-констрейнт PostgreSQL
  (`tstzrange && tstzrange` по посту для активных статусов) — гонка
  параллельных запросов физически не может создать пересечение.
- Бот работает с БД напрямую через сервисный слой (`core/services/`) —
  инварианты в одном месте, без HTTP-прослойки.

```
config/    — настройки Django
core/      — модели, сервисный слой (слоты, записи), админка, seed
api/       — DRF: услуги, посты, клиенты, записи, свободные слоты
bot/       — Telegram-бот (aiogram 3)
frontend/  — панель мастера (React 19 + Vite + Tailwind v4)
```

## Запуск

### 1. Окружение

```powershell
python -m venv .venv
.\.venv\Scripts\pip install -r requirements.txt
copy .env.example .env   # заполнить DB_PASSWORD и BOT_TOKEN
```

### 2. База данных

```powershell
# создать БД (пароль postgres спросит)
& "C:\Program Files\PostgreSQL\17\bin\createdb.exe" -U postgres -h 127.0.0.1 navbatgo

.\.venv\Scripts\python manage.py migrate
.\.venv\Scripts\python manage.py seed_demo        # демо-сервис: 2 поста, 6 услуг
.\.venv\Scripts\python manage.py createsuperuser  # для админки
```

### 3. API-сервер

```powershell
.\.venv\Scripts\python manage.py runserver
```

- Админка: http://127.0.0.1:8000/admin/
- API: http://127.0.0.1:8000/api/ (в DEBUG доступен браузерный интерфейс DRF)

### 4. Панель мастера (React)

```powershell
cd frontend
npm install
npm run dev     # http://localhost:3000, API берётся из frontend/.env (VITE_API_URL)
```

Дизайн-спецификация панели: [frontend/DESIGN.md](frontend/DESIGN.md).

### 5. Telegram-бот

Получите токен у [@BotFather](https://t.me/BotFather), впишите в `.env`
(`BOT_TOKEN=...`), затем:

```powershell
.\.venv\Scripts\python manage.py runbot
```

## API (основное)

| Метод | URL | Что делает |
|---|---|---|
| GET | `/api/services/?active=1` | услуги |
| GET | `/api/bays/` | посты |
| GET | `/api/slots/?service=<uuid>&date=YYYY-MM-DD` | свободные слоты по постам |
| GET | `/api/appointments/?date=YYYY-MM-DD` | записи на день |
| POST | `/api/appointments/` | создать запись (см. ниже) |
| POST | `/api/appointments/{id}/start/` | мастер: начал |
| POST | `/api/appointments/{id}/finish/` | мастер: закончил |
| POST | `/api/appointments/{id}/no_show/` | не приехал (+1 к счётчику неявок) |
| POST | `/api/appointments/{id}/cancel/` | отмена |
| POST | `/api/appointments/{id}/extend/` | продлить flexible: `{"extra_minutes": 30}` |

Создание записи мастером (клиент «с улицы», пост выберется автоматически):

```json
POST /api/appointments/
{
  "client_name": "Азиз",
  "client_phone": "+998901234567",
  "service": "<uuid услуги>",
  "start_time": "2026-07-09T10:00:00+05:00",
  "source": "manual"
}
```

Занятый слот → `409 Conflict` с сообщением.

## Режим мастера в боте

Бот различает роли по telegram_id: мастера (модель `ServiceManager`,
заполняется в админке или командой) получают админ-меню своего сервиса,
все остальные — клиентское меню записи.

```powershell
.\.venv\Scripts\python manage.py add_manager <telegram_id> --name "Имя"
```

Мастеру доступно: записи по дням с навигацией, карточка записи
(начал/завершил/не приехал/отменить — с подтверждением необратимых),
продление in_progress на 15/30/60 мин и сдвиг очереди поста с
уведомлением клиентов (логика — те же core/services, что у панели).

## Напоминания (cron)

Напоминание за N часов (поле `reminder_hours_before` автосервиса) создаётся
при записи и отправляется командой:

```powershell
.\.venv\Scripts\python manage.py send_due_notifications
```

Команда идемпотентна (повторный запуск ничего не шлёт дважды) и не падает,
если клиент заблокировал бота (уведомление помечается `failed`).

На сервере (Linux) — запуск раз в 2 минуты через crontab:

```cron
*/2 * * * * cd /opt/navbatgo && .venv/bin/python manage.py send_due_notifications >> /var/log/navbatgo/notifications.log 2>&1
```

На Windows — Task Scheduler с тем же вызовом раз в 2–5 минут.

## Тесты

```powershell
.\.venv\Scripts\python manage.py test core
```

Покрыто: генерация слотов по постам, буфер, рабочие часы, двойная запись
(включая констрейнт БД), автоподбор поста, освобождение слота при отмене,
инкремент неявок.

## Статусы записи

`scheduled → confirmed → in_progress → done`, плюс `no_show`, `cancelled`,
`rescheduled` (задействуется на этапе 3 при сдвиге очереди).

## Дорожная карта

- **Этап 1 (готов):** модели, слоты, API, бот.
- **Этап 2:** React-панель мастера (день по постам, статусы, ручная запись).
- **Этап 3:** сдвиг очереди с уведомлениями, напоминания за N часов
  (модель `Notification` уже заложена).
