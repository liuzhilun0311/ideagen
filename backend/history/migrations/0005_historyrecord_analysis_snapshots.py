from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("history", "0004_imagecandidate"),
    ]

    operations = [
        migrations.AddField(
            model_name="historyrecord",
            name="analysis_snapshots",
            field=models.JSONField(blank=True, default=list),
        ),
    ]
