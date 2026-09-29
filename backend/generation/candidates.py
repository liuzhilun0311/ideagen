"""Single-page trials are immutable and never publish until explicitly adopted."""
import json
import base64
import binascii
import shutil
import uuid
import mimetypes
from datetime import timedelta

from django.db import transaction
from django.http import FileResponse, JsonResponse

from common.api import api_error_response, json_body, require_auth
from history.models import HistoryRecord, ImageCandidate
from history.permissions import actor, can_modify, private_response, task_directory, source_file
from postprocessing.services import sync_published_images
from .services.image import ImageService, get_image_service
from .services.task_cancel import reset_cancel
from .styles import resolve_style, style_prompt, format_image_prompt
from .structure import image_page_content
from .parameters import apply_image_parameters, normalize_image_parameters
from .image_prompt import automatic_image_template, render_page_prompt
from .reference_roles import validate_reference_roles
from .catalog import catalog_request
from .utils.image_compressor import compress_image


def snapshot(record, index):
    page = next((p for p in record.outline.get('pages', []) if p.get('index') == index), None)
    if page is None:
        raise ValueError('页面不存在，请刷新作品。')
    return json.dumps({'title': record.title, 'page': page}, ensure_ascii=False, sort_keys=True)


def directory(record, task_id, candidate_id):
    root = task_directory(record.user_id, task_id)
    if root is None:
        raise ValueError('图片目录无效。')
    path = root / 'candidates' / candidate_id
    if path.resolve() != path:
        raise ValueError('图片目录无效。')
    return path


def published(record, index):
    files = (record.images or {}).get('generated', [])
    return files[index] if index < len(files) else ''


def cover_reference(record, index, enabled):
    if not enabled:
        return None
    pages = record.outline.get('pages', [])
    if not pages or index == pages[0]['index']:
        return None
    path = source_file(record, published(record, pages[0]['index']))
    if path is None:
        raise ValueError('已开启参考第一张图，请先生成并采用第一张图片；若首图文件已丢失，请重新生成。')
    try:
        return compress_image(path.read_bytes(), max_size_kb=200)
    except (OSError, ValueError):
        raise ValueError('第一张参考图片无法读取，请重新生成并采用首图。') from None


def detail(candidate, record):
    try:
        stale = candidate.page_content != snapshot(record, candidate.page_index)
    except ValueError:
        stale = True
    return {
        'id': candidate.id, 'index': candidate.page_index, 'style': candidate.style,
        'prompt': candidate.prompt, 'provider': candidate.provider, 'status': candidate.status,
        'image_url': f'/api/image-candidates/{record.pk}/{candidate.pk}/image',
        'adopted': bool(candidate.filename and published(record, candidate.page_index) == candidate.filename),
        'stale': stale, 'created_at': candidate.created_at.isoformat(),
    }


def authorized(request, record_id, lock=False):
    query = HistoryRecord.objects.select_for_update() if lock else HistoryRecord.objects
    record = query.filter(pk=record_id).first()
    if not can_modify(actor(request.user_id), record):
        raise PermissionError('作品不存在或无权修改。')
    return record


