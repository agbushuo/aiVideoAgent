"""SSE (Server-Sent Events) 事件流系统

提供单向实时推送，替代 WebSocket 用于任务进度广播。
支持按 task_id 过滤，自动管理连接生命周期。
"""

from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator

# 活跃的 SSE 连接集合
# 每个连接是一个 dict: {"task_filter": task_id or None, "queue": asyncio.Queue}
_active_connections: list[dict[str, Any]] = []


def _add_connection(task_filter: str | None, queue: asyncio.Queue) -> None:
    """添加 SSE 连接"""
    _active_connections.append({
        "task_filter": task_filter,
        "queue": queue,
        "created_at": time.time(),
    })


def _remove_connection(queue: asyncio.Queue) -> None:
    """移除 SSE 连接"""
    global _active_connections
    _active_connections = [
        c for c in _active_connections
        if c["queue"] is not queue
    ]


async def broadcast_event(event_type: str, data: dict[str, Any]) -> None:
    """广播事件给所有匹配的 SSE 连接

    Args:
        event_type: 事件类型 (task_status, stage_start, log, etc.)
        data: 事件数据（必须包含 task_id 字段）
    """
    task_id = data.get("task_id")
    dead = []

    for conn in _active_connections:
        # 过滤：如果连接订阅了特定 task，只推送该 task 的事件
        if conn["task_filter"] and task_id != conn["task_filter"]:
            continue

        try:
            conn["queue"].put_nowait({
                "event": event_type,
                "data": data,
            })
        except asyncio.QueueFull:
            dead.append(conn)

    # 清理队列已满的连接
    for conn in dead:
        _remove_connection(conn["queue"])


async def event_stream(task_id: str | None = None) -> AsyncIterator[str]:
    """SSE 事件生成器

    用法:
        @app.get("/api/events")
        async def events(task_id: str | None = None):
            return StreamingResponse(
                event_stream(task_id),
                media_type="text/event-stream",
            )
    """
    queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
    _add_connection(task_id, queue)

    try:
        while True:
            try:
                item = await asyncio.wait_for(queue.get(), timeout=30)
            except asyncio.TimeoutError:
                # 发送 keepalive 评论，防止代理超时
                yield ": keepalive\n\n"
                continue

            event_type = item["event"]
            data = item["data"]

            yield f"event: {event_type}\n"
            yield f"data: {json.dumps(data, ensure_ascii=False, default=str)}\n\n"

    except GeneratorExit:
        # 客户端断开连接
        pass
    finally:
        _remove_connection(queue)
