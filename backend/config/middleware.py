"""自定义中间件：/api/ 接口跳过 CSRF（前端用 Bearer token，非 cookie 会话）。"""
from django.utils.deprecation import MiddlewareMixin


class SkipCsrfForApi(MiddlewareMixin):
    def process_request(self, request):
        if request.path.startswith('/api/'):
            setattr(request, '_dont_enforce_csrf_checks', True)