@require_auth
@catalog_request
def candidates(request, record_id):
    candidate = None
    try:
        record = authorized(request, record_id)
        if request.method == 'GET':
            return private_response(JsonResponse({
                'success': True, 'candidates': [detail(c, record) for c in record.image_candidates.all()],
            }))
        if request.method != 'POST':
            return api_error_response('请求方法不支持。', status=405)
        data = json_body(request)
        use_reference = data.get('use_reference', False)
        if type(use_reference) is not bool:
            raise ValueError('参考第一张图必须为布尔值。')
        parameters = normalize_image_parameters(data.get('image_parameters'))
        index = data.get('index')
        if type(index) is not int or index < 0:
            raise ValueError('页面索引无效。')
        request_id = str(uuid.UUID(data.get('request_id', '')))
        style = resolve_style(data.get('image_style', record.image_style),
                              (record.image_style or {}).get('recommendation'))
        style.pop('applied', None)
        provider = data.get('provider_name', '')
        prompt_name = data.get('image_prompt_name', '')
        if not isinstance(provider, str) or not isinstance(prompt_name, str):
            raise ValueError('模型或提示词配置无效。')
        encoded_references = data.get('user_images', [])
        reference_roles = validate_reference_roles(data.get('reference_roles'))
        if not isinstance(encoded_references, list) or any(not isinstance(item, str) for item in encoded_references):
            raise ValueError('参考图片格式无效。')
        try:
            references = [base64.b64decode(item.split(',', 1)[-1], validate=True) for item in encoded_references]
        except binascii.Error:
            raise ValueError('参考图片编码无效。')
        with transaction.atomic():
            record = authorized(request, record_id, lock=True)
            existing = ImageCandidate.objects.filter(pk=request_id).first()
            if existing:
                if existing.record_id != record.pk:
                    raise PermissionError('请求编号不可用。')
                return JsonResponse({'success': True, 'candidate': detail(existing, record)})
            content = snapshot(record, index)
            cover = cover_reference(record, index, use_reference)
            images = dict(record.images or {})
            task_id = images.get('task_id') or uuid.uuid4().hex
            images['task_id'] = task_id
            record.images = images
            record.save(update_fields=['images', 'updated_at'])
            page = json.loads(content)['page']
            outline = '\n\n<page>\n\n'.join(p.get('content', '') for p in record.outline.get('pages', []))
            preferences = record.outline.get("generation_preferences") or {}
            template = automatic_image_template(style, len(references), bool(cover), reference_roles, preferences)
            final_prompt = render_page_prompt(page, record.title, style, len(references), bool(cover), reference_roles, preferences)
            candidate = ImageCandidate.objects.create(
                id=request_id, record=record, page_index=index, page_content=content,
                task_id=task_id, style=style, prompt=final_prompt, provider=provider,
            )
        service = ImageService(provider, record.user_id) if provider else get_image_service(record.user_id)
        service = apply_image_parameters(service, parameters)
        target = directory(record, task_id, candidate.pk)
        target.mkdir(parents=True, exist_ok=True)
        reset_cancel(record.user_id)
        # Resolve the adopted first page, never a guessed 0.png or an unadopted trial.
        _, success, generated_filename, error = service._generate_single_image(
            page, task_id, full_outline=outline, user_topic=record.title,
            task_dir=str(target), prompt_text=template,
            user_images=references or None,
            generation_id=candidate.pk,
            **({"reference_image": cover} if cover else {}),
        )
        if not success:
            ImageCandidate.objects.filter(pk=candidate.pk).update(status='failed')
            return api_error_response(error or '本页生成失败，原图片已保留。', status=502)
        candidate.status = 'ready'
        extension = generated_filename.rsplit(".", 1)[-1]
        if extension not in ("png", "jpeg", "webp"):
            raise ValueError("生成图片格式无效。")
        candidate.filename = f'version_{candidate.pk.replace("-", "")}.{extension}'
        candidate.save(update_fields=['status', 'filename'])
        record.refresh_from_db()
        return JsonResponse({'success': True, 'candidate': detail(candidate, record)})
    except PermissionError as error:
        return api_error_response(str(error), status=403)
    except (ValueError, TypeError, AttributeError) as error:
        if candidate:
            ImageCandidate.objects.filter(pk=candidate.pk).update(status='failed')
        return api_error_response(str(error), status=400)
    except Exception as error:
        if candidate:
            ImageCandidate.objects.filter(pk=candidate.pk).update(status='failed')
        return api_error_response(error, context={'endpoint': '/api/image-candidates'})


