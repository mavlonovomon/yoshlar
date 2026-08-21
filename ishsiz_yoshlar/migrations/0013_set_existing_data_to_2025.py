from django.db import migrations


def set_existing_data_to_2025(apps, schema_editor):
    UnemployedYouth = apps.get_model('ishsiz_yoshlar', 'UnemployedYouth')
    UnemployedYouth.objects.all().update(year=2025)


class Migration(migrations.Migration):

    dependencies = [
        ('ishsiz_yoshlar', '0012_unemployedyouth_year_and_more'),
    ]

    operations = [
        migrations.RunPython(set_existing_data_to_2025, migrations.RunPython.noop),
    ]
