"""任务取消注册表（按用户维度）。

前端点击"取消"后调用后端取消接口，把用户 ID 加入取消集合；
各生成服务在关键节点检查该集合，命中则立即停止后续工作
（图片：不再发起新的页面生成；大纲/文案：完成后的结果作废、不落历史）。
"""
from __future__ import annotations

import threading
from typing import Set

# 已标记取消的用户集合（线程安全）
_cancelled_users: Set[str] = set()
_guard = threading.Lock()


def cancel_user(user_id) -> None:
    """标记某个用户的当前任务为已取消。"""
    if not user_id:
        return
    with _guard:
        _cancelled_users.add(str(user_id))


def reset_cancel(user_id) -> None:
    """开始新任务前清除该用户的取消标记。"""
    if not user_id:
        return
    with _guard:
        _cancelled_users.discard(str(user_id))


def is_cancelled(user_id) -> bool:
    """判断该用户当前任务是否已被取消。"""
    if not user_id:
        return False
    with _guard:
        return str(user_id) in _cancelled_users