"""图片生成服务"""
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Generator, List, Optional, Tuple

from django.conf import settings

from providers.config import get_active_image_provider, get_image_provider_config
from prompts.services import safe_format
from ..generators.factory import ImageGeneratorFactory
from ..generators.image_provider_policy import ImageProviderPolicy
from ..utils.image_compressor import compress_image
from .image_rate_limiter import ImageRateLimiter
from .task_cancel import is_cancelled, reset_cancel
from history.services import get_history_service

logger = logging.getLogger(__name__)


class ImageService:
    """图片生成服务类"""

    # 并发配置
    AUTO_RETRY_COUNT = 1  # 不自动重试，超时后让用户手动重试

    def __init__(self, provider_name: str = None, user_id: Optional[str] = None):
        """
        初始化图片生成服务

        Args:
            provider_name: 服务商名称，如果为None则使用配置文件中的激活服务商
            user_id: 当前操作用户 ID（用于按用户加载服务商配置）
        """
        logger.debug("初始化 ImageService...")
        self.user_id = user_id

        # 获取服务商配置（支持每用户配置覆盖）
        if provider_name is None:
            provider_name = get_active_image_provider(user_id)

        logger.info(f"使用图片服务商: {provider_name}")
        provider_config = get_image_provider_config(provider_name, user_id)

        # 创建生成器实例
        provider_type = provider_config.get('type', provider_name)
        logger.debug(f"创建生成器: type={provider_type}")
        self.generator = ImageGeneratorFactory.create(provider_type, provider_config)

        # 保存配置信息
        self.provider_name = provider_name
        self.provider_config = provider_config
        self.policy = ImageProviderPolicy.from_config(
            provider_config,
            default_model=provider_config.get('model', 'default-model'),
        )
        self.worker_count = self.policy.worker_count
        self.rate_limiter = ImageRateLimiter(
            max_concurrent=self.worker_count,
            interval_seconds=self.policy.request_interval_seconds,
        )
        self.history_service = get_history_service()

        # 检查是否启用短 prompt 模式
        self.use_short_prompt = provider_config.get('short_prompt', False)

        # 加载提示词模板
        self.prompt_template = self._load_prompt_template()
        self.prompt_template_short = self._load_prompt_template(short=True)

        # 历史记录根目录（settings.HISTORY_ROOT）
        self.history_root_dir = settings.HISTORY_ROOT
        os.makedirs(self.history_root_dir, exist_ok=True)

        # 当前任务的输出目录（每个任务一个子文件夹，按用户隔离）
        self.current_task_dir = None
        # 当前操作用户（图片目录按用户分开：history/<user_id>/<task_id>/）
        self.current_user_id = None

        # 存储任务状态（用于重试）
        self._task_states: Dict[str, Dict] = {}

        logger.info(f"ImageService 初始化完成: provider={provider_name}, type={provider_type}")

    def _task_dir(self, task_id: str, user_id: Optional[str] = None) -> str:
        """计算任务专属目录（按用户隔离：history/<user_id>/<task_id>/）

        user_id 显式传入时优先使用（避免并发请求互相覆盖共享的 current_user_id）。
        """
        user_id = user_id or self.current_user_id or 'default'
        return os.path.join(str(self.history_root_dir), user_id, task_id)

    def _resolve_task_owner(self, task_id: str, record_id: Optional[str] = None,
                            user_id: Optional[str] = None) -> str:
        """确定任务目录归属用户：优先任务/记录的实际归属者，其次请求用户

        图片必须写入记录归属者的目录，否则按 task_id 反查归属时找不到文件（404）。
        """
        if task_id:
            try:
                owner = self.history_service.find_owner_by_task(task_id)
                if owner:
                    return owner
            except Exception:
                pass
        if record_id:
            try:
                rec = self.history_service.get_record(record_id)
                if rec and rec.get('user_id'):
                    return rec['user_id']
            except Exception:
                pass
        return user_id or 'default'

    @staticmethod
    def _count_generated(generated_images: List[str]) -> int:
        return sum(1 for filename in generated_images if filename)

    @staticmethod
    def _remember_generated(generated_images: List[str], index: int, filename: str, total: int):
        target_len = max(len(generated_images), total, index + 1)
        while len(generated_images) < target_len:
            generated_images.append("")
        generated_images[index] = filename

    def _load_prompt_template(self, short: bool = False) -> str:
        """加载 Prompt 模板"""
        filename = "image_prompt_short.txt" if short else "image_prompt.txt"
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            filename
        )
        if not os.path.exists(prompt_path):
            # 如果短模板不存在，返回空字符串
            return ""
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _save_image(self, image_data: bytes, filename: str, task_dir: str = None) -> str:
        """
        保存图片到本地，同时生成缩略图

        Args:
            image_data: 图片二进制数据
            filename: 文件名
            task_dir: 任务目录（如果为None则使用当前任务目录）

        Returns:
            保存的文件路径
        """
        if task_dir is None:
            task_dir = self.current_task_dir

        if task_dir is None:
            raise ValueError("任务目录未设置")

        # 保存原图
        filepath = os.path.join(task_dir, filename)
        with open(filepath, "wb") as f:
            f.write(image_data)

        # 生成缩略图（50KB左右）
        thumbnail_data = compress_image(image_data, max_size_kb=50)
        thumbnail_filename = f"thumb_{filename}"
        thumbnail_path = os.path.join(task_dir, thumbnail_filename)
        with open(thumbnail_path, "wb") as f:
            f.write(thumbnail_data)

        return filepath

    def _merge_image_into_record(self, record_id: str, task_id: str, index: int,
                                 filename: str, total_count: Optional[int] = None) -> bool:
        """将单张已生成图片合并进历史记录，并同步状态与缩略图（对应 Flask 版 merge_generated_image）。

        Django 版 history.services 只提供 sync_record_images(record_id, task_id, generated,
        status, thumbnail)，这里读当前记录、按索引合并后调用它。
        """
        try:
            record = self.history_service.get_record(record_id)
            if not record:
                return False
            if total_count is None:
                total_count = len(record.get("outline", {}).get("pages", []))

            existing = (record.get("images") or {}).get("generated", [])
            generated = [item or "" for item in (existing or [])]
            target_len = max(len(generated), index + 1, total_count or 0)
            while len(generated) < target_len:
                generated.append("")
            generated[index] = filename

            completed = sum(1 for item in generated if item)
            if completed == 0:
                status = "draft"
            elif total_count and completed >= total_count:
                status = "completed"
            else:
                status = "partial"
            thumbnail = next((item for item in generated if item), None)

            return self.history_service.sync_record_images(
                record_id, task_id, generated, status=status, thumbnail=thumbnail
            )
        except Exception as e:
            logger.error(f"合并图片到历史记录失败: {e}")
            return False

    @staticmethod
    def _has_images(generated: Optional[List[str]]) -> bool:
        return any(bool(item) for item in (generated or []))

    def _generate_single_image(
        self,
        page: Dict,
        task_id: str,
        reference_image: Optional[bytes] = None,
        retry_count: int = 0,
        full_outline: str = "",
        user_images: Optional[List[bytes]] = None,
        user_topic: str = "",
        record_id: Optional[str] = None,
        total_count: Optional[int] = None,
        task_dir: Optional[str] = None,
        prompt_text: Optional[str] = None,
    ) -> Tuple[int, bool, Optional[str], Optional[str]]:
        """
        生成单张图片（带自动重试）

        Args:
            page: 页面数据
            task_id: 任务ID
            reference_image: 参考图片（封面图）
            retry_count: 当前重试次数
            full_outline: 完整的大纲文本
            user_images: 用户上传的参考图片列表
            user_topic: 用户原始输入
            task_dir: 本请求的任务输出目录（显式传入，避免并发时共享 current_task_dir 被串改）

        Returns:
            (index, success, filename, error_message)
        """
        index = page["index"]
        page_type = page["type"]
        page_content = page["content"]

        # 用户已取消：不再发起该页生成
        if is_cancelled(self.user_id or self.current_user_id):
            return (index, False, None, '已取消')

        try:
            logger.debug(f"生成图片 [{index}]: type={page_type}")

            # 根据配置选择模板（短 prompt 或完整 prompt）
            if prompt_text:
                # 用户自定义提示词优先（缺失占位符原样保留，不报错）
                prompt = safe_format(prompt_text, {
                    "page_content": page_content,
                    "page_type": page_type,
                    "full_outline": full_outline,
                    "user_topic": user_topic if user_topic else "未提供",
                })
                logger.debug(f"  使用用户自定义提示词 ({len(prompt)} 字符)")
            elif self.use_short_prompt and self.prompt_template_short:
                # 短 prompt 模式：只包含页面类型和内容
                prompt = self.prompt_template_short.format(
                    page_content=page_content,
                    page_type=page_type
                )
                logger.debug(f"  使用短 prompt 模式 ({len(prompt)} 字符)")
            else:
                # 完整 prompt 模式：包含大纲和用户需求
                prompt = self.prompt_template.format(
                    page_content=page_content,
                    page_type=page_type,
                    full_outline=full_outline,
                    user_topic=user_topic if user_topic else "未提供"
                )

            # 调用生成器生成图片。所有路径共用 limiter，避免批量和重试打爆上游。
            with self.rate_limiter.acquire():
                if self.provider_config.get('type') == 'google_genai':
                    logger.debug(f"  使用 Google GenAI 生成器")
                    image_data = self.generator.generate_image(
                        prompt=prompt,
                        aspect_ratio=self.provider_config.get('default_aspect_ratio', '3:4'),
                        temperature=self.provider_config.get('temperature', 1.0),
                        model=self.provider_config.get('model', 'gemini-3-pro-image-preview'),
                        reference_image=reference_image,
                    )
                elif self.provider_config.get('type') == 'image_api':
                    logger.debug(f"  使用 Image API 生成器")
                    # Image API 支持多张参考图片
                    # 组合参考图片：用户上传的图片 + 封面图
                    reference_images = []
                    if user_images:
                        reference_images.extend(user_images)
                    if reference_image:
                        reference_images.append(reference_image)

                    image_data = self.generator.generate_image(
                        prompt=prompt,
                        aspect_ratio=self.provider_config.get('default_aspect_ratio', '3:4'),
                        temperature=self.provider_config.get('temperature', 1.0),
                        model=self.provider_config.get('model', 'nano-banana-2'),
                        reference_images=reference_images if reference_images else None,
                    )
                else:
                    logger.debug(f"  使用 OpenAI 兼容生成器")
                    image_data = self.generator.generate_image(
                        prompt=prompt,
                        size=self.provider_config.get('default_size', '1024x1024'),
                        model=self.provider_config.get('model'),
                        quality=self.provider_config.get('quality', 'standard'),
                    )

            # 生成过程中用户取消：丢弃结果，不保存、不合并
            if is_cancelled(self.user_id or self.current_user_id):
                return (index, False, None, '已取消')

            # 保存图片（优先使用显式传入的任务目录，避免并发请求串写）
            filename = f"{index}.png"
            self._save_image(image_data, filename, task_dir or self.current_task_dir)
            logger.info(f"✅ 图片 [{index}] 生成成功: {filename}")

            if record_id:
                self._merge_image_into_record(
                    record_id,
                    task_id,
                    index,
                    filename,
                    total_count=total_count,
                )

            return (index, True, filename, None)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 图片 [{index}] 生成失败: {error_msg[:200]}")
            return (index, False, None, error_msg)

    def generate_images(
        self,
        pages: list,
        task_id: str = None,
        full_outline: str = "",
        user_images: Optional[List[bytes]] = None,
        user_topic: str = "",
        record_id: Optional[str] = None,
        force: bool = False,
        user_id: Optional[str] = None,
        image_prompt_text: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        生成图片（生成器，支持 SSE 流式返回）
        优化版本：先生成封面，然后并发生成其他页面

        Args:
            pages: 页面列表
            task_id: 任务 ID（可选）
            full_outline: 完整的大纲文本（用于保持风格一致）
            user_images: 用户上传的参考图片列表（可选）
            user_topic: 用户原始输入（用于保持意图一致）
            user_id: 当前操作用户 ID（图片目录按用户隔离）

        Yields:
            进度事件字典
        """
        if user_id:
            self.current_user_id = user_id

        # 开始新任务：清除该用户的取消标记
        reset_cancel(user_id or self.user_id)

        if record_id and not force:
            cached_events = self.get_cached_generation_events(record_id, pages)
            if cached_events:
                for event in cached_events:
                    yield event
                return

        if task_id is None and record_id:
            record = self.history_service.get_record(record_id, sync_images=True)
            task_id = record.get("images", {}).get("task_id") if record else None

        if task_id is None:
            task_id = f"task_{uuid.uuid4().hex[:8]}"

        logger.info(f"开始图片生成任务: task_id={task_id}, pages={len(pages)}")

        # 创建任务专属目录（按归属用户隔离）。归属优先取记录/task 的实际归属者，
        # 再作为局部变量传递，避免并发请求通过共享的 current_task_dir/current_user_id 串写
        task_dir = self._task_dir(task_id, self._resolve_task_owner(task_id, record_id, user_id))
        os.makedirs(task_dir, exist_ok=True)
        self.current_task_dir = task_dir
        logger.debug(f"任务目录: {task_dir}")

        total = len(pages)
        generated_images = [""] * total
        failed_pages = []
        cover_image_data = None

        # 压缩用户上传的参考图到200KB以内（减少内存和传输开销）
        compressed_user_images = None
        if user_images:
            compressed_user_images = [compress_image(img, max_size_kb=200) for img in user_images]

        # 初始化任务状态
        self._task_states[task_id] = {
            "pages": pages,
            "generated": {},
            "failed": {},
            "cover_image": None,
            "full_outline": full_outline,
            "user_images": compressed_user_images,
            "user_topic": user_topic
        }

        # ==================== 第一阶段：生成封面 ====================
        cover_page = None
        other_pages = []

        for page in pages:
            if page["type"] == "cover":
                cover_page = page
            else:
                other_pages.append(page)

        # 如果没有封面，使用第一页作为封面
        if cover_page is None and len(pages) > 0:
            cover_page = pages[0]
            other_pages = pages[1:]

        if cover_page:
            # 发送封面生成进度
            yield {
                "event": "progress",
                "data": {
                    "index": cover_page["index"],
                    "status": "generating",
                    "message": "正在生成封面...",
                    "current": 1,
                    "total": total,
                    "phase": "cover"
                }
            }

            # 生成封面（使用用户上传的图片作为参考）
            index, success, filename, error = self._generate_single_image(
                cover_page, task_id, reference_image=None, full_outline=full_outline,
                user_images=compressed_user_images, user_topic=user_topic,
                record_id=record_id, total_count=total, task_dir=task_dir,
                prompt_text=image_prompt_text,
            )

            if success:
                self._remember_generated(generated_images, index, filename, total)
                self._task_states[task_id]["generated"][index] = filename

                # 读取封面图片作为参考，并立即压缩到200KB以内
                cover_path = os.path.join(task_dir, filename)
                with open(cover_path, "rb") as f:
                    cover_image_data = f.read()

                # 压缩封面图（减少内存占用和后续传输开销）
                cover_image_data = compress_image(cover_image_data, max_size_kb=200)
                self._task_states[task_id]["cover_image"] = cover_image_data

                yield {
                    "event": "complete",
                    "data": {
                        "index": index,
                        "status": "done",
                        "image_url": f"/api/images/{task_id}/{filename}",
                        "phase": "cover"
                    }
                }
            else:
                failed_pages.append(cover_page)
                self._task_states[task_id]["failed"][index] = error

                yield {
                    "event": "error",
                    "data": {
                        "index": index,
                        "status": "error",
                        "message": error,
                        "retryable": True,
                        "phase": "cover"
                    }
                }

        # ==================== 第二阶段：生成其他页面 ====================
        if other_pages:
            high_concurrency = self.worker_count > 1

            if high_concurrency:
                # 高并发模式：并行生成
                yield {
                    "event": "progress",
                    "data": {
                        "status": "batch_start",
                        "message": f"开始并发生成 {len(other_pages)} 页内容...",
                        "current": self._count_generated(generated_images),
                        "total": total,
                        "phase": "content"
                    }
                }

                # 使用线程池并发生成
                with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
                    # 提交所有任务
                    future_to_page = {
                        executor.submit(
                            self._generate_single_image,
                            page,
                            task_id,
                            cover_image_data,  # 使用封面作为参考
                            0,  # retry_count
                            full_outline,  # 传入完整大纲
                            compressed_user_images,  # 用户上传的参考图片（已压缩）
                            user_topic,  # 用户原始输入
                            record_id,
                            total,
                            task_dir,  # 显式传入本请求的任务目录
                            image_prompt_text  # 用户自定义图片提示词（可选）
                        ): page
                        for page in other_pages
                    }

                    # 发送每个页面的进度
                    for page in other_pages:
                        yield {
                            "event": "progress",
                            "data": {
                                "index": page["index"],
                                "status": "generating",
                                "current": self._count_generated(generated_images) + 1,
                                "total": total,
                                "phase": "content"
                            }
                        }

                    # 收集结果
                    for future in as_completed(future_to_page):
                        page = future_to_page[future]
                        try:
                            index, success, filename, error = future.result()

                            if success:
                                self._remember_generated(generated_images, index, filename, total)
                                self._task_states[task_id]["generated"][index] = filename

                                yield {
                                    "event": "complete",
                                    "data": {
                                        "index": index,
                                        "status": "done",
                                        "image_url": f"/api/images/{task_id}/{filename}",
                                        "phase": "content"
                                    }
                                }
                            else:
                                failed_pages.append(page)
                                self._task_states[task_id]["failed"][index] = error

                                yield {
                                    "event": "error",
                                    "data": {
                                        "index": index,
                                        "status": "error",
                                        "message": error,
                                        "retryable": True,
                                        "phase": "content"
                                    }
                                }

                        except Exception as e:
                            failed_pages.append(page)
                            error_msg = str(e)
                            self._task_states[task_id]["failed"][page["index"]] = error_msg

                            yield {
                                "event": "error",
                                "data": {
                                    "index": page["index"],
                                    "status": "error",
                                    "message": error_msg,
                                    "retryable": True,
                                    "phase": "content"
                                }
                            }
            else:
                # 顺序模式：逐个生成
                yield {
                    "event": "progress",
                    "data": {
                        "status": "batch_start",
                        "message": f"开始顺序生成 {len(other_pages)} 页内容...",
                        "current": self._count_generated(generated_images),
                        "total": total,
                        "phase": "content"
                    }
                }

                for page in other_pages:
                    # 发送生成进度
                    yield {
                        "event": "progress",
                        "data": {
                            "index": page["index"],
                            "status": "generating",
                            "current": self._count_generated(generated_images) + 1,
                            "total": total,
                            "phase": "content"
                        }
                    }

                    # 生成单张图片
                    index, success, filename, error = self._generate_single_image(
                        page,
                        task_id,
                        cover_image_data,
                        0,
                        full_outline,
                        compressed_user_images,
                        user_topic,
                        record_id,
                        total,
                        task_dir,
                        image_prompt_text
                    )

                    if success:
                        self._remember_generated(generated_images, index, filename, total)
                        self._task_states[task_id]["generated"][index] = filename

                        yield {
                            "event": "complete",
                            "data": {
                                "index": index,
                                "status": "done",
                                "image_url": f"/api/images/{task_id}/{filename}",
                                "phase": "content"
                            }
                        }
                    else:
                        failed_pages.append(page)
                        self._task_states[task_id]["failed"][index] = error

                        yield {
                            "event": "error",
                            "data": {
                                "index": index,
                                "status": "error",
                                "message": error,
                                "retryable": True,
                                "phase": "content"
                            }
                        }

        # ==================== 完成 ====================
        yield {
            "event": "finish",
            "data": {
                "success": len(failed_pages) == 0,
                "task_id": task_id,
                "images": generated_images,
                "total": total,
                "completed": self._count_generated(generated_images),
                "failed": len(failed_pages),
                "failed_indices": [p["index"] for p in failed_pages]
            }
        }

    def get_cached_generation_events(self, record_id: str, pages: list) -> List[Dict[str, Any]]:
        record = self.history_service.get_record(record_id, sync_images=True)
        if not record:
            return []

        images = record.get("images") or {}
        task_id = images.get("task_id")
        generated = images.get("generated") or []
        if not task_id or not self._has_images(generated):
            return []

        total = len(pages)
        completed = 0
        failed_indices = []
        events: List[Dict[str, Any]] = []

        for page in pages:
            index = page.get("index")
            filename = generated[index] if isinstance(index, int) and index < len(generated) else ""
            if filename:
                completed += 1
                events.append({
                    "event": "complete",
                    "data": {
                        "index": index,
                        "status": "done",
                        "image_url": f"/api/images/{task_id}/{filename}",
                        "phase": "cached",
                        "cached": True,
                    }
                })
            else:
                failed_indices.append(index)
                events.append({
                    "event": "error",
                    "data": {
                        "index": index,
                        "status": "error",
                        "message": "历史记录中缺少该页图片，可手动补全",
                        "retryable": True,
                        "phase": "cached",
                        "cached": True,
                    }
                })

        events.append({
            "event": "finish",
            "data": {
                "success": len(failed_indices) == 0,
                "task_id": task_id,
                "images": generated,
                "total": total,
                "completed": completed,
                "failed": len(failed_indices),
                "failed_indices": failed_indices,
                "cached": True,
            }
        })
        return events

    def retry_single_image(
        self,
        task_id: str,
        page: Dict,
        use_reference: bool = True,
        full_outline: str = "",
        user_topic: str = "",
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
        image_prompt_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        重试生成单张图片

        Args:
            task_id: 任务ID
            page: 页面数据
            use_reference: 是否使用封面作为参考
            full_outline: 完整大纲文本（从前端传入）
            user_topic: 用户原始输入（从前端传入）
            user_id: 当前操作用户 ID（图片目录按用户隔离）

        Returns:
            生成结果
        """
        if user_id:
            self.current_user_id = user_id

        # 新的重试/重新生成：清除该用户的取消标记
        reset_cancel(user_id or self.user_id)

        # 用任务的归属用户计算任务目录并作为局部变量传递，避免并发串写
        task_dir = self._task_dir(task_id, self._resolve_task_owner(task_id, record_id, user_id))
        os.makedirs(task_dir, exist_ok=True)
        self.current_task_dir = task_dir

        reference_image = None
        user_images = None

        # 首先尝试从任务状态中获取上下文
        if task_id in self._task_states:
            task_state = self._task_states[task_id]
            if use_reference:
                reference_image = task_state.get("cover_image")
            # 如果没有传入上下文，则使用任务状态中的
            if not full_outline:
                full_outline = task_state.get("full_outline", "")
            if not user_topic:
                user_topic = task_state.get("user_topic", "")
            user_images = task_state.get("user_images")

        # 如果任务状态中没有封面图，尝试从文件系统加载
        if use_reference and reference_image is None:
            cover_path = os.path.join(task_dir, "0.png")
            if os.path.exists(cover_path):
                with open(cover_path, "rb") as f:
                    cover_data = f.read()
                # 压缩封面图到 200KB
                reference_image = compress_image(cover_data, max_size_kb=200)

        total_count = None
        if task_id in self._task_states:
            total_count = len(self._task_states[task_id].get("pages", []))

        index, success, filename, error = self._generate_single_image(
            page,
            task_id,
            reference_image,
            0,
            full_outline,
            user_images,
            user_topic,
            record_id,
            total_count,
            task_dir,
            image_prompt_text
        )

        if success:
            if task_id in self._task_states:
                self._task_states[task_id]["generated"][index] = filename
                if index in self._task_states[task_id]["failed"]:
                    del self._task_states[task_id]["failed"][index]

            return {
                "success": True,
                "index": index,
                "image_url": f"/api/images/{task_id}/{filename}"
            }
        else:
            return {
                "success": False,
                "index": index,
                "error": error,
                "retryable": True
            }

    def retry_failed_images(
        self,
        task_id: str,
        pages: List[Dict],
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
        image_prompt_text: Optional[str] = None,
    ) -> Generator[Dict[str, Any], None, None]:
        """
        批量重试失败的图片

        Args:
            task_id: 任务ID
            pages: 需要重试的页面列表
            user_id: 当前操作用户 ID（图片目录按用户隔离）

        Yields:
            进度事件
        """
        if user_id:
            self.current_user_id = user_id

        # 新的批量重试：清除该用户的取消标记
        reset_cancel(user_id or self.user_id)

        # 用任务的归属用户计算任务目录并作为局部变量传递，避免并发串写
        task_dir = self._task_dir(task_id, self._resolve_task_owner(task_id, record_id, user_id))
        os.makedirs(task_dir, exist_ok=True)
        self.current_task_dir = task_dir

        # 获取参考图和上下文
        reference_image = None
        user_images = None
        user_topic = ""
        if task_id in self._task_states:
            task_state = self._task_states[task_id]
            reference_image = task_state.get("cover_image")
            user_images = task_state.get("user_images")
            user_topic = task_state.get("user_topic", "")

        if reference_image is None:
            cover_path = os.path.join(task_dir, "0.png")
            if os.path.exists(cover_path):
                with open(cover_path, "rb") as f:
                    reference_image = compress_image(f.read(), max_size_kb=200)

        total = len(pages)
        success_count = 0
        failed_count = 0

        yield {
            "event": "retry_start",
            "data": {
                "total": total,
                "message": f"开始重试 {total} 张失败的图片"
            }
        }

        # 从任务状态中获取完整大纲
        full_outline = ""
        if task_id in self._task_states:
            full_outline = self._task_states[task_id].get("full_outline", "")
        total_count = None
        if task_id in self._task_states:
            total_count = len(self._task_states[task_id].get("pages", []))
        if record_id:
            record = self.history_service.get_record(record_id)
            if record:
                total_count = total_count or len(record.get("outline", {}).get("pages", []))

        def handle_result(page: Dict, result: Tuple[int, bool, Optional[str], Optional[str]]):
            nonlocal success_count, failed_count
            index, success, filename, error = result
            if success:
                success_count += 1
                if task_id in self._task_states:
                    self._task_states[task_id]["generated"][index] = filename
                    if index in self._task_states[task_id]["failed"]:
                        del self._task_states[task_id]["failed"][index]
                return {
                    "event": "complete",
                    "data": {
                        "index": index,
                        "status": "done",
                        "image_url": f"/api/images/{task_id}/{filename}"
                    }
                }

            failed_count += 1
            return {
                "event": "error",
                "data": {
                    "index": index,
                    "status": "error",
                    "message": error,
                    "retryable": True
                }
            }

        if self.worker_count > 1:
            with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
                future_to_page = {
                    executor.submit(
                        self._generate_single_image,
                        page,
                        task_id,
                        reference_image,
                        0,
                        full_outline,
                        user_images,
                        user_topic,
                        record_id,
                        total_count,
                        task_dir,
                        image_prompt_text
                    ): page
                    for page in pages
                }

                for future in as_completed(future_to_page):
                    page = future_to_page[future]
                    try:
                        yield handle_result(page, future.result())
                    except Exception as e:
                        failed_count += 1
                        yield {
                            "event": "error",
                            "data": {
                                "index": page["index"],
                                "status": "error",
                                "message": str(e),
                                "retryable": True
                            }
                        }
        else:
            for page in pages:
                result = self._generate_single_image(
                    page,
                    task_id,
                    reference_image,
                    0,
                    full_outline,
                    user_images,
                    user_topic,
                    record_id,
                    total_count,
                    task_dir,
                    image_prompt_text
                )
                yield handle_result(page, result)

        yield {
            "event": "retry_finish",
            "data": {
                "success": failed_count == 0,
                "total": total,
                "completed": success_count,
                "failed": failed_count
            }
        }

    def regenerate_image(
        self,
        task_id: str,
        page: Dict,
        use_reference: bool = True,
        full_outline: str = "",
        user_topic: str = "",
        record_id: Optional[str] = None,
        user_id: Optional[str] = None,
        image_prompt_text: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        重新生成图片（用户手动触发，即使成功的也可以重新生成）

        Args:
            task_id: 任务ID
            page: 页面数据
            use_reference: 是否使用封面作为参考
            full_outline: 完整大纲文本
            user_topic: 用户原始输入
            user_id: 当前操作用户 ID（图片目录按用户隔离）
            image_prompt_text: 用户自定义图片提示词（可选）

        Returns:
            生成结果
        """
        return self.retry_single_image(
            task_id, page, use_reference,
            full_outline=full_outline,
            user_topic=user_topic,
            record_id=record_id,
            user_id=user_id,
            image_prompt_text=image_prompt_text
        )

    def get_image_path(self, task_id: str, filename: str, user_id: Optional[str] = None) -> str:
        """
        获取图片完整路径（按用户隔离）

        Args:
            task_id: 任务ID
            filename: 文件名
            user_id: 用户 ID（缺省用当前用户）

        Returns:
            完整路径
        """
        owner = user_id or self.current_user_id or 'default'
        task_dir = os.path.join(str(self.history_root_dir), owner, task_id)
        return os.path.join(task_dir, filename)

    def get_task_state(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self._task_states.get(task_id)

    def cleanup_task(self, task_id: str):
        """清理任务状态（释放内存）"""
        if task_id in self._task_states:
            del self._task_states[task_id]


# 全局服务实例（按用户 ID 缓存，支持每用户配置）
_service_instances: Dict[str, "ImageService"] = {}

def get_image_service(user_id: Optional[str] = None) -> ImageService:
    """获取图片生成服务实例（按用户 ID 缓存，配置按用户加载）"""
    global _service_instances
    key = user_id or '__default__'
    if key not in _service_instances:
        _service_instances[key] = ImageService(user_id=user_id)
    return _service_instances[key]

def reset_image_service(user_id: Optional[str] = None):
    """重置全局服务实例（配置更新后调用）。

    user_id 为 None 时清空全部实例，否则只重置指定用户的实例。
    """
    global _service_instances
    if user_id is None:
        _service_instances.clear()
    else:
        _service_instances.pop(user_id, None)
        _service_instances.pop('__default__', None)
