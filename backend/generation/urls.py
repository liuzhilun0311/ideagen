"""图片/文案/大纲生成 API 路由（挂载前缀为 'api/'，见 config/urls.py）。"""
from django.urls import re_path

from . import views

urlpatterns = [
    re_path(r'^outline/?$', views.generate_outline),
    re_path(r'^content/?$', views.generate_content),
    re_path(r'^generate/cancel/?$', views.cancel_generation),
    re_path(r'^generate/?$', views.generate_images),
    re_path(r'^retry/?$', views.retry_single_image),
    re_path(r'^retry-failed/?$', views.retry_failed_images),
    re_path(r'^regenerate/?$', views.regenerate_image),
    re_path(r'^task/(?P<task_id>[^/]+)/?$', views.get_task_state),
    re_path(r'^images/(?P<task_id>[^/]+)/(?P<filename>[^/]+)/?$', views.get_image),
    re_path(r'^health/?$', views.health_check),
]
