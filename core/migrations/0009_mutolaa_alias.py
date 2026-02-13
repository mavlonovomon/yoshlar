from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0008_mutolaa_mahalla_match'),
    ]

    operations = [
        migrations.CreateModel(
            name='MutolaaMahallaAlias',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('api_name', models.CharField(max_length=255)),
                ('api_norm', models.CharField(db_index=True, max_length=255, unique=True)),
                ('last_seen', models.DateTimeField(auto_now=True)),
                ('mahalla', models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mutolaa_aliases', to='core.mahalla')),
            ],
            options={
                'verbose_name': 'Mutolaa mahalla moslash',
                'verbose_name_plural': 'Mutolaa mahalla moslash',
                'ordering': ['api_name'],
            },
        ),
    ]
