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

from django.conf import settings
from django.http import FileResponse, JsonResponse, StreamingHttpResponse

from common.api import (api_error_response, json_body, log_request,
                        normalize_error_result, require_auth, validation_error)
from common.errors import ensure_app_error
from prompts.services import resolve_prompt_text

from .services.content import get_content_service
from .services.image import ImageService, get_image_service
from .services.task_cancel import cancel_user
from .services.outline import get_outline_service
from history.services import get_history_service

logger = logging.getLogger(__name__)

_JSON_PARAMS = {"ensure_ascii": False}


# ==================== 大纲生成 ====================

@require_auth
def generate_outline(request):
    """POST /api/outline 生成大纲（支持图片上传）"""
    try:
        # 解析请求数据
        topic, reference_content, images = _parse_outline_request(request)
        prompt_name = _outline_prompt_name(request)
        provider_name = _outline_provider_name(request) or None
        prompt_text = resolve_prompt_text(request.user_id, 'outline', prompt_name)

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
        outline_service = get_outline_service(request.user_id)
        result = outline_service.generate_outline(
            topic,
            images if images else None,
            prompt_text=prompt_text,
            reference_content=reference_content,
            provider_name=provider_name,
        )

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
        logger.error(f"大纲生成异常: {e}")
        return api_error_response(e, context={"endpoint": "/api/outline"})


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
            for file in files:
                if file and file.name:
                    image_data = file.read()
                    images.append(image_data)

        return topic, reference_content, images

    # JSON 请求（无图片或 base64 图片）
    data = json_body(request)
    topic = data.get('topic')
    reference_content = (data.get('reference_content') or '').strip()
    images = []

    # 支持 base64 格式的图片
    images_base64 = data.get('images', [])
    if images_base64:
        for img_b64 in images_base64:
            # 移除可能的 data URL 前缀
            if ',' in img_b64:
                img_b64 = img_b64.split(',')[1]
            images.append(base64.b64decode(img_b64))

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
def generate_content(request):
    """POST /api/content 生成标题、文案、标签"""
    try:
        data = json_body(request)
        topic = data.get('topic', '')
        outline = data.get('outline', '')
        prompt_name = data.get('prompt_name') or ''
        provider_name = (data.get('provider_name') or '').strip() or None
        prompt_text = resolve_prompt_text(request.user_id, 'content', prompt_name)

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
        content_service = get_content_service(request.user_id)
        result = content_service.generate_content(topic, outline, prompt_text=prompt_text, provider_name=provider_name)

        # 记录结果
        if result["success"]:
            logger.info(f"✅ 内容生成成功")
            return JsonResponse(result, status=200, json_dumps_params=_JSON_PARAMS)
        else:
            logger.error(f"❌ 内容生成失败: {result.get('error', '未知错误')}")
            result = normalize_error_result(
                result,
                context={"endpoint": "/api/content"},
                fallback_status=500,
            )
            return JsonResponse(result, status=result["error"].get("status", 500),
                                json_dumps_params=_JSON_PARAMS)

    except Exception as e:
        logger.error(f"内容生成异常: {e}")
        return api_error_response(e, context={"endpoint": "/api/content"})


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
def generate_images(request):
    """POST /api/generate 批量生成图片（SSE 流式返回）"""
    try:
        data = json_body(request)
        pages = data.get('pages')
        task_id = data.get('task_id')
        record_id = data.get('record_id')
        force = bool(data.get('force', False))
        full_outline = data.get('full_outline', '')
        user_topic = data.get('user_topic', '')

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
        user_id = request.user_id
        image_prompt_name = data.get('image_prompt_name') or ''
        image_provider_name = (data.get('provider_name') or '').strip() or None
        image_prompt_text = resolve_prompt_text(user_id, 'image', image_prompt_name)
        # 用户选择模型（服务商）时按指定服务商创建实例，否则使用当前激活服务商
        image_service = ImageService(image_provider_name, user_id) if image_provider_name else get_image_service(user_id)

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
            ):
                event_type = event["event"]
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

