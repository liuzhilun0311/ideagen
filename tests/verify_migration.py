"""验证旧数据迁移结果。"""
import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts.models import User, Token
from history.models import HistoryRecord
from history.services import get_history_service

print('users:', list(User.objects.values_list('username', 'id')))
print('tokens:', Token.objects.count())
print('records:', HistoryRecord.objects.count())
print('by status:', dict(HistoryRecord.objects.values_list('status').annotate(c=__import__('django.db.models', fromlist=['Count']).Count('id'))))

# 取一条已迁移记录，检查归属与图片目录
rec = HistoryRecord.objects.order_by('-created_at').first()
if rec:
    print('sample record:', rec.id, rec.title, rec.user_id, rec.images)
    task_id = (rec.images or {}).get('task_id')
    owner = get_history_service().find_owner_by_task(task_id) if task_id else None
    print('task owner:', owner)
    from pathlib import Path
    from django.conf import settings
    d = settings.HISTORY_ROOT / (rec.user_id or 'default') / task_id
    print('task dir exists:', d.exists(), 'files:', sorted(p.name for p in d.glob('*.png'))[:8] if d.exists() else [])
