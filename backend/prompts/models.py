from django.db import models


class PromptEntry(models.Model):
    id = models.CharField(primary_key=True, max_length=100)
    module = models.CharField(max_length=16)
    category = models.CharField(max_length=24)
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=500, default="")
    content = models.TextField()
    metadata = models.JSONField(default=dict)
    legacy_value = models.CharField(max_length=100, default="")
    builtin = models.BooleanField(default=False)
    owner = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)
    enabled = models.BooleanField(default=True)
    visibility = models.CharField(max_length=16, default="private")
    allowed_users = models.JSONField(default=list)
    revision = models.PositiveIntegerField(default=1)
    default_snapshot = models.JSONField(default=dict)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["module", "category", "id"]


class PromptVersion(models.Model):
    entry = models.ForeignKey(PromptEntry, on_delete=models.PROTECT, related_name="versions")
    number = models.PositiveIntegerField()
    snapshot = models.JSONField()
    actor = models.ForeignKey("accounts.User", null=True, on_delete=models.SET_NULL)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-number"]
        constraints = [
            models.UniqueConstraint(fields=["entry", "number"], name="prompt_version_number"),
        ]
