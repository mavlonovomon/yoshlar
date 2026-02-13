from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("core", "0012_ustoz_ai_seed_aliases"),
    ]

    operations = [
        migrations.CreateModel(
            name="UzchessStatSnapshot",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("snapshot_date", models.DateField(db_index=True)),
                ("fetched_at", models.DateTimeField(auto_now_add=True)),
                ("source_url", models.TextField()),
                ("raw_payload", models.JSONField(default=dict)),
            ],
            options={
                "verbose_name": "UzChess snapshot",
                "verbose_name_plural": "UzChess snapshotlar",
                "ordering": ["-snapshot_date", "-fetched_at"],
            },
        ),
        migrations.CreateModel(
            name="UzchessMahallaAlias",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("api_name", models.CharField(max_length=255)),
                ("api_norm", models.CharField(db_index=True, max_length=255, unique=True)),
                ("last_seen", models.DateTimeField(auto_now=True)),
                ("mahalla", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uzchess_aliases", to="core.mahalla")),
            ],
            options={
                "verbose_name": "UzChess mahalla moslash",
                "verbose_name_plural": "UzChess mahalla moslash",
                "ordering": ["api_name"],
            },
        ),
        migrations.CreateModel(
            name="UzchessMahallaStat",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("area_external_id", models.CharField(blank=True, db_index=True, max_length=64, null=True)),
                ("area_name", models.CharField(db_index=True, max_length=255)),
                ("metrics", models.JSONField(default=dict)),
                ("mahalla", models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name="uzchess_stats", to="core.mahalla")),
                ("snapshot", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name="area_stats", to="core.uzchessstatsnapshot")),
            ],
            options={
                "verbose_name": "UzChess mahalla statistikasi",
                "verbose_name_plural": "UzChess mahalla statistikasi",
                "ordering": ["area_name"],
            },
        ),
    ]
