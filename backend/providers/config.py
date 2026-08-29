"""服务商配置加载（移植自 Flask 版 backend/config.py，支持按用户覆盖）。"""
from __future__ import annotations

import logging
from pathlib import Path
from typing import Dict, Optional

import yaml
from django.conf import settings

logger = logging.getLogger(__name__)

_cached_image: Dict = {}
_cached_text: Dict = {}


def _base_paths() -> tuple:
    root = Path(settings.PROJECT_ROOT)
    return root / 'image_providers.yaml', root / 'text_providers.yaml'


def _user_config_path(kind: str, user_id: Optional[str]) -> Optional[Path]:
    if not user_id:
        return None
    path = settings.USER_CONFIGS_ROOT / user_id / f"{kind}_providers.yaml"
    return path if path.exists() else None


def _read_yaml(path: Path, default: dict) -> dict:
    try:
        with open(path, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f) or {}
            return data if isinstance(data, dict) else default
    except Exception as e:
        logger.error("读取配置文件失败 %s: %s", path, e)
        return default


def _resolve_config(kind: str, user_id: Optional[str], cache: dict) -> dict:
    """读取指定 kind（image/text）的配置：优先用户私有配置，其次共享配置。"""
    cache_key = user_id or '__shared__'
    if cache.get(cache_key) is not None:
        return cache[cache_key]

    image_path, text_path = _base_paths()
    path = image_path if kind == 'image' else text_path
    default = {
        'active_provider': 'google_genai' if kind == 'image' else 'google_gemini',
        'providers': {},
    }
    config = _read_yaml(path, default)

    # 用户私有配置覆盖（非共享模式；管理员统一使用共享配置）
    if user_id:
        try:
            from accounts.models import User
            user = User.objects.filter(id=user_id).first()
            use_shared = user.use_shared_config if user else True
            if user and user.is_admin:
                # 管理员始终使用/管理共享配置
                use_shared = True
            if not use_shared:
                override = _user_config_path(kind, user_id)
                if override:
                    user_cfg = _read_yaml(override, default)
                    if isinstance(user_cfg, dict) and user_cfg:
                        config = user_cfg
        except Exception:
            pass
    cache[cache_key] = config
    return config


def load_image_providers_config(user_id: Optional[str] = None) -> dict:
    return _resolve_config('image', user_id, _cached_image)


def load_text_providers_config(user_id: Optional[str] = None) -> dict:
    return _resolve_config('text', user_id, _cached_text)


def get_active_image_provider(user_id: Optional[str] = None) -> str:
    config = load_image_providers_config(user_id)
    active = config.get('active_provider', 'google_genai')
    if is_provider_allowed('image', active, user_id):
        return active
    # 当前激活的服务商对用户不可用，回退到第一个可用服务商
    for name in config.get('providers', {}):
        if is_provider_allowed('image', name, user_id):
            return name
    return active


def get_active_text_provider(user_id: Optional[str] = None) -> str:
    config = load_text_providers_config(user_id)
    active = config.get('active_provider', 'google_gemini')
    if is_provider_allowed('text', active, user_id):
        return active
    for name in config.get('providers', {}):
        if is_provider_allowed('text', name, user_id):
            return name
    return active


