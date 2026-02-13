from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0007_merge_0006_mutolaa_stats_0006_uchrashuv_photo'),
    ]

    operations = [
        migrations.AddField(
            model_name='mutolaamahallastat',
            name='mahalla',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='mutolaa_stats', to='core.mahalla'),
        ),
    ]
