from django.db import migrations, models
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ("ishsiz_yoshlar", "0006_alter_task_status_and_more"),
    ]

    operations = [
        migrations.AddField(
            model_name="task",
            name="batch_id",
            field=models.UUIDField(db_index=True, default=uuid.uuid4, editable=False),
        ),
    ]
