from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


def forwards_create_groups(apps, schema_editor):
    Task = apps.get_model("ishsiz_yoshlar", "Task")
    TaskGroup = apps.get_model("ishsiz_yoshlar", "TaskGroup")
    db_alias = schema_editor.connection.alias

    # Cache by signature so identical tasks are grouped
    cache = {}
    for task in Task.objects.using(db_alias).all():
        attachment_name = ""
        try:
            attachment_name = task.attachment.name or ""
        except Exception:
            attachment_name = ""

        key = (
            task.title,
            task.description,
            task.priority,
            task.due_date,
            task.created_by_id,
            task.target_youth_id,
            task.target_mahalla_id,
            attachment_name,
        )

        group = cache.get(key)
        if not group:
            group = TaskGroup.objects.using(db_alias).create(
                title=task.title,
                description=task.description,
                priority=task.priority,
                created_by_id=task.created_by_id,
                target_youth_id=task.target_youth_id,
                target_mahalla_id=task.target_mahalla_id,
                due_date=task.due_date,
                attachment=task.attachment,
                created_at=task.created_at,
                updated_at=task.updated_at,
            )
            cache[key] = group

        task.task_group_id = group.id
        task.save(update_fields=["task_group"])


def backwards_remove_groups(apps, schema_editor):
    Task = apps.get_model("ishsiz_yoshlar", "Task")
    TaskGroup = apps.get_model("ishsiz_yoshlar", "TaskGroup")
    db_alias = schema_editor.connection.alias
    Task.objects.using(db_alias).update(task_group=None)
    TaskGroup.objects.using(db_alias).all().delete()


class Migration(migrations.Migration):

    dependencies = [
        ("ishsiz_yoshlar", "0007_task_batch_id"),
    ]

    operations = [
        migrations.CreateModel(
            name="TaskGroup",
            fields=[
                ("id", models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=255, verbose_name="Topshiriq nomi")),
                ("description", models.TextField(verbose_name="Topshiriq tavsifi")),
                ("priority", models.CharField(choices=[("LOW", "Past"), ("MEDIUM", "O'rta"), ("HIGH", "Yuqori"), ("URGENT", "Shoshilinch")], default="MEDIUM", max_length=10, verbose_name="Muhimlik")),
                ("due_date", models.DateTimeField(verbose_name="Bajarish muddati")),
                ("attachment", models.FileField(blank=True, null=True, upload_to="task_attachments/", validators=[django.core.validators.FileExtensionValidator(["pdf", "doc", "docx", "xls", "xlsx", "jpg", "jpeg", "png", "zip"])], verbose_name="Biriktirilgan fayl")),
                ("created_at", models.DateTimeField(auto_now_add=True, verbose_name="Yaratilgan vaqt")),
                ("updated_at", models.DateTimeField(auto_now=True, verbose_name="Yangilangan vaqt")),
                ("created_by", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="created_task_groups", to="core.user", verbose_name="Yaratgan admin")),
                ("target_mahalla", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="task_groups", to="core.mahalla", verbose_name="Mo'ljaldagi mahalla")),
                ("target_youth", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="task_groups", to="core.yosh", verbose_name="Mo'ljaldagi yosh")),
            ],
            options={
                "verbose_name": "Topshiriq guruhi",
                "verbose_name_plural": "Topshiriq guruhlari",
                "ordering": ["-created_at"],
            },
        ),
        migrations.AddField(
            model_name="task",
            name="task_group",
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.CASCADE, related_name="assignments", to="ishsiz_yoshlar.taskgroup", verbose_name="Topshiriq guruhi"),
        ),
        migrations.AddIndex(
            model_name="task",
            index=models.Index(fields=["task_group"], name="ishsiz_yos_task_gr_3c0a1e_idx"),
        ),
        migrations.RunPython(forwards_create_groups, backwards_remove_groups),
    ]
