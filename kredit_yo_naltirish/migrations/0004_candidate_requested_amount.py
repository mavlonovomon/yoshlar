from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("kredit_yo_naltirish", "0003_candidate_choices_fields"),
    ]

    operations = [
        migrations.AddField(
            model_name="creditcandidate",
            name="requested_amount",
            field=models.DecimalField(blank=True, decimal_places=2, max_digits=12, null=True),
        ),
    ]
