"""打包部署 zip（排除 .venv / node_modules / 运行时数据 / 敏感本地文件）。

用法: python pack_deploy.py
输出: ideagen_deploy.zip（含 Dockerfile、compose、后端、前端源码、服务商配置模板）
"""
import os
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / 'ideagen_deploy.zip'

# 需要排除的目录/文件（打包时跳过）
# 注意：backend/history 是 Django 代码，必须保留；根目录的 history/ 才是运行时数据
EXCLUDE_DIRS = {
    '.venv', 'node_modules', '__pycache__', '.git', 'dist', 'tests',
    '.superpowers', '.pytest_cache', 'test-results', 'staticfiles',
}
# 项目根目录下的运行时数据目录（只排除顶层，任意层级出现不算）
EXCLUDE_ROOT_DIRS = {'history', 'output', 'user_configs', 'data'}
EXCLUDE_FILES = {
    'ideagen_deploy.zip', 'db.sqlite3',
    'image_providers.yaml', 'text_providers.yaml',
}


def _skip(rel: str, is_dir: bool) -> bool:
    parts = rel.replace('\\', '/').split('/')
    if parts[0] in EXCLUDE_ROOT_DIRS:
        return True
    for p in parts:
        if p in EXCLUDE_DIRS:
            return True
    name = parts[-1]
    if is_dir:
        return False
    if name in EXCLUDE_FILES:
        return True
    if name == '.env' or (name.startswith('.env.') and name != '.env.example'):
        return True
    if name.endswith(('.pyc', '.log', '.sqlite3', '.db', '.zip', '.pem', '.key')):
        return True
    return False


def main():
    count = 0
    with zipfile.ZipFile(OUT, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(ROOT):
            dirs[:] = [d for d in dirs if not _skip(os.path.relpath(os.path.join(root, d), ROOT), True)]
            for f in files:
                full = os.path.join(root, f)
                rel = os.path.relpath(full, ROOT)
                if _skip(rel, False):
                    continue
                zf.write(full, rel)
                count += 1
    size = OUT.stat().st_size / 1024 / 1024
    print(f"打包完成: {OUT.name}（{size:.1f} MB，{count} 个文件）")
    print("部署包不含真实服务商配置及用户数据；部署时需单独配置，迁移数据请按部署说明备份。")


if __name__ == '__main__':
    main()
