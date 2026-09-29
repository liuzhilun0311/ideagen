from django.urls import path

from . import views

urlpatterns = [
    path('postprocessing/<str:record_id>', views.state),
    path('postprocessing/images/<str:record_id>/<int:index>/<str:version>/<str:revision>', views.image),
]
