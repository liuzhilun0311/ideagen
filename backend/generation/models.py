import uuid
from django.db import models


class OutlineRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    prompt = models.TextField()
    preferences = models.JSONField(default=dict)
    references = models.JSONField(default=list)
    provider = models.CharField(max_length=255, default="")
    model = models.CharField(max_length=255, default="")
    status = models.CharField(max_length=20, default="prepared")
    sent = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

class ContentRun(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey("accounts.User", on_delete=models.CASCADE)
    prompt = models.TextField()
    preferences = models.JSONField(default=dict)
    provider = models.CharField(max_length=255, default="")
    status = models.CharField(max_length=20, default="prepared")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
