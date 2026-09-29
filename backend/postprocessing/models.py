import uuid

from django.db import models
from django.db.models import Q


class ProcessingPreference(models.Model):
    user = models.OneToOneField('accounts.User', on_delete=models.CASCADE, primary_key=True)
    automatic = models.BooleanField(default=False)
    strength = models.CharField(max_length=8, default='medium')
    automatic_since = models.DateTimeField(null=True, blank=True)


class ImagePage(models.Model):
    record = models.ForeignKey('history.HistoryRecord', on_delete=models.CASCADE, related_name='image_versions')
    index = models.PositiveIntegerField()
    identity = models.CharField(max_length=64)
    source_revision = models.CharField(max_length=64)
    source_digest = models.CharField(max_length=64)
    source_path = models.CharField(max_length=512)
    published_revision = models.CharField(max_length=64, default='', blank=True)
    adopted = models.CharField(max_length=12, default='original')
    adoption_serial = models.PositiveIntegerField(default=0)
    current_job = models.ForeignKey('ImageJob', null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='+')

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=['record', 'index'], name='processing_record_page'),
        ]


class ImageJob(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    page = models.ForeignKey(ImagePage, on_delete=models.CASCADE, related_name='jobs')
    owner = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    source_revision = models.CharField(max_length=64)
    source_digest = models.CharField(max_length=64)
    source_path = models.CharField(max_length=512)
    strength = models.CharField(max_length=8)
    algorithm = models.CharField(max_length=80)
    status = models.CharField(max_length=12, default='queued')
    adoption_serial = models.PositiveIntegerField()
    attempts = models.PositiveIntegerField(default=0)
    lease_token = models.UUIDField(null=True, blank=True)
    lease_until = models.DateTimeField(null=True, blank=True)
    error = models.CharField(max_length=256, default='', blank=True)
    output_path = models.CharField(max_length=512, default='', blank=True)
    output_digest = models.CharField(max_length=64, default='', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['status', 'created_at'], name='processing_queue')]
        constraints = [
            models.UniqueConstraint(
                fields=['page'], condition=Q(status__in=['queued', 'processing']),
                name='processing_one_active_page',
            ),
        ]
