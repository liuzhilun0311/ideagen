"""核心冒烟测试：auth + history CRUD（用 Django test Client）。"""
import os
import sys
import django

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
import time

c = Client()
USERNAME = f"smoketest_{int(time.time())}"

# 1. health
r = c.get('/api/health')
print('health:', r.status_code, r.json())

# 2. register
r = c.post('/api/auth/register', data={'username': USERNAME, 'password': 'secret123'}, content_type='application/json')
print('register:', r.status_code, r.json())
assert r.status_code == 200 and r.json()['success']

# 3. duplicate register
r = c.post('/api/auth/register', data={'username': USERNAME, 'password': 'secret123'}, content_type='application/json')
print('dup register:', r.status_code, r.json())

# 4. login
r = c.post('/api/auth/login', data={'username': USERNAME, 'password': 'secret123'}, content_type='application/json')
print('login:', r.status_code, r.json())
assert r.status_code == 200
token = r.json()['token']

# 5. me without token -> 401
r = c.get('/api/auth/me')
print('me no token:', r.status_code, r.json()['success'])

# 6. me with token
r = c.get('/api/auth/me', HTTP_AUTHORIZATION=f'Bearer {token}')
print('me:', r.status_code, r.json())

# 7. create history
payload = {
    'topic': '拒绝内耗',
    'outline': {'raw': '完整大纲', 'pages': [{'index': 0, 'type': 'cover', 'content': '封面'}, {'index': 1, 'type': 'content', 'content': '内容'}]},
    'task_id': 'task_smoke_001',
}
r = c.post('/api/history', data=payload, content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {token}')
print('create history:', r.status_code, r.json())
assert r.status_code == 200
rid = r.json()['record_id']

# 8. list history
r = c.get('/api/history', HTTP_AUTHORIZATION=f'Bearer {token}')
print('list history:', r.status_code, r.json().get('total'), r.json().get('records')[0].get('title'))

# 9. get detail
r = c.get(f'/api/history/{rid}', HTTP_AUTHORIZATION=f'Bearer {token}')
print('detail:', r.status_code, r.json()['record']['title'], r.json()['record']['images'])

# 10. update
r = c.put(f'/api/history/{rid}', data={'status': 'completed', 'images': {'task_id': 'task_smoke_001', 'generated': ['0.png', '1.png']}},
          content_type='application/json', HTTP_AUTHORIZATION=f'Bearer {token}')
print('update:', r.status_code, r.json())

# 11. stats
r = c.get('/api/history/stats', HTTP_AUTHORIZATION=f'Bearer {token}')
print('stats:', r.status_code, r.json())

# 12. search
r = c.get('/api/history/search?keyword=内耗', HTTP_AUTHORIZATION=f'Bearer {token}')
print('search:', r.status_code, len(r.json()['records']))

# 13. exists
r = c.get(f'/api/history/{rid}/exists', HTTP_AUTHORIZATION=f'Bearer {token}')
print('exists:', r.status_code, r.json())

# 14. admin list users
r = c.get('/api/auth/users', HTTP_AUTHORIZATION='Bearer ' + token)
print('admin users (non-admin):', r.status_code)

print('=== SMOKE OK ===')
