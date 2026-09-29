"""Atomic replacement of a complete recipient set."""
from django.db import transaction
from django.http import JsonResponse
from django.views.decorators.http import require_http_methods

from accounts.models import User
from common.api import api_error_response, json_body, require_auth
from .models import HistoryRecord
from .permissions import actor, can_share, private_view


@private_view
@require_auth
@require_http_methods(['GET', 'PUT'])
def sharing(request, record_id):
    with transaction.atomic():
        record = HistoryRecord.objects.select_for_update().filter(pk=record_id).first()
        if record is None:
            return api_error_response('作品不存在。', status=404)
        if not can_share(actor(request.user_id), record):
            return api_error_response('仅作品所属管理员可配置共享。', status=403)
        if request.method == 'PUT':
            data = json_body(request)
            ids = data.get('user_ids') if isinstance(data, dict) else None
            if (not isinstance(ids, list) or any(not isinstance(uid, str) or not uid for uid in ids)
                    or record.user_id in ids):
                return api_error_response('请选择有效的共享用户，且不能包含自己。', status=400)
            recipients = list(User.objects.filter(pk__in=set(ids)))
            if len(recipients) != len(set(ids)):
                return api_error_response('部分共享用户已不存在，请刷新后重试。', status=400)
            record.shared_users.set(recipients)
        return JsonResponse({
            'success': True,
            'user_ids': list(record.shared_users.order_by('pk').values_list('pk', flat=True)),
        })
