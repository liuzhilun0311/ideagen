"""迁移旧 Flask 版数据到 Django 数据库。

从旧项目（默认 D:\\Tools\\redlink）读取 users.json + history/<user_id>/<task_id>.json，
导入到数据库，并把图片目录 / user_configs 拷贝到新项目对应目录。

用法: python manage.py migrate_legacy [--legacy-root D:\\Tools\\redlink]
"""
import json
import os
import shutil
from datetime import datetime
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

from accounts.models import Token, User


def _parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except (ValueError, TypeError):
        return None


class Command(BaseCommand):
    help = '从旧 Flask 项目迁移用户/记录/图片到数据库'

    def add_arguments(self, parser):
        parser.add_argument('--legacy-root', type=str, default=r'D:\Tools\redlink',
                            help='旧项目根目录')

    @transaction.atomic
    def handle(self, *args, **options):
        legacy = Path(options['legacy_root'])
        if not legacy.exists():
            self.stderr.write(self.style.ERROR(f"旧项目目录不存在: {legacy}"))
            return

        # ---- 1. 用户与 token ----
        users_file = legacy / 'users.json'
        users_created = tokens_created = 0
        if users_file.exists():
            data = json.loads(users_file.read_text(encoding='utf-8'))
            for u in data.get('users', []):
                if User.objects.filter(id=u['id']).exists():
                    continue
                # 同名不同 id（如 initadmin 自动创建的 admin）：删除后者，采用旧库账号（保留原密码）
                dup = User.objects.filter(username=u['username']).exclude(id=u['id']).first()
                if dup:
                    dup.delete()
                User.objects.create(
                    id=u['id'],
                    username=u['username'],
                    password_hash=u.get('password_hash', ''),
                    created_at=_parse_dt(u.get('created_at')) or datetime.now(),
                    is_admin=bool(u.get('is_admin', False)),
                    use_shared_config=bool(u.get('use_shared_config', True)),
                )
                users_created += 1
            for tok, info in data.get('tokens', {}).items():
                expires = _parse_dt(info.get('expires_at'))
                if not expires:
                    continue
                if Token.objects.filter(key=tok).exists():
                    continue
                Token.objects.create(
                    key=tok,
                    user_id=info.get('user_id'),
                    expires_at=expires,
                )
                tokens_created += 1
        self.stdout.write(self.style.SUCCESS(f"用户导入 {users_created}，token 导入 {tokens_created}"))

        # ---- 2. 图片目录 + 用户配置 拷贝 ----
        history_src = legacy / 'history'
        if history_src.exists():
            history_src.mkdir(exist_ok=True)  # 确保目标存在
            settings.HISTORY_ROOT.mkdir(parents=True, exist_ok=True)
            for child in history_src.iterdir():
                if not child.is_dir() or not child.name.startswith('u_'):
                    continue
                target = settings.HISTORY_ROOT / child.name
                if not target.exists():
                    shutil.copytree(child, target)
                    self.stdout.write(f"  拷贝图片目录: {child.name}")
        uc_src = legacy / 'user_configs'
        if uc_src.exists():
            settings.USER_CONFIGS_ROOT.mkdir(parents=True, exist_ok=True)
            for child in uc_src.iterdir():
                if not child.is_dir():
                    continue
                target = settings.USER_CONFIGS_ROOT / child.name
                if not target.exists():
                    shutil.copytree(child, target)

        # ---- 3. 历史记录 JSON → 数据库 ----
        from history.models import HistoryRecord
        records_created = 0
        for user_dir in history_src.iterdir() if history_src.exists() else []:
            if not user_dir.is_dir() or not user_dir.name.startswith('u_'):
                continue
            user_id = user_dir.name
            for rec_file in user_dir.glob('*.json'):
                try:
                    rec = json.loads(rec_file.read_text(encoding='utf-8'))
                except Exception:
                    continue
                if HistoryRecord.objects.filter(id=rec.get('id')).exists():
                    continue
                images = rec.get('images') or {}
                HistoryRecord.objects.create(
                    id=rec['id'],
                    user_id=rec.get('user_id') or user_id,
                    title=rec.get('title', ''),
                    outline=rec.get('outline', {'raw': '', 'pages': []}),
                    content=rec.get('content', {'titles': [], 'copywriting': '', 'tags': []}),
                    images={
                        'task_id': images.get('task_id'),
                        'generated': images.get('generated', images.get('files', [])),
                    },
                    status=rec.get('status', 'completed'),
                    thumbnail=rec.get('thumbnail'),
                    created_at=_parse_dt(rec.get('created_at')) or datetime.now(),
                    updated_at=_parse_dt(rec.get('updated_at')) or datetime.now(),
                )
                records_created += 1
        self.stdout.write(self.style.SUCCESS(f"历史记录导入 {records_created} 条"))
        self.stdout.write(self.style.SUCCESS("迁移完成"))
