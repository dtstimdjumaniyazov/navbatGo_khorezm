import uuid

from django.contrib.postgres.constraints import ExclusionConstraint
from django.contrib.postgres.fields import DateTimeRangeField, RangeOperators
from django.db import models
from django.db.models import Func, Q


class TsTzRange(Func):
    """Диапазон [start, end) для exclusion-констрейнта в PostgreSQL."""

    function = "TSTZRANGE"
    output_field = DateTimeRangeField()


class BaseModel(models.Model):
    """UUID pk + created_at/updated_at для всех основных моделей."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class NotificationChannel(models.TextChoices):
    """Куда слать уведомления: Telegram-бот или push в мобильном приложении.
    Общий выбор для клиентов и мастеров, переключается в любой момент —
    см. Client.notification_channel / ServiceManager.notification_channel."""

    TELEGRAM = "telegram", "Telegram"
    PUSH = "push", "Push в приложении"


class ServicePoint(BaseModel):
    """Автосервис. Пока один, но модель заложена под мультифилиал."""

    name = models.CharField("Название", max_length=200)
    description = models.TextField("Описание (о сервисе)", blank=True)
    # Узбекские (кириллица) варианты; пусто — клиенту показывается русский
    description_uz = models.TextField("Описание (ўзб.)", blank=True)
    address = models.CharField("Адрес", max_length=255, blank=True)
    address_uz = models.CharField("Адрес (ўзб.)", max_length=255, blank=True)
    latitude = models.DecimalField(
        "Широта", max_digits=9, decimal_places=6, null=True, blank=True
    )
    longitude = models.DecimalField(
        "Долгота", max_digits=9, decimal_places=6, null=True, blank=True
    )
    timezone = models.CharField("Часовой пояс", max_length=64, default="Asia/Tashkent")
    work_start = models.TimeField("Начало рабочего дня")
    work_end = models.TimeField("Конец рабочего дня")
    # Дни недели, когда сервис работает: список int, 0=понедельник ... 6=воскресенье
    work_days = models.JSONField("Рабочие дни", default=list)
    slot_buffer_minutes = models.PositiveIntegerField("Буфер между записями, мин", default=10)
    reminder_hours_before = models.PositiveIntegerField("Напоминание за N часов", default=3)
    # Клиент не может онлайн записаться ближе, чем за N минут — мастеру нужно
    # время подготовиться. На запись «с улицы» через мастера не влияет.
    min_lead_minutes = models.PositiveIntegerField(
        "Не принимать записи онлайн ближе N минут", default=60
    )
    instagram = models.URLField("Instagram", blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Автосервис"
        verbose_name_plural = "Автосервисы"

    def __str__(self):
        return self.name


class WorkingHours(BaseModel):
    """
    Переопределение графика на конкретный день недели: другие часы или
    выходной. Если строки для дня нет — действует базовый график сервиса
    (work_days + work_start/work_end).
    """

    WEEKDAYS = (
        (0, "Понедельник"), (1, "Вторник"), (2, "Среда"), (3, "Четверг"),
        (4, "Пятница"), (5, "Суббота"), (6, "Воскресенье"),
    )

    service_point = models.ForeignKey(
        ServicePoint, on_delete=models.CASCADE, related_name="working_hours"
    )
    weekday = models.PositiveSmallIntegerField("День недели", choices=WEEKDAYS)
    is_closed = models.BooleanField("Выходной", default=False)
    work_start = models.TimeField("Начало", null=True, blank=True)
    work_end = models.TimeField("Конец", null=True, blank=True)

    class Meta:
        verbose_name = "График дня"
        verbose_name_plural = "График по дням"
        ordering = ["weekday"]
        constraints = [
            models.UniqueConstraint(
                fields=["service_point", "weekday"], name="uniq_hours_per_weekday"
            ),
        ]

    def __str__(self):
        if self.is_closed:
            return f"{self.get_weekday_display()} — выходной"
        return f"{self.get_weekday_display()} {self.work_start}–{self.work_end}"


class ServiceManager(BaseModel):
    """
    Мастер (владелец/сотрудник) автосервиса. Заполняется вручную в админке —
    саморегистрации нет. По telegram_id бот включает режим мастера.
    Один человек может управлять несколькими сервисами (на будущее).
    """

    class Role(models.TextChoices):
        OWNER = "owner", "Владелец"
        STAFF = "staff", "Сотрудник"  # на будущее, пока не используется

    service_point = models.ForeignKey(
        ServicePoint, on_delete=models.CASCADE, related_name="managers"
    )
    telegram_id = models.BigIntegerField("Telegram ID", db_index=True)
    # Аккаунт для входа в панель/приложение (JWT); пусто — мастер только в Telegram
    user = models.OneToOneField(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manager_profile",
        verbose_name="Логин панели",
    )
    name = models.CharField("Имя", max_length=200, blank=True)
    role = models.CharField(max_length=10, choices=Role.choices, default=Role.OWNER)
    # Язык интерфейса мастера (бот + приложение)
    language = models.CharField(
        "Язык",
        max_length=2,
        choices=(("ru", "Русский"), ("uz", "Ўзбекча (кирилл)")),
        default="ru",
    )
    # Публичный профиль (витрина для клиентов)
    bio = models.TextField("О себе", blank=True)
    bio_uz = models.TextField("О себе (ўзб.)", blank=True)
    experience_years = models.PositiveIntegerField("Стаж, лет", null=True, blank=True)
    avatar = models.ImageField("Фото профиля", upload_to="avatars/", blank=True)
    is_active = models.BooleanField(default=True)
    # Показали ли мастеру мини-инструкцию по боту при первом /start
    onboarding_seen = models.BooleanField(default=False)
    notification_channel = models.CharField(
        "Канал уведомлений", max_length=10,
        choices=NotificationChannel.choices, default=NotificationChannel.TELEGRAM,
    )
    # Expo push-токен устройства; пусто, пока мастер не открыл приложение
    # и не разрешил уведомления
    push_token = models.CharField("Push-токен", max_length=200, blank=True)

    class Meta:
        verbose_name = "Мастер"
        verbose_name_plural = "Мастера"
        constraints = [
            models.UniqueConstraint(
                fields=["service_point", "telegram_id"], name="uniq_manager_per_point"
            ),
        ]

    def __str__(self):
        return f"{self.name or self.telegram_id} @ {self.service_point}"


class ServicePointMedia(BaseModel):
    """
    Портфолио автосервиса: фото работ (файлы на сервере) или видео
    (ссылки YouTube). Принадлежит сервису, а не мастеру: галерея — витрина
    всей точки, личное у мастера — только его карточка (фото/био/стаж).
    """

    class MediaType(models.TextChoices):
        PHOTO = "photo", "Фото"
        VIDEO = "video", "Видео (YouTube)"

    service_point = models.ForeignKey(
        ServicePoint, on_delete=models.CASCADE, related_name="media"
    )
    media_type = models.CharField(max_length=5, choices=MediaType.choices)
    image = models.ImageField("Фото", upload_to="service_media/", blank=True)
    video_url = models.URLField("Ссылка на YouTube", blank=True)
    caption = models.CharField("Подпись", max_length=200, blank=True)
    order = models.PositiveIntegerField("Порядок", default=0)

    class Meta:
        verbose_name = "Медиа сервиса"
        verbose_name_plural = "Медиа сервисов"
        ordering = ["order", "created_at"]

    def __str__(self):
        return f"{self.get_media_type_display()} — {self.service_point}"


class Bay(BaseModel):
    """Пост (подъёмник/место). Ресурс планирования — именно пост, не мастер."""

    service_point = models.ForeignKey(
        ServicePoint, on_delete=models.CASCADE, related_name="bays"
    )
    name = models.CharField("Название", max_length=100)
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Пост"
        verbose_name_plural = "Посты"
        ordering = ["created_at"]

    def __str__(self):
        return self.name


class Service(BaseModel):
    """Услуга сервиса."""

    class ServiceType(models.TextChoices):
        FIXED = "fixed", "Фиксированная длительность"
        FLEXIBLE = "flexible", "Гибкая (осмотр, длительность оценочная)"

    service_point = models.ForeignKey(
        ServicePoint, on_delete=models.CASCADE, related_name="services"
    )
    name = models.CharField("Название", max_length=200)
    # Название на узбекском (кириллица); пусто — клиенту показывается name
    name_uz = models.CharField("Название (ўзб.)", max_length=200, blank=True)
    service_type = models.CharField(
        max_length=10, choices=ServiceType.choices, default=ServiceType.FIXED
    )
    # для fixed — точная длительность, для flexible — оценка (слот резервируется по ней)
    duration_minutes = models.PositiveIntegerField("Длительность, мин")
    price = models.DecimalField(
        "Цена", max_digits=12, decimal_places=2, null=True, blank=True
    )
    is_active = models.BooleanField(default=True)

    class Meta:
        verbose_name = "Услуга"
        verbose_name_plural = "Услуги"
        ordering = ["name"]

    def __str__(self):
        return self.name


class Client(BaseModel):
    """Клиент. telegram_id пуст у клиентов «с улицы», добавленных мастером вручную."""

    class Language(models.TextChoices):
        RU = "ru", "Русский"
        UZ = "uz", "Ўзбекча (кирилл)"

    telegram_id = models.BigIntegerField(
        unique=True, db_index=True, null=True, blank=True
    )
    # Аккаунт для входа в приложение/сайт (JWT); создаётся при первом
    # входе через Telegram. Пусто — клиент пользуется только ботом
    user = models.OneToOneField(
        "auth.User",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="client_profile",
        verbose_name="Аккаунт приложения",
    )
    name = models.CharField("Имя", max_length=200, blank=True)
    language = models.CharField(
        "Язык", max_length=2, choices=Language.choices, default=Language.RU
    )
    # Хранится нормализованным (см. services.clients.normalize_phone) —
    # по нему дедуплицируются клиенты «с улицы»
    phone = models.CharField("Телефон", max_length=32, blank=True, db_index=True)
    no_show_count = models.PositiveIntegerField("Неявок", default=0)
    notification_channel = models.CharField(
        "Канал уведомлений", max_length=10,
        choices=NotificationChannel.choices, default=NotificationChannel.TELEGRAM,
    )
    # Expo push-токен устройства; пусто, пока клиент не открыл приложение
    # и не разрешил уведомления
    push_token = models.CharField("Push-токен", max_length=200, blank=True)

    class Meta:
        verbose_name = "Клиент"
        verbose_name_plural = "Клиенты"

    def __str__(self):
        return self.name or self.phone or f"tg:{self.telegram_id}"


class Appointment(BaseModel):
    """Запись клиента на пост. Центральная модель системы."""

    class Status(models.TextChoices):
        SCHEDULED = "scheduled", "Записан"
        CONFIRMED = "confirmed", "Подтвердил"
        IN_PROGRESS = "in_progress", "На посту"
        DONE = "done", "Готово"
        NO_SHOW = "no_show", "Не приехал"
        CANCELLED = "cancelled", "Отменён"
        RESCHEDULED = "rescheduled", "Перенесён"

    class Source(models.TextChoices):
        TELEGRAM = "telegram", "Telegram"
        MANUAL = "manual", "Вручную (мастер)"
        APP = "app", "Приложение/сайт"

    class CancelledBy(models.TextChoices):
        CLIENT = "client", "Клиент"
        MASTER = "master", "Мастер"

    # Статусы, при которых запись занимает пост (учитываются в расчёте слотов)
    ACTIVE_STATUSES = (Status.SCHEDULED, Status.CONFIRMED, Status.IN_PROGRESS)

    client = models.ForeignKey(Client, on_delete=models.PROTECT, related_name="appointments")
    service = models.ForeignKey(Service, on_delete=models.PROTECT, related_name="appointments")
    bay = models.ForeignKey(Bay, on_delete=models.PROTECT, related_name="appointments")
    start_time = models.DateTimeField("Начало")
    # Длительность самой работы, без буфера. Хранится отдельно, чтобы история
    # оставалась читаемой, даже если сервис потом поменяет slot_buffer_minutes
    duration_minutes = models.PositiveIntegerField(
        "Длительность работ, мин", null=True, blank=True
    )
    # start + duration + буфер; для flexible может сдвигаться при продлении
    estimated_end_time = models.DateTimeField("Расчётный конец")
    actual_start = models.DateTimeField(null=True, blank=True)
    actual_end = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=15, choices=Status.choices, default=Status.SCHEDULED, db_index=True
    )
    source = models.CharField(
        max_length=10, choices=Source.choices, default=Source.TELEGRAM
    )
    car_details = models.CharField("Автомобиль", max_length=120, blank=True)
    note = models.TextField("Комментарий", blank=True)
    # Кто отменил и почему — для уведомления клиенту (причина мастера) и для
    # статистики качества (доля отмен по вине сервиса вместо клиента)
    cancelled_by = models.CharField(
        max_length=10, choices=CancelledBy.choices, blank=True
    )
    cancel_reason = models.TextField("Причина отмены", blank=True)

    class Meta:
        verbose_name = "Запись"
        verbose_name_plural = "Записи"
        ordering = ["start_time"]
        indexes = [
            models.Index(fields=["bay", "start_time"]),
            models.Index(fields=["status", "start_time"]),
        ]
        constraints = [
            # Железная защита от двойной записи на пост: БД не даст создать
            # пересекающиеся по времени активные записи даже при гонке запросов.
            ExclusionConstraint(
                name="excl_overlapping_active_appts",
                expressions=[
                    (TsTzRange("start_time", "estimated_end_time"), RangeOperators.OVERLAPS),
                    ("bay", RangeOperators.EQUAL),
                ],
                condition=Q(status__in=("scheduled", "confirmed", "in_progress")),
            ),
            # То же самое, но по клиенту: не даёт одному клиенту оказаться
            # одновременно записанным на два разных сервиса/поста в один момент
            # времени (баг: запись на 09:00 в двух разных автосервисах сразу).
            ExclusionConstraint(
                name="excl_overlapping_client_appts",
                expressions=[
                    (TsTzRange("start_time", "estimated_end_time"), RangeOperators.OVERLAPS),
                    ("client", RangeOperators.EQUAL),
                ],
                condition=Q(status__in=("scheduled", "confirmed", "in_progress")),
            ),
            models.CheckConstraint(
                condition=Q(estimated_end_time__gt=models.F("start_time")),
                name="appt_end_after_start",
            ),
        ]

    def __str__(self):
        return f"{self.client} — {self.service} @ {self.start_time:%d.%m %H:%M}"


class TelegramLoginCode(BaseModel):
    """
    Одноразовый код входа через Telegram (device-code flow):
    приложение создаёт код → открывает t.me/<бот>?start=login_<код> →
    пользователь жмёт Start → бот подтверждает код → приложение
    обменивает подтверждённый код на JWT. Код живёт 5 минут, гасится
    после первой выдачи токенов.
    """

    code = models.CharField(max_length=64, unique=True)
    # Кто подтвердил код в боте; пусто, пока Start не нажат
    telegram_id = models.BigIntegerField(null=True, blank=True)
    expires_at = models.DateTimeField("Истекает")
    confirmed_at = models.DateTimeField(null=True, blank=True)
    used_at = models.DateTimeField("Токены выданы", null=True, blank=True)

    class Meta:
        verbose_name = "Код входа через Telegram"
        verbose_name_plural = "Коды входа через Telegram"

    def __str__(self):
        return f"{self.code[:8]}… ({self.telegram_id or 'не подтверждён'})"


class Notification(BaseModel):
    """Очередь уведомлений в Telegram. Отправка реализуется на этапе 3."""

    class Type(models.TextChoices):
        REMINDER = "reminder", "Напоминание"
        SHIFTED = "shifted", "Очередь сдвинулась"
        CANCELLED = "cancelled", "Запись отменена"
        CONFIRM_REQUEST = "confirm_request", "Просьба подтвердить"

    class Status(models.TextChoices):
        PENDING = "pending", "Ожидает"
        SENT = "sent", "Отправлено"
        FAILED = "failed", "Ошибка"
        CANCELLED = "cancelled", "Отменено"  # запись отменена/no_show до отправки

    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, related_name="notifications"
    )
    notification_type = models.CharField(max_length=20, choices=Type.choices)
    scheduled_for = models.DateTimeField("Когда отправить")
    sent_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(
        max_length=10, choices=Status.choices, default=Status.PENDING
    )

    class Meta:
        verbose_name = "Уведомление"
        verbose_name_plural = "Уведомления"

    def __str__(self):
        return f"{self.notification_type} для {self.appointment_id}"