@require_auth
def candidate_image(request, record_id, candidate_id):
    try:
        record = authorized(request, record_id)
        candidate = record.image_candidates.filter(pk=candidate_id, status='ready').first()
        if candidate is None:
            return api_error_response('候选图不存在。', status=404)
        extension = candidate.filename.rsplit(".", 1)[-1]
        path = directory(record, candidate.task_id, candidate.pk) / f'{candidate.page_index}.{extension}'
        if path.resolve() != path or not path.is_file():
            return api_error_response('候选图文件不存在。', status=404)
        return private_response(FileResponse(open(path, 'rb'), content_type=mimetypes.guess_type(str(path))[0]))
    except PermissionError as error:
        return api_error_response(str(error), status=403)
    except ValueError as error:
        return api_error_response(str(error), status=400)


@require_auth
def adopt_candidate(request, record_id, candidate_id):
    if request.method != 'POST':
        return api_error_response('请求方法不支持。', status=405)
    try:
        data = json_body(request)
        with transaction.atomic():
            record = authorized(request, record_id, lock=True)
            candidate = record.image_candidates.filter(pk=candidate_id, status='ready').first()
            if candidate is None:
                return api_error_response('候选版本不存在或尚未生成成功。', status=404)
            index = candidate.page_index
            if snapshot(record, index) != candidate.page_content:
                return api_error_response('页面内容已修改，请按当前内容重新试图。', status=409)
            if (record.images or {}).get('task_id') != candidate.task_id:
                return api_error_response('作品图片任务已变化，请重新试图。', status=409)
            old = published(record, index)
            if data.get('expected_filename', '') != old:
                return api_error_response('本页采用版本已变化，请刷新后重试。', status=409)
            root = task_directory(record.user_id, candidate.task_id)
            extension = candidate.filename.rsplit(".", 1)[-1]
            target = directory(record, candidate.task_id, candidate.pk) / f'{index}.{extension}'
            if not target.is_file() or target.resolve() != target:
                raise ValueError('候选图文件不存在。')
            # Preserve legacy images too, before replacing their publication pointer.
            if old and not record.image_candidates.filter(filename=old).exists():
                source = source_file(record, old)
                if source:
                    legacy_id = str(uuid.uuid4())
                    legacy_dir = directory(record, candidate.task_id, legacy_id)
                    legacy_dir.mkdir(parents=True, exist_ok=True)
                    shutil.copyfile(source, legacy_dir / f'{index}{source.suffix}')
                    legacy = ImageCandidate.objects.create(
                        id=legacy_id, record=record, page_index=index,
                        page_content=snapshot(record, index), task_id=candidate.task_id,
                        style=(record.image_style or {}).get('applied') or {'preset': 'auto', 'notes': ''},
                        status='ready', filename=old,
                    )
                    ImageCandidate.objects.filter(pk=legacy.pk).update(
                        created_at=candidate.created_at - timedelta(microseconds=1))
            destination = root / candidate.filename
            if destination.resolve() != destination:
                raise ValueError('图片路径无效。')
            shutil.copyfile(target, destination)
            images = dict(record.images or {})
            files = list(images.get('generated', []))
            while len(files) <= index:
                files.append('')
            files[index] = candidate.filename
            images['generated'] = files
            record.images = images
            indices = [p['index'] for p in record.outline.get('pages', [])]
            record.status = 'completed' if all(i < len(files) and files[i] for i in indices) else 'partial'
            record.thumbnail = next((f for f in files if f), None)
            record.save(update_fields=['images', 'status', 'thumbnail', 'updated_at'])
            transaction.on_commit(lambda: sync_published_images(record_id))
        return JsonResponse({
            'success': True, 'task_id': candidate.task_id, 'filename': candidate.filename,
            'image_url': f'/api/images/{candidate.task_id}/{candidate.filename}?thumbnail=false',
            'candidate': detail(candidate, record),
        })
    except PermissionError as error:
        return api_error_response(str(error), status=403)
    except ValueError as error:
        return api_error_response(str(error), status=400)
    except Exception as error:
        return api_error_response(error, context={'endpoint': '/api/image-candidates/adopt'})
