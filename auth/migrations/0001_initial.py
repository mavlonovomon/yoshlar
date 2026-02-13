from django.db import migrations, models
import django.db.models.deletion
from django.conf import settings


class Migration(migrations.Migration):
    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='EimzoProfile',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('cert_serial', models.CharField(blank=True, max_length=128, null=True)),
                ('cert_subject', models.TextField(blank=True, null=True)),
                ('cert_valid_from', models.DateTimeField(blank=True, null=True)),
                ('cert_valid_to', models.DateTimeField(blank=True, null=True)),
                ('last_verified_at', models.DateTimeField(blank=True, null=True)),
                ('user', models.OneToOneField(on_delete=django.db.models.deletion.CASCADE, related_name='eimzo_profile', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'verbose_name': 'E-IMZO profil',
                'verbose_name_plural': 'E-IMZO profillar',
            },
        ),
    ]
