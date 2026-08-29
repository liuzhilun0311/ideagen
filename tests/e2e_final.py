"""最终端到端验证：迁移数据的图片/下载/任务状态（真实 HTTP）。"""
import requests

BASE = 'http://127.0.0.1:12399'
s = requests.Session()

# admin 登录
r = s.post(f'{BASE}/api/auth/login', json={'username': 'admin', 'password': 'admin123'}, timeout=30)
assert r.status_code == 200 and r.json().get('token'), 'admin 登录失败'
s.headers['Authorization'] = f"Bearer {r.json()['token']}"
print('admin login OK')

# 历史列表 → 取第一条带 task_id 的记录
r = s.get(f'{BASE}/api/history?page=1&page_size=1', timeout=15)
recs = r.json().get('records', [])
print('history list OK, total =', r.json().get('total'))
assert recs, '无历史记录'

# 详情
rid = recs[0]['id']
r = s.get(f'{BASE}/api/history/{rid}', timeout=15)
detail = r.json().get('record', {})
task_id = (detail.get('images') or {}).get('task_id')
generated = (detail.get('images') or {}).get('generated', [])
print('detail OK:', detail.get('title'), '| task:', task_id, '| imgs:', generated)
assert task_id and generated

# 图片访问（原图 + 缩略图）
for fname in generated[:2]:
    r = s.get(f'{BASE}/api/images/{task_id}/{fname}?thumbnail=false', timeout=15)
    print(f'  image {fname}:', r.status_code, 'type:', r.headers.get('Content-Type'), 'bytes:', len(r.content))
    assert r.status_code == 200
    thumb = f"thumb_{fname}"
    r = s.get(f'{BASE}/api/images/{task_id}/{thumb}?thumbnail=true', timeout=15)
    print(f'  thumb {thumb}:', r.status_code)
    break  # 只需验证一张

# 无 token 访问图片 → 401
r = requests.get(f'{BASE}/api/images/{task_id}/{generated[0]}?thumbnail=false', timeout=10)
print('image no token:', r.status_code)

# 任务状态
r = s.get(f'{BASE}/api/task/{task_id}', timeout=15)
print('task state:', r.status_code, 'generated:', len(r.json().get('state', {}).get('generated', {})),
      'has_cover:', r.json().get('state', {}).get('has_cover'))

# 下载 zip（历史记录打包下载）
r = s.get(f'{BASE}/api/history/{rid}/download', timeout=20)
print('download zip:', r.status_code, 'type:', r.headers.get('Content-Type'), 'bytes:', len(r.content))
assert r.status_code == 200 and len(r.content) > 0

# 服务商配置（脱敏）
r = s.get(f'{BASE}/api/config', timeout=15)
cfg = r.json().get('config', {})
tp = cfg.get('text_generation', {})
ip = cfg.get('image_generation', {})
print('config OK: text=', tp.get('active_provider'), 'img=', ip.get('active_provider'),
      '| api_key masked=', bool(next(iter((ip.get('providers') or {}).values()), {}).get('api_key_masked')))

# DeAI 配置
r = s.get(f'{BASE}/api/config/deai', timeout=15)
print('deai config:', r.status_code, 'python_script set =', bool(r.json().get('config', {}).get('python_script')))

print('=== FINAL E2E OK ===')
