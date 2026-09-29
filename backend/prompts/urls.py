"""提示词库管理 API 路由（挂载前缀 api/，见 config/urls.py）。"""
from django.urls import re_path

from . import views, catalog_views


urlpatterns = [
    re_path(r'^prompt-center/?$', catalog_views.listing),
    re_path(r'^prompt-center/save/?$', catalog_views.save),
    re_path(r'^prompt-center/copy/?$', catalog_views.copy),
    re_path(r'^prompt-center/restore/?$', catalog_views.restore),
    re_path(r'^prompt-center/reorder/?$', catalog_views.reorder),
    re_path(r'^prompt-center/users/?$', catalog_views.users),
    re_path(r'^prompt-center/(?P<entry_id>[^/]+)/versions/?$', catalog_views.versions),
    re_path(r'^prompts/?$', views.get_prompts),
    re_path(r'^prompts/save/?$', views.save_prompt),
    re_path(r'^prompts/delete/?$', views.delete_prompt),
    re_path(r'^prompts/base/save/?$', views.save_base_prompt),
    re_path(r'^prompts/admin/users/?$', views.set_prompt_users),
    re_path(r'^prompts/admin/delete/?$', views.admin_delete),
]
