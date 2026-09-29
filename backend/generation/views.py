"""
图片/大纲/文案生成 API 视图（对应 Flask 版 outline_routes.py / content_routes.py / image_routes.py）。

包含接口：
- POST /api/outline          生成大纲（支持 multipart 图片 / JSON base64 图片）
- POST /api/content          生成标题/文案/标签
- POST /api/generate         批量生成图片（SSE 流式）
- GET  /api/images/<task_id>/<filename>   获取图片（含缩略图）
- POST /api/retry            重试单张图片
- POST /api/retry-failed     批量重试失败图片（SSE 流式）
- POST /api/regenerate       重新生成单张图片
- GET  /api/task/<task_id>   获取任务状态
- GET  /api/health           健康检查
"""
import base64
import json
import logging
import os
import re
import mimetypes

from django.http import FileResponse, JsonResponse, StreamingHttpResponse

from common.api import (api_error_response, json_body, log_request,
                        normalize_error_result, require_auth, validation_error)
from common.errors import ensure_app_error
from prompts.services import resolve_prompt_text
from prompts.catalog_runtime import base as catalog_base, snapshot as catalog_snapshot
from .catalog import catalog_request

from .services.content import get_content_service
from .services.image import ImageService, get_image_service
from .styles import request_style, style_prompt, validate_image_pages
from .diagnostics import read as read_diagnostics, capture, record as record_diagnostic, sanitize
from .consistency import check_content_image_consistency
from .parameters import apply_image_parameters
from .services.task_cancel import cancel_user
from .services.outline import get_outline_service
from history.services import get_history_service
from history.models import HistoryRecord
from history.permissions import actor, can_modify, can_read, private_view, source_file, task_records
from .outline_prompt import preferences, build_outline_prompt, expression_instruction
from .generation_context import audit_context, build_generation_context
from .models import OutlineRun
from .models import ContentRun
from .content_diagnostics import finish as finish_content_run
from .outline_inspection import reference_summaries, serialize as serialize_outline_run
from .reference_roles import reference_instruction
from .styles import FrozenImageTemplate
from .reference_images import (
    MAX_REFERENCE_IMAGE_BYTES, MAX_REFERENCE_DATA_URL_LENGTH, REFERENCE_IMAGE_TYPES,
    validate_reference_count, validate_reference_image,
)

logger = logging.getLogger(__name__)

_JSON_PARAMS = {"ensure_ascii": False}

def _reference_template(template, data, record_id=None):
    record = HistoryRecord.objects.filter(pk=record_id).first() if record_id else None
    saved = (record.outline or {}).get("creation_inputs") or {} if record else {}
    references = data.get("user_images")
    if references is None:
        references = [item["data"] for item in saved.get("reference_images", [])]
    roles = data.get("reference_roles")
    if roles is None:
        roles = saved.get("reference_roles", [])
    from .palettes import image_reference_roles
    context = getattr(template, "generation_context", None) or {}
    style = (context.get("visual") or {}).get("image_style") or data.get("image_style") or {}
    roles = image_reference_roles(style, roles)
    return FrozenImageTemplate(
        str(template).replace("参考图只保留必要的主体关系，按最终风格重新绘制。",
                              "参考图仅按用户选定维度使用。") + reference_instruction(len(references), roles),
        generation_context=getattr(template, "generation_context", None),
    )

def _image_generation_context(data, topic, outline, image_style, record_id=None, page=None):
    generation_preferences = data.get("generation_preferences") or {}
    if not generation_preferences and record_id:
        record = HistoryRecord.objects.filter(pk=record_id).first()
        stored_outline = record.outline if record else {}
        if isinstance(stored_outline, dict):
            generation_preferences = stored_outline.get("generation_preferences") or {}
    return build_generation_context(
        topic,
        outline,
        generation_preferences,
        data.get("copy_preferences") or {},
        image_style,
        page=page,
    )


# ==================== 大纲生成 ====================

