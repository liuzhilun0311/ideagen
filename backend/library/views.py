import logging

from django.http import JsonResponse
from django.views.decorators.http import require_GET, require_POST

from common.api import api_error_response, json_body, require_auth
from common.errors import AppError
from library import services

logger = logging.getLogger(__name__)


def _run(operation):
    try:
        return JsonResponse(operation())
    except services.LibraryError as exc:
        codes = {400: 'INVALID_REQUEST', 403: 'FORBIDDEN', 404: 'NOT_FOUND', 409: 'REVISION_CONFLICT'}
        return api_error_response(AppError(
            code=codes.get(exc.status, 'LIBRARY_ERROR'),
            title='Library operation failed', detail=str(exc),
            suggestion='Refresh the list and retry.' if exc.status == 409 else str(exc),
            status=exc.status, retryable=exc.status >= 409,
        ))
    except Exception:
        # File/parser errors may include credentials; never return or log them.
        logger.error('Library operation failed; no resource data logged.')
        return api_error_response('Unable to save or read the library. Please retry.', status=500)


def _body(request):
    data = json_body(request)
    if not isinstance(data, dict):
        raise services.LibraryError('Expected a JSON object.')
    return data


@require_auth
@require_GET
def get_order(request, resource, kind):
    return _run(lambda: services.get_order(request.user_id, resource, kind))


@require_auth
@require_POST
def reorder(request, resource, kind):
    def operation():
        data = _body(request)
        return services.reorder(request.user_id, resource, kind, data.get('revision'), data.get('order'))
    return _run(operation)


@require_auth
@require_POST
def copy_resource(request, resource, kind):
    def operation():
        data = _body(request)
        return services.copy_resource(
            request.user_id, resource, kind, data.get('source'),
            data.get('revision'), data.get('request_id'),
        )
    return _run(operation)
