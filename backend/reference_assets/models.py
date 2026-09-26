import uuid

from django.db import models


class ImageAnalysis(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="image_analyses")
    source_image_path = models.CharField(max_length=512, blank=True, default="")
    source_image_digest = models.CharField(max_length=64, blank=True, default="")
    content = models.JSONField(default=dict)
    layout = models.JSONField(default=dict)
    visual_style = models.JSONField(default=dict)
    rewritten_content = models.TextField(blank=True, default="")
    user_note = models.TextField(blank=True, default="")
    status = models.CharField(max_length=16, default="completed")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]


class ReferenceAsset(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    owner = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="reference_assets")
    analysis = models.ForeignKey(
        ImageAnalysis,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="reference_assets",
    )
    title = models.CharField(max_length=120, default="")
    image_path = models.CharField(max_length=512, blank=True, default="")
    content = models.JSONField(default=dict)
    rewritten_content = models.TextField(blank=True, default="")
    user_note = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]
