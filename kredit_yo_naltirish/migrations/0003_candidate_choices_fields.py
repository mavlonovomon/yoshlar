from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("kredit_yo_naltirish", "0002_candidate_monitoring_note"),
    ]

    operations = [
        migrations.AddField(
            model_name="creditcandidate",
            name="business_type",
            field=models.CharField(blank=True, choices=[("PRODUCTION", "Ishlab chiqarish"), ("SERVICE", "Xizmat ko'rsatish")], default="", max_length=20),
        ),
        migrations.AddField(
            model_name="creditcandidate",
            name="collateral_type",
            field=models.CharField(blank=True, choices=[("NONE", "Garovsiz"), ("COLLATERAL", "Garov bilan"), ("GUARANTOR", "Kafillik bilan"), ("INSURANCE", "Sug'urta polisi bilan")], default="", max_length=20),
        ),
        migrations.AddField(
            model_name="creditcandidate",
            name="decision_basis",
            field=models.CharField(blank=True, choices=[("PQ60", "PQ-60"), ("PQ61", "PQ-61"), ("PQ62", "PQ-62")], default="", max_length=10),
        ),
    ]
