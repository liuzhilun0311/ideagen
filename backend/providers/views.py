"""配置管理 / DeAI API 视图（移植自 Flask 版 config_routes.py + file_routes.py）。

包含功能：
- 获取/更新服务商配置（支持每用户私有配置）
- 测试服务商连接
- DeAI 去指纹工具执行（脚本路径相对项目目录自动解析、Python 解释器自动搜索）
- DeAI 处理后图片服务
"""

import glob
import logging
import os
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import NamedTuple

from django.conf import settings
from django.http import FileResponse, JsonResponse

from common.api import (
    admin_required,
    api_error_response,
    json_body,
    prepare_providers_for_response,
    require_auth,
    validation_error,
)
from history.services import get_history_service
from providers.config import (
    load_image_providers_config,
    load_shared_providers_config,
    load_text_providers_config,
    reload_config,
    save_provider_config,
    save_single_provider,
    set_provider_allowed_users,
)

logger = logging.getLogger(__name__)


class LlmSmokeResult(NamedTuple):
    text: str
    source: str
    finish_reason: str


# ==================== 通用辅助 ====================

def _is_pid_alive(pid: int) -> bool:
    """检查进程是否存活（跨平台）

    Windows 上 os.kill(pid, 0) 对无效 PID 会抛 OSError[WinError 87] 甚至被包装成
    SystemError，导致调用方 500；改用 OpenProcess 探测，稳定且不抛异常。
    """
    if pid <= 0:
        return False
    if os.name == 'nt':
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            # PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
            handle = kernel32.OpenProcess(0x1000, False, int(pid))
            if not handle:
                return False
            kernel32.CloseHandle(handle)
            return True
        except Exception:
            return False
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False


def _find_task_owner(task_id: str):
    """通过历史索引查找任务归属的用户 ID（用于目录按用户隔离）"""
    try:
        return get_history_service().find_owner_by_task(task_id)
    except Exception:
        return None


def _resolve_deai_script() -> str:
    """DeAI 脚本路径：固定使用项目内相对位置 deai-image/scripts/deai.py"""
    p = settings.PROJECT_ROOT / 'deai-image' / 'scripts' / 'deai.py'
    return str(p) if p.is_file() else ''


def _resolve_python() -> str:
    """自动搜索可用的 Python 解释器。

    优先使用当前运行 Django 的 Python（必然可用），再依次查找 PATH 与
    Windows 常见安装路径（C:\\Python*、%LOCALAPPDATA%\\Programs\\Python）。
    均未找到时回退为 'python'（依赖 PATH）。
    """
    candidates = []
    if getattr(sys, 'executable', None):
        candidates.append(sys.executable)
    for name in ('python', 'python3'):
        found = shutil.which(name)
        if found:
            candidates.append(found)
    if os.name == 'nt':
        local = os.environ.get('LOCALAPPDATA', '')
        roots = [
            r'C:\Python311', r'C:\Python312', r'C:\Python313',
            r'C:\Python310', r'C:\Python39',
        ]
        if local:
            roots.append(os.path.join(local, 'Programs', 'Python'))
        for root in roots:
            for p in glob.glob(os.path.join(root, 'python.exe')):
                candidates.append(p)
            for p in glob.glob(os.path.join(root, 'Python*', 'python.exe')):
                candidates.append(p)
    seen = set()
    for c in candidates:
        c = str(c)
        if c in seen:
            continue
        seen.add(c)
        if os.path.isfile(c) or shutil.which(c):
            return c
    return 'python'


def _clear_config_cache():
    """清除配置缓存"""
    try:
        reload_config()
    except Exception:
        pass
    try:
        from generation.services.image import reset_image_service
        reset_image_service()
    except Exception:
        pass


def _filter_providers_for_user(config: dict, user: dict) -> dict:
    """普通用户视角（使用共享配置时）：仅保留管理员勾选（在名单中）的服务商，并隐藏名单字段。"""
    providers = config.get('providers', {}) or {}
    filtered = {}
    username = user.get('username')
    for name, p in providers.items():
        p = dict(p)
        allowed = p.pop('allowed_users', None) or []
        if username in allowed:
            filtered[name] = p
    result = dict(config)
    result['providers'] = filtered
    active = config.get('active_provider')
    if active not in filtered:
        result['active_provider'] = next(iter(filtered), active or '')
    return result


