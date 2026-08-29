"""提示词库服务：每个用户按名称保存自己的提示词（JSON 文件），并提供系统默认提示词回退。

存储位置：user_configs/<user_id>/prompts/<type>.json
格式：    [{"name": "提示词名称", "content": "提示词内容", "allowed_users": ["用户名", ...]}, ...]

- allowed_users：该提示词对哪些"其他用户"可见（拥有者始终可见，无需列入）。
  管理员可在提示词管理页为任意提示词配置 allowed_users。
- 用户列表提示词 = 系统默认 + 自己创建的 + 别人共享给我（我在其 allowed_users 中）的。

提示词类型（kind）与系统默认文件的对应关系：
- outline -> generation/prompts/outline_prompt.txt
- content -> generation/prompts/content_prompt.txt
- image   -> generation/prompts/image_prompt.txt
"""
import json
import logging
import re
from pathlib import Path

from django.conf import settings

from accounts.models import User

logger = logging.getLogger(__name__)

# 提示词类型 -> 系统默认提示词文件名
KINDS = {
    'outline': 'outline_prompt.txt',
    'content': 'content_prompt.txt',
    'image': 'image_prompt.txt',
}

# 系统默认提示词的显示名（保留字，用户不能创建同名提示词）
BASE_NAME = '默认提示词'

# 各类型提示词可用的占位符（用于编辑界面提示）
KIND_PLACEHOLDERS = {
    'outline': ['topic'],
    'content': ['topic', 'outline'],
    'image': ['page_content', 'page_type', 'full_outline', 'user_topic'],
}

_NAME_MAX_LEN = 50
_CONTENT_MAX_LEN = 20000


def _prompts_file(user_id, kind: str) -> Path:
    return settings.USER_CONFIGS_ROOT / str(user_id) / 'prompts' / f'{kind}.json'


def _read_user_prompts(user_id, kind: str) -> list:
    """读取用户指定类型的提示词列表，文件不存在或损坏时返回空列表。"""
    path = _prompts_file(user_id, kind)
    if not path.exists():
        return []
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        if isinstance(data, list):
            return [
                item for item in data
                if isinstance(item, dict) and item.get('name') and item.get('content')
            ]
    except Exception as e:
        logger.error("读取提示词失败 %s: %s", path, e)
    return []


def _write_user_prompts(user_id, kind: str, prompts: list) -> None:
    """原子写入提示词列表（先写临时文件再替换）。"""
    path = _prompts_file(user_id, kind)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix('.json.tmp')
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(prompts, f, ensure_ascii=False, indent=2)
    tmp.replace(path)


def _username_of(user_id):
    """根据用户 id 查用户名，找不到返回 None。"""
    user = User.objects.filter(id=str(user_id)).first()
    return user.username if user else None


def _all_prompt_owners() -> list:
    """列出所有在 USER_CONFIGS_ROOT 下拥有提示词目录的用户 id。"""
    root = settings.USER_CONFIGS_ROOT
    if not root.exists():
        return []
    return [p.name for p in root.iterdir() if (p / 'prompts').is_dir()]


def _iter_shared_prompt_items(user_id, kind: str, username: str) -> list:
    """收集其他用户拥有的、允许 username 使用的提示词（含拥有者信息）。"""
    results = []
    for owner_id in _all_prompt_owners():
        if owner_id == str(user_id):
            continue
        owner = User.objects.filter(id=owner_id).first()
        if not owner:
            continue
        for item in _read_user_prompts(owner_id, kind):
            allowed = item.get('allowed_users') or []
            if username in allowed:
                results.append({
                    'name': item['name'],
                    'content': item['content'],
                    'owner': owner.username,
                    'owner_id': owner_id,
                })
    return results


def get_base_prompt(kind: str) -> str:
    """读取系统默认提示词内容（generation/prompts 下的内置文件）。"""
    filename = KINDS.get(kind)
    if not filename:
        raise ValueError(f"未知的提示词类型: {kind}")
    path = Path(__file__).resolve().parent.parent / 'generation' / 'prompts' / filename
    try:
        with open(path, 'r', encoding='utf-8') as f:
            return f.read()
    except Exception as e:
        logger.error("读取系统默认提示词失败 %s: %s", path, e)
        return ''


