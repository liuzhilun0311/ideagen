from django.urls import path

from library import views

urlpatterns = [
    path('library/<str:resource>/<str:kind>', views.get_order),
    path('library/<str:resource>/<str:kind>/reorder', views.reorder),
    path('library/<str:resource>/<str:kind>/copy', views.copy_resource),
]
