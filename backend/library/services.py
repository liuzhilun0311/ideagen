"""Revisioned views over file-backed resources.

Library mutations acquire a database writer gate before reading files or orders.
Files are replaced atomically; exceptions (including commit errors) restore the
previous bytes. A filesystem and SQL transaction cannot guarantee atomicity on
process termination, and legacy file editors do not participate in this gate.
"""
import copy
import json
import os
import tempfile
from pathlib import Path

import yaml
from django.conf import settings
from django.db import transaction
from django.db.models import F

from accounts.models import User
from library.locking import serialized
from library.models import CopyRequest, LibraryMutex, LibraryOrder


KINDS = {'models': ('text', 'image'), 'prompts': ('outline', 'content', 'image')}


class LibraryError(Exception):
    def __init__(self, detail, status=400):
        super().__init__(detail)
        self.status = status


def validate_scope(resource, kind):
    if resource not in KINDS or kind not in KINDS[resource]:
        raise LibraryError('Unknown resource or category.', 404)


def prompt_id(item):
    return json.dumps(
        ['base' if item.get('is_base') else (item.get('owner_id') or ''), item['name']],
        ensure_ascii=False, separators=(',', ':'),
    )


def effective_order(saved, visible):
    visible = list(dict.fromkeys(visible))
    available = set(visible)
    result = list(dict.fromkeys(item for item in saved if item in available))
    included = set(result)
    return result + [item for item in visible if item not in included]


def ordered_ids(user_id, resource, kind, visible):
    """Pure ordering integration: callers supply visibility, never recurse."""
    row = LibraryOrder.objects.filter(user_id=user_id, resource=resource, kind=kind).first()
    return effective_order(row.order if row else [], visible)


def order_providers(user_id, kind, providers):
    return {key: providers[key] for key in ordered_ids(user_id, 'models', kind, providers)}


def order_prompts(user_id, kind, items):
    by_id = {prompt_id(item): item for item in items}
    return [by_id[key] for key in ordered_ids(user_id, 'prompts', kind, by_id)]


def _model_path(user, kind):
    if user.is_admin or user.use_shared_config:
        return Path(settings.PROJECT_ROOT) / f'{kind}_providers.yaml'
    private = settings.USER_CONFIGS_ROOT / str(user.id) / f'{kind}_providers.yaml'
    # Match config visibility fallback, but never treat fallback keys as owned.
    return private if private.exists() else Path(settings.PROJECT_ROOT) / f'{kind}_providers.yaml'


def _read_models(path):
    if not path.exists():
        return {'providers': {}}
    with path.open(encoding='utf-8') as handle:
        data = yaml.safe_load(handle) or {}
    if not isinstance(data, dict) or not isinstance(data.get('providers', {}), dict):
        raise LibraryError('Invalid provider configuration.', 500)
    return data


def _visible(user, resource, kind):
    if resource == 'prompts':
        from prompts.services import _list_all_prompts_unordered
        return {prompt_id(item): item for item in _list_all_prompts_unordered(user.id)[kind]}
    providers = _read_models(_model_path(user, kind)).get('providers', {})
    if not user.is_admin and user.use_shared_config:
        providers = {
            key: value for key, value in providers.items()
            if user.username in (value.get('allowed_users') or [])
        }
    return providers


def _response(row, visible):
    return {
        'success': True, 'revision': row.revision if row else 0,
        'order': effective_order(row.order if row else [], visible),
    }


def _writer_gate():
    # UPDATE is deliberately the first SQL statement: SQLite must acquire its
    # writer lock before any read snapshot (select_for_update alone is a no-op).
    if not LibraryMutex.objects.filter(pk=1).update(version=F('version') + 1):
        LibraryMutex.objects.create(pk=1)


@serialized
def get_order(user_id, resource, kind):
    validate_scope(resource, kind)
    with transaction.atomic():
        _writer_gate()
        user = User.objects.get(pk=user_id)
        visible = _visible(user, resource, kind)
        row = LibraryOrder.objects.filter(user=user, resource=resource, kind=kind).first()
        return _response(row, visible)


def _revision(value):
    if type(value) is not int or value < 0:
        raise LibraryError('revision must be a non-negative integer.')


def _check_revision(row, revision):
    if row.revision != revision:
        raise LibraryError('The list has changed. Refresh before retrying.', 409)


@serialized
def reorder(user_id, resource, kind, revision, order):
    validate_scope(resource, kind)
    _revision(revision)
    if not isinstance(order, list) or any(not isinstance(item, str) for item in order):
        raise LibraryError('order must be an array of IDs.')
    if len(order) != len(set(order)):
        raise LibraryError('Duplicate IDs are not allowed.')
    with transaction.atomic():
        _writer_gate()
        user = User.objects.get(pk=user_id)
        visible = _visible(user, resource, kind)
        row, _ = LibraryOrder.objects.get_or_create(user=user, resource=resource, kind=kind)
        _check_revision(row, revision)
        if set(order) != set(visible):
            raise LibraryError('order must contain exactly the currently visible IDs.')
        row.order = order
        row.revision += 1
        row.save(update_fields=['order', 'revision'])
        return _response(row, visible)