@require_auth
@catalog_request
def generate_outline(request):
    """POST /api/outline 生成大纲（支持图片上传）"""
    run = None
    try:
        # 解析请求数据
        topic, reference_content, images = _parse_outline_request(request)
        raw_roles = request.POST.get('reference_roles', '[]') if request.content_type and 'multipart' in request.content_type else (json_body(request).get('reference_roles', []))
        try:
            reference_roles = json.loads(raw_roles) if isinstance(raw_roles, str) else raw_roles
        except (TypeError, ValueError):
            raise ValueError("参考内容选项格式无效，请重新选择。") from None
        prompt_name = _outline_prompt_name(request)
        provider_name = _outline_provider_name(request) or None
        data = request.POST if request.content_type and 'multipart/form-data' in request.content_type else json_body(request)
        options = preferences(data)
        options_for_storage = {key: value for key, value in options.items() if not key.startswith("_")}
        prompt_text = build_outline_prompt(topic, reference_content, len(images or []), options, reference_roles=reference_roles)
        run = OutlineRun.objects.create(user_id=request.user_id, prompt=prompt_text,
            preferences={**options_for_storage, "reference_roles": reference_roles, "catalog_snapshot": catalog_snapshot()},
            references=reference_summaries(images or []), provider=provider_name or "")
        diagnostic_id = f"outline-{run.pk}"
        record_diagnostic(diagnostic_id, sanitize({
            "event": "request", "source": "local", "phase": "outline",
            "prompt": prompt_text, "provider": provider_name or "active",
            "parameters": options,
            "references": [{"bytes": len(image)} for image in images or []],
        }))

        def on_send(prompt, model):
            run.prompt = prompt
            run.model = model
            run.sent = True
            run.status = "generating"
            run.save(update_fields=["prompt", "model", "sent", "status"])

        log_request('/outline', {
            'topic': topic,
            'images': images,
            'prompt_name': prompt_name,
            'reference_content': (reference_content or '')[:200],
        })

        # 验证必填参数
        if not topic:
            logger.warning("大纲生成请求缺少 topic 参数")
            return api_error_response(
                validation_error("topic 不能为空", "请输入要生成图文的主题内容。"),
                context={"endpoint": "/api/outline"},
            )

        # 调用大纲生成服务
        logger.info(f"🔄 开始生成大纲，主题: {topic[:50]}...")
        with capture(diagnostic_id, 0):
            outline_service = get_outline_service(request.user_id)
            result = outline_service.generate_outline(
                topic,
                images if images else None,
                prepared_prompt=prompt_text,
                options=options,
                on_send=on_send,
                reference_content=reference_content,
                provider_name=provider_name,
                organization=options["organization"],
            )
        run.status = "succeeded" if result.get("success") else "cancelled" if result.get("cancelled") else "failed"
        run.save(update_fields=["status"])
        record_diagnostic(diagnostic_id, sanitize({
            "event": "response", "source": "local", "phase": "outline",
            "status": run.status, "model": run.model,
            "error": result.get("error"), "page_count": len(result.get("pages", [])),
        }))
        result["generation_record"] = serialize_outline_run(run)
        from .generation_context import effective_preferences
        effective = effective_preferences(options, result.get("growth_recommendation"))
        if result.get("success"):
            from .recommendations import (
                resolve_adopted_audience, resolve_adopted_tone,
                resolve_adopted_outline_modes,
            )
            effective = resolve_adopted_audience(effective, result.get("generation_recommendation"))
            effective = resolve_adopted_tone(effective, result.get("generation_recommendation"))
            effective = resolve_adopted_outline_modes(effective, result.get("generation_recommendation"))
            if effective.get("content_form") == "single_infographic" and effective.get("page_count") == "auto":
                effective["page_count"] = 1
        if result.get("success") and options.get("organization") == "自动":
            from prompts.catalog_runtime import option
            try:
                selected = option("outline", "organization", result.get("organization", "自动"))
                effective["organization"] = selected.get("legacy_value") or selected["id"]
            except ValueError:
                effective["organization"] = "自动"
        effective = {key: value for key, value in effective.items() if not key.startswith("_")}
        result["requested_preferences"] = options_for_storage
        result["generation_preferences"] = effective
        if result.get("success"):
            from .recommendations import attach_outline_explanation
            attach_outline_explanation(result, options)
        outline_context = build_generation_context(topic, result.get("outline", ""), options, {}, {})
        result["generation_audit"] = {
            "context": outline_context,
            "effective": {
                "platform": effective.get("platform", "auto"),
                "goal": effective.get("goal", "auto"),
                "content_form": effective.get("content_form", "auto"),
                "information_density": effective.get("information_density", "auto"),
                "auto_recommended": options.get("platform", "auto") == "auto"
                    or options.get("goal", "auto") == "auto"
                    or options.get("content_form", "auto") == "auto"
                    or options.get("information_density", "auto") == "auto",
            },
            "prompts": [{
                "phase": "outline",
                "prompt_name": prompt_name or "outline",
                "used_fields": [item["field"] for item in audit_context(outline_context)
                                if item["phase"] == "outline" and item["applied"]],
                "rules": [outline_context["prompt_rules"]["outline"]],
                "verification": "prompt_compiled",
                "output_verified": False,
            }],
        }

        # 记录结果
        if result["success"]:
            logger.info(f"✅ 大纲生成成功，共 {len(result.get('pages', []))} 页")
            return JsonResponse(result, status=200, json_dumps_params=_JSON_PARAMS)
        else:
            logger.error(f"❌ 大纲生成失败: {result.get('error', '未知错误')}")
            result = normalize_error_result(
                result,
                context={"endpoint": "/api/outline"},
                fallback_status=500,
            )
            return JsonResponse(result, status=result["error"].get("status", 500),
                                json_dumps_params=_JSON_PARAMS)

    except Exception as e:
        safe_error = sanitize(str(e))
        if run:
            run.status = "failed"
            run.save(update_fields=["status"])
            record_diagnostic(f"outline-{run.pk}", {
                "event": "response", "source": "local", "phase": "outline",
                "status": "failed", "error": safe_error,
            })
            result = normalize_error_result({
                "success": False, "error": safe_error,
                "generation_record": serialize_outline_run(run),
            }, context={"endpoint": "/api/outline"})
            return JsonResponse(result, status=result["error"]["status"], json_dumps_params=_JSON_PARAMS)
        logger.error(f"大纲生成异常: {safe_error}")
        if isinstance(e, (ValueError, TypeError)):
            return api_error_response(
                validation_error("大纲输入无效", safe_error),
                context={"endpoint": "/api/outline"},
            )
        return api_error_response(safe_error, context={"endpoint": "/api/outline"})


