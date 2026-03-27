from django.db import migrations


class Migration(migrations.Migration):
    dependencies = [
        ("beshtashabbus", "0003_application_snapshot_models"),
    ]

    operations = [
        migrations.AlterModelOptions(
            name="fiveinitiativeapplicationentry",
            options={
                "ordering": ["mahalla_name_raw", "participant_name"],
                "verbose_name": "5 tashabbus ariza qatori",
                "verbose_name_plural": "5 tashabbus ariza qatorlari",
                "permissions": [("submit_application", "5 tashabbus ariza yuborish ruxsati")],
            },
        ),
    ]
