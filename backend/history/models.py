"""历史记录数据模型（对应 Flask 版 history/<user_id>/<task_id>.json）。"""
from django.db import models


class HistoryRecord(models.Model):
    """一条创作历史记录（大纲/标题/文案/标签/图片清单）。"""
    id = models.CharField(max_length=64, primary_key=True)        # record_id (UUID)
    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='history_records')
    shared_users = models.ManyToManyField(
        'accounts.User', blank=True, related_name='shared_history_records',
    )
    title = models.CharField(max_length=255, default='')
    outline = models.JSONField(default=dict, blank=True)          # {raw, pages:[{index,type,content}]}
    content = models.JSONField(default=dict, blank=True)          # {titles:[], copywriting:'', tags:[]}
    analysis_snapshots = models.JSONField(default=list, blank=True)
    generation_audit = models.JSONField(default=dict, blank=True)
    images = models.JSONField(default=dict, blank=True)           # {task_id, generated:[...]}
    image_style = models.JSONField(default=dict, blank=True)
    status = models.CharField(max_length=32, default='draft')     # draft/generating/partial/completed/error
    thumbnail = models.CharField(max_length=255, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'history_record'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.id}:{self.title}"


class ImageCandidate(models.Model):
    """Immutable generated source; publication is a separate explicit action."""
    id = models.CharField(max_length=64, primary_key=True)
    record = models.ForeignKey(HistoryRecord, on_delete=models.CASCADE, related_name='image_candidates')
    page_index = models.PositiveIntegerField()
    page_content = models.TextField()
    task_id = models.CharField(max_length=64)
    style = models.JSONField(default=dict)
    prompt = models.TextField(default='')
    provider = models.CharField(max_length=255, default='')
    status = models.CharField(max_length=16, default='generating')
    filename = models.CharField(max_length=100, default='')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['created_at', 'id']