def _parse_outline_request(request):
    """
    解析大纲生成请求

    支持两种格式：
    1. multipart/form-data - 用于文件上传
    2. application/json - 用于 base64 图片

    返回：
        tuple: (topic, reference_content, images) - 主题、参考内容文本和图片列表
    """
    # 检查是否是 multipart/form-data（带图片文件）
    if request.content_type and 'multipart/form-data' in request.content_type:
        topic = request.POST.get('topic')
        reference_content = (request.POST.get('reference_content') or '').strip()
        images = []

        # 获取上传的图片文件
        if 'images' in request.FILES:
            files = request.FILES.getlist('images')
            validate_reference_count(len(files))
            for file in files:
                if file and file.name:
                    if file.size > MAX_REFERENCE_IMAGE_BYTES:
                        raise ValueError("参考图片每张不超过5 MiB。")
                    image_data = file.read(MAX_REFERENCE_IMAGE_BYTES + 1)
                    validate_reference_image(image_data, file.content_type)
                    images.append(image_data)

        return topic, reference_content, images

    # JSON 请求（无图片或 base64 图片）
    data = json_body(request)
    topic = data.get('topic')
    reference_content = (data.get('reference_content') or '').strip()
    images = []

    # 支持 base64 格式的图片
    images_base64 = data.get('images', [])
    if not isinstance(images_base64, list):
        raise ValueError("参考图片格式无效。")
    validate_reference_count(len(images_base64))
    if images_base64:
        for img_b64 in images_base64:
            if not isinstance(img_b64, str) or len(img_b64) > MAX_REFERENCE_DATA_URL_LENGTH:
                raise ValueError("参考图片每张不超过5 MiB。")
            expected_type = None
            if ',' in img_b64:
                header, img_b64 = img_b64.split(',', 1)
                if header not in tuple(f"data:{mime};base64" for mime in REFERENCE_IMAGE_TYPES):
                    raise ValueError("参考图片格式无效，仅支持 JPEG、PNG 或 WebP。")
                expected_type = header[5:-7]
            try:
                binary = base64.b64decode(img_b64, validate=True)
            except ValueError:
                raise ValueError("参考图片编码无效。") from None
            validate_reference_image(binary, expected_type)
            images.append(binary)

    return topic, reference_content, images


def _outline_prompt_name(request) -> str:
    """从 outline 请求中读取提示词名称（兼容 multipart 和 JSON）。"""
    if request.content_type and 'multipart/form-data' in request.content_type:
        return (request.POST.get('prompt_name') or '').strip()
    data = json_body(request)
    return (data.get('prompt_name') or '').strip()


def _outline_provider_name(request) -> str:
    """从 outline 请求中读取用户选择的模型（服务商）名称（兼容 multipart 和 JSON）。"""
    if request.content_type and 'multipart/form-data' in request.content_type:
        return (request.POST.get('provider_name') or '').strip()
    data = json_body(request)
    return (data.get('provider_name') or '').strip()


# ==================== 内容生成 ====================

