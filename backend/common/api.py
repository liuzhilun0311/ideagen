"""API 通用工具：错误响应、鉴权装饰器、JSON 解析（对应 Flask 版 routes/utils.py）。"""
from __future__ import annotations

import json
import logging
from functools import wraps

from django.http import JsonResponse

from .errors import AppError, ensure_app_error, error_payload

logger = logging.getLogger(__name__)


# ==================== 响应 ====================

def api_error_response(error, status: int = None, context: dict = None):
    """返回统一结构化 API 错误响应（与 Flask 版一致）。"""
    app_error = ensure_app_error(error, context=context)
    if status is not None:
        app_error.status = status
    return JsonResponse(error_payload(app_error), status=app_error.status)


def validation_error(detail: str, suggestion: str = "请检查输入后重试") -> AppError:
    """构造参数校验错误。"""
    return AppError(
        code="INVALID_REQUEST",
        title="请求参数不完整",
        detail=detail,
        suggestion=suggestion,
        status=400,
        retryable=False,
    )


def normalize_error_result(result: dict, context: dict = None, fallback_status: int = 500) -> dict:
    """将 service 返回的旧格式错误转换为统一错误对象，同时保留兼容字段。"""
    if result.get("success", False):
        return result

    error = result.get("error") or result.get("error_message") or "操作失败"
    if isinstance(error, dict) and error.get("code"):
        error_obj = error
        error_message = result.get("error_message") or f"{error_obj.get('title', '操作失败')}：{error_obj.get('suggestion') or error_obj.get('detail', '')}"
    else:
        app_error = ensure_app_error(error, context=context)
        if app_error.status == 500 and fallback_status != 500:
            app_error.status = fallback_status
        error_obj = app_error.to_dict()
        error_message = app_error.to_message()

    next_result = dict(result)
    next_result["error"] = error_obj
    next_result["error_message"] = error_message
    return next_result


# ==================== 请求解析 ====================

def json_body(request):
    """安全解析 JSON 请求体，失败返回 {}。"""
    try:
        return json.loads(request.body.decode('utf-8') or '{}')
    except Exception:
        return {}


def extract_token(request) -> str:
    """从请求头或 query 参数提取 Bearer token（图片 <img> 走 query）。"""
    auth_header = request.headers.get('Authorization', '')
    if auth_header.startswith('Bearer '):
        return auth_header[7:].strip()
    return (request.GET.get('token') or '').strip()


# ==================== 鉴权装饰器 ====================

def _resolve_user(request):
    """根据 token 解析当前用户，未登录返回 None。"""
    from accounts.auth import get_user_by_token
    token = extract_token(request)
    if not token:
        return None
    return get_user_by_token(token)


def require_auth(view):
    """要求登录：未登录返回 401（与 Flask 版 before_request 一致）。"""
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        user = _resolve_user(request)
        if not user:
            return JsonResponse({
                "success": False,
                "error": {
                    "code": "UNAUTHORIZED",
                    "title": "未登录",
                    "detail": "请先登录后再访问",
                    "suggestion": "请重新登录",
                    "status": 401,
                    "retryable": True,
                }
            }, status=401)
        request.user_obj = user
        request.user_id = user['id']
        return view(request, *args, **kwargs)
    return wrapper


def admin_required(view):
    """要求管理员：未登录 401，非管理员 403。"""
    @wraps(view)
    @require_auth
    def wrapper(request, *args, **kwargs):
        if not request.user_obj.get('is_admin'):
            return api_error_response("需要管理员权限", status=403, context={})
        return view(request, *args, **kwargs)
    return wrapper


# ==================== 服务商脱敏 ====================

def mask_api_key(key: str) -> str:
    """遮盖 API Key，只显示前4位和后4位。"""
    if not key:
        return ''
    if len(key) <= 8:
        return '*' * len(key)
    return key[:4] + '*' * (len(key) - 8) + key[-4:]


def prepare_providers_for_response(providers: dict) -> dict:
    """将 api_key 替换为脱敏版本，避免泄露。"""
    result = {}
    for name, config in providers.items():
        provider_copy = config.copy()
        if 'api_key' in provider_copy and provider_copy['api_key']:
            provider_copy['api_key_masked'] = mask_api_key(provider_copy['api_key'])
            provider_copy['api_key'] = ''
        else:
            provider_copy['api_key_masked'] = ''
            provider_copy['api_key'] = ''
        result[name] = provider_copy
    return result


def log_request(endpoint: str, data: dict = None):
    """记录 API 请求日志（过滤敏感信息）。"""
    logger.info(f"📥 收到请求: {endpoint}")
    if data:
        safe_data = {
            k: v for k, v in data.items()
            if k not in ['images', 'user_images'] and not isinstance(v, bytes)
        }
        if 'images' in data:
            safe_data['images'] = f"[{len(data['images'])} 张图片]"
        if 'user_images' in data:
            safe_data['user_images'] = f"[{len(data['user_images'])} 张图片]"
        logger.debug(f"  请求数据: {safe_data}")
