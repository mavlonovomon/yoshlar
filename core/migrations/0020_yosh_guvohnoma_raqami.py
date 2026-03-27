from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0019_leaderkpisnapshot'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunSQL(
                    sql="ALTER TABLE core_yosh ADD COLUMN guvohnoma_raqami varchar(30) NOT NULL DEFAULT ''",
                    reverse_sql=migrations.RunSQL.noop,
                ),
            ],
            state_operations=[
                migrations.AddField(
                    model_name='yosh',
                    name='guvohnoma_raqami',
                    field=models.CharField(blank=True, max_length=30, verbose_name='Guvohnoma raqami'),
                ),
            ],
        ),
    ]
