"""历史记录服务（DB 版，接口与 Flask 版 services/history.py 对齐）。"""
from __future__ import annotations

import os
import re
import shutil
import uuid
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from django.conf import settings

from .models import HistoryRecord
from .permissions import actor, capabilities, record_scope, task_directory, can_modify

STATUS_COMPLETED = 'completed'
STATUS_PARTIAL = 'partial'
STATUS_DRAFT = 'draft'
STATUS_GENERATING = 'generating'
STATUS_ERROR = 'error'


def _iso(dt: Optional[datetime]) -> Optional[str]:
    return dt.isoformat() if dt else None


def _merge_generation_audit(existing: Any, incoming: Any) -> Dict:
    """Merge audit snapshots without dropping data from another generation phase."""
    current = deepcopy(existing) if isinstance(existing, dict) else {}
    update = incoming if isinstance(incoming, dict) else {}

    for key, value in update.items():
        if key in ("context", "effective") and isinstance(value, dict):
            base = current.get(key) if isinstance(current.get(key), dict) else {}
            current[key] = {**base, **deepcopy(value)}
        elif key == "prompts" and isinstance(value, list):
            previous = current.get("prompts") if isinstance(current.get("prompts"), list) else []
            merged = deepcopy(previous)
            positions = {
                (item.get("phase"), item.get("prompt_name")): index
                for index, item in enumerate(merged)
                if isinstance(item, dict) and item.get("phase") and item.get("prompt_name")
            }
            for item in value:
                if not isinstance(item, dict):
                    continue
                identity = (item.get("phase"), item.get("prompt_name"))
                if identity in positions:
                    merged[positions[identity]] = deepcopy(item)
                else:
                    positions[identity] = len(merged)
                    merged.append(deepcopy(item))
            current[key] = merged
        else:
            current[key] = deepcopy(value)
    return current


def _to_detail(rec: HistoryRecord, user=None) -> Dict:
    from postprocessing.services import adopted_thumbnail_url
    outline = rec.outline or {"raw": "", "pages": []}
    images = rec.images or {"task_id": None, "generated": []}
    return {
        "id": rec.id,
        "title": rec.title,
        "created_at": _iso(rec.created_at),
        "updated_at": _iso(rec.updated_at),
        "outline": {
            "raw": outline.get("raw", ""),
            "organization": outline.get("organization", "自动"),
            "copy_preferences": outline.get("copy_preferences"),
            "generation_preferences": outline.get("generation_preferences"),
            "requested_preferences": outline.get("requested_preferences"),
            "growth_recommendation": outline.get("growth_recommendation"),
            **({"creation_inputs": outline.get("creation_inputs")} if can_modify(user, rec) else {}),
            "generation_record_id": outline.get("generation_record_id"),
            "pages": outline.get("pages", []),
        },
        "images": {
            "task_id": images.get("task_id"),
            "generated": images.get("generated", []),
        },
        "status": rec.status,
        "thumbnail": rec.thumbnail,
        "adopted_thumbnail_url": adopted_thumbnail_url(rec),
        "content": rec.content,
        "analysis_snapshots": rec.analysis_snapshots or [],
        "generation_audit": rec.generation_audit or {},
        "image_style": rec.image_style,
        "user_id": rec.user_id,
        **capabilities(user, rec),
    }


def _to_list_item(rec: HistoryRecord, user=None) -> Dict:
    from postprocessing.services import adopted_thumbnail_url
    outline = rec.outline or {"raw": "", "pages": []}
    images = rec.images or {"task_id": None, "generated": []}
    return {
        "id": rec.id,
        "title": rec.title,
        "created_at": _iso(rec.created_at),
        "updated_at": _iso(rec.updated_at),
        "status": rec.status,
        "thumbnail": rec.thumbnail,
        "adopted_thumbnail_url": adopted_thumbnail_url(rec),
        "page_count": len(outline.get("pages", [])),
        "task_id": images.get("task_id"),
        **capabilities(user, rec),
    }