def list_all_prompts(user_id) -> dict:
    """返回全部类型提示词（默认在前）。

    - 普通用户：系统默认 + 自己创建的 + 别人共享给我的（系统默认不可编辑）
    - 管理员：系统默认（可编辑）+ 所有用户的所有提示词（可逐个配置使用名单）

    每项含 can_edit（是否可编辑/删除，仅拥有者或管理员编辑系统默认可为 True）、owner/is_shared/allowed_users 信息。
    """
    username = _username_of(user_id)
    is_admin_user = bool(
        User.objects.filter(id=str(user_id), is_admin=True).exists()
    )
    result = {}
    for kind in KINDS:
        own_items = _read_user_prompts(user_id, kind)
        own_names = {it['name'] for it in own_items}
        items = [{
            'name': BASE_NAME,
            'content': get_base_prompt(kind),
            'type': kind,
            'is_base': True,
            # 系统默认提示词：仅管理员可编辑
            'can_edit': is_admin_user,
            'owner': None,
            'owner_id': None,
            'is_shared': False,
            'allowed_users': [],
        }]
        for item in own_items:
            items.append({
                'name': item['name'],
                'content': item['content'],
                'type': kind,
                'is_base': False,
                'can_edit': True,
                'owner': username,
                'owner_id': str(user_id),
                'is_shared': False,
                'allowed_users': item.get('allowed_users') or [],
            })
        if is_admin_user:
            # 管理员：看到所有用户的所有提示词，可在任意提示词旁配置使用名单
            for owner_id in _all_prompt_owners():
                if owner_id == str(user_id):
                    continue
                owner = User.objects.filter(id=owner_id).first()
                if not owner:
                    continue
                for item in _read_user_prompts(owner_id, kind):
                    if item['name'] in own_names:
                        continue  # 同名以自己创建的为准
                    items.append({
                        'name': item['name'],
                        'content': item['content'],
                        'type': kind,
                        'is_base': False,
                        'can_edit': False,
                        'owner': owner.username,
                        'owner_id': owner_id,
                        'is_shared': True,
                        'allowed_users': item.get('allowed_users') or [],
                    })
        elif username:
            # 普通用户：只看到共享给我的
            for shared in _iter_shared_prompt_items(user_id, kind, username):
                # 同名时以自己创建的为准，避免重复与歧义
                if shared['name'] in own_names:
                    continue
                items.append({
                    'name': shared['name'],
                    'content': shared['content'],
                    'type': kind,
                    'is_base': False,
                    'can_edit': False,
                    'owner': shared['owner'],
                    'owner_id': shared['owner_id'],
                    'is_shared': True,
                    'allowed_users': [],
                })
        result[kind] = items
    return result


def resolve_prompt_text(user_id, kind: str, name: str) -> str:
    """按名称解析提示词内容。

    - 未指定名称 / 名称为"默认提示词" -> 系统默认
    - 自己的提示词优先；其次是我可见（被共享）的提示词
    - 指定了但找不到（如已被删除） -> 回退系统默认
    """
    if not name or name == BASE_NAME:
        return get_base_prompt(kind)
    for item in _read_user_prompts(user_id, kind):
        if item['name'] == name:
            return item['content']
    username = _username_of(user_id)
    if username:
        for shared in _iter_shared_prompt_items(user_id, kind, username):
            if shared['name'] == name:
                return shared['content']
    logger.warning("提示词 %s/%s 不存在，回退系统默认", kind, name)
    return get_base_prompt(kind)


