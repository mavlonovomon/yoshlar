from django.db import migrations


def cleanup_boshqa_assistance_type(apps, schema_editor):
    AssistanceInfo = apps.get_model('ishsiz_yoshlar', 'AssistanceInfo')
    AssistanceInfo.objects.filter(assistance_type='BOSHQA').update(assistance_type=None)


class Migration(migrations.Migration):

    dependencies = [
        ('ishsiz_yoshlar', '0009_rename_ishsiz_yos_task_gr_3c0a1e_idx_ishsiz_yosh_task_gr_3e8d78_idx_and_more'),
    ]

    operations = [
        migrations.RunPython(cleanup_boshqa_assistance_type, migrations.RunPython.noop),
    ]