def get_image_provider_config(provider_name: Optional[str] = None, user_id: Optional[str] = None) -> dict:
    config = load_image_providers_config(user_id)
    if provider_name is None:
        provider_name = config.get('active_provider', 'google_genai')
        if not is_provider_allowed('image', provider_name, user_id):
            for name in config.get('providers', {}):
                if is_provider_allowed('image', name, user_id):
                    provider_name = name
                    break
    providers = config.get('providers', {})
    if not providers:
        raise ValueError(
            "未找到任何图片生成服务商配置。\n"
            "解决方案：\n"
            "1. 在系统设置页面添加图片生成服务商\n"
            "2. 或手动编辑 image_providers.yaml 文件\n"
            "3. 确保文件中有 providers 字段"
        )
    if provider_name not in providers:
        available = ', '.join(providers.keys()) if providers else '无'
        raise ValueError(
            f"未找到图片生成服务商配置: {provider_name}\n"
            f"可用的服务商: {available}\n"
            "解决方案：\n"
            "1. 在系统设置页面添加该服务商\n"
            "2. 或修改 active_provider 为已存在的服务商\n"
            "3. 检查 image_providers.yaml 文件"
        )
    provider_config = providers[provider_name].copy()
    if not is_provider_allowed('image', provider_name, user_id):
        raise ValueError(
            f"服务商 {provider_name} 未授权给当前用户使用\n"
            "解决方案：请联系管理员将该服务商加入你的可用名单。"
        )
    if not provider_config.get('api_key'):
        raise ValueError(
            f"服务商 {provider_name} 未配置 API Key\n"
            "解决方案：\n"
            "1. 在系统设置页面编辑该服务商，填写 API Key\n"
            "2. 或手动在 image_providers.yaml 中添加 api_key 字段"
        )
    provider_type = provider_config.get('type', provider_name)
    if provider_type in ['openai', 'openai_compatible', 'image_api']:
        if not provider_config.get('base_url'):
            raise ValueError(
                f"服务商 {provider_name} 未配置 Base URL\n"
                f"服务商类型 {provider_type} 需要配置 base_url\n"
                "解决方案：在系统设置页面编辑该服务商，填写 Base URL"
            )
    return provider_config


def get_text_provider_config(provider_name: Optional[str] = None, user_id: Optional[str] = None) -> dict:
    config = load_text_providers_config(user_id)
    if provider_name is None:
        provider_name = config.get('active_provider', 'google_gemini')
        if not is_provider_allowed('text', provider_name, user_id):
            for name in config.get('providers', {}):
                if is_provider_allowed('text', name, user_id):
                    provider_name = name
                    break
    providers = config.get('providers', {})
    if not providers:
        raise ValueError(
            "未找到任何文本生成服务商配置。\n"
            "解决方案：\n"
            "1. 在系统设置页面添加文本生成服务商\n"
            "2. 或手动编辑 text_providers.yaml 文件"
        )
    if provider_name not in providers:
        available = ', '.join(providers.keys()) if providers else '无'
        raise ValueError(
            f"未找到文本生成服务商配置: {provider_name}\n"
            f"可用的服务商: {available}\n"
            "解决方案：在系统设置页面添加该服务商，或修改 active_provider。"
        )
    provider_config = providers[provider_name].copy()
    if not is_provider_allowed('text', provider_name, user_id):
        raise ValueError(
            f"服务商 {provider_name} 未授权给当前用户使用\n"
            "解决方案：请联系管理员将该服务商加入你的可用名单。"
        )
    if not provider_config.get('api_key'):
        raise ValueError(
            f"服务商 {provider_name} 未配置 API Key\n"
            "解决方案：在系统设置页面编辑该服务商，填写 API Key"
        )
    provider_type = provider_config.get('type', provider_name)
    if provider_type in ['openai', 'openai_compatible']:
        if not provider_config.get('base_url'):
            raise ValueError(
                f"服务商 {provider_name} 未配置 Base URL\n"
                "解决方案：在系统设置页面编辑该服务商，填写 Base URL"
            )
    return provider_config


def reload_config() -> None:
    _cached_image.clear()
    _cached_text.clear()


def save_provider_config(kind: str, data: dict, user_id: Optional[str] = None) -> None:
    """保存服务商配置（kind: image/text）。写共享文件；user_id 存在时写用户私有目录。"""
    root = Path(settings.PROJECT_ROOT)
    filename = f"{kind}_providers.yaml"
    if user_id:
        # 管理员统一管理共享配置；普通用户写私有配置
        try:
            from accounts.models import User
            user = User.objects.filter(id=user_id).first()
            if user and user.is_admin:
                user_id = None
        except Exception:
            pass
    if user_id:
        # 写用户私有配置（并标记该用户为"使用私有配置"）
        target_dir = settings.USER_CONFIGS_ROOT / user_id
        target_dir.mkdir(parents=True, exist_ok=True)
        path = target_dir / filename
        try:
            from accounts.models import User
            User.objects.filter(id=user_id).update(use_shared_config=False)
        except Exception:
            pass
    else:
        path = root / filename
    _write_yaml(path, data)
    reload_config()