@require_auth
def get_image(request, task_id, filename):
    """GET /api/images/<task_id>/<filename> 获取图片文件"""
    try:
        logger.debug(f"获取图片: {task_id}/{filename}")

        # 检查是否请求缩略图
        thumbnail = request.GET.get('thumbnail', 'true').lower() == 'true'

        # 构建 history 目录路径
        history_root = settings.HISTORY_ROOT

        # 归属校验：任务属于当前用户或管理员
        owner_id = _find_task_owner(task_id)
        user = getattr(request, 'user_obj', None)
        is_admin = bool(user and user.get('is_admin'))
        if not (is_admin or (user and owner_id and user['id'] == owner_id)):
            return api_error_response(
                "无权访问该图片",
                status=403,
                context={"endpoint": "/api/images", "task_id": task_id, "filename": filename},
            )

        task_dir = os.path.join(str(history_root), owner_id or 'default', task_id)

        if thumbnail:
            # 尝试返回缩略图
            thumb_filename = f"thumb_{filename}"
            thumb_filepath = os.path.join(task_dir, thumb_filename)

            if os.path.exists(thumb_filepath):
                return FileResponse(open(thumb_filepath, 'rb'), content_type='image/png')

        # 返回原图
        filepath = os.path.join(task_dir, filename)

        if not os.path.exists(filepath):
            return api_error_response(
                "图片不存在",
                status=404,
                context={"endpoint": "/api/images", "task_id": task_id, "filename": filename},
            )

        return FileResponse(open(filepath, 'rb'), content_type='image/png')

    except Exception as e:
        logger.error(f"获取图片异常: {e}")
        return api_error_response(e, context={"endpoint": "/api/images", "task_id": task_id, "filename": filename})


# ==================== 重试和重新生成 ====================

@require_auth
def retry_single_image(request):
    """POST /api/retry 重试生成单张失败的图片"""
    try:
        data = json_body(request)
        task_id = data.get('task_id')
        page = data.get('page')
        use_reference = data.get('use_reference', True)
        record_id = data.get('record_id')

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
        image_prompt_text = resolve_prompt_text(owner_user_id, 'image', image_prompt_name)
        # 用户选择模型（服务商）时按指定服务商创建实例，否则使用当前激活服务商
        image_service = ImageService(image_provider_name, owner_user_id) if image_provider_name else get_image_service(owner_user_id)
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
def retry_failed_images(request):
    """POST /api/retry-failed 批量重试失败的图片（SSE 流式返回）"""
    try:
        data = json_body(request)
        task_id = data.get('task_id')
        pages = data.get('pages')
        record_id = data.get('record_id')

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
        image_prompt_text = resolve_prompt_text(owner_user_id, 'image', image_prompt_name)
        # 用户选择模型（服务商）时按指定服务商创建实例，否则使用当前激活服务商
        image_service = ImageService(image_provider_name, owner_user_id) if image_provider_name else get_image_service(owner_user_id)

        def generate():
            """SSE 事件生成器"""
            for event in image_service.retry_failed_images(
                task_id, pages, record_id=record_id, user_id=owner_user_id,
                image_prompt_text=image_prompt_text,
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
        image_prompt_text = resolve_prompt_text(owner_user_id, 'image', image_prompt_name)
        # 用户选择模型（服务商）时按指定服务商创建实例，否则使用当前激活服务商
        image_service = ImageService(image_provider_name, owner_user_id) if image_provider_name else get_image_service(owner_user_id)
        result = image_service.regenerate_image(
            task_id, page, use_reference,
            full_outline=full_outline,
            user_topic=user_topic,
            record_id=record_id,
            user_id=owner_user_id,
            image_prompt_text=image_prompt_text,
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

@require_auth
def get_task_state(request, task_id):
    """GET /api/task/<task_id> 获取任务状态"""
    try:
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


# ==================== 健康检查 ====================

def health_check(request):
    """GET /api/health 健康检查接口"""
    return JsonResponse({
        "success": True,
        "message": "服务正常运行"
    }, status=200)


# ==================== 辅助函数 ====================

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
