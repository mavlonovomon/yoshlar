from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0005_user_pinfl'),
    ]

    operations = [
        migrations.CreateModel(
            name='MutolaaStatSnapshot',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('snapshot_date', models.DateField(db_index=True)),
                ('fetched_at', models.DateTimeField(auto_now_add=True)),
                ('source_url', models.TextField()),
                ('raw_payload', models.JSONField(default=dict)),
            ],
            options={
                'verbose_name': 'Mutolaa snapshot',
                'verbose_name_plural': 'Mutolaa snapshotlar',
                'ordering': ['-snapshot_date', '-fetched_at'],
            },
        ),
        migrations.CreateModel(
            name='MutolaaMahallaStat',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('mahalla_external_id', models.CharField(blank=True, db_index=True, max_length=64, null=True)),
                ('mahalla_name', models.CharField(db_index=True, max_length=255)),
                ('metrics', models.JSONField(default=dict)),
                ('snapshot', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='mahalla_stats', to='core.mutolaastatsnapshot')),
            ],
            options={
                'verbose_name': 'Mutolaa mahalla statistikasi',
                'verbose_name_plural': 'Mutolaa mahalla statistikasi',
                'ordering': ['mahalla_name'],
            },
        ),
    ]
