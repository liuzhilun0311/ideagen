"""Record-scoped versions and a fenced, database-backed processing queue."""
import hashlib
import io
import json
import logging
import os
import re
import shutil
import subprocess
import tempfile
import uuid
from datetime import timedelta
from pathlib import Path

from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils import timezone
from PIL import Image

from accounts.models import User
from history.models import HistoryRecord
from history.permissions import actor, can_modify, can_read, source_file
from .models import ImageJob, ImagePage, ProcessingPreference
from .processor import process_image

logger = logging.getLogger(__name__)
STRENGTHS = ('light', 'medium', 'heavy')
ACTIVE = ('queued', 'processing')
SAFE_COMPONENT = re.compile(r'^[A-Za-z0-9_-]+$')


class ProcessingError(Exception):
    def __init__(self, message, status=400):
        self.status = status
        super().__init__(message)


def digest_file(path):
    with path.open('rb') as stream:
        return hashlib.file_digest(stream, 'sha256').hexdigest()


def safe_path(relative):
    root = Path(settings.HISTORY_ROOT).resolve()
    relative = Path(relative)
    if (relative.is_absolute() or not relative.parts or '..' in relative.parts
            or not SAFE_COMPONENT.fullmatch(relative.parts[0])):
        raise ValueError('Invalid image location')
    path = (root / relative).resolve()
    owner_root = root / relative.parts[0]
    if not path.is_relative_to(owner_root) or path == owner_root:
        raise ValueError('Invalid image location')
    return path


def algorithm_version():
    script = settings.PROJECT_ROOT / 'deai-image' / 'scripts' / 'deai.py'
    return 'deai-v1-' + (digest_file(script) if script.is_file() else 'unavailable')


def _lock_record(record_id):
    # The first statement is a write: SQLite must acquire its writer lock before
    # reading state, avoiding deferred read-to-write upgrades in parallel requests.
    if not HistoryRecord.objects.filter(pk=record_id).update(id=F('id')):
        raise ProcessingError('作品不存在或无权访问。', 404)
    return HistoryRecord.objects.get(pk=record_id)


def _preference(user_id):
    return ProcessingPreference.objects.get_or_create(user_id=user_id)[0]


def _originals(record, indices=None):
    images = record.images or {}
    task = images.get('task_id')
    if not isinstance(task, str) or not SAFE_COMPONENT.fullmatch(task):
        return []
    if not SAFE_COMPONENT.fullmatch(record.user_id):
        return []
    generated = images.get('generated', [])
    if not isinstance(generated, list):
        return []
    available = {name for name in generated if isinstance(name, str)}
    pages = (record.outline or {}).get('pages', [])
    result = []
    seen = set()
    for position, page in enumerate(pages):
        if not isinstance(page, dict):
            continue
        index = page.get('index', position)
        if type(index) is not int or index < 0 or index in seen:
            continue
        seen.add(index)
        if indices is not None and index not in indices:
            continue
        # Generation names files by stable page index, not the compacted list position.
        filename = next((f'{index}{suffix}' for suffix in ('.png', '.jpg', '.jpeg', '.webp')
                         if f'{index}{suffix}' in available), None)
        if index < len(generated) and isinstance(generated[index], str) and generated[index].startswith('version_'):
            filename = generated[index]
        if not filename:
            continue
        relative = Path(record.user_id) / task / filename
        try:
            path = source_file(record, filename)
            if path is None:
                continue
            content = path.read_bytes()
            with Image.open(io.BytesIO(content)) as image:
                image.verify()
            digest = hashlib.sha256(content).hexdigest()
        except (OSError, ValueError, SyntaxError, Image.DecompressionBombError):
            continue
        identity_data = page.get('id') or {key: value for key, value in page.items() if key != 'index'}
        identity = hashlib.sha256(json.dumps(identity_data, sort_keys=True).encode()).hexdigest()
        revision = hashlib.sha256(f'{relative.as_posix()}:{identity}:{digest}'.encode()).hexdigest()
        result.append((index, identity, revision, digest, relative.as_posix(), path))
    return result


def _valid_output(job):
    if not job or job.status != 'done' or not job.output_path or not job.output_digest:
        return False
    try:
        path = safe_path(job.output_path)
        return path.is_file() and digest_file(path) == job.output_digest
    except (OSError, ValueError):
        return False


def adopted_thumbnail_url(record):
    """Read only candidate pages; do not reconcile or mutate during list queries."""
    candidates = record.image_versions.filter(
        adopted='processed', current_job__status='done',
    ).select_related('current_job').order_by('index')
    for page in candidates:
        originals = _originals(record, indices={page.index})
        if not originals or originals[0][2] != page.source_revision:
            continue
        job = page.current_job
        if job.source_revision != page.source_revision or not _valid_output(job):
            continue
        return f'/api/postprocessing/images/{record.pk}/{page.index}/processed/{job.pk}'
    return None


