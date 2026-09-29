import base64
import uuid
from io import BytesIO
from PIL import Image
from django.http import JsonResponse
from common.api import require_auth, api_error_response, json_body
from .models import OutlineRun
from .outline_prompt import build_outline_prompt, preferences
from .catalog import catalog_request
from .diagnostics import read, sanitize
from history.permissions import private_view
from .reference_images import validate_reference_count


def reference_summaries(images):
    result = []
    for image in images:
        with Image.open(BytesIO(image)) as source:
            source.thumbnail((160, 160))
            output = BytesIO()
            source.convert("RGB").save(output, format="JPEG", quality=65)
        result.append({"bytes": len(image), "thumbnail":
                       "data:image/jpeg;base64," + base64.b64encode(output.getvalue()).decode()})
    return result


def serialize(run):
    return {"id": str(run.pk), "prompt": run.prompt, "preferences": run.preferences,
            "references": run.references, "provider": run.provider, "model": run.model,
            "status": run.status, "sent": run.sent, "created_at": run.created_at.isoformat()}


@require_auth
@catalog_request
def preview(request):
    if request.method != "POST":
        return api_error_response("请求方法不支持", status=405)
    try:
        data = json_body(request)
        count = data.get("image_count", 0)
        validate_reference_count(count)
        options = preferences(data)
        response = JsonResponse({"success": True, "prompt": build_outline_prompt(
            data.get("topic"), data.get("reference_content", ""), count, options,
            reference_roles=data.get("reference_roles")),
            "preferences": options, "image_count": count})
        response["Cache-Control"] = "no-store"
        return response
    except (ValueError, TypeError, AttributeError) as error:
        return api_error_response(str(error), status=400)


@require_auth
def records(request):
    if request.method != "GET":
        return api_error_response("请求方法不支持", status=405)
    query = OutlineRun.objects.filter(user_id=request.user_id)
    runs = list(query[:20])
    if request.GET.get("id"):
        try:
            selected = query.filter(pk=uuid.UUID(request.GET["id"])).first()
        except ValueError:
            return api_error_response("记录编号无效", status=400)
        if selected and selected not in runs:
            runs.insert(0, selected)
    response = JsonResponse({"success": True, "records": [serialize(run) for run in runs]})
    response["Cache-Control"] = "no-store"
    return response


@private_view
@require_auth
def diagnostics(request, run_id):
    if request.method != "GET":
        return api_error_response("请求方法不支持", status=405)
    try:
        run_uuid = uuid.UUID(run_id)
    except ValueError:
        return api_error_response("记录编号无效", status=400)
    run = OutlineRun.objects.filter(pk=run_uuid, user_id=request.user_id).first()
    if run is None:
        return api_error_response("大纲记录不存在或无权访问。", status=404)
    events = read(f"outline-{run.pk}")
    response_available = any(event.get("event") == "response" for event in events)
    if not events:
        events = [sanitize({
            "at": run.created_at.isoformat(), "event": "request", "source": "snapshot",
            "phase": "outline", "prompt": run.prompt, "provider": run.provider,
            "model": run.model, "status": run.status, "sent": run.sent,
            "parameters": run.preferences,
            "references": [{"bytes": image.get("bytes")} for image in run.references],
        })]
    response = JsonResponse({
        "success": True, "record_id": str(run.pk), "status": run.status,
        "events": events, "response_available": response_available,
    }, json_dumps_params={"ensure_ascii": False})
    response["Cache-Control"] = "no-store"
    return response
