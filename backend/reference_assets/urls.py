from django.urls import re_path

from . import views


urlpatterns = [
    re_path(r"^image-analysis/?$", views.analyze),
    re_path(r"^image-analysis/(?P<analysis_id>[0-9a-f-]+)/?$", views.analysis_detail),
    re_path(r"^image-analysis/(?P<analysis_id>[0-9a-f-]+)/apply/?$", views.apply_analysis),
    re_path(r"^reference-assets/?$", views.assets),
    re_path(r"^reference-assets/(?P<asset_id>[0-9a-f-]+)/?$", views.asset_detail),
    re_path(r"^reference-assets/images/(?P<asset_id>[0-9a-f-]+)/?$", views.asset_image),
    re_path(r"^prompt-center/from-analysis/?$", views.create_prompts_from_analysis),
]