def record_output_directory(record_id, owner_id):
    key = hashlib.sha256(record_id.encode()).hexdigest()
    relative = Path(owner_id) / '_postprocessing' / key
    path = safe_path(relative)
    # Cleanup must never follow a same-owner symlink into the originals directory.
    if path != Path(settings.HISTORY_ROOT).resolve() / relative:
        raise ValueError('Invalid processing output location')
    return path


def cleanup_record_outputs(record_id, owner_id, output_paths=()):
    """Remove only this record's directory and its pre-directory-layout outputs."""
    try:
        directory = record_output_directory(record_id, owner_id)
        if directory.exists():
            shutil.rmtree(directory)
        legacy_root = directory.parent
        for relative in output_paths:
            if not relative:
                continue
            path = safe_path(relative)
            if path.parent == legacy_root and re.fullmatch(
                r'[0-9a-f-]{36}-[0-9a-f-]{36}\.png', path.name,
            ):
                path.unlink(missing_ok=True)
    except (OSError, ValueError):
        logger.warning('Could not remove all files for a deleted processing record')


def _enqueue(page, strength, force=False):
    active = page.jobs.filter(status__in=ACTIVE).first()
    if active:
        return active
    if not force and _valid_output(page.current_job):
        return page.current_job
    algorithm = algorithm_version()
    if not force:
        reusable = page.jobs.filter(
            source_revision=page.source_revision, strength=strength, algorithm=algorithm,
            status='done',
        ).order_by('-created_at').first()
        if _valid_output(reusable):
            page.current_job = reusable
            page.adopted = 'processed'
            page.save(update_fields=['current_job', 'adopted'])
            return reusable
    return ImageJob.objects.create(
        page=page, owner_id=page.record.user_id, source_revision=page.source_revision,
        source_digest=page.source_digest, source_path=page.source_path,
        strength=strength, algorithm=algorithm, adoption_serial=page.adoption_serial,
    )


def _reconcile(record, automatic=False):
    preference = _preference(record.user_id)
    retained = []
    for index, identity, revision, digest, relative, path in _originals(record):
        page, created = ImagePage.objects.get_or_create(
            record=record, index=index,
            defaults={'identity': identity, 'source_revision': revision,
                      'source_digest': digest, 'source_path': relative},
        )
        retained.append(page.pk)
        changed = created or page.source_revision != revision
        if changed and not created:
            page.jobs.filter(status__in=ACTIVE).update(
                status='stale', lease_token=None, lease_until=None, finished_at=timezone.now())
            page.identity = identity
            page.source_revision = revision
            page.source_digest = digest
            page.source_path = relative
            page.current_job = None
            page.adopted = 'original'
            page.adoption_serial += 1
            page.save()
        if page.current_job_id and not _valid_output(page.current_job):
            page.current_job = None
            page.adopted = 'original'
            page.save(update_fields=['current_job', 'adopted'])
        if automatic and page.published_revision != revision:
            # GET may discover the file before generation publishes its event.
            # Only the publication hook consumes this revision's automatic trigger.
            page.published_revision = revision
            page.save(update_fields=['published_revision'])
            if preference.automatic:
                since = preference.automatic_since
                if since is not None and path.stat().st_mtime >= since.timestamp():
                    _enqueue(page, preference.strength)
    record.image_versions.exclude(pk__in=retained).delete()
    return preference


def sync_published_images(record_id):
    """Called by history publication, independently of any browser polling."""
    try:
        with transaction.atomic():
            record = _lock_record(record_id)
            _reconcile(record, automatic=True)
    except Exception as error:
        # Postprocessing must never turn successful model generation into failure.
        logger.warning('Image processing synchronization failed category=%s', _failure_category(error))


def _state(record, preference, readonly=False):
    pages = []
    stored = list(record.image_versions.select_related('current_job').order_by('index'))
    if readonly:
        by_index = {page.index: page for page in stored}
        stored = []
        for index, identity, revision, digest, relative, _ in _originals(record):
            page = by_index.get(index)
            if page is None or page.source_revision != revision:
                page = ImagePage(record=record, index=index, identity=identity,
                                 source_revision=revision, source_digest=digest, source_path=relative)
            elif page.current_job_id and not _valid_output(page.current_job):
                page.current_job = None
                page.adopted = 'original'
            stored.append(page)
        stored.sort(key=lambda page: page.index)
    for page in stored:
        latest = (page.jobs.filter(source_revision=page.source_revision).order_by('-created_at').first()
                  if page.pk else None)
        current = page.current_job
        status = latest.status if latest and latest.status in ('queued', 'processing', 'error') else (
            'done' if current else 'idle')
        base = f'/api/postprocessing/images/{record.pk}/{page.index}'
        pages.append({
            'index': page.index,
            'source_revision': page.source_revision,
            'original_url': f'{base}/original/{page.source_revision}',
            'processed_url': f'{base}/processed/{current.pk}' if current else None,
            'strength': current.strength if current else None,
            'status': status,
            'error': '图片处理失败，请重试。' if latest and status == 'error' else '',
            'adopted': page.adopted,
        })
    return {'success': True, 'preferences': {
        'automatic': preference.automatic, 'strength': preference.strength,
    }, 'pages': pages}


