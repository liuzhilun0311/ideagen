from django.db import models


class LibraryMutex(models.Model):
    """One writer gate also serializes shared-file naming across administrators."""

    id = models.PositiveSmallIntegerField(primary_key=True, default=1)
    version = models.PositiveBigIntegerField(default=0)


class LibraryOrder(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    resource = models.CharField(max_length=16)
    kind = models.CharField(max_length=32)
    revision = models.PositiveBigIntegerField(default=0)
    order = models.JSONField(default=list)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'resource', 'kind'], name='library_order_scope',
            ),
        ]


class CopyRequest(models.Model):
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE)
    request_id = models.CharField(max_length=128)
    resource = models.CharField(max_length=16)
    kind = models.CharField(max_length=16)
    source = models.TextField()
    revision = models.PositiveBigIntegerField()
    response = models.JSONField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'request_id'], name='library_copy_request_scope',
            ),
        ]
