"""扩展冒烟测试：generation + providers 接口。"""
import os
import sys
import time
import django

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client

c = Client()
USERNAME = f"exttest_{int(time.time())}"

# 登录
r = c.post('/api/auth/register', data={'username': USERNAME, 'password': 'secret123'}, content_type='application/json')
assert r.status_code == 200
r = c.post('/api/auth/login', data={'username': USERNAME, 'password': 'secret123'}, content_type='application/json')
token = r.json()['token']
AUTH = {'HTTP_AUTHORIZATION': f'Bearer {token}'}
print('login ok')

# 1. config get（脱敏）
r = c.get('/api/config', **AUTH)
print('config:', r.status_code, 'text active:', r.json().get('config', {}).get('text_generation', {}).get('active_provider'),
      'img active:', r.json().get('config', {}).get('image_generation', {}).get('active_provider'))

# 2. config/deai get
r = c.get('/api/config/deai', **AUTH)
print('deai config:', r.status_code, r.json())

# 3. outline 缺参数 -> 400
r = c.post('/api/outline', data={'topic': ''}, content_type='application/json', **AUTH)
print('outline empty topic:', r.status_code, r.json().get('success'))

# 4. content 缺参数 -> 400
r = c.post('/api/content', data={'topic': 'x'}, content_type='application/json', **AUTH)
print('content missing outline:', r.status_code)

# 5. generate 缺 pages -> 400
r = c.post('/api/generate', data={'task_id': 't1'}, content_type='application/json', **AUTH)
print('generate no pages:', r.status_code)

# 6. retry 缺参数 -> 400
r = c.post('/api/retry', data={}, content_type='application/json', **AUTH)
print('retry empty:', r.status_code)

# 7. retry-failed 缺参数 -> 400
r = c.post('/api/retry-failed', data={}, content_type='application/json', **AUTH)
print('retry-failed empty:', r.status_code)

# 8. regenerate 缺参数 -> 400
r = c.post('/api/regenerate', data={}, content_type='application/json', **AUTH)
print('regenerate empty:', r.status_code)

# 9. images 不存在 -> 404
r = c.get('/api/images/task_nonexist/0.png?thumbnail=false', **AUTH)
print('images nonexist:', r.status_code)

# 10. task 不存在 -> 404
r = c.get('/api/task/task_nonexist', **AUTH)
print('task nonexist:', r.status_code)

# 11. 未登录访问 -> 401
r = c.get('/api/config')
print('config no token:', r.status_code)

# 12. 生成器链能创建（用共享配置）
from providers.config import get_image_provider_config, get_text_provider_config
try:
    pc = get_image_provider_config(user_id=None)
    print('image provider loaded:', pc.get('type'), bool(pc.get('api_key')))
except Exception as e:
    print('image provider load FAILED:', str(e)[:120])
try:
    tc = get_text_provider_config(user_id=None)
    print('text provider loaded:', tc.get('type'), bool(tc.get('api_key')))
except Exception as e:
    print('text provider load FAILED:', str(e)[:120])

# 13. generation services 可导入并创建
from generation.services.image import get_image_service
from generation.services.outline import get_outline_service
from generation.services.content import get_content_service
img_svc = get_image_service(None)
print('image service workers:', img_svc.worker_count if hasattr(img_svc, 'worker_count') else 'n/a')
print('outline service:', type(get_outline_service(None)).__name__)
print('content service:', type(get_content_service(None)).__name__)

print('=== EXT SMOKE OK ===')