@require_auth
@catalog_request
def generate_content(request):
    """POST /api/content 生成标题、文案、标签"""
    run = None
    try:
        data = json_body(request)
        topic = data.get('topic', '')
        outline = data.get('outline', '')
        prompt_name = data.get('prompt_name') or ''
        provider_name = (data.get('provider_name') or '').strip() or None
        from .copy_prompt import build_copy_prompt
        try:
            prompt_text, copy_options, _ = build_copy_prompt(data)
        except (ValueError, TypeError, AttributeError) as error:
            return api_error_response(str(error), status=400)

        log_request('/content', {
            'topic': topic[:50] if topic else '',
            'outline_length': len(outline),
            'prompt_name': prompt_name,
            'provider_name': provider_name,
        })

        # 验证必填参数
        if not topic:
            logger.warning("内容生成请求缺少 topic 参数")
            return api_error_response(
                validation_error("topic 不能为空", "请输入主题内容。"),
                context={"endpoint": "/api/content"},
            )

        if not outline:
            logger.warning("内容生成请求缺少 outline 参数")
            return api_error_response(
                validation_error("outline 不能为空", "请先生成大纲。"),
                context={"endpoint": "/api/content"},
            )

        # 调用内容生成服务
        logger.info(f"🔄 开始生成内容，主题: {topic[:50]}...")
        run = ContentRun.objects.create(user_id=request.user_id, prompt=prompt_text,
            provider=provider_name or "", preferences={
                "copy": copy_options, "generation": data.get("generation_preferences"),
                "catalog_snapshot": catalog_snapshot(),
            })
        diagnostic_id = f"content-{run.pk}"
        record_diagnostic(diagnostic_id, {
            "event": "request", "source": "local", "phase": "content",
            "prompt": prompt_text, "provider": provider_name or "active", "parameters": run.preferences,
        })
        with capture(diagnostic_id, 0):
            content_service = get_content_service(request.user_id)
            result = content_service.generate_content(topic, outline, prepared_prompt=prompt_text, provider_name=provider_name)
        if result.get("success"):
            from .copy_validation import validate_copy_result
            try:
                result["validation"] = validate_copy_result(result, copy_options)
            except ValueError as error:
                return finish_content_run(run, api_error_response(str(error), status=422))

        # 记录结果
        if result["success"]:
            logger.info(f"✅ 内容生成成功")
            return finish_content_run(run, JsonResponse(result, status=200, json_dumps_params=_JSON_PARAMS))
        else:
            logger.error(f"❌ 内容生成失败: {result.get('error', '未知错误')}")
            result = normalize_error_result(
                result,
                context={"endpoint": "/api/content"},
                fallback_status=500,
            )
            return finish_content_run(run, JsonResponse(result, status=result["error"].get("status", 500),
                                json_dumps_params=_JSON_PARAMS))

    except Exception as e:
        logger.error(f"内容生成异常: {e}")
        return finish_content_run(run, api_error_response(e, context={"endpoint": "/api/content"}))


# ==================== 图片生成 ====================

