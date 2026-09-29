"""URL 配置：API 路由 + 前端静态托管（SPA fallback）。"""
from django.conf import settings
from django.http import JsonResponse, FileResponse
from django.urls import include, path, re_path
from django.contrib import admin
from pathlib import Path


def health(request):
    return JsonResponse({"success": True, "message": "服务正常运行"})


# 前端构建产物（生产/Docker 环境存在时托管）
def _spa_serve(request):
    """服务前端构建产物：dist 下真实存在的文件直接返回，其余路径 SPA fallback 到 index.html"""
    dist = settings.PROJECT_ROOT / 'frontend' / 'dist'
    if dist.exists():
        rel = request.path.lstrip('/')
        if rel:
            target = (dist / rel).resolve()
            if target.is_relative_to(dist.resolve()) and target.is_file():
                # Windows MIME databases do not consistently recognize WebP.
                content_type = 'image/webp' if target.suffix.lower() == '.webp' else None
                response = FileResponse(open(target, 'rb'), content_type=content_type)
                if target.suffix.lower() == '.html':
                    response['Cache-Control'] = 'no-cache'
                return response
        index = dist / 'index.html'
        if index.exists():
            response = FileResponse(open(index, 'rb'))
            response['Cache-Control'] = 'no-cache'
            return response
    return JsonResponse({
        "message": "IdeaGen 图文生成器 API",
        "version": "0.1.0",
        "endpoints": {
            "health": "/api/health",
            "outline": "POST /api/outline",
            "generate": "POST /api/generate",
            "images": "GET /api/images/<filename>",
        },
    })


urlpatterns = [
    path('api/health', health),
    path('api/auth/', include('accounts.urls')),
    path('api/', include('history.urls')),
    path('api/', include('generation.urls')),
    path('api/', include('providers.urls')),
    path('api/', include('prompts.urls')),
    path('api/', include('library.urls')),
    path('api/', include('postprocessing.urls')),
    path('api/', include('reference_assets.urls')),
    path('django-admin/', admin.site.urls),
]

# SPA fallback：非 /api 路径全部回落到前端构建产物（Vue Router history 模式）
urlpatterns += [
    re_path(r'^(?!api/|django-admin/|static/).*$', _spa_serve),
]
