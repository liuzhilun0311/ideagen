"""用户认证 API 视图（对应 Flask 版 auth_routes.py）。"""
from django.http import JsonResponse

from common.api import api_error_response, json_body, require_auth, admin_required, validation_error
from . import auth as auth_service


def register_user(request):
    """POST /api/auth/register"""
    data = json_body(request)
    username = data.get('username', '')
    password = data.get('password', '')
    if not username or not password:
        return api_error_response(
            validation_error("用户名和密码不能为空", "请填写用户名和密码。"),
            context={"endpoint": "/api/auth/register"},
        )
    try:
        user = auth_service.register(username, password)
        return JsonResponse({"success": True, "user": user}, status=200)
    except ValueError as e:
        return api_error_response(
            validation_error(str(e), str(e)),
            context={"endpoint": "/api/auth/register"},
        )
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/auth/register"})


def login_user(request):
    """POST /api/auth/login"""
    data = json_body(request)
    username = data.get('username', '')
    password = data.get('password', '')
    if not username or not password:
        return api_error_response(
            validation_error("用户名和密码不能为空", "请填写用户名和密码。"),
            context={"endpoint": "/api/auth/login"},
        )
    try:
        result = auth_service.login(username, password)
        return JsonResponse({"success": True, **result}, status=200)
    except ValueError as e:
        return api_error_response(
            validation_error(str(e), str(e)),
            context={"endpoint": "/api/auth/login"},
        )
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/auth/login"})


def logout_user(request):
    """POST /api/auth/logout"""
    try:
        from common.api import extract_token
        auth_service.logout(extract_token(request))
        return JsonResponse({"success": True}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/auth/logout"})


def current_user(request):
    """GET /api/auth/me"""
    try:
        from common.api import extract_token
        user = auth_service.get_user_by_token(extract_token(request))
        # get_user_by_token 已返回 dict 形态，直接返回
        return JsonResponse({"success": True, "user": user}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/auth/me"})


@admin_required
def admin_list_users(request):
    """GET /api/auth/users（仅管理员）"""
    try:
        users = auth_service.list_users()
        return JsonResponse({"success": True, "users": users}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/auth/users"})


@require_auth
def change_user_password(request, user_id: str):
    """POST /api/auth/users/<user_id>/password"""
    try:
        data = json_body(request)
        new_password = data.get('new_password', '')
        old_password = data.get('old_password', '')
        current = request.user_obj
        auth_service.change_password(
            user_id,
            old_password,
            new_password,
            is_admin=bool(current.get('is_admin', False)),
            current_user_id=current['id'],
        )
        return JsonResponse({"success": True, "message": "密码已修改"}, status=200)
    except ValueError as e:
        return api_error_response(
            validation_error(str(e), str(e)),
            context={"endpoint": "/api/auth/users/<id>/password"},
        )
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/auth/users/<id>/password"})


@admin_required
def admin_delete_user(request, user_id: str):
    """DELETE /api/auth/users/<user_id>（仅管理员）"""
    try:
        auth_service.delete_user(user_id, request.user_id)
        return JsonResponse({"success": True, "message": "用户已删除"}, status=200)
    except ValueError as e:
        return api_error_response(
            validation_error(str(e), str(e)),
            context={"endpoint": "/api/auth/users/<id>"},
        )
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/auth/users/<id>"})