# ==================== 配置读写 ====================

@require_auth
def get_config(request):
    """获取当前配置（支持每用户私有配置，providers 脱敏）。

    - 管理员：看到共享配置中的全部服务商（含使用名单，用于展示与配置）
    - 普通用户：自己的私有配置，或共享配置中允许其使用的服务商
    """
    try:
        user_id = request.user_id
        user = request.user_obj

        # Other workers may have copied a file-backed provider.
        reload_config()

        if user.get('is_admin'):
            # 管理员：共享配置全量（保留 allowed_users 供展示/配置）
            image_config = load_shared_providers_config('image')
            text_config = load_shared_providers_config('text')
            # 规范化：每个服务商都带 allowed_users 字段（未配置默认为空 = 对所有用户开放）
            for _cfg in (image_config, text_config):
                for _p in _cfg.get('providers', {}).values():
                    _p.setdefault('allowed_users', [])
        else:
            # 普通用户
            image_config = load_image_providers_config(user_id)
            text_config = load_text_providers_config(user_id)
            if user.get('use_shared_config'):
                # 使用共享配置：只显示管理员勾选（在名单中）的服务商
                image_config = _filter_providers_for_user(image_config, user)
                text_config = _filter_providers_for_user(text_config, user)
            else:
                # 使用私有配置（自己创建的服务商）：全部可见，隐藏名单字段
                for _cfg in (image_config, text_config):
                    for _p in _cfg.get('providers', {}).values():
                        _p.pop('allowed_users', None)

        from library.services import order_providers

        return JsonResponse({
            "success": True,
            "config": {
                "text_generation": {
                    "active_provider": text_config.get('active_provider', ''),
                    "providers": prepare_providers_for_response(
                        order_providers(user_id, 'text', text_config.get('providers', {}))
                    )
                },
                "image_generation": {
                    "active_provider": image_config.get('active_provider', ''),
                    "providers": prepare_providers_for_response(
                        order_providers(user_id, 'image', image_config.get('providers', {}))
                    )
                }
            }
        })

    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/config"})


@require_auth
def update_config(request):
    """更新配置（image_generation / text_generation，可选）"""
    try:
        data = json_body(request)
        user_id = request.user_id

        # 更新图片生成配置
        if 'image_generation' in data:
            _update_provider_config('image', data['image_generation'], user_id)

        # 更新文本生成配置
        if 'text_generation' in data:
            _update_provider_config('text', data['text_generation'], user_id)

        # 清除配置缓存，确保下次使用时读取新配置
        _clear_config_cache()

        return JsonResponse({
            "success": True,
            "message": "配置已保存"
        })

    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/config"})


def _update_provider_config(kind: str, new_data: dict, user_id=None) -> None:
    """
    更新服务商配置

    Args:
        kind: 服务商类型（image/text）
        new_data: 新的配置数据
        user_id: 当前用户 ID（写私有配置时使用）
    """
    # 读取现有配置（含用户私有配置覆盖）
    if kind == 'image':
        existing_config = load_image_providers_config(user_id)
    else:
        existing_config = load_text_providers_config(user_id)
    existing_config = dict(existing_config or {})

    # 更新 active_provider
    if 'active_provider' in new_data:
        existing_config['active_provider'] = new_data['active_provider']

    # 更新 providers
    if 'providers' in new_data:
        existing_providers = existing_config.get('providers', {}) or {}
        new_providers = new_data['providers']

        for name, new_provider_config in new_providers.items():
            # 如果新配置的 api_key 是空的，保留原有的
            if new_provider_config.get('api_key') in [True, False, '', None]:
                if name in existing_providers and existing_providers[name].get('api_key'):
                    new_provider_config['api_key'] = existing_providers[name]['api_key']
                else:
                    new_provider_config.pop('api_key', None)

            # 移除不需要保存的字段
            new_provider_config.pop('api_key_env', None)
            new_provider_config.pop('api_key_masked', None)

        existing_config['providers'] = new_providers

    # 保存配置（写共享文件或用户私有目录，并触发缓存重载）
    save_provider_config(kind, existing_config, user_id)


