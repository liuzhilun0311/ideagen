"""历史记录 API 视图（对应 Flask 版 history_routes.py）。"""
import io
import zipfile

from django.http import JsonResponse
from django.db import transaction

from common.api import (api_error_response, json_body, normalize_error_result,
                        require_auth, validation_error)
from .services import get_history_service
from .models import HistoryRecord
from .creation_inputs import validate_creation_inputs
from generation.styles import normalize_style
from generation.catalog import catalog_request
from .permissions import (actor, can_modify, can_read, private_view, source_file,
                          task_records, valid_task_binding)


def _user_ctx(request) -> dict:
    return {
        "user_id": getattr(request, 'user_id', None),
        "is_admin": bool(request.user_obj.get('is_admin', False)) if getattr(request, 'user_obj', None) else False,
    }


@require_auth
@catalog_request
def create_history(request):
    """POST /api/history"""
    try:
        data = json_body(request)
        topic = data.get('topic')
        outline = data.get('outline')
        validate_creation_inputs(outline)
        task_id = data.get('task_id')
        generation_audit = data.get('generation_audit')
        try:
            image_style = normalize_style(data.get('image_style'))
        except ValueError as error:
            return api_error_response(str(error), status=400)
        if not valid_task_binding(request.user_id, task_id):
            return api_error_response('任务无效或属于其他用户。', status=400)
        if not topic or not outline:
            return api_error_response(
                validation_error("topic 和 outline 不能为空", "请提供主题和大纲内容。"),
                context={"endpoint": "/api/history"},
            )
        record_id = get_history_service().create_record(
            topic, outline, task_id, user_id=_user_ctx(request)['user_id'],
            image_style=image_style, generation_audit=generation_audit,
        )
        return JsonResponse({"success": True, "record_id": record_id}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history"})


@private_view
@require_auth
def list_history(request):
    """GET /api/history"""
    try:
        page = int(request.GET.get('page', 1))
        page_size = int(request.GET.get('page_size', 20))
        status = request.GET.get('status')
        ctx = _user_ctx(request)
        result = get_history_service().list_records(
            page, page_size, status, ctx['user_id'], ctx['is_admin'],
            source=request.GET.get('source'), keyword=request.GET.get('keyword'),
        )
        return JsonResponse({"success": True, **result}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history"})


@private_view
@require_auth
def get_history(request, record_id: str):
    """GET /api/history/<record_id>"""
    try:
        record = HistoryRecord.objects.select_related('user').filter(pk=record_id).first()
        if not record:
            return api_error_response(
                f"历史记录不存在：{record_id}",
                status=404,
                context={"endpoint": "/api/history/<id>", "record_id": record_id},
            )
        user = actor(request.user_id)
        if not can_read(user, record):
            return api_error_response("无权访问该记录", status=403,
                                      context={"endpoint": "/api/history/<id>", "record_id": record_id})
        detail = get_history_service().get_record(
            record_id, sync_images=can_modify(user, record), user=user,
        )
        return JsonResponse({"success": True, "record": detail}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history/<id>", "record_id": record_id})


@private_view
@require_auth
def check_history_exists(request, record_id: str):
    """GET /api/history/<record_id>/exists"""
    try:
        record = HistoryRecord.objects.select_related('user').filter(pk=record_id).first()
        exists = can_read(actor(request.user_id), record)
        return JsonResponse({"exists": exists}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history/<id>/exists", "record_id": record_id})


@require_auth
@catalog_request
def update_history(request, record_id: str):
    """PUT /api/history/<record_id>"""
    try:
        data = json_body(request)
        record = HistoryRecord.objects.filter(pk=record_id).first()
        if not record:
            return api_error_response(f"历史记录不存在：{record_id}", status=404,
                                      context={"endpoint": "/api/history/<id>", "record_id": record_id})
        if not can_modify(actor(request.user_id), record):
            return api_error_response("无权操作该记录", status=403,
                                      context={"endpoint": "/api/history/<id>", "record_id": record_id})
        validate_creation_inputs(data.get("outline"))
        if 'structure_change' in data:
            change = data['structure_change']
            outline = change.get('outline') if isinstance(change, dict) else None
            validate_creation_inputs(outline)
            pages = outline.get('pages') if isinstance(outline, dict) else None
            if (not isinstance(pages, list) or not pages
                    or not isinstance(outline.get('raw'), str)
                    or any(not isinstance(page, dict)
                           or type(page.get('index')) is not int
                           or page.get('index') != index
                           or page.get('type') not in ('cover', 'content', 'summary', 'infographic')
                           or not isinstance(page.get('content'), str)
                           for index, page in enumerate(pages))):
                return api_error_response('页面结构格式无效。', status=400)
            with transaction.atomic():
                record = HistoryRecord.objects.select_for_update().get(pk=record_id)
                if not can_modify(actor(request.user_id), record):
                    return api_error_response('无权操作该记录', status=403)
                if record.outline != change.get('expected_outline'):
                    return api_error_response('大纲已被修改，请刷新后重试。', status=409)
                if (record.status == 'generating'
                        or record.image_candidates.filter(status='generating').exists()
                        or record.image_versions.filter(jobs__status__in=['queued', 'processing']).exists()):
                    return api_error_response('图片仍在生成或处理中，请完成后再修改页面结构。', status=409)
                # Detach the old task as well: legacy image scanning must not restore it.
                record.image_candidates.all().delete()
                record.image_versions.all().delete()
                record.outline = outline
                record.images = {'task_id': None, 'generated': []}
                record.thumbnail = None
                record.status = 'draft'
                record.save(update_fields=['outline', 'images', 'thumbnail', 'status', 'updated_at'])
            return JsonResponse({'success': True})
        images = data.get('images')
        analysis_snapshots = data.get('analysis_snapshots')
        if analysis_snapshots is not None:
            if not isinstance(analysis_snapshots, list):
                return api_error_response('分析快照格式无效。', status=400)
            for snapshot in analysis_snapshots:
                if not isinstance(snapshot, dict):
                    return api_error_response('分析快照格式无效。', status=400)
                if any(not isinstance(snapshot.get(part), dict)
                       for part in ('content', 'layout', 'visual_style')):
                    return api_error_response('分析快照缺少必要分区。', status=400)
        try:
            image_style = normalize_style(data['image_style']) if 'image_style' in data else None
        except ValueError as error:
            return api_error_response(str(error), status=400)
        if images is not None and (
            not isinstance(images, dict)
            or not valid_task_binding(record.user_id, images.get('task_id'))
        ):
            return api_error_response('任务无效或属于其他用户。', status=400)
        success = get_history_service().update_record(
            record_id,
            title=data.get('title'),
            outline=data.get('outline'),
            images=data.get('images'),
            status=data.get('status'),
            thumbnail=data.get('thumbnail'),
            content=data.get('content'),
            analysis_snapshots=analysis_snapshots,
            image_style=image_style,
        )
        if not success:
            return api_error_response(f"更新历史记录失败：{record_id}", status=404,
                                      context={"endpoint": "/api/history/<id>", "record_id": record_id})
        return JsonResponse({"success": True}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history/<id>", "record_id": record_id})


@require_auth
def delete_history(request, record_id: str):
    """DELETE /api/history/<record_id>"""
    try:
        record = HistoryRecord.objects.filter(pk=record_id).first()
        if not record:
            return api_error_response(f"历史记录不存在：{record_id}", status=404,
                                      context={"endpoint": "/api/history/<id>", "record_id": record_id})
        if not can_modify(actor(request.user_id), record):
            return api_error_response("无权删除该记录", status=403,
                                      context={"endpoint": "/api/history/<id>", "record_id": record_id})
        success = get_history_service().delete_record(record_id)
        if not success:
            return api_error_response(f"删除历史记录失败：{record_id}", status=404,
                                      context={"endpoint": "/api/history/<id>", "record_id": record_id})
        return JsonResponse({"success": True}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history/<id>", "record_id": record_id})


@private_view
@require_auth
def search_history(request):
    """GET /api/history/search?keyword=..."""
    try:
        keyword = request.GET.get('keyword', '')
        if not keyword:
            return api_error_response(validation_error("keyword 不能为空", "请输入搜索关键词。"),
                                      context={"endpoint": "/api/history/search"})
        ctx = _user_ctx(request)
        results = get_history_service().search_records(
            keyword, ctx['user_id'], ctx['is_admin'],
            source=request.GET.get('source'), status=request.GET.get('status'),
        )
        return JsonResponse({"success": True, "records": results}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history/search"})


@private_view
@require_auth
def get_history_stats(request):
    """GET /api/history/stats"""
    try:
        ctx = _user_ctx(request)
        stats = get_history_service().get_statistics(
            ctx['user_id'], ctx['is_admin'], source=request.GET.get('source'),
        )
        return JsonResponse({"success": True, **stats}, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history/stats"})


@private_view
@require_auth
def scan_task(request, task_id: str):
    """GET /api/history/scan/<task_id>"""
    try:
        records = list(task_records(task_id))
        if not records:
            return api_error_response('任务不存在。', status=404)
        user = actor(request.user_id)
        if not all(can_modify(user, record) for record in records):
            return api_error_response('无权同步该任务。', status=403)
        result = get_history_service().scan_and_sync_task_images(task_id)
        if not result.get("success"):
            result = normalize_error_result(result, context={"endpoint": "/api/history/scan/<task_id>", "task_id": task_id}, fallback_status=404)
            return JsonResponse(result, status=result["error"].get("status", 404))
        return JsonResponse(result, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history/scan/<task_id>", "task_id": task_id})


@require_auth
def scan_all_tasks(request):
    """POST /api/history/scan-all"""
    try:
        result = get_history_service().scan_all_tasks(user=actor(request.user_id))
        if not result.get("success"):
            result = normalize_error_result(result, context={"endpoint": "/api/history/scan-all"}, fallback_status=500)
            return JsonResponse(result, status=result["error"].get("status", 500))
        return JsonResponse(result, status=200)
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history/scan-all"})


@private_view
@require_auth
def download_history_zip(request, record_id: str):
    """GET /api/history/<record_id>/download"""
    try:
        record = HistoryRecord.objects.select_related('user').filter(pk=record_id).first()
        if not record:
            return api_error_response(f"历史记录不存在：{record_id}", status=404,
                                      context={"endpoint": "/api/history/<id>/download", "record_id": record_id})
        if not can_read(actor(request.user_id), record):
            return api_error_response("无权下载该记录", status=403,
                                      context={"endpoint": "/api/history/<id>/download", "record_id": record_id})
        task_id = (record.images or {}).get('task_id')
        if not task_id:
            return api_error_response("该记录没有关联的任务图片", status=404,
                                      context={"endpoint": "/api/history/<id>/download", "record_id": record_id})
        memory_file = _create_images_zip(record)
        from django.http import HttpResponse
        response = HttpResponse(memory_file.getvalue(), content_type='application/zip')
        safe_title = _sanitize_filename(record.title or 'images')
        response['Content-Disposition'] = f'attachment; filename="{safe_title}.zip"'
        return response
    except Exception as e:
        return api_error_response(e, context={"endpoint": "/api/history/<id>/download", "record_id": record_id})


def _create_images_zip(record: HistoryRecord) -> io.BytesIO:
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for position, filename in enumerate((record.images or {}).get('generated', [])):
            file_path = source_file(record, filename)
            if filename.startswith('thumb_') or file_path is None:
                continue
            try:
                index = int(filename.split('.')[0])
                archive_name = f"page_{index + 1}{file_path.suffix}"
            except ValueError:
                archive_name = f"page_{position + 1}{file_path.suffix}"
            zf.write(file_path, archive_name)
    memory_file.seek(0)
    return memory_file


def _sanitize_filename(title: str) -> str:
    safe_title = "".join(c for c in title if c.isalnum() or c in (' ', '-', '_')).strip()
    return safe_title if safe_title else 'images'
