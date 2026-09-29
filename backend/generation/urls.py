"""图片/文案/大纲生成 API 路由（挂载前缀为 'api/'，见 config/urls.py）。"""
from django.urls import re_path

from . import views
from . import candidates
from . import outline_inspection
from . import image_prompt
from . import copy_prompt
from . import content_diagnostics
from . import reference_document

urlpatterns = [
    re_path(r'^reference-document/import/?$', reference_document.import_document),
    re_path(r'^content/records/(?P<run_id>[^/]+)/diagnostics/?$', content_diagnostics.diagnostics),
    re_path(r'^content/preview/?$', copy_prompt.preview),
    re_path(r'^image-prompt/preview/?$', image_prompt.preview),
    re_path(r'^outline/preview/?$', outline_inspection.preview),
    re_path(r'^outline/records/?$', outline_inspection.records),
    re_path(r'^outline/records/(?P<run_id>[^/]+)/diagnostics/?$', outline_inspection.diagnostics),
    re_path(r'^image-candidates/(?P<record_id>[A-Za-z0-9_-]+)/?$', candidates.candidates),
    re_path(r'^image-candidates/(?P<record_id>[A-Za-z0-9_-]+)/(?P<candidate_id>[A-Za-z0-9_-]+)/adopt/?$', candidates.adopt_candidate),
    re_path(r'^image-candidates/(?P<record_id>[A-Za-z0-9_-]+)/(?P<candidate_id>[A-Za-z0-9_-]+)/image/?$', candidates.candidate_image),
    re_path(r'^outline/?$', views.generate_outline),
    re_path(r'^content/?$', views.generate_content),
    re_path(r'^generate/cancel/?$', views.cancel_generation),
    re_path(r'^generate/?$', views.generate_images),
    re_path(r'^retry/?$', views.retry_single_image),
    re_path(r'^retry-failed/?$', views.retry_failed_images),
    re_path(r'^regenerate/?$', views.regenerate_image),
    re_path(r'^task/(?P<task_id>[^/]+)/?$', views.get_task_state),
    re_path(r'^diagnostics/(?P<task_id>[^/]+)/?$', views.get_diagnostics),
    re_path(r'^generation/consistency/(?P<task_id>[A-Za-z0-9_-]+)/?$', views.get_consistency),
    re_path(r'^images/(?P<task_id>[^/]+)/(?P<filename>[^/]+)/?$', views.get_image),
    re_path(r'^health/?$', views.health_check),
]
