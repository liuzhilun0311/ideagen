from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('postprocessing', '0002_imagepage_published_revision'),
    ]

    operations = [
        migrations.AlterField(
            model_name='processingpreference',
            name='strength',
            field=models.CharField(default='medium', max_length=8),
        ),
    ]