def _copy_name(source, occupied, limit=50):
    number = 1
    while True:
        suffix = '\uff08\u526f\u672c\uff09' if number == 1 else f'\uff08\u526f\u672c{number}\uff09'
        name = source[:limit - len(suffix)] + suffix
        if name not in occupied:
            return name
        number += 1


def _atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f'.{path.name}.', suffix='.tmp', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def _prepare_copy(user, resource, kind, source, visible):
    if resource == 'models':
        private = settings.USER_CONFIGS_ROOT / str(user.id) / f'{kind}_providers.yaml'
        if not user.is_admin and (user.use_shared_config or not private.exists()):
            raise LibraryError('Only configurations you manage can be copied.', 403)
    if source not in visible:
        raise LibraryError('Source is no longer available.', 404)
    if resource == 'models':
        path = _model_path(user, kind)
        config = _read_models(path)
        providers = config.setdefault('providers', {})
        name = _copy_name(source, providers)
        value = copy.deepcopy(providers[source])
        occupied_labels = {provider.get('provider_label') or key for key, provider in providers.items()}
        occupied_displays = {provider.get('display_name') or key for key, provider in providers.items()}
        source_label = value.get('provider_label') or source
        while True:
            label = _copy_name(source_label, occupied_labels)
            display_name = f"{label}:{value.get('model') or ''}"
            if display_name not in occupied_displays:
                break
            occupied_labels.add(label)
        value['provider_label'] = label
        value['display_name'] = display_name
        if kind == 'image':
            # Legacy image configurations infer their adapter from the map key.
            value.setdefault('type', source)
        value['enabled'] = False
        value['allowed_users'] = []
        providers[name] = value
        content = yaml.safe_dump(config, allow_unicode=True, sort_keys=False).encode('utf-8')
        return path, content, {'id': name, 'name': name}
    from prompts.services import _prompts_file, _NAME_MAX_LEN
    path = _prompts_file(user.id, kind)
    # Unlike the legacy permissive reader, refuse to overwrite malformed data.
    items = json.loads(path.read_text(encoding='utf-8')) if path.exists() else []
    if not isinstance(items, list) or any(not isinstance(item, dict) or 'name' not in item for item in items):
        raise LibraryError('Invalid prompt file.', 500)
    name = _copy_name(visible[source]['name'], {item['name'] for item in items}, _NAME_MAX_LEN)
    items.append({'name': name, 'content': visible[source]['content'], 'allowed_users': []})
    content = json.dumps(items, ensure_ascii=False, indent=2).encode('utf-8')
    return path, content, {'id': prompt_id({'owner_id': str(user.id), 'name': name}), 'name': name}


@serialized
def copy_resource(user_id, resource, kind, source, revision, request_id):
    validate_scope(resource, kind)
    _revision(revision)
    if not isinstance(source, str) or not source:
        raise LibraryError('source must be a non-empty ID.')
    if not isinstance(request_id, str) or not request_id.strip() or len(request_id) > 128:
        raise LibraryError('request_id must contain 1 to 128 characters.')
    written = False
    path = None
    original = None
    try:
        with transaction.atomic():
            _writer_gate()
            user = User.objects.get(pk=user_id)
            previous = CopyRequest.objects.filter(user=user, request_id=request_id).first()
            if previous:
                if (previous.resource, previous.kind, previous.source, previous.revision) != (
                    resource, kind, source, revision,
                ):
                    raise LibraryError('request_id has already been used for a different request.', 409)
                visible = _visible(user, resource, kind)
                if resource == 'models':
                    private = settings.USER_CONFIGS_ROOT / str(user.id) / f'{kind}_providers.yaml'
                    if not user.is_admin and (user.use_shared_config or not private.exists()):
                        raise LibraryError('Only configurations you manage can be copied.', 403)
                if source not in visible or previous.response['created']['id'] not in visible:
                    raise LibraryError('Source or copy is no longer available.', 404)
                row = LibraryOrder.objects.filter(user=user, resource=resource, kind=kind).first()
                return {**_response(row, visible), 'created': previous.response['created']}
            visible = _visible(user, resource, kind)
            row, _ = LibraryOrder.objects.get_or_create(user=user, resource=resource, kind=kind)
            _check_revision(row, revision)
            path, content, created = _prepare_copy(user, resource, kind, source, visible)
            order = effective_order(row.order, visible)
            order.insert(order.index(source) + 1, created['id'])
            row.order = order
            row.revision += 1
            row.save(update_fields=['order', 'revision'])
            response = {
                'success': True, 'revision': row.revision,
                'order': order, 'created': created,
            }
            original = path.read_bytes() if path.exists() else None
            _atomic_write(path, content)
            written = True
            CopyRequest.objects.create(
                user=user, request_id=request_id, resource=resource, kind=kind,
                source=source, revision=revision, response=response,
            )
        return response
    except Exception:
        if written:
            if original is None:
                path.unlink(missing_ok=True)
            else:
                _atomic_write(path, original)
        raise
    finally:
        if resource == 'models':
            from providers.config import reload_config
            reload_config()
