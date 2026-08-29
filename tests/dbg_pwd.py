"""调试：验证密码哈希往返。"""
import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from accounts import auth
from accounts.models import User

h = auth._hash_password('secret123')
print('hash:', h)
print('verify new:', auth._verify_password('secret123', h))

u = User.objects.filter(username__startswith='smoketest_').order_by('-created_at').first()
if u:
    print('stored:', u.password_hash)
    print('verify stored:', auth._verify_password('secret123', u.password_hash))
    # 用服务层登录
    try:
        res = auth.login('u' if False else u.username, 'secret123')
        print('login ok:', bool(res.get('token')))
    except ValueError as e:
        print('login ValueError:', e)
