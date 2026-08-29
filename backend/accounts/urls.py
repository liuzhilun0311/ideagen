"""用户认证 API 路由。"""
from django.urls import path

from . import views

urlpatterns = [
    path('register', views.register_user),
    path('login', views.login_user),
    path('logout', views.logout_user),
    path('me', views.current_user),
    path('users', views.admin_list_users),
    path('users/<str:user_id>/password', views.change_user_password),
    path('users/<str:user_id>', views.admin_delete_user),
]
