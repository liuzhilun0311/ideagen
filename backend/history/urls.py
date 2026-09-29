"""历史记录 API 路由（含 HTTP 方法分发，兼容有无尾斜杠）。"""
from django.http import JsonResponse
from django.urls import path, re_path

from . import views
from .sharing import sharing


def _history_root(request):
    if request.method == 'POST':
        return views.create_history(request)
    if request.method == 'GET':
        return views.list_history(request)
    return JsonResponse({"success": False, "error_message": "方法不允许"}, status=405)


def _history_detail(request, record_id: str):
    method = request.method
    if method == 'GET':
        return views.get_history(request, record_id)
    if method == 'PUT':
        return views.update_history(request, record_id)
    if method == 'DELETE':
        return views.delete_history(request, record_id)
    return JsonResponse({"success": False, "error_message": "方法不允许"}, status=405)


urlpatterns = [
    re_path(r'^history/?$', _history_root),
    re_path(r'^history/search/?$', views.search_history),
    re_path(r'^history/stats/?$', views.get_history_stats),
    re_path(r'^history/scan-all/?$', views.scan_all_tasks),
    re_path(r'^history/scan/(?P<task_id>[^/]+)/?$', views.scan_task),
    re_path(r'^history/(?P<record_id>[^/]+)/exists/?$', views.check_history_exists),
    re_path(r'^history/(?P<record_id>[^/]+)/sharing/?$', sharing),
    re_path(r'^history/(?P<record_id>[^/]+)/download/?$', views.download_history_zip),
    re_path(r'^history/(?P<record_id>[^/]+)/?$', _history_detail),
]
