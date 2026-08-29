"""提示词库管理 API 视图。

接口：
- GET  /api/prompts               获取全部提示词（管理员会看到所有用户的提示词）
- POST /api/prompts/save          新增/覆盖一个用户提示词
- POST /api/prompts/delete        删除一个用户提示词
- POST /api/prompts/base/save     管理员保存系统默认提示词
- POST /api/prompts/admin/users   管理员配置某提示词的用户名单
- POST /api/prompts/admin/delete  管理员删除任意提示词
"""
import logging

from django.http import JsonResponse

from common.api import (
    admin_required,
    api_error_response,
    json_body,
    require_auth,
    validation_error,
)

from . import services

logger = logging.getLogger(__name__)


@require_auth
def get_prompts(request):
    """获取全部类型提示词（系统默认 + 用户自定义）。"""
    try:
        return JsonResponse({
            "success": True,
            "prompts": services.list_all_prompts(request.user_id),
        }, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/prompts"})


@admin_required
def save_base_prompt(request):
    """POST /api/prompts/base/save — 管理员保存系统默认提示词（kind/content）。"""
    try:
        data = json_body(request) or {}
        kind = (data.get('kind') or '').strip()
        content = data.get('content') or ''
        try:
            services.save_base_prompt(kind, content)
        except ValueError as ve:
            return api_error_response(
                validation_error(str(ve)),
                context={"endpoint": "/api/prompts/base/save"},
            )
        return JsonResponse({"success": True, "message": "默认提示词已保存"}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/prompts/base/save"})


@require_auth
def save_prompt(request):
    """保存提示词（kind/name/content，按名称覆盖）。"""
    try:
        data = json_body(request) or {}
        kind = (data.get('kind') or '').strip()
        name = (data.get('name') or '').strip()
        content = data.get('content') or ''
        try:
            services.save_prompt(request.user_id, kind, name, content)
        except ValueError as ve:
            return api_error_response(
                validation_error(str(ve)),
                context={"endpoint": "/api/prompts/save"},
            )
        return JsonResponse({"success": True, "message": "提示词已保存"}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/prompts/save"})


@require_auth
def delete_prompt(request):
    """删除提示词（kind/name）。"""
    try:
        data = json_body(request) or {}
        kind = (data.get('kind') or '').strip()
        name = (data.get('name') or '').strip()
        if not kind or not name:
            return api_error_response(
                validation_error("kind 和 name 不能为空", "请提供提示词类型和名称。"),
                context={"endpoint": "/api/prompts/delete"},
            )
        deleted = services.delete_prompt(request.user_id, kind, name)
        if not deleted:
            return api_error_response(
                validation_error(f"提示词不存在：{name}", "未找到要删除的提示词。"),
                context={"endpoint": "/api/prompts/delete"},
            )
        return JsonResponse({"success": True, "message": "提示词已删除"}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/prompts/delete"})


# ==================== 管理员接口 ====================

@admin_required
def set_prompt_users(request):
    """POST /api/prompts/admin/users — 配置某提示词的用户名单（owner_id/kind/name/allowed_users）。"""
    try:
        data = json_body(request) or {}
        owner_id = str(data.get('owner_id') or '').strip()
        kind = (data.get('kind') or '').strip()
        name = (data.get('name') or '').strip()
        usernames = data.get('allowed_users') or []
        if not owner_id or not kind or not name:
            return api_error_response(
                validation_error("owner_id / kind / name 不能为空", "请提供完整参数。"),
                context={"endpoint": "/api/prompts/admin/users"},
            )
        try:
            services.set_prompt_allowed_users(owner_id, kind, name, usernames)
        except ValueError as ve:
            return api_error_response(
                validation_error(str(ve)),
                context={"endpoint": "/api/prompts/admin/users"},
            )
        return JsonResponse({"success": True, "message": "已更新使用名单"}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/prompts/admin/users"})


@admin_required
def admin_delete(request):
    """POST /api/prompts/admin/delete — 管理员删除任意用户的提示词。"""
    try:
        data = json_body(request) or {}
        owner_id = str(data.get('owner_id') or '').strip()
        kind = (data.get('kind') or '').strip()
        name = (data.get('name') or '').strip()
        if not owner_id or not kind or not name:
            return api_error_response(
                validation_error("owner_id / kind / name 不能为空", "请提供完整参数。"),
                context={"endpoint": "/api/prompts/admin/delete"},
            )
        deleted = services.admin_delete_prompt(owner_id, kind, name)
        if not deleted:
            return api_error_response(
                validation_error(f"提示词不存在：{name}", "未找到要删除的提示词。"),
                context={"endpoint": "/api/prompts/admin/delete"},
            )
        return JsonResponse({"success": True, "message": "提示词已删除"}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/prompts/admin/delete"})
