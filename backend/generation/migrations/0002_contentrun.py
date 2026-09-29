import uuid
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [("generation", "0001_initial")]
    operations = [
        migrations.CreateModel(
            name="ContentRun",
            fields=[
                ("id", models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False, serialize=False)),
                ("prompt", models.TextField()),
                ("preferences", models.JSONField(default=dict)),
                ("provider", models.CharField(max_length=255, default="")),
                ("status", models.CharField(max_length=20, default="prepared")),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("user", models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to="accounts.user")),
            ],
            options={"ordering": ["-created_at"]},
        ),
    ]