def save_prompt(user_id, kind: str, name: str, content: str) -> None:
    """新增或覆盖一个用户提示词（按名称 upsert）。"""
    if kind not in KINDS:
        raise ValueError(f"未知的提示词类型: {kind}")
    name = (name or '').strip()
    if not name:
        raise ValueError('提示词名称不能为空')
    if len(name) > _NAME_MAX_LEN:
        raise ValueError(f'提示词名称不能超过 {_NAME_MAX_LEN} 个字符')
    if name == BASE_NAME:
        raise ValueError(f'不能使用系统保留名称："{BASE_NAME}"')

    content = content or ''
    if not content.strip():
        raise ValueError('提示词内容不能为空')
    if len(content) > _CONTENT_MAX_LEN:
        raise ValueError(f'提示词内容不能超过 {_CONTENT_MAX_LEN} 个字符')

    prompts = _read_user_prompts(user_id, kind)
    for item in prompts:
        if item['name'] == name:
            # 覆盖内容时保留已配置的共享名单
            item['content'] = content
            _write_user_prompts(user_id, kind, prompts)
            return
    prompts.append({'name': name, 'content': content, 'allowed_users': []})
    _write_user_prompts(user_id, kind, prompts)


def save_base_prompt(kind: str, content: str) -> None:
    """保存系统默认提示词内容（仅管理员调用）。

    直接写入 generation/prompts 下的内置文件，普通用户读取到的
    默认提示词随即更新（base 内容在列表与解析时实时读取）。
    """
    if kind not in KINDS:
        raise ValueError(f"未知的提示词类型: {kind}")
    content = content or ''
    if not content.strip():
        raise ValueError('提示词内容不能为空')
    if len(content) > _CONTENT_MAX_LEN:
        raise ValueError(f'提示词内容不能超过 {_CONTENT_MAX_LEN} 个字符')

    filename = KINDS[kind]
    path = Path(__file__).resolve().parent.parent / 'generation' / 'prompts' / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)


def delete_prompt(user_id, kind: str, name: str) -> bool:
    """删除一个用户提示词，返回是否删除成功。"""
    prompts = _read_user_prompts(user_id, kind)
    remaining = [item for item in prompts if item['name'] != name]
    if len(remaining) == len(prompts):
        return False
    _write_user_prompts(user_id, kind, remaining)
    return True


# ==================== 管理员：共享名单配置 ====================

def set_prompt_allowed_users(owner_id, kind: str, name: str, usernames: list) -> None:
    """设置某提示词对哪些用户可见。

    - 拥有者（创建者）始终可见，会自动加入名单且不可被移除
    - 传入名单 = 允许使用的其他用户（拥有者除外时也会自动补上）
    """
    if kind not in KINDS:
        raise ValueError(f"未知的提示词类型: {kind}")
    name = (name or '').strip()
    if not name or name == BASE_NAME:
        raise ValueError('请指定要配置的提示词')

    usernames = [str(u).strip() for u in (usernames or []) if str(u).strip()]
    # 拥有者默认打勾、始终在名单中
    owner = User.objects.filter(id=str(owner_id)).first()
    if owner and owner.username not in usernames:
        usernames.insert(0, owner.username)

    if usernames:
        valid = set(
            User.objects.filter(username__in=usernames).values_list('username', flat=True)
        )
        for uname in usernames:
            if uname not in valid:
                raise ValueError(f"用户不存在：{uname}")

    prompts = _read_user_prompts(owner_id, kind)
    for item in prompts:
        if item['name'] == name:
            item['allowed_users'] = usernames
            _write_user_prompts(owner_id, kind, prompts)
            return
    raise ValueError(f"提示词不存在：{name}")


def admin_delete_prompt(owner_id, kind: str, name: str) -> bool:
    """管理员删除任意用户的提示词，返回是否删除成功。"""
    prompts = _read_user_prompts(owner_id, kind)
    remaining = [item for item in prompts if item['name'] != name]
    if len(remaining) == len(prompts):
        return False
    _write_user_prompts(owner_id, kind, remaining)
    return True


def safe_format(template: str, mapping: dict) -> str:
    """格式化提示词模板。

    自定义提示词可能没有包含全部占位符，直接用 str.format() 会因缺少字段报错。
    这里把缺失的 {字段} 原样保留，不报错。
    """
    def repl(match):
        key = match.group(1)
        return str(mapping[key]) if key in mapping else match.group(0)
    return re.sub(r'\{(\w+)\}', repl, template)
