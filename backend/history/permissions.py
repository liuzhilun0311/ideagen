"""Separate record reads, mutations, and administrator-owned sharing grants."""
import re
from functools import wraps
from pathlib import Path

from django.conf import settings
from django.utils.cache import patch_vary_headers

from accounts.models import User
from .models import HistoryRecord


def actor(user_id):
    return User.objects.filter(pk=user_id).first() if user_id else None


def can_modify(user, record, *, allow_admin=True):
    return bool(user and record and (
        record.user_id == user.pk or (allow_admin and user.is_admin)
    ))


def can_share(user, record):
    return bool(user and record and user.is_admin and record.user_id == user.pk)


def can_read(user, record, *, allow_admin=True):
    return can_modify(user, record, allow_admin=allow_admin) or bool(
        user and record and record.user.is_admin
        and record.shared_users.filter(pk=user.pk).exists()
    )


def capabilities(user, record):
    result = {
        'owner': {'id': record.user_id, 'username': record.user.username},
        'can_edit': can_modify(user, record),
        'can_share': can_share(user, record),
        'is_shared': bool(record.user.is_admin and record.shared_users.exists()),
    }
    if result['can_share']:
        result['shared_count'] = record.shared_users.count()
    return result


def record_scope(user, source=None):
    qs = HistoryRecord.objects.select_related('user').prefetch_related('shared_users')
    if not user:
        return qs.none()
    if source == 'shared':
        return qs.filter(shared_users=user, user__is_admin=True).exclude(user=user)
    return qs if user.is_admin else qs.filter(user=user)


def task_records(task_id):
    return HistoryRecord.objects.select_related('user').filter(images__task_id=task_id)


def valid_task_binding(owner_id, task_id):
    if task_id is None:
        return True
    return bool(
        isinstance(task_id, str) and re.fullmatch(r'[A-Za-z0-9_-]+', task_id)
        and not task_records(task_id).exclude(user_id=owner_id).exists()
    )


def task_directory(owner_id, task_id, root=None):
    if (not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', task_id)
            or not re.fullmatch(r'[A-Za-z0-9_-]+', owner_id)):
        return None
    root = Path(root if root is not None else settings.HISTORY_ROOT).resolve()
    path = root / owner_id / task_id
    return path if path.resolve() == path else None


def source_file(record, filename):
    """Resolve only a listed source in this exact task, without following aliases."""
    images = record.images or {}
    task = images.get('task_id')
    generated = images.get('generated', [])
    if (not isinstance(generated, list) or not isinstance(filename, str) or filename not in generated
            or not re.fullmatch(r'[A-Za-z0-9_.-]+\.(?:png|jpg|jpeg|webp)', filename)
    ):
        return None
    directory = task_directory(record.user_id, task)
    if directory is None:
        return None
    path = directory / filename
    if path.resolve() != path or not path.is_file():
        return None
    return path


def private_response(response):
    response['Cache-Control'] = 'private, no-store'
    response['X-Content-Type-Options'] = 'nosniff'
    patch_vary_headers(response, ['Authorization', 'Cookie'])
    return response


def private_view(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        return private_response(view(*args, **kwargs))
    return wrapper