# ==================== 服务商使用名单（管理员） ====================

@admin_required
def set_provider_users(request):
    """POST /api/config/providers/users — 配置某共享服务商可使用的用户名单。

    请求体：
    - kind: text / image
    - provider_name: 服务商名称
    - usernames: 用户名列表（空列表 = 默认对所有用户开放）
    """
    try:
        data = json_body(request) or {}
        kind = (data.get('kind') or '').strip()
        provider_name = (data.get('provider_name') or '').strip()
        usernames = [str(u).strip() for u in (data.get('usernames') or []) if str(u).strip()]
        # 创建者（当前管理员）默认打勾、始终在名单中
        owner_name = (request.user_obj or {}).get('username')
        if owner_name and owner_name not in usernames:
            usernames.insert(0, owner_name)

        if kind not in ('text', 'image'):
            return api_error_response(
                validation_error("kind 只能是 text 或 image", "请指定服务商类型。"),
                context={"endpoint": "/api/config/providers/users"},
            )
        if not provider_name:
            return api_error_response(
                validation_error("provider_name 不能为空", "请指定要配置的服务商。"),
                context={"endpoint": "/api/config/providers/users"},
            )
        try:
            set_provider_allowed_users(kind, provider_name, usernames)
        except ValueError as ve:
            return api_error_response(
                validation_error(str(ve)),
                context={"endpoint": "/api/config/providers/users"},
            )
        return JsonResponse({"success": True, "message": "已更新使用名单"}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/config/providers/users"})


@require_auth
def save_provider(request):
    """POST /api/config/providers/save — 保存单个服务商配置（只更新这一个，不影响其他）。

    请求体：
    - kind: text / image
    - name: 服务商名称
    - config: 服务商配置对象（api_key 为空时保留原有；remark 备注等字段一并保存）
    """
    try:
        data = json_body(request) or {}
        kind = (data.get('kind') or '').strip()
        name = (data.get('name') or '').strip()
        config = data.get('config') or {}

        if kind not in ('text', 'image'):
            return api_error_response(
                validation_error("kind 只能是 text 或 image", "请指定服务商类型。"),
                context={"endpoint": "/api/config/providers/save"},
            )
        if not name:
            return api_error_response(
                validation_error("name 不能为空", "请指定要保存的服务商。"),
                context={"endpoint": "/api/config/providers/save"},
            )
        try:
            if kind == 'image' and config.get('type') == 'image_api':
                from generation.generators.gpt_images import validate_image_endpoint
                validate_image_endpoint(config.get('endpoint_type') or '')
            save_single_provider(kind, name, config, request.user_id)
        except ValueError as ve:
            return api_error_response(
                validation_error(str(ve)),
                context={"endpoint": "/api/config/providers/save"},
            )
        return JsonResponse({"success": True, "message": "服务商已保存"}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/config/providers/save"})


# ==================== 连接测试 ====================

@require_auth
def test_connection(request):
    """
    测试服务商连接

    请求体：
    - type: 服务商类型（google_genai/google_gemini/openai_compatible/image_api）
    - provider_name: 服务商名称（用于从配置读取 API Key）
    - api_key: API Key（可选，若不提供则从配置读取）
    - base_url: Base URL（可选）
    - model: 模型名称（可选）
    """
    data = {}
    config = {}
    try:
        data = json_body(request) or {}
        provider_type = data.get('type')
        provider_name = data.get('provider_name')

        if not provider_type:
            return api_error_response(
                validation_error("缺少 type 参数", "请选择服务商类型后再测试连接。")
            )
        if provider_type not in ['google_genai', 'google_gemini', 'openai_compatible', 'image_api']:
            return api_error_response(
                validation_error(f"不支持的类型: {provider_type}", "请选择正确的服务商类型后再测试连接。")
            )

        # 构建配置
        config = {
            'api_key': data.get('api_key'),
            'base_url': data.get('base_url'),
            'model': data.get('model'),
            'endpoint_type': data.get('endpoint_type'),
            'api_protocol': data.get('api_protocol'),
        }

        # 如果没有提供 api_key，从配置文件读取
        if not config['api_key'] and provider_name:
            config = _load_provider_config(provider_type, provider_name, config, request.user_id)

        if not config['api_key']:
            return api_error_response(
                validation_error("API Key 未配置", "请先填写并保存该服务商的 API Key。"),
                context=_error_context(provider_type, provider_name, config),
            )

        # 根据类型执行测试
        result = _test_provider_connection(provider_type, config)
        return JsonResponse(result, status=200 if result['success'] else 400)

    except Exception as e:
        return api_error_response(
            e,
            context=_error_context(
                data.get('type') if data else None,
                data.get('provider_name') if data else None,
                config or data,
            ),
        )


def _load_provider_config(provider_type: str, provider_name: str, config: dict, user_id=None) -> dict:
    """
    从配置文件加载服务商配置（文本型读 text、图片型读 image，含用户私有覆盖）

    Args:
        provider_type: 服务商类型
        provider_name: 服务商名称
        config: 当前配置（会被合并）
        user_id: 当前用户 ID

    Returns:
        dict: 合并后的配置
    """
    # 确定配置文件类型
    if provider_type in ['openai_compatible', 'google_gemini']:
        yaml_config = load_text_providers_config(user_id)
    else:
        yaml_config = load_image_providers_config(user_id)

    providers = yaml_config.get('providers', {}) or {}

    if provider_name in providers:
        saved = providers[provider_name]
        config['api_key'] = saved.get('api_key')

        if not config['base_url']:
            config['base_url'] = saved.get('base_url')
        if not config['model']:
            config['model'] = saved.get('model')
        # An edited protocol/endpoint must not inherit a conflicting saved value.
        if not config.get('api_protocol') and not config.get('endpoint_type'):
            config['api_protocol'] = saved.get('api_protocol')
        if not config.get('endpoint_type') and (
            not config.get('api_protocol')
            or config.get('api_protocol') == saved.get('api_protocol')
        ):
            config['endpoint_type'] = saved.get('endpoint_type')

    return config


def _test_provider_connection(provider_type: str, config: dict) -> dict:
    """测试服务商连接"""
    test_prompt = "请只回复：IdeaGen连接测试成功"

    if provider_type == 'google_genai':
        return _test_google_genai(config)

    elif provider_type == 'google_gemini':
        return _test_google_gemini(config, test_prompt)

    elif provider_type == 'openai_compatible':
        return _test_openai_compatible(config, test_prompt)

    elif provider_type == 'image_api':
        return _test_image_api(config)

    else:
        raise ValueError(f"不支持的类型: {provider_type}")


def _error_context(provider_type: str = None, provider_name: str = None, config: dict = None) -> dict:
    config = config or {}
    base_url = config.get('base_url')
    endpoint_type = config.get('endpoint_type')
    return {
        "provider_type": provider_type,
        "provider": provider_name,
        "base_url": base_url,
        "model": config.get('model'),
        "endpoint": endpoint_type,
    }


def _test_google_genai(config: dict) -> dict:
    """测试 Google GenAI 图片生成服务"""
    from google import genai

    if config.get('base_url'):
        client = genai.Client(
            api_key=config['api_key'],
            http_options={
                'base_url': config['base_url'],
                'api_version': 'v1beta'
            },
            vertexai=False
        )
        # 测试列出模型
        try:
            list(client.models.list())
            return {
                "success": True,
                "message": "连接成功！仅代表连接稳定，不确定是否可以稳定支持图片生成"
            }
        except Exception as e:
            raise Exception(f"连接测试失败: {str(e)}")
    else:
        return {
            "success": True,
            "message": "Vertex AI 无法通过 API Key 测试连接（需要 OAuth2 认证）。请在实际生成图片时验证配置是否正确。"
        }


def _test_google_gemini(config: dict, test_prompt: str) -> dict:
    """测试 Google Gemini 文本生成服务"""
    from google import genai

    if config.get('base_url'):
        client = genai.Client(
            api_key=config['api_key'],
            http_options={
                'base_url': config['base_url'],
                'api_version': 'v1beta'
            },
            vertexai=False
        )
    else:
        client = genai.Client(
            api_key=config['api_key'],
            vertexai=True
        )

    model = config.get('model') or 'gemini-2.0-flash-exp'
    response = client.models.generate_content(
        model=model,
        contents=test_prompt
    )
    result_text = response.text if hasattr(response, 'text') else str(response)

    return _check_response(result_text)


def _test_openai_compatible(config: dict, test_prompt: str) -> dict:
    """测试 OpenAI 兼容接口"""
    from generation.utils.text_protocol import resolve_text_protocol

    if resolve_text_protocol(config) == 'responses':
        from generation.utils.responses_client import ResponsesTextClient

        client = ResponsesTextClient(
            api_key=config.get('api_key'),
            base_url=config.get('base_url'),
            endpoint_type=config.get('endpoint_type'),
            timeout=30,
        )
        text = client.generate_text(test_prompt, model=config.get('model'))
        return _check_response(LlmSmokeResult(text, "content", ""))
    result = _test_openai_chat_completion(config, test_prompt)
    return _check_response(result)


def _test_image_api(config: dict) -> dict:
    """测试图片 API 连接"""
    import requests

    base_url = config['base_url'].rstrip('/') if config.get('base_url') else 'https://api.openai.com'
    if base_url.endswith('/v1'):
        base_url = base_url[:-3]

    endpoint_type = config.get('endpoint_type', '')
    from generation.generators.gpt_images import validate_image_endpoint
    validate_image_endpoint(endpoint_type or '')

    # 如果端点是 chat/completions 类型，用真实 LLM 请求来测试
    if endpoint_type and ('chat' in endpoint_type or 'completions' in endpoint_type):
        result = _test_openai_chat_completion(
            config,
            "请只回复：IdeaGen连接测试成功",
        )
        return _llm_smoke_response_payload(result)

    # 标准 images API，尝试 /v1/models
    url = f"{base_url}/v1/models"
    response = requests.get(
        url,
        headers={'Authorization': f"Bearer {config['api_key']}"},
        timeout=30
    )

    if response.status_code == 200:
        return {
            "success": True,
            "warning": True,
            "status": "warning",
            "message": "鉴权检查通过，尚未验证图片生成。请在图片制作页生成一张图片以确认模型权限和接口兼容性。"
        }
    else:
        raise Exception(f"HTTP {response.status_code}: {response.text[:200]}")


def _test_openai_chat_completion(config: dict, test_prompt: str) -> LlmSmokeResult:
    """用当前配置发送一次真实 OpenAI-compatible LLM 请求。"""
    import requests

    base_url = _normalize_base_url(config.get('base_url') or 'https://api.openai.com')
    endpoint = _normalize_endpoint(config.get('endpoint_type') or '/v1/chat/completions')
    url = f"{base_url}{endpoint}"

    payload = {
        "model": config.get('model') or 'gpt-3.5-turbo',
        "messages": [{"role": "user", "content": test_prompt}],
        "max_tokens": 256,
        "stream": False
    }
    headers = {
        'Authorization': f"Bearer {config['api_key']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )
    if _should_retry_with_max_completion_tokens(response):
        retry_payload = dict(payload)
        retry_payload["max_completion_tokens"] = retry_payload.pop("max_tokens")
        response = requests.post(
            url,
            headers=headers,
            json=retry_payload,
            timeout=30
        )

    if response.status_code != 200:
        raise Exception(f"HTTP {response.status_code}: {response.text[:500]}")

    try:
        result = response.json()
    except Exception as exc:
        raise Exception(f"LLM 响应不是合法 JSON: {response.text[:500]}") from exc

    smoke_result = _extract_chat_completion_text(result)
    if not smoke_result.text.strip() and smoke_result.source not in ["reasoning_tokens"]:
        raise Exception(
            "LLM 响应为空。\n"
            f"响应数据: {str(result)[:500]}"
        )
    return smoke_result


def _extract_chat_completion_text(result: dict) -> LlmSmokeResult:
    choices = result.get('choices')
    if not isinstance(choices, list) or not choices:
        raise Exception(
            "LLM 响应格式异常：未找到 choices。\n"
            f"响应数据: {str(result)[:500]}"
        )

    choice = choices[0] if isinstance(choices[0], dict) else {}
    finish_reason = choice.get('finish_reason') or ""
    message = choice.get('message', {}) if isinstance(choice, dict) else {}
    content = message.get('content')
    if isinstance(content, str) and content.strip():
        return LlmSmokeResult(content.strip(), "content", finish_reason)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get('text') or item.get('content')
                if isinstance(text, str):
                    parts.append(text)
        joined = "\n".join(parts).strip()
        if joined:
            return LlmSmokeResult(joined, "content", finish_reason)

    reasoning_content = message.get('reasoning_content') or message.get('reasoning')
    if isinstance(reasoning_content, str) and reasoning_content.strip():
        return LlmSmokeResult(reasoning_content.strip(), "reasoning_content", finish_reason)

    if finish_reason == "length" and _extract_reasoning_token_count(result) > 0:
        return LlmSmokeResult("", "reasoning_tokens", finish_reason)

    raise Exception(
        "LLM 响应格式异常：未找到 message.content 或 reasoning_content。\n"
        f"响应数据: {str(result)[:500]}"
    )


def _extract_reasoning_token_count(result: dict) -> int:
    usage = result.get("usage") if isinstance(result, dict) else {}
    if not isinstance(usage, dict):
        return 0
    for details_key in ["completion_tokens_details", "output_tokens_details"]:
        details = usage.get(details_key)
        if isinstance(details, dict):
            value = details.get("reasoning_tokens")
            if isinstance(value, int):
                return value
    return 0


def _should_retry_with_max_completion_tokens(response) -> bool:
    if response.status_code not in [400, 422]:
        return False
    text = (response.text or "").lower()
    return (
        "max_tokens" in text
        and (
            "max_completion_tokens" in text
            or "not compatible" in text
            or "unsupported" in text
            or "不支持" in text
        )
    )


def _normalize_base_url(base_url: str) -> str:
    base_url = base_url.rstrip('/')
    if base_url.endswith('/v1'):
        return base_url[:-3]
    return base_url


def _normalize_endpoint(endpoint: str) -> str:
    if endpoint == 'chat':
        endpoint = '/v1/chat/completions'
    elif endpoint == 'images':
        endpoint = '/v1/images/generations'
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    return endpoint


def _format_llm_success_message(result: LlmSmokeResult) -> str:
    if result.source in ["reasoning_content", "reasoning_tokens"]:
        suffix = "，输出预算已耗尽" if result.finish_reason == "length" else ""
        return f"LLM 请求成功！模型返回了推理过程但没有最终文本{suffix}。如果正式生成也出现空内容，请提高输出上限或关闭思考模式后重试。"
    return f"LLM 请求成功！响应: {result.text[:100]}"


def _llm_smoke_response_payload(result: LlmSmokeResult) -> dict:
    payload = {
        "success": True,
        "message": _format_llm_success_message(result),
    }
    if result.source in ["reasoning_content", "reasoning_tokens"]:
        payload["warning"] = True
        payload["status"] = "warning"
    return payload


def _check_response(result: LlmSmokeResult) -> dict:
    """检查响应是否符合预期"""
    if result.source in ["reasoning_content", "reasoning_tokens"]:
        return _llm_smoke_response_payload(result)

    if "IdeaGen" in result.text:
        return _llm_smoke_response_payload(result)
    else:
        return {
            "success": True,
            "message": f"LLM 请求成功，但响应内容不符合预期: {result.text[:100]}"
        }


# ==================== DeAI 工具 ====================

@require_auth
def get_deai_config(request):
    """获取 DeAI 工具信息（脚本与 Python 路径由后端自动解析，无需配置）"""
    try:
        return JsonResponse({
            "success": True,
            "config": {
                "deai_script": _resolve_deai_script(),
                "python_script": _resolve_python(),
            }
        }, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/config/deai"})


@require_auth
def run_deai(request):
    """
    自动执行 DeAI 去指纹工具（处理指定任务目录的图片）

    请求体：
    - task_id: 任务 ID（必填）
    - strength: 处理强度（可选，light/medium/heavy，默认 medium）

    返回：
    - success: 是否成功
    - reason: ok / not_configured / task_not_found / python_not_found / timeout / failed
    - exit_code: 进程退出码
    - stdout / stderr: 输出信息（截断）
    - output_dir: 处理结果目录
    """
    try:
        data = json_body(request) or {}
        task_id = str(data.get('task_id', '') or '').strip()
        strength = str(data.get('strength', 'medium') or 'medium').strip()

        if not task_id:
            return api_error_response(
                validation_error("task_id 不能为空", "请提供任务 ID。"),
                context={"endpoint": "/api/config/deai/run"},
            )
        if strength not in ('light', 'medium', 'heavy'):
            strength = 'medium'

        # 自动解析 DeAI 脚本路径与 Python 解释器（无需用户配置）
        python_script = _resolve_python()
        deai_script = _resolve_deai_script()

        if not deai_script:
            return JsonResponse({
                "success": False,
                "reason": "not_found",
                "error_message": "未找到 DeAI 工具脚本（deai-image/scripts/deai.py），请确认其已放入项目目录。",
            }, status=200)

        # 校验任务目录（按用户隔离：history/<user_id>/<task_id>）
        history_dir = settings.HISTORY_ROOT
        owner_id = _find_task_owner(task_id) or request.user_id or 'default'
        task_dir = history_dir / owner_id / task_id
        if not task_dir.exists() or not task_dir.is_dir():
            return JsonResponse({
                "success": False,
                "reason": "task_not_found",
                "error_message": f"任务目录不存在：{task_id}",
            }, status=200)

        # 任务级并发锁：同一任务同时只允许一个去AI化进程，避免并发写坏文件
        # 锁文件内容为两行：子进程PID + 启动时间ISO；超时（>35分钟）视为过期，
        # 防止 deai 被强杀后残留锁 + PID 被复用导致永久误判"正在处理中"。
        lock_file = task_dir / '.deai.lock'
        if lock_file.exists():
            _stale = False
            try:
                lines = (lock_file.read_text(encoding='utf-8') or '').splitlines()
                pid = int(lines[0].strip()) if lines else 0
                started = lines[1].strip() if len(lines) > 1 else ''
                if started:
                    try:
                        elapsed = (datetime.now() - datetime.fromisoformat(started)).total_seconds()
                        if elapsed > 35 * 60:
                            _stale = True
                    except ValueError:
                        pass
                if not _stale and _is_pid_alive(pid):
                    return JsonResponse({
                        "success": False,
                        "reason": "already_running",
                        "error_message": "该任务正在去AI化处理中，请稍候（处理完成后刷新页面再试）。",
                    }, status=200)
            except ValueError:
                pass
            if _stale:
                try:
                    lock_file.unlink()
                except Exception:
                    pass

        # 输出目录（先清理上次结果，避免重复处理）
        # 放在任务目录同级的 <task_id>_deai_out 文件夹（同用户目录下），
        # 避免输出混在任务目录内、也避免 deai.py 处理输入时与自身输出互相干扰
        output_dir = history_dir / owner_id / f"{task_id}_deai_out"
        if output_dir.exists():
            shutil.rmtree(output_dir, ignore_errors=True)
        output_dir.mkdir(parents=True, exist_ok=True)

        # 执行 deai.py
        cmd = [
            python_script,
            deai_script,
            str(task_dir),
            '--strength', strength,
            '-o', str(output_dir),
            '--batch',
        ]
        logger.info("执行 DeAI: %s", ' '.join(cmd))

        if os.name == 'nt':
            # Windows：打开独立控制台窗口运行 deai.py，实时显示处理进度，跑完自动关闭
            try:
                proc = subprocess.Popen(
                    cmd,
                    creationflags=subprocess.CREATE_NEW_CONSOLE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                )
                stdout = stderr = None
            except OSError:
                logger.error("找不到 Python 可执行文件: %s", python_script)
                return JsonResponse({
                    "success": False,
                    "reason": "python_not_found",
                    "error_message": f"找不到 Python 可执行文件：{python_script}",
                }, status=200)
        else:
            # 服务器/容器（无控制台窗口）：静默捕获输出
            try:
                proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                )
            except FileNotFoundError:
                logger.error("找不到 Python 可执行文件: %s", python_script)
                return JsonResponse({
                    "success": False,
                    "reason": "python_not_found",
                    "error_message": f"找不到 Python 可执行文件：{python_script}",
                }, status=200)

        # 写入锁（记录 deai 子进程 PID + 启动时间），结束时释放
        lock_file.write_text(
            f"{proc.pid}\n{datetime.now().isoformat(timespec='seconds')}",
            encoding='utf-8',
        )
        try:
            try:
                if os.name == 'nt':
                    proc.wait(timeout=1800)
                    stdout = stderr = None
                else:
                    stdout, stderr = proc.communicate(timeout=1800)
            except subprocess.TimeoutExpired:
                proc.kill()
                logger.error("DeAI 执行超时: %s", task_id)
                return JsonResponse({
                    "success": False,
                    "reason": "timeout",
                    "error_message": "DeAI 执行超时（30分钟），请检查图片数量或 Python 环境。",
                }, status=200)
            except Exception as exc:
                # 子进程通信异常（如进程被外部终止/环境异常），转为友好错误而非 500
                try:
                    proc.kill()
                except Exception:
                    pass
                logger.error("DeAI 子进程异常 %s: %s", task_id, exc)
                return JsonResponse({
                    "success": False,
                    "reason": "subprocess_error",
                    "error_message": f"DeAI 子进程异常退出：{exc}",
                }, status=200)
        finally:
            try:
                lock_file.unlink()
            except Exception:
                pass

        ok = proc.returncode == 0
        err_tail = ''
        if not ok:
            err_tail = ((stderr or stdout or '').strip()[-300:]) if (stdout or stderr) else ''
            logger.error(
                "DeAI 执行失败 %s: exit=%s stderr=%s",
                task_id, proc.returncode, err_tail,
            )
        resp = {
            "success": ok,
            "reason": "ok" if ok else "failed",
            "exit_code": proc.returncode,
            "stdout": (stdout or '')[-4000:] if stdout else '',
            "stderr": (stderr or '')[-4000:] if stderr else '',
            "output_dir": str(output_dir),
        }
        if not ok:
            if err_tail:
                resp["error_message"] = err_tail
            elif os.name == 'nt':
                resp["error_message"] = f"DeAI 执行失败（退出码 {proc.returncode}），请查看弹出的 DeAI 窗口输出。"
            else:
                resp["error_message"] = f"DeAI 执行失败（退出码 {proc.returncode}）"
        return JsonResponse(resp, status=200)

    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/config/deai/run"})


@require_auth
def serve_deai_image(request, task_id, filename):
    """
    获取 DeAI 处理后的图片（history/<user_id>/<task_id>_deai_out/<filename>）

    路径参数：
    - task_id: 任务 ID
    - filename: 处理后的文件名（如 0_deai.png）
    """
    try:
        # 文件名安全校验，防止路径穿越
        if '/' in filename or '\\' in filename or filename.startswith('.'):
            return api_error_response("非法文件名", status=400, context={"endpoint": "/api/deai/images"})

        owner_id = _find_task_owner(task_id) or request.user_id or 'default'
        out_dir = settings.HISTORY_ROOT / owner_id / f"{task_id}_deai_out"
        file_path = out_dir / filename
        if not file_path.exists() or not file_path.is_file():
            return api_error_response(
                f"文件不存在：{filename}",
                status=404,
                context={"endpoint": "/api/deai/images", "task_id": task_id, "filename": filename},
            )
        mimetype = 'image/png' if Path(filename).suffix.lower() == '.png' else 'image/jpeg'
        return FileResponse(open(str(file_path), 'rb'), content_type=mimetype)

    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/deai/images"})
