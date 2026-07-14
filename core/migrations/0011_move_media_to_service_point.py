# Перенос галереи с мастера на сервис: медиа — портфолио точки, не человека.
# Файлы на диске не трогаем (пути в image остаются прежними, manager_media/).
from django.db import migrations


def forward(apps, schema_editor):
    ManagerMedia = apps.get_model("core", "ManagerMedia")
    ServicePointMedia = apps.get_model("core", "ServicePointMedia")
    for item in ManagerMedia.objects.select_related("manager").all():
        ServicePointMedia.objects.create(
            service_point_id=item.manager.service_point_id,
            media_type=item.media_type,
            image=item.image.name,
            video_url=item.video_url,
            caption=item.caption,
            order=item.order,
        )


def backward(apps, schema_editor):
    # Обратный перенос невозможен без потери привязки к мастеру — чистим копию
    apps.get_model("core", "ServicePointMedia").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("core", "0010_servicepointmedia"),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
