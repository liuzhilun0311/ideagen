from django.http import FileResponse, JsonResponse
from django.views.decorators.http import require_GET, require_http_methods

from common.api import api_error_response, json_body, require_auth
from history.permissions import private_view
from .services import ProcessingError, image_file, record_state


@private_view
@require_auth
@require_http_methods(['GET', 'POST'])
def state(request, record_id):
    try:
        data = json_body(request) if request.method == 'POST' else None
        if request.method == 'POST' and not isinstance(data, dict):
            raise ProcessingError('请求内容必须是 JSON 对象。')
        return JsonResponse(record_state(record_id, request.user_id, data))
    except ProcessingError as error:
        return api_error_response(str(error), status=error.status)
    except Exception:
        return api_error_response('图片处理服务暂时不可用，请稍后重试。', status=503)


@private_view
@require_auth
@require_GET
def image(request, record_id, index, version, revision):
    try:
        stream = image_file(record_id, request.user_id, index, version, revision)
        response = FileResponse(stream)
        response['Cache-Control'] = 'private, no-store'
        response['X-Content-Type-Options'] = 'nosniff'
        return response
    except ProcessingError as error:
        return api_error_response(str(error), status=error.status)
    except Exception:
        return api_error_response('图片暂时无法读取，请稍后重试。', status=503)
