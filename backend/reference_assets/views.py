import hashlib
import io
import json
import mimetypes
import uuid
from pathlib import Path

from django.conf import settings
from django.http import FileResponse, JsonResponse
from PIL import Image, UnidentifiedImageError

from common.api import api_error_response, json_body, require_auth, validation_error
from prompts import catalog

from .models import ImageAnalysis, ReferenceAsset
from .protocol import normalize_analysis_payload
from .services import analyze_image

MAX_IMAGE_BYTES = 10 * 1024 * 1024
ALLOWED_IMAGE_TYPES = {"JPEG", "PNG", "WEBP", "GIF"}


def _analysis_data(row):
    return {
        "id": str(row.pk),
        "content": row.content or {},
        "layout": row.layout or {},
        "visual_style": row.visual_style or {},
        "rewritten_content": row.rewritten_content or "",
        "user_note": row.user_note or "",
        "source_image_available": bool(row.source_image_path),
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _asset_data(row):
    return {
        "id": str(row.pk),
        "analysis_id": str(row.analysis_id) if row.analysis_id else None,
        "title": row.title,
        "content": row.content or {},
        "rewritten_content": row.rewritten_content,
        "user_note": row.user_note,
        "image_url": f"/api/reference-assets/images/{row.pk}" if row.image_path else "",
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def _safe_root():
    root = (settings.HISTORY_ROOT / "_reference_assets").resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _safe_path(path):
    resolved = Path(path).resolve()
    root = _safe_root()
    if not resolved.is_relative_to(root):
        raise ValueError("参考图片路径无效")
    return resolved


def _validate_image(upload):
    if not upload or not getattr(upload, "size", 0):
        raise ValueError("请上传图片")
    if upload.size > MAX_IMAGE_BYTES:
        raise ValueError("图片大小不能超过10MB")
    data = upload.read()
    try:
        with Image.open(io.BytesIO(data)) as image:
            if image.format not in ALLOWED_IMAGE_TYPES:
                raise ValueError("仅支持 JPEG、PNG、WEBP 或 GIF 图片")
            image.verify()
    except (UnidentifiedImageError, OSError):
        raise ValueError("图片文件无法读取") from None
    return data


def _save_source_image(owner_id, image):
    digest = hashlib.sha256(image).hexdigest()
    path = _safe_root() / str(owner_id) / f"{digest}.bin"
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        path.write_bytes(image)
    return str(path), digest


def _delete_path(path):
    if not path:
        return
    try:
        safe = _safe_path(path)
        if safe.is_file():
            safe.unlink()
    except (OSError, ValueError):
        return


def _get_analysis(request, analysis_id):
    return ImageAnalysis.objects.filter(pk=analysis_id, owner_id=request.user_id).first()


@require_auth
def analyze(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error_message": "请求方法不支持"}, status=405)
    try:
        upload = request.FILES.get("image")
        image = _validate_image(upload)
        context = {
            "topic": request.POST.get("topic", ""),
            "page_content": request.POST.get("page_content", ""),
        }
        result = analyze_image(
            image,
            request.user_id,
            context=context,
            provider_name=request.POST.get("provider_name") or None,
        )
        path, digest = _save_source_image(request.user_id, image) if request.POST.get("save_source") == "1" else ("", "")
        row = ImageAnalysis.objects.create(
            owner_id=request.user_id,
            source_image_path=path,
            source_image_digest=digest,
            content=result["content"],
            layout=result["layout"],
            visual_style=result["visual_style"],
            rewritten_content=result["rewritten_content"],
        )
        return JsonResponse({"success": True, "analysis": _analysis_data(row)})
    except ValueError as error:
        return api_error_response(validation_error(str(error)), context={"endpoint": request.path})
    except Exception as error:
        return api_error_response(error, context={"endpoint": request.path})


@require_auth
def analysis_detail(request, analysis_id):
    row = _get_analysis(request, analysis_id)
    if not row:
        return api_error_response("图片分析记录不存在或无权访问", status=404)
    try:
        if request.method == "GET":
            return JsonResponse({"success": True, "analysis": _analysis_data(row)})
        if request.method == "PUT":
            data = json_body(request)
            if not isinstance(data, dict):
                raise ValueError("请求必须是 JSON 对象")
            normalized = normalize_analysis_payload(data)
            row.content = normalized["content"]
            row.layout = normalized["layout"]
            row.visual_style = normalized["visual_style"]
            row.rewritten_content = normalized["rewritten_content"]
            row.user_note = str(data.get("user_note") or "")[:2000]
            row.save()
            return JsonResponse({"success": True, "analysis": _analysis_data(row)})
        if request.method == "DELETE":
            _delete_path(row.source_image_path)
            row.delete()
            return JsonResponse({"success": True})
        return JsonResponse({"success": False, "error_message": "请求方法不支持"}, status=405)
    except ValueError as error:
        return api_error_response(validation_error(str(error)), context={"endpoint": request.path})


@require_auth
def apply_analysis(request, analysis_id):
    if request.method != "POST":
        return JsonResponse({"success": False, "error_message": "请求方法不支持"}, status=405)
    row = _get_analysis(request, analysis_id)
    if not row:
        return api_error_response("图片分析记录不存在或无权访问", status=404)
    data = json_body(request)
    if not isinstance(data, dict):
        return api_error_response(validation_error("请求必须是 JSON 对象"))
    parts = data.get("parts", [])
    mode = data.get("mode", "merge")
    if mode not in ("merge", "replace") or not isinstance(parts, list):
        return api_error_response(validation_error("应用方式或分析部分无效"))
    if any(part not in ("content", "layout", "visual_style") for part in parts):
        return api_error_response(validation_error("分析部分无效"))
    source = _analysis_data(row)
    return JsonResponse({
        "success": True,
        "applied": {
            "mode": mode,
            "parts": parts,
            **{part: source[part] for part in parts},
        },
    })


@require_auth
def assets(request):
    if request.method == "GET":
        rows = ReferenceAsset.objects.filter(owner_id=request.user_id)
        return JsonResponse({"success": True, "assets": [_asset_data(row) for row in rows]})
    if request.method != "POST":
        return JsonResponse({"success": False, "error_message": "请求方法不支持"}, status=405)
    try:
        data = json_body(request)
        if not isinstance(data, dict):
            raise ValueError("请求必须是 JSON 对象")
        analysis_id = data.get("analysis_id")
        analysis = _get_analysis(request, analysis_id) if analysis_id else None
        if analysis_id and not analysis:
            raise ValueError("图片分析记录不存在或无权访问")
        asset = ReferenceAsset.objects.create(
            owner_id=request.user_id,
            analysis=analysis,
            title=str(data.get("title") or "未命名参考素材")[:120],
            content=data.get("content") if isinstance(data.get("content"), dict) else (analysis.content if analysis else {}),
            rewritten_content=str(data.get("rewritten_content") or (analysis.rewritten_content if analysis else "")),
            user_note=str(data.get("user_note") or "")[:2000],
        )
        return JsonResponse({"success": True, "asset": _asset_data(asset)})
    except ValueError as error:
        return api_error_response(validation_error(str(error)), context={"endpoint": request.path})


@require_auth
def asset_detail(request, asset_id):
    row = ReferenceAsset.objects.filter(pk=asset_id, owner_id=request.user_id).first()
    if not row:
        return api_error_response("参考素材不存在或无权访问", status=404)
    if request.method == "GET":
        return JsonResponse({"success": True, "asset": _asset_data(row)})
    if request.method == "DELETE":
        _delete_path(row.image_path)
        row.delete()
        return JsonResponse({"success": True})
    if request.method != "PUT":
        return JsonResponse({"success": False, "error_message": "请求方法不支持"}, status=405)
    data = json_body(request)
    if not isinstance(data, dict):
        return api_error_response(validation_error("请求必须是 JSON 对象"))
    row.title = str(data.get("title", row.title))[:120]
    row.content = data.get("content", row.content) if isinstance(data.get("content", row.content), dict) else row.content
    row.rewritten_content = str(data.get("rewritten_content", row.rewritten_content))
    row.user_note = str(data.get("user_note", row.user_note))[:2000]
    row.save()
    return JsonResponse({"success": True, "asset": _asset_data(row)})


@require_auth
def asset_image(request, asset_id):
    row = ReferenceAsset.objects.filter(pk=asset_id, owner_id=request.user_id).first()
    if not row or not row.image_path:
        return api_error_response("参考图片不存在或无权访问", status=404)
    try:
        path = _safe_path(row.image_path)
        if not path.is_file():
            raise FileNotFoundError
        content_type = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
        response = FileResponse(path.open("rb"), content_type=content_type)
        response["Cache-Control"] = "private, no-store"
        return response
    except (FileNotFoundError, ValueError):
        return api_error_response("参考图片不存在或无权访问", status=404)


@require_auth
def create_prompts_from_analysis(request):
    if request.method != "POST":
        return JsonResponse({"success": False, "error_message": "请求方法不支持"}, status=405)
    data = json_body(request)
    if not isinstance(data, dict):
        return api_error_response(validation_error("请求必须是 JSON 对象"))
    row = _get_analysis(request, data.get("analysis_id"))
    if not row:
        return api_error_response("图片分析记录不存在或无权访问", status=404)
    parts = data.get("parts", [])
    if not isinstance(parts, list) or any(part not in ("layout", "visual_style") for part in parts):
        return api_error_response(validation_error("只能保存单页布局或图片风格提示词"))
    drafts = data.get("drafts") if isinstance(data.get("drafts"), dict) else {}
    names = data.get("names") if isinstance(data.get("names"), dict) else {}
    user = catalog.actor(request.user_id)
    entries = []
    for part, category in (("layout", "layout"), ("visual_style", "style")):
        if part not in parts:
            continue
        source = row.layout if part == "layout" else row.visual_style
        draft = drafts.get(part) if isinstance(drafts.get(part), dict) else {}
        content = str(draft.get("content") or source.get("prompt_text") or "").strip()
        if not content:
            raise ValueError("提示词内容不能为空")
        entry = catalog.save(user, {
            "module": "image",
            "category": category,
            "name": str(names.get(part) or ("图片布局参考" if part == "layout" else "图片风格参考"))[:50],
            "description": str(draft.get("description") or "由参考图片分析生成")[:500],
            "content": content,
            "metadata": {},
        })
        entries.append(entry)
    return JsonResponse({"success": True, "entries": entries})
