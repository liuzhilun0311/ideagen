from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [('history', '0003_historyrecord_image_style')]
    operations = [
        migrations.CreateModel(
            name='ImageCandidate',
            fields=[
                ('id', models.CharField(max_length=64, primary_key=True, serialize=False)),
                ('page_index', models.PositiveIntegerField()),
                ('page_content', models.TextField()),
                ('task_id', models.CharField(max_length=64)),
                ('style', models.JSONField(default=dict)),
                ('prompt', models.TextField(default='')),
                ('provider', models.CharField(default='', max_length=255)),
                ('status', models.CharField(default='generating', max_length=16)),
                ('filename', models.CharField(default='', max_length=100)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('record', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE,
                                            related_name='image_candidates', to='history.historyrecord')),
            ],
            options={'ordering': ['created_at', 'id']},
        ),
    ]
