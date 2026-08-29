"""提示词库管理 API 路由（挂载前缀 api/，见 config/urls.py）。"""
from django.urls import re_path

from . import views


urlpatterns = [
    re_path(r'^prompts/?$', views.get_prompts),
    re_path(r'^prompts/save/?$', views.save_prompt),
    re_path(r'^prompts/delete/?$', views.delete_prompt),
    re_path(r'^prompts/base/save/?$', views.save_base_prompt),
    re_path(r'^prompts/admin/users/?$', views.set_prompt_users),
    re_path(r'^prompts/admin/delete/?$', views.admin_delete),
]
