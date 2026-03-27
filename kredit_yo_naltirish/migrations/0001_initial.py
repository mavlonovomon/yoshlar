from django.db import migrations, models
import django.db.models.deletion
import django.core.validators


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        ("core", "0020_yosh_guvohnoma_raqami"),
    ]

    operations = [
        migrations.CreateModel(
            name="CreditCandidate",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("stage", models.CharField(choices=[("NOMINATION", "Nomzod"), ("IN_PROCESS", "Jarayonda"), ("APPROVED", "Kredit ajratildi"), ("REJECTED", "Rad etildi"), ("MONITORING", "Monitoring")], db_index=True, default="NOMINATION", max_length=20)),
                ("monitoring_enabled", models.BooleanField(default=False)),
                ("business_name", models.CharField(blank=True, default="", max_length=255)),
                ("project_goal", models.CharField(blank=True, default="", max_length=500)),
                ("collateral", models.CharField(blank=True, default="", max_length=255)),
                ("credit_amount", models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True)),
                ("reject_reason", models.CharField(blank=True, default="", max_length=500)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                ("decided_at", models.DateTimeField(blank=True, null=True)),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="credit_candidates_created", to="core.user")),
                ("processed_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="credit_candidates_processed", to="core.user")),
                ("yosh", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="credit_candidates", to="core.yosh")),
            ],
            options={
                "verbose_name": "Kredit nomzodi",
                "verbose_name_plural": "Kredit nomzodlari",
                "ordering": ["-created_at"],
                "permissions": [("manage_pipeline", "Kredit jarayonini boshqarish")],
            },
        ),
        migrations.CreateModel(
            name="CreditMonitoringEntry",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("monitoring_date", models.DateField()),
                ("note", models.TextField(blank=True, default="")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("candidate", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="monitoring_entries", to="kredit_yo_naltirish.creditcandidate")),
                ("created_by", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="credit_monitoring_entries", to="core.user")),
            ],
            options={
                "verbose_name": "Kredit monitoring yozuvi",
                "verbose_name_plural": "Kredit monitoring yozuvlari",
                "ordering": ["-monitoring_date", "-created_at"],
            },
        ),
        migrations.CreateModel(
            name="CreditMonitoringFile",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("file", models.FileField(upload_to="kredit_yo_naltirish/monitoring/", validators=[django.core.validators.FileExtensionValidator(["jpg", "jpeg", "png", "pdf"])])),
                ("file_type", models.CharField(choices=[("image", "Rasm"), ("document", "Hujjat")], max_length=20)),
                ("uploaded_at", models.DateTimeField(auto_now_add=True)),
                ("monitoring_entry", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="files", to="kredit_yo_naltirish.creditmonitoringentry")),
            ],
            options={
                "verbose_name": "Monitoring fayli",
                "verbose_name_plural": "Monitoring fayllari",
                "ordering": ["-uploaded_at"],
            },
        ),
    ]
