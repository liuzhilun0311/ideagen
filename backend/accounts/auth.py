"""用户认证服务（从 Flask 版 services/auth.py 移植到 Django ORM）。"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
from datetime import datetime, timedelta
from typing import Dict, Optional

from django.conf import settings
from django.utils import timezone

from .models import Token, User

TOKEN_TTL_DAYS = 7


# ==================== 密码哈希（与 Flask 版完全一致的格式） ====================

def _hash_password(password: str, salt: Optional[str] = None) -> str:
    if salt is None:
        salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac(
        'sha256',
        password.encode('utf-8'),
        salt.encode('utf-8'),
        200000,
    )
    return f"pbkdf2:sha256:200000${salt}${digest.hex()}"


def _verify_password(password: str, stored: str) -> bool:
    try:
        scheme, salt, hexdigest = stored.split('$')
        # scheme = "pbkdf2:sha256:200000"，用 rsplit 拆成 algo 与 iterations
        algo, iterations = scheme.rsplit(':', 1)
        if algo != 'pbkdf2:sha256' or iterations != '200000':
            return False
        digest = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode('utf-8'),
            salt.encode('utf-8'),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), hexdigest)
    except (ValueError, TypeError):
        return False


# ==================== 序列化 ====================

def _to_public(user: User) -> Dict[str, Optional[str]]:
    return {
        "id": user.id,
        "username": user.username,
        "is_admin": user.is_admin,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }


def _user_dict(user: User) -> Dict:
    data = _to_public(user)
    data['use_shared_config'] = user.use_shared_config
    return data


# ==================== 注册 / 登录 / 退出 ====================

def register(username: str, password: str) -> Dict:
    username = (username or '').strip()
    if len(username) < 2:
        raise ValueError("用户名至少需要 2 个字符")
    if len(password) < 6:
        raise ValueError("密码至少需要 6 个字符")
    if User.objects.filter(username=username).exists():
        raise ValueError("用户名已存在")

    user = User(
        id=f"u_{secrets.token_hex(4)}",
        username=username,
        password_hash=_hash_password(password),
        is_admin=False,
    )
    user.save()
    return _to_public(user)


def login(username: str, password: str) -> Dict:
    user = User.objects.filter(username=(username or '').strip()).first()
    if not user or not _verify_password(password, user.password_hash):
        raise ValueError("用户名或密码错误")

    token = secrets.token_hex(32)
    expires_at = timezone.now() + timedelta(days=TOKEN_TTL_DAYS)
    Token.objects.create(key=token, user=user, expires_at=expires_at)

    return {
        "token": token,
        "user": _to_public(user),
        "expires_at": expires_at.isoformat(),
    }


def logout(token: str) -> None:
    if token:
        Token.objects.filter(key=token).delete()


def get_user_by_token(token: Optional[str]) -> Optional[Dict]:
    if not token:
        return None
    token_obj = Token.objects.select_related('user').filter(key=token).first()
    if not token_obj:
        return None
    if token_obj.expires_at < timezone.now():
        token_obj.delete()
        return None
    return _user_dict(token_obj.user)


# ==================== 用户管理 ====================

def list_users() -> list:
    return [_to_public(u) for u in User.objects.order_by('created_at')]


def change_password(user_id: str, old_password: str, new_password: str, is_admin: bool, current_user_id: str) -> None:
    if len(new_password) < 6:
        raise ValueError("新密码至少需要 6 个字符")
    user = User.objects.filter(id=user_id).first()
    if not user:
        raise ValueError("用户不存在")

    if not is_admin or user_id == current_user_id:
        # 普通用户只能改自己，且必须验证原密码
        if not (user_id == current_user_id and _verify_password(old_password, user.password_hash)):
            raise ValueError("原密码错误")
    user.password_hash = _hash_password(new_password)
    user.save()


def delete_user(user_id: str, current_user_id: str) -> None:
    if user_id == current_user_id:
        raise ValueError("不能删除当前登录账号")
    user = User.objects.filter(id=user_id).first()
    if not user:
        raise ValueError("用户不存在")
    if user.is_admin:
        raise ValueError("不能删除管理员账号")

    _delete_user_records(user_id)
    user.delete()


def _delete_user_records(user_id: str) -> None:
    """删除用户的历史记录（数据库 + 图片目录）。"""
    try:
        from history.models import HistoryRecord
        HistoryRecord.objects.filter(user_id=user_id).delete()
    except Exception:
        pass

    # 删除磁盘上的图片目录与私有配置目录
    import shutil
    for path in (
        settings.HISTORY_ROOT / user_id,
        settings.USER_CONFIGS_ROOT / user_id,
    ):
        try:
            if path.exists():
                shutil.rmtree(path)
        except Exception:
            pass


# ==================== 管理员初始化 ====================

def ensure_admin() -> Optional[Dict]:
    """确保存在 admin 账号（用环境变量 ADMIN_PASSWORD，默认 admin123）。"""
    if User.objects.filter(is_admin=True).exists():
        return None
    password = os.environ.get('ADMIN_PASSWORD', settings.ADMIN_PASSWORD or 'admin123')
    user = User(
        id=f"u_{secrets.token_hex(4)}",
        username="admin",
        password_hash=_hash_password(password),
        is_admin=True,
    )
    user.save()
    return _user_dict(user)
