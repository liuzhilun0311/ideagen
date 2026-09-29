from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ("history", "0005_historyrecord_analysis_snapshots"),
    ]

    operations = [
        migrations.AddField(
            model_name="historyrecord",
            name="generation_audit",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