def record_state(record_id, owner_id, data=None):
    if data is None:
        record = HistoryRecord.objects.select_related('user').filter(pk=record_id).first()
        if not can_read(actor(owner_id), record):
            raise ProcessingError('作品不存在或无权访问。', 404)
        preference = (ProcessingPreference.objects.filter(user_id=record.user_id).first()
                      or ProcessingPreference(user_id=record.user_id))
        return _state(record, preference, readonly=True)
    record = HistoryRecord.objects.filter(pk=record_id).first()
    if not can_modify(actor(owner_id), record, allow_admin=False):
        raise ProcessingError('作品不存在或无权访问。', 404)
    with transaction.atomic():
        record = _lock_record(record_id)
        if not can_modify(actor(owner_id), record, allow_admin=False):
            raise ProcessingError('作品不存在或无权访问。', 404)
        preference = _reconcile(record)
        if data is not None:
            if not isinstance(data, dict):
                raise ProcessingError('请求内容必须是 JSON 对象。')
            action = data.get('action')
            if action == 'preferences':
                automatic = data.get('automatic')
                strength = data.get('strength')
                if type(automatic) is not bool or strength not in STRENGTHS:
                    raise ProcessingError('自动处理设置或强度无效。')
                # Serialize account-wide preference changes across different records.
                User.objects.filter(pk=owner_id).update(id=F('id'))
                preference.refresh_from_db()
                if automatic and not preference.automatic:
                    preference.automatic_since = timezone.now()
                preference.automatic = automatic
                preference.strength = strength
                preference.save()
            elif action == 'process':
                indices = data.get('indices')
                strength = data.get('strength', preference.strength)
                force = data.get('force', False)
                if (not isinstance(indices, list) or not indices or len(indices) > 1000
                        or any(type(index) is not int or index < 0 for index in indices)
                        or strength not in STRENGTHS or type(force) is not bool):
                    raise ProcessingError('图片索引、处理强度或重处理参数无效。')
                pages = {page.index: page for page in record.image_versions.all()}
                if any(index not in pages for index in indices):
                    raise ProcessingError('部分图片尚未生成或无法读取。')
                for index in dict.fromkeys(indices):
                    _enqueue(pages[index], strength, force)
            elif action == 'adopt':
                index, version = data.get('index'), data.get('version')
                if type(index) is not int or version not in ('original', 'processed'):
                    raise ProcessingError('图片索引或版本无效。')
                page = record.image_versions.filter(index=index).first()
                if page is None or data.get('source_revision') != page.source_revision:
                    raise ProcessingError('原图已更新，请刷新后重试。', 409)
                if version == 'processed' and not _valid_output(page.current_job):
                    raise ProcessingError('暂无可用的处理图。', 409)
                page.adopted = version
                page.adoption_serial += 1
                page.save(update_fields=['adopted', 'adoption_serial'])
            else:
                raise ProcessingError('不支持此图片处理操作。')
        return _state(record, preference)


def image_file(record_id, owner_id, index, version, revision):
    """Read only the requested page without transactions or reconciliation."""
    record = HistoryRecord.objects.select_related('user').filter(pk=record_id).first()
    if not can_read(actor(owner_id), record):
        raise ProcessingError('图片不存在或无权访问。', 404)
    originals = _originals(record, indices={index})
    if not originals:
        raise ProcessingError('图片不存在或无权访问。', 404)
    _, _, source_revision, source_digest, source_path, _ = originals[0]
    if version == 'original' and revision == source_revision:
        relative, digest = source_path, source_digest
    elif version == 'processed':
        try:
            job_id = uuid.UUID(revision)
        except ValueError:
            raise ProcessingError('图片不存在或无权访问。', 404) from None
        job = ImageJob.objects.filter(
            pk=job_id, page__record_id=record_id, page__index=index,
            source_revision=source_revision, status='done', owner_id=record.user_id,
        ).first()
        if not job or not job.output_path or not job.output_digest:
            raise ProcessingError('图片不存在或无权访问。', 404)
        relative, digest = job.output_path, job.output_digest
    else:
        raise ProcessingError('图片不存在或无权访问。', 404)
    try:
        path = safe_path(relative)
        content = path.read_bytes()
        if hashlib.sha256(content).hexdigest() != digest:
            raise ProcessingError('图片已更新，请刷新后重试。', 409)
        stream = io.BytesIO(content)
        stream.name = path.name
        return stream
    except (OSError, ValueError):
        raise ProcessingError('图片不存在或无权访问。', 404) from None