def _write_yaml(path: Path, data: dict) -> None:
    with open(path, 'w', encoding='utf-8') as f:
        yaml.dump(data, f, allow_unicode=True, default_flow_style=False)


# ==================== 服务商使用名单（allowed_users） ====================

def load_shared_providers_config(kind: str) -> dict:
    """读取共享服务商配置（不做用户私有覆盖），用于管理员管理与权限判断。"""
    default = {
        'active_provider': 'google_genai' if kind == 'image' else 'google_gemini',
        'providers': {},
    }
    image_path, text_path = _base_paths()
    path = image_path if kind == 'image' else text_path
    return _read_yaml(path, default)


def is_provider_allowed(kind: str, provider_name: str, user_id: Optional[str]) -> bool:
    """判断用户是否可以使用某服务商。

    - 未登录 / 管理员 / 使用私有配置的用户：始终允许（私有配置为用户自己创建）
    - 使用共享配置的用户：只有被管理员勾选（在 allowed_users 名单中）的用户才可见可用
    """
    if not user_id:
        return True
    from accounts.models import User
    user = User.objects.filter(id=str(user_id)).first()
    if not user:
        return False
    if user.is_admin or not user.use_shared_config:
        return True
    provider = load_shared_providers_config(kind).get('providers', {}).get(provider_name)
    if provider is None:
        return False
    allowed = provider.get('allowed_users') or []
    return user.username in allowed


def set_provider_allowed_users(kind: str, provider_name: str, usernames: list) -> None:
    """设置某共享服务商可使用的用户名单（空名单 = 仅管理员可见，不共享给任何用户）。"""
    if kind not in ('text', 'image'):
        raise ValueError(f"未知的服务商类型: {kind}")
    provider_name = (provider_name or '').strip()
    if not provider_name:
        raise ValueError('请指定要配置的服务商')

    usernames = [str(u).strip() for u in (usernames or []) if str(u).strip()]
    if usernames:
        from accounts.models import User
        valid = set(
            User.objects.filter(username__in=usernames).values_list('username', flat=True)
        )
        for uname in usernames:
            if uname not in valid:
                raise ValueError(f"用户不存在：{uname}")

    config = load_shared_providers_config(kind)
    providers = config.get('providers', {})
    if provider_name not in providers:
        raise ValueError(f"服务商不存在：{provider_name}")
    providers[provider_name]['allowed_users'] = usernames
    filename = f"{kind}_providers.yaml"
    path = Path(settings.PROJECT_ROOT) / filename
    _write_yaml(path, config)
    reload_config()


def save_single_provider(kind: str, provider_name: str, new_data: dict, user_id: Optional[str] = None) -> None:
    """保存单个服务商配置（只更新这一个服务商，不影响其他）。

    - API Key 为空时保留原有；allowed_users / remark 等字段按传入内容保存
    - 管理员写共享配置；普通用户写私有配置
    """
    if kind not in ('text', 'image'):
        raise ValueError(f"未知的服务商类型: {kind}")
    provider_name = (provider_name or '').strip()
    if not provider_name:
        raise ValueError('请指定服务商名称')

    config = load_image_providers_config(user_id) if kind == 'image' else load_text_providers_config(user_id)
    config = dict(config or {})
    providers = dict(config.get('providers', {}) or {})
    existing = providers.get(provider_name) or {}

    new_data = dict(new_data or {})
    new_data.pop('api_key_env', None)
    new_data.pop('api_key_masked', None)
    new_data.pop('_has_api_key', None)
    # API Key 为空 -> 保留原有
    if new_data.get('api_key') in [True, False, '', None]:
        if existing.get('api_key'):
            new_data['api_key'] = existing['api_key']
        else:
            new_data.pop('api_key', None)
    # 未提供 allowed_users 时保留原有名单
    if 'allowed_users' not in new_data and 'allowed_users' in existing:
        new_data['allowed_users'] = existing['allowed_users']

    providers[provider_name] = new_data
    config['providers'] = providers
    save_provider_config(kind, config, user_id)