class HistoryService:
    """历史记录服务。"""

    def __init__(self):
        self.history_dir = settings.HISTORY_ROOT

    # ==================== CRUD ====================

    def create_record(
        self,
        topic: str,
        outline: dict,
        task_id: str = None,
        user_id: str = None,
        image_style=None,
        generation_audit=None,
    ) -> str:
        record_id = str(uuid.uuid4())
        images = {"task_id": task_id, "generated": []} if task_id else {"task_id": None, "generated": []}
        rec = HistoryRecord.objects.create(
            id=record_id,
            user_id=user_id,
            title=(outline.get("title") if isinstance(outline, dict) else None) or topic,
            outline=outline or {"raw": "", "pages": []},
            images=images,
            status=STATUS_DRAFT,
            image_style=image_style or {},
            generation_audit=_merge_generation_audit({}, generation_audit),
        )
        return rec.id

    def get_record(self, record_id: str, sync_images: bool = False, user=None) -> Optional[Dict]:
        rec = HistoryRecord.objects.filter(id=record_id).first()
        if not rec:
            return None
        if sync_images:
            self._sync_record_images(rec)
        return _to_detail(rec, user)

    def update_record(self, record_id: str, **fields) -> bool:
        rec = HistoryRecord.objects.filter(id=record_id).first()
        if not rec:
            return False
        if 'title' in fields and fields['title'] is not None:
            rec.title = fields['title']
        if 'outline' in fields and fields['outline'] is not None:
            rec.outline = fields['outline']
        if 'content' in fields and fields['content'] is not None:
            rec.content = fields['content']
        if 'analysis_snapshots' in fields and fields['analysis_snapshots'] is not None:
            rec.analysis_snapshots = fields['analysis_snapshots']
        if 'generation_audit' in fields and fields['generation_audit'] is not None:
            rec.generation_audit = _merge_generation_audit(
                rec.generation_audit,
                fields['generation_audit'],
            )
        if 'image_style' in fields and fields['image_style'] is not None:
            rec.image_style = fields['image_style']
        if 'images' in fields and fields['images'] is not None:
            rec.images = fields['images']
        if 'status' in fields and fields['status'] is not None:
            rec.status = fields['status']
        if 'thumbnail' in fields and fields['thumbnail'] is not None:
            rec.thumbnail = fields['thumbnail']
        rec.save()
        return True

    def delete_record(self, record_id: str) -> bool:
        rec = HistoryRecord.objects.filter(id=record_id).first()
        if not rec:
            return False
        task_id = (rec.images or {}).get('task_id')
        from postprocessing.services import cleanup_record_outputs
        output_paths = list(rec.image_versions.values_list('jobs__output_path', flat=True))
        rec.delete()
        cleanup_record_outputs(record_id, rec.user_id, output_paths)
        # 清理磁盘图片目录 history/<user_id>/<task_id>（及其 _deai_out）
        if task_id:
            for name in (task_id, f"{task_id}_deai_out"):
                p = task_directory(rec.user_id, name, self.history_dir)
                if p is not None and p.exists():
                    shutil.rmtree(p, ignore_errors=True)
        return True

    # ==================== 列表 / 搜索 / 统计 ====================

    def _filtered_records(self, user, source=None, status=None, keyword=None):
        qs = record_scope(user, source)
        if status and status not in ('all', ''):
            qs = qs.filter(status=status)
        records = qs.order_by('-created_at', 'id')
        if keyword:
            term = keyword.lower()
            return [record for record in records if term in ' '.join([
                record.title or '', (record.outline or {}).get('raw', '') or '',
                (record.content or {}).get('copywriting', '') or '',
            ]).lower()]
        return records

    def list_records(self, page: int, page_size: int, status: Optional[str],
                     user_id: str, is_admin: bool, source=None, keyword=None) -> Dict:
        user = actor(user_id)
        records = self._filtered_records(user, source, status, keyword)
        total = len(records) if isinstance(records, list) else records.count()
        page = max(1, page)
        page_size = max(1, min(page_size, 100))
        total_pages = (total + page_size - 1) // page_size if total else 0
        items = records[(page - 1) * page_size: page * page_size]
        return {
            "records": [_to_list_item(r, user) for r in items],
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
        }

    def search_records(self, keyword: str, user_id: str, is_admin: bool,
                       source=None, status=None) -> List[Dict]:
        user = actor(user_id)
        return [_to_list_item(record, user)
                for record in self._filtered_records(user, source, status, keyword)]

    def get_statistics(self, user_id: str, is_admin: bool, source=None) -> Dict:
        qs = record_scope(actor(user_id), source)
        by_status = {}
        for s in qs.values_list('status', flat=True):
            by_status[s] = by_status.get(s, 0) + 1
        return {
            "total": qs.count(),
            "by_status": by_status,
        }

    # ==================== 归属与同步 ====================

    def find_owner_by_task(self, task_id: str) -> Optional[str]:
        """通过记录里的 task_id 反查归属用户。"""
        for rec in HistoryRecord.objects.only('user_id', 'images'):
            images = rec.images or {}
            if images.get('task_id') == task_id:
                return rec.user_id
        return None

    def sync_record_images(self, record_id: str, task_id: str, generated: List[str],
                           status: str = None, thumbnail: str = None) -> bool:
        """同步图片清单到记录（图片生成过程中调用）。"""
        rec = HistoryRecord.objects.filter(id=record_id).first()
        if not rec:
            return False
        images = dict(rec.images or {})
        images['task_id'] = task_id
        images['generated'] = generated
        rec.images = images
        if status:
            rec.status = status
        if thumbnail:
            rec.thumbnail = thumbnail
        rec.save()
        from postprocessing.services import sync_published_images
        sync_published_images(rec.id)
        return True

    def _sync_record_images(self, rec: HistoryRecord) -> None:
        """根据磁盘上的实际图片刷新记录的 generated 列表与状态。"""
        # Versioned records publish explicit pointers; disk scans must not adopt archived trials.
        if rec.image_candidates.exists():
            return
        images = rec.images or {}
        task_id = images.get('task_id')
        if not task_id:
            return
        task_dir = task_directory(rec.user_id, task_id, self.history_dir)
        if task_dir is None or not task_dir.exists():
            return
        generated = sorted(
            f for f in os.listdir(task_dir)
            if f.endswith(('.png', '.jpeg', '.jpg', '.webp')) and not f.startswith('thumb_')
        )
        changed = False
        if generated != images.get('generated', []):
            images['generated'] = generated
            rec.images = images
            changed = True
        # 根据数量推算状态
        pages = (rec.outline or {}).get('pages', [])
        expected = len(pages)
        if expected and len(generated) >= expected:
            new_status = STATUS_COMPLETED
        elif generated:
            new_status = STATUS_PARTIAL
        else:
            new_status = rec.status
        if new_status != rec.status:
            rec.status = new_status
            changed = True
        if changed:
            rec.save()

    def scan_and_sync_task_images(self, task_id: str) -> Dict:
        owner = self.find_owner_by_task(task_id)
        if not owner:
            return {"success": False, "error": f"任务不存在：{task_id}"}
        rec = HistoryRecord.objects.filter(user_id=owner).first()
        found = HistoryRecord.objects.filter(user_id=owner)
        target = None
        for r in found:
            if (r.images or {}).get('task_id') == task_id:
                target = r
                break
        if not target:
            return {"success": False, "error": f"任务不存在：{task_id}"}
        self._sync_record_images(target)
        return {"success": True, "images": (target.images or {}).get('generated', [])}

    def scan_all_tasks(self, user=None) -> Dict:
        if user is not None:
            records = record_scope(user)
            synced = 0
            failed = 0
            for record in records:
                try:
                    self._sync_record_images(record)
                    synced += 1
                except Exception:
                    failed += 1
            return {"success": True, "total_tasks": synced + failed,
                    "synced": synced, "failed": failed, "orphan_tasks": []}
        synced = 0
        failed = 0
        orphan_tasks = []
        total = 0
        for user_dir in self.history_dir.iterdir():
            if not user_dir.is_dir() or not user_dir.name.startswith('u_'):
                continue
            for child in user_dir.iterdir():
                if not child.is_dir():
                    continue
                name = child.name
                if name.endswith('_deai_out'):
                    continue
                task_id = name
                total += 1
                try:
                    self.scan_and_sync_task_images(task_id)
                    synced += 1
                except Exception:
                    failed += 1
        return {
            "success": True,
            "total_tasks": total,
            "synced": synced,
            "failed": failed,
            "orphan_tasks": orphan_tasks,
        }


_service_instance: Optional[HistoryService] = None


def get_history_service() -> HistoryService:
    global _service_instance
    if _service_instance is None:
        _service_instance = HistoryService()
    return _service_instance