def claim_job():
    now = timezone.now()
    maximum = settings.POSTPROCESSING_MAX_ATTEMPTS
    with transaction.atomic():
        # This initial write also serializes claims on SQLite across processes.
        ImageJob.objects.filter(
            status='processing', lease_until__lte=now, attempts__gte=maximum,
        ).update(status='error', error='处理多次中断，请手动重试。',
                 lease_token=None, lease_until=None, finished_at=now)
        ImageJob.objects.filter(
            status='processing', lease_until__lte=now, attempts__lt=maximum,
        ).update(status='queued', lease_token=None, lease_until=None)
        candidate = ImageJob.objects.filter(status='queued', attempts__lt=maximum).order_by('created_at').first()
        if candidate is None:
            return None
        token = uuid.uuid4()
        claimed = ImageJob.objects.filter(pk=candidate.pk, status='queued').update(
            status='processing', attempts=F('attempts') + 1, lease_token=token,
            lease_until=now + timedelta(seconds=settings.POSTPROCESSING_LEASE_SECONDS), error='',
        )
        return ImageJob.objects.get(pk=candidate.pk) if claimed else None


def _leased(job):
    return ImageJob.objects.filter(
        pk=job.pk, status='processing', lease_token=job.lease_token,
        lease_until__gt=timezone.now(),
    )


def _failure_category(error):
    # Fixed categories only: never include exception text, commands, paths or stderr.
    if isinstance(error, subprocess.TimeoutExpired):
        return 'timeout'
    if isinstance(error, subprocess.CalledProcessError):
        return 'processor_exit'
    if isinstance(error, ProcessingError):
        return 'validation'
    if isinstance(error, OSError):
        return 'io'
    return 'unexpected'


def run_job(job):
    if not _leased(job).exists():
        return
    published = None
    try:
        if job.algorithm != algorithm_version():
            raise ProcessingError('处理算法已更新，请重新提交。')
        source = safe_path(job.source_path)
        record_id = ImageJob.objects.values_list('page__record_id', flat=True).get(pk=job.pk)
        output_dir = record_output_directory(record_id, job.owner_id)
        output_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix='work-', dir=output_dir) as temporary:
            work = Path(temporary)
            isolated = work / ('source' + source.suffix)
            shutil.copyfile(source, isolated)
            if digest_file(isolated) != job.source_digest:
                raise ProcessingError('原图已更新，请重新提交。')
            output = work / 'output.png'
            process_image(isolated, output, job.strength)
            if output.is_symlink() or not output.is_file():
                raise ProcessingError('未生成有效的处理图。')
            with Image.open(output) as image:
                if image.format != 'PNG':
                    raise ProcessingError('处理结果不是有效的 PNG 图片。')
                image.verify()
            with Image.open(output) as image:
                image.load()
            output_digest = digest_file(output)
            with transaction.atomic():
                # Fence before touching page state; stale workers cannot publish.
                if not _leased(job).update(error=''):
                    return
                current = ImageJob.objects.select_related('page').get(pk=job.pk)
                record = _lock_record(current.page.record_id)
                _reconcile(record)
                current = _leased(job).select_related('page').first()
                if current is None or current.page.source_revision != job.source_revision:
                    return
                # UUID+lease token gives every attempt its own immutable target.
                published = output_dir / f'{job.pk}-{job.lease_token}.png'
                os.replace(output, published)
                current.status = 'done'
                current.output_path = published.relative_to(Path(settings.HISTORY_ROOT).resolve()).as_posix()
                current.output_digest = output_digest
                current.finished_at = timezone.now()
                current.lease_until = None
                current.lease_token = None
                current.save()
                page = current.page
                page.current_job = current
                if page.adoption_serial == job.adoption_serial:
                    page.adopted = 'processed'
                page.save(update_fields=['current_job', 'adopted'])
                published = None
    except Exception as error:
        logger.warning('Image processing failed job=%s category=%s', job.pk, _failure_category(error))
        _leased(job).update(
            status='error', error='图片处理失败，请重试。',
            lease_token=None, lease_until=None, finished_at=timezone.now(),
        )
    finally:
        if published is not None:
            published.unlink(missing_ok=True)