@require_auth
def cancel_generation(request):
    """POST /api/generate/cancel 真正取消当前用户的生成任务。

    图片生成会立即停止调度后续页面；大纲/文案生成完成后结果作废、不落历史。
    """
    try:
        user_id = request.user_id
        cancel_user(user_id)
        logger.info("用户 %s 已取消当前生成任务", user_id)
        return JsonResponse({"success": True, "message": "已取消"}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/generate/cancel"})


@require_auth
@catalog_request
def generate_images(request):
    """POST /api/generate 批量生成图片（SSE 流式返回）"""
    try:
        data = json_body(request)
        pages = data.get('pages')
        use_reference = data.get('use_reference', True)
        task_id = data.get('task_id')
        record_id = data.get('record_id')
        use_reference = data.get('use_reference', True)
        denied = _generation_denied(request, task_id, record_id)
        if denied is not None:
            return denied
        force = bool(data.get('force', False))
        full_outline = data.get('full_outline', '')
        user_topic = data.get('user_topic', '')
        use_reference = data.get('use_reference', True)

        # 解析 base64 格式的用户参考图片
        user_images = _parse_base64_images(data.get('user_images', []))

        log_request('/generate', {
            'pages_count': len(pages) if pages else 0,
            'task_id': task_id,
            'record_id': record_id,
            'force': force,
            'user_topic': user_topic[:50] if user_topic else None,
            'user_images': user_images,
        })

        if not pages:
            logger.warning("图片生成请求缺少 pages 参数")
            return api_error_response(
                validation_error("pages 不能为空", "请提供要生成的页面列表数据。"),
                context={"endpoint": "/api/generate", "record_id": record_id},
            )

        logger.info(f"🖼️  开始图片生成任务: {task_id}, 共 {len(pages)} 页")
        # 在请求上下文内先取出用户 ID，SSE 生成器惰性执行时 request 已不可用
        user_id = _task_owner_user_id(task_id, record_id, request.user_id)
        image_prompt_name = data.get('image_prompt_name') or ''
        image_provider_name = (data.get('provider_name') or '').strip() or None
        image_prompt_text = catalog_base('image')
        try:
            selected_style = request_style(data, record_id, task_id)
            context = _image_generation_context(
                data,
                user_topic,
                full_outline,
                selected_style,
                record_id=record_id,
            )
            image_prompt_text = style_prompt(
                image_prompt_text,
                selected_style,
                generation_context=context,
            )
            validate_image_pages(image_prompt_text, pages)
            image_prompt_text = _reference_template(image_prompt_text, data, record_id)
        except ValueError as error:
            return api_error_response(str(error), status=400)
        # 用户选择模型（服务商）时按指定服务商创建实例，否则使用当前激活服务商
        image_service = ImageService(image_provider_name, user_id) if image_provider_name else get_image_service(user_id)
        image_service = apply_image_parameters(image_service, data.get('image_parameters'))

        def generate():
            """SSE 事件生成器"""
            for event in image_service.generate_images(
                pages, task_id, full_outline,
                user_images=user_images if user_images else None,
                user_topic=user_topic,
                record_id=record_id,
                force=force,
                user_id=user_id,
                image_prompt_text=image_prompt_text,
                use_reference=use_reference,
            ):
                event_type = event["event"]
                if event_type == 'complete' and record_id:
                    choice = {key: selected_style[key] for key in ('preset', 'notes', 'palette') if key in selected_style}
                    record = HistoryRecord.objects.filter(pk=record_id).first()
                    if record:
                        HistoryRecord.objects.filter(pk=record_id).update(
                            image_style={**(record.image_style or {}), 'applied': choice})
                event_data = _normalize_sse_error(
                    event_type,
                    event["data"],
                    {
                        "endpoint": "/api/generate",
                        "task_id": task_id,
                        "record_id": record_id,
                    },
                )

                # 格式化为 SSE 格式
                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    except Exception as e:
        logger.error(f"图片生成异常: {e}")
        return api_error_response(e, context={"endpoint": "/api/generate"})


# ==================== 图片获取 ====================

@private_view
@require_auth
def get_image(request, task_id, filename):
    """GET /api/images/<task_id>/<filename> 获取图片文件"""
    try:
        logger.debug(f"获取图片: {task_id}/{filename}")

        # 检查是否请求缩略图
        thumbnail = request.GET.get('thumbnail', 'true').lower() == 'true'

        # 归属校验：任务属于当前用户或管理员
        user = actor(request.user_id)
        record = next((record for record in task_records(task_id)
                       if can_read(user, record) and source_file(record, filename)), None)
        if record is None:
            return api_error_response(
                "无权访问该图片",
                status=403,
                context={"endpoint": "/api/images", "task_id": task_id, "filename": filename},
            )

        filepath = source_file(record, filename)

        if thumbnail:
            # 尝试返回缩略图
            thumb_filepath = filepath.with_name(f"thumb_{filename}")
            if thumb_filepath.resolve() == thumb_filepath and thumb_filepath.is_file():
                return FileResponse(open(thumb_filepath, 'rb'), content_type=mimetypes.guess_type(str(thumb_filepath))[0] or 'image/png')

        # 返回原图
        if not os.path.exists(filepath):
            return api_error_response(
                "图片不存在",
                status=404,
                context={"endpoint": "/api/images", "task_id": task_id, "filename": filename},
            )

        return FileResponse(open(filepath, 'rb'), content_type=mimetypes.guess_type(str(filepath))[0] or 'image/png')

    except Exception as e:
        logger.error(f"获取图片异常: {e}")
        return api_error_response(e, context={"endpoint": "/api/images", "task_id": task_id, "filename": filename})


# ==================== 重试和重新生成 ====================

@require_auth
@catalog_request
def retry_single_image(request):
    """POST /api/retry 重试生成单张失败的图片"""
    try:
        data = json_body(request)
        task_id = data.get('task_id')
        page = data.get('page')
        use_reference = data.get('use_reference', True)
        record_id = data.get('record_id')
        denied = _generation_denied(request, task_id, record_id)
        if denied is not None:
            return denied

        log_request('/retry', {
            'task_id': task_id,
            'record_id': record_id,
            'page_index': page.get('index') if page else None
        })

        if not task_id or not page:
            logger.warning("重试请求缺少必要参数")
            return api_error_response(
                validation_error("task_id 和 page 不能为空", "请提供任务 ID 和页面信息。"),
                context={"endpoint": "/api/retry", "task_id": task_id, "record_id": record_id},
            )

        logger.info(f"🔄 重试生成图片: task={task_id}, page={page.get('index')}")
        # 重试时归属用任务/记录的归属者（防止 admin 替别人补图写错目录）
        owner_user_id = _task_owner_user_id(task_id, record_id, request.user_id)
        image_prompt_name = data.get('image_prompt_name') or ''
        image_provider_name = (data.get('provider_name') or '').strip() or None
        image_prompt_text = catalog_base('image')
        try:
            selected_style = request_style(data, record_id, task_id)
            context = _image_generation_context(
                data,
                data.get("user_topic", ""),
                data.get("full_outline", ""),
                selected_style,
                record_id=record_id,
                page=page,
            )
            image_prompt_text = style_prompt(
                image_prompt_text,
                selected_style,
                generation_context=context,
            )
            validate_image_pages(image_prompt_text, [page])
            image_prompt_text = _reference_template(image_prompt_text, data, record_id)
        except ValueError as error:
            return api_error_response(str(error), status=400)
        # 用户选择模型（服务商）时按指定服务商创建实例，否则使用当前激活服务商
        image_service = ImageService(image_provider_name, owner_user_id) if image_provider_name else get_image_service(owner_user_id)
        image_service = apply_image_parameters(image_service, data.get('image_parameters'))
        result = image_service.retry_single_image(
            task_id,
            page,
            use_reference,
            record_id=record_id,
            user_id=owner_user_id,
            image_prompt_text=image_prompt_text,
        )

        if result["success"]:
            logger.info(f"✅ 图片重试成功: {result.get('image_url')}")
        else:
            logger.error(f"❌ 图片重试失败: {result.get('error')}")
            result = normalize_error_result(
                result,
                context={"endpoint": "/api/retry", "task_id": task_id, "record_id": record_id},
                fallback_status=500,
            )

        return JsonResponse(result, status=200 if result["success"] else result["error"].get("status", 500),
                            json_dumps_params=_JSON_PARAMS)

    except Exception as e:
        logger.error(f"重试图片异常: {e}")
        return api_error_response(e, context={"endpoint": "/api/retry"})


@require_auth
@catalog_request
def retry_failed_images(request):
    """POST /api/retry-failed 批量重试失败的图片（SSE 流式返回）"""
    try:
        data = json_body(request)
        task_id = data.get('task_id')
        pages = data.get('pages')
        record_id = data.get('record_id')
        use_reference = data.get('use_reference', True)
        denied = _generation_denied(request, task_id, record_id)
        if denied is not None:
            return denied

        log_request('/retry-failed', {
            'task_id': task_id,
            'record_id': record_id,
            'pages_count': len(pages) if pages else 0
        })

        if not task_id or not pages:
            logger.warning("批量重试请求缺少必要参数")
            return api_error_response(
                validation_error("task_id 和 pages 不能为空", "请提供任务 ID 和要重试的页面列表。"),
                context={"endpoint": "/api/retry-failed", "task_id": task_id, "record_id": record_id},
            )

        logger.info(f"🔄 批量重试失败图片: task={task_id}, 共 {len(pages)} 页")
        # 在请求上下文内先取出归属用户 ID，SSE 生成器惰性执行时 request 已不可用
        owner_user_id = _task_owner_user_id(task_id, record_id, request.user_id)
        image_prompt_name = data.get('image_prompt_name') or ''
        image_provider_name = (data.get('provider_name') or '').strip() or None
        image_prompt_text = catalog_base('image')
        try:
            selected_style = request_style(data, record_id, task_id)
            context = _image_generation_context(
                data,
                data.get("user_topic", ""),
                data.get("full_outline", ""),
                selected_style,
                record_id=record_id,
            )
            image_prompt_text = style_prompt(
                image_prompt_text,
                selected_style,
                generation_context=context,
            )
            validate_image_pages(image_prompt_text, pages)
            image_prompt_text = _reference_template(image_prompt_text, data, record_id)
        except ValueError as error:
            return api_error_response(str(error), status=400)
        # 用户选择模型（服务商）时按指定服务商创建实例，否则使用当前激活服务商
        image_service = ImageService(image_provider_name, owner_user_id) if image_provider_name else get_image_service(owner_user_id)

        image_service = apply_image_parameters(image_service, data.get('image_parameters'))

        def generate():
            """SSE 事件生成器"""
            for event in image_service.retry_failed_images(
                task_id, pages, record_id=record_id, user_id=owner_user_id,
                image_prompt_text=image_prompt_text,
                use_reference=use_reference,
            ):
                event_type = event["event"]
                event_data = _normalize_sse_error(
                    event_type,
                    event["data"],
                    {
                        "endpoint": "/api/retry-failed",
                        "task_id": task_id,
                        "record_id": record_id,
                    },
                )

                yield f"event: {event_type}\n"
                yield f"data: {json.dumps(event_data, ensure_ascii=False)}\n\n"

        response = StreamingHttpResponse(generate(), content_type='text/event-stream')
        response['Cache-Control'] = 'no-cache'
        response['X-Accel-Buffering'] = 'no'
        return response

    except Exception as e:
        logger.error(f"批量重试图片异常: {e}")
        return api_error_response(e, context={"endpoint": "/api/retry-failed"})


@require_auth
@catalog_request
def regenerate_image(request):
    """POST /api/regenerate 重新生成图片（即使成功的也可以重新生成）"""
    try:
        data = json_body(request)
        task_id = data.get('task_id')
        page = data.get('page')
        use_reference = data.get('use_reference', True)
        full_outline = data.get('full_outline', '')
        user_topic = data.get('user_topic', '')
        record_id = data.get('record_id')
        denied = _generation_denied(request, task_id, record_id)
        if denied is not None:
            return denied

        log_request('/regenerate', {
            'task_id': task_id,
            'record_id': record_id,
            'page_index': page.get('index') if page else None
        })

        if not task_id or not page:
            logger.warning("重新生成请求缺少必要参数")
            return api_error_response(
                validation_error("task_id 和 page 不能为空", "请提供任务 ID 和页面信息。"),
                context={"endpoint": "/api/regenerate", "task_id": task_id, "record_id": record_id},
            )

        logger.info(f"🔄 重新生成图片: task={task_id}, page={page.get('index')}")
        # 重绘时归属用任务/记录的归属者（防止 admin 替别人补图写错目录）
        owner_user_id = _task_owner_user_id(task_id, record_id, request.user_id)
        image_prompt_name = data.get('image_prompt_name') or ''
        image_provider_name = (data.get('provider_name') or '').strip() or None
        image_prompt_text = catalog_base('image')
        try:
            selected_style = request_style(data, record_id, task_id)
            context = _image_generation_context(
                data,
                data.get("user_topic", ""),
                data.get("full_outline", ""),
                selected_style,
                record_id=record_id,
                page=page,
            )
            image_prompt_text = style_prompt(
                image_prompt_text,
                selected_style,
                generation_context=context,
            )
            validate_image_pages(image_prompt_text, [page])
            image_prompt_text = _reference_template(image_prompt_text, data, record_id)
        except ValueError as error:
            return api_error_response(str(error), status=400)
        # 用户选择模型（服务商）时按指定服务商创建实例，否则使用当前激活服务商
        image_service = ImageService(image_provider_name, owner_user_id) if image_provider_name else get_image_service(owner_user_id)
        image_service = apply_image_parameters(image_service, data.get('image_parameters'))
        result = image_service.regenerate_image(
            task_id, page, use_reference,
            full_outline=full_outline,
            user_topic=user_topic,
            record_id=record_id,
            user_id=owner_user_id,
            image_prompt_text=image_prompt_text,
            user_images=_parse_base64_images(data["user_images"]) if "user_images" in data else None,
        )

        if result["success"]:
            logger.info(f"✅ 图片重新生成成功: {result.get('image_url')}")
        else:
            logger.error(f"❌ 图片重新生成失败: {result.get('error')}")
            result = normalize_error_result(
                result,
                context={"endpoint": "/api/regenerate", "task_id": task_id, "record_id": record_id},
                fallback_status=500,
            )

        return JsonResponse(result, status=200 if result["success"] else result["error"].get("status", 500),
                            json_dumps_params=_JSON_PARAMS)

    except Exception as e:
        logger.error(f"重新生成图片异常: {e}")
        return api_error_response(e, context={"endpoint": "/api/regenerate"})


# ==================== 任务状态 ====================

@private_view
@require_auth
def get_task_state(request, task_id):
    """GET /api/task/<task_id> 获取任务状态"""
    try:
        denied = _generation_denied(request, task_id)
        if denied is not None:
            return denied
        image_service = get_image_service(request.user_id)
        state = image_service.get_task_state(task_id)

        if state is None:
            return api_error_response(
                f"任务不存在：{task_id}",
                status=404,
                context={"endpoint": "/api/task", "task_id": task_id},
            )

        # 不返回封面图片数据（太大）
        safe_state = {
            "generated": state.get("generated", {}),
            "failed": state.get("failed", {}),
            "has_cover": state.get("cover_image") is not None
        }

        return JsonResponse({
            "success": True,
            "state": safe_state
        }, status=200, json_dumps_params=_JSON_PARAMS)

    except Exception as e:
        logger.error(f"获取任务状态异常: {e}")
        return api_error_response(e, context={"endpoint": "/api/task", "task_id": task_id})


@require_auth
def get_diagnostics(request, task_id):
    denied = _generation_denied(request, task_id)
    if denied is not None:
        return denied
    page_index = request.GET.get("page_index")
    generation_id = request.GET.get("generation_id")
    events = read_diagnostics(task_id)
    if page_index is not None:
        try:
            events = [event for event in events if event.get("page_index") == int(page_index)]
        except ValueError:
            return api_error_response("页面索引无效。", status=400)
    if generation_id:
        events = [event for event in events if event.get("generation_id") == generation_id]
    return JsonResponse({"success": True, "task_id": task_id, "events": events},
                        json_dumps_params={"ensure_ascii": False})


@private_view
@require_auth
def get_consistency(request, task_id):
    """GET /api/generation/consistency/<task_id>."""
    denied = _generation_denied(request, task_id)
    if denied is not None:
        return denied
    user = actor(request.user_id)
    record = next(
        (item for item in task_records(task_id) if can_read(user, item)),
        None,
    )
    if record is None:
        return api_error_response("无权访问该任务。", status=403,
                                  context={"endpoint": "/api/generation/consistency",
                                           "task_id": task_id})
    outline = record.outline or {}
    pages = outline.get("pages", []) if isinstance(outline, dict) else []
    images = []
    for event in read_diagnostics(task_id):
        if event.get("event") != "request" or not event.get("prompt"):
            continue
        images.append({
            "index": event.get("page_index"),
            "prompt": event.get("prompt"),
        })
    result = check_content_image_consistency(
        record.title,
        pages,
        images,
        outline.get("generation_preferences", {}) if isinstance(outline, dict) else {},
    )
    return JsonResponse({"success": True, "task_id": task_id, "result": result},
                        json_dumps_params={"ensure_ascii": False})


# ==================== 健康检查 ====================

def health_check(request):
    """GET /api/health 健康检查接口"""
    return JsonResponse({
        "success": True,
        "message": "服务正常运行"
    }, status=200)


# ==================== 辅助函数 ====================

def _generation_denied(request, task_id=None, record_id=None):
    """Check both identifiers before loading owner prompts, providers, or tasks."""
    user = actor(request.user_id)
    record = None
    if task_id is not None and (
        not isinstance(task_id, str) or not re.fullmatch(r'[A-Za-z0-9_-]+', task_id)
    ):
        return api_error_response('任务 ID 无效。', status=400)
    if record_id:
        record = HistoryRecord.objects.filter(pk=record_id).first()
        if record is None:
            return api_error_response('作品不存在。', status=404)
        if not can_modify(user, record):
            return api_error_response('无权修改该作品。', status=403)
        existing_task = (record.images or {}).get('task_id')
        if task_id and existing_task and task_id != existing_task:
            return api_error_response('任务不属于该作品。', status=400)
        task_id = task_id or existing_task
        if task_id and (not isinstance(task_id, str)
                        or not re.fullmatch(r'[A-Za-z0-9_-]+', task_id)):
            return api_error_response('任务 ID 无效。', status=400)
    if task_id:
        records = list(task_records(task_id))
        if any(not can_modify(user, item) for item in records):
            return api_error_response('无权修改该任务。', status=403)
        if record and records and any(item.user_id != record.user_id for item in records):
            return api_error_response('任务不属于该作品。', status=400)
    if request.method == 'POST':
        data = json_body(request)
        pages = data.get('pages', [])
        if 'page' in data:
            pages = [data['page']]
        if not isinstance(pages, list) or any(
            not isinstance(page, dict) or type(page.get('index')) is not int or page['index'] < 0
            for page in pages
        ):
            return api_error_response('页面索引无效。', status=400)
    return None

def _find_task_owner(task_id: str):
    """通过历史记录反查任务归属的用户 ID（用于图片目录按用户隔离）"""
    try:
        return get_history_service().find_owner_by_task(task_id)
    except Exception:
        return None


def _task_owner_user_id(task_id: str, record_id=None, fallback=None):
    """确定任务归属用户：优先任务/记录的实际归属者，其次请求用户。

    用于重试/重绘时选择按归属者加载的 ImageService（配置与目录都归属记录者）。
    """
    try:
        owner = get_history_service().find_owner_by_task(task_id)
        if owner:
            return owner
    except Exception:
        pass
    if record_id:
        try:
            rec = get_history_service().get_record(record_id)
            if rec and rec.get('user_id'):
                return rec['user_id']
        except Exception:
            pass
    return fallback


def _parse_base64_images(images_base64: list) -> list:
    """
    解析 base64 编码的图片列表

    Args:
        images_base64: base64 编码的图片字符串列表

    Returns:
        list: 解码后的图片二进制数据列表
    """
    if not images_base64:
        return []

    images = []
    for img_b64 in images_base64:
        # 移除可能的 data URL 前缀（如 data:image/png;base64,）
        if ',' in img_b64:
            img_b64 = img_b64.split(',')[1]
        images.append(base64.b64decode(img_b64))

    return images


def _normalize_sse_error(event_type: str, data: dict, context: dict) -> dict:
    if event_type != "error":
        return data

    next_data = dict(data)
    if isinstance(next_data.get("error"), dict):
        return next_data

    app_error = ensure_app_error(
        next_data.get("error") or next_data.get("message") or "图片生成失败",
        context=context,
    )
    next_data["error"] = app_error.to_dict()
    next_data["message"] = app_error.to_message()
    next_data["retryable"] = bool(next_data.get("retryable", app_error.retryable))
    return next_data
