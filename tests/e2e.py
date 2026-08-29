"""端到端验证：真实 HTTP 调 Django 后端，含真实 AI 大纲生成。"""
import requests

BASE = 'http://127.0.0.1:12399'

s = requests.Session()

# 登录 admin
r = s.post(f'{BASE}/api/auth/login', json={'username': 'admin', 'password': 'admin123'}, timeout=30)
print('login:', r.status_code, bool(r.json().get('token')))
token = r.json()['token']
s.headers['Authorization'] = f'Bearer {token}'

# 首页 (SPA)
r = s.get(f'{BASE}/', timeout=10)
print('root:', r.status_code, 'html:', r.text[:30].strip())

# 历史列表
r = s.get(f'{BASE}/api/history?page=1&page_size=3', timeout=15)
print('history:', r.status_code, 'total:', r.json().get('total'))

# 真实大纲生成（DeepSeek）
try:
    r = s.post(f'{BASE}/api/outline', json={'topic': '一杯咖啡的早晨', 'images': []}, timeout=120)
    data = r.json()
    print('outline:', r.status_code, 'success:', data.get('success'))
    if data.get('success'):
        print('  pages:', len(data.get('pages', [])), '| title:', (data.get('pages') or [{}])[0].get('content', '')[:20])
    else:
        print('  error:', data.get('error_message', '')[:120])
except Exception as e:
    print('outline EXC:', str(e)[:200])

print('=== E2E DONE ===')
