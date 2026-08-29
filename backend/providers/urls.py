"""配置 / DeAI API 路由（含 HTTP 方法分发，兼容有无尾斜杠）。

挂载前缀 'api/'（见 config/urls.py 中 path('api/', include('providers.urls'))）。
"""
from django.http import JsonResponse
from django.urls import re_path

from . import views


def _config_root(request):
    if request.method == 'GET':
        return views.get_config(request)
    if request.method == 'POST':
        return views.update_config(request)
    return JsonResponse({"success": False, "error_message": "方法不允许"}, status=405)


def _deai_config(request):
    # 只读：DeAI 脚本 / Python 路径由后端自动解析，无需前端配置
    if request.method == 'GET':
        return views.get_deai_config(request)
    return JsonResponse({"success": False, "error_message": "方法不允许"}, status=405)


urlpatterns = [
    re_path(r'^config/?$', _config_root),
    re_path(r'^config/test/?$', views.test_connection),
    re_path(r'^config/providers/users/?$', views.set_provider_users),
    re_path(r'^config/providers/save/?$', views.save_provider),
    re_path(r'^config/deai/?$', _deai_config),
    re_path(r'^config/deai/run/?$', views.run_deai),
    re_path(r'^deai/images/(?P<task_id>[^/]+)/(?P<filename>[^/]+)/?$', views.serve_deai_image),
]
