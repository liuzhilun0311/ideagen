from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [('history', '0002_historyrecord_shared_users')]
    operations = [
        migrations.AddField(
            model_name='historyrecord', name='image_style',
            field=models.JSONField(default=dict, blank=True),
        ),
    ]
