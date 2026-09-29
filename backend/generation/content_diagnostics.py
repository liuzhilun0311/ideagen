import uuid
from django.http import JsonResponse
from common.api import require_auth, api_error_response
from history.permissions import private_view
from .models import ContentRun
from .diagnostics import read, record, sanitize


def finish(run, response):
    if run is None:
        return response
    import json
    data = json.loads(response.content)
    run.status = "succeeded" if data.get("success") else "failed"
    run.save(update_fields=["status"])
    data["generation_record"] = {"id": str(run.pk), "status": run.status}
    record(f"content-{run.pk}", sanitize({
        "event": "response", "source": "local", "phase": "content",
        "status": run.status, "result": data,
    }))
    response.content = json.dumps(data, ensure_ascii=False).encode("utf-8")
    return response


@private_view
@require_auth
def diagnostics(request, run_id):
    if request.method != "GET":
        return api_error_response("请求方法不支持", status=405)
    try:
        selected = uuid.UUID(run_id)
    except ValueError:
        return api_error_response("记录编号无效", status=400)
    run = ContentRun.objects.filter(pk=selected, user_id=request.user_id).first()
    if run is None:
        return api_error_response("文案记录不存在或无权访问。", status=404)
    return JsonResponse({"success": True, "record_id": str(run.pk), "status": run.status,
                         "events": read(f"content-{run.pk}")},
                        json_dumps_params={"ensure_ascii": False})
