from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('accounts', '0001_initial'),
        ('history', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='historyrecord',
            name='shared_users',
            field=models.ManyToManyField(
                blank=True, related_name='shared_history_records', to='accounts.user',
            ),
        ),
    ]
