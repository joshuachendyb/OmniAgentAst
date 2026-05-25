# -*- coding: utf-8 -*-
"""
ChunkBuffer — chunk拼接、阈值检测、flush管理 — 小沈 2026-05-25

消除 run_stream 和 react_sse_wrapper 中3处重复的chunk flush逻辑。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.agent.message_builder import MessageBuilder


class ChunkBuffer:
    """管理chunk拼接、阈值检测、flush到message_builder

    使用场景:
        - run_stream中chunk内容的累积和阈值检测
        - react_sse_wrapper中SSE chunk的累积逻辑
        - 所有需要"累积→阈值检测→flush"模式的场景

    使用示例:
        buffer = ChunkBuffer(max_consecutive=10)
        buffer.append("hello")
        buffer.append(" world")
        if buffer.should_promote():
            content = buffer.flush_to(message_builder)

    返回数据说明:
        - append: 无返回值，修改内部状态
        - should_promote: 返回bool，True表示连续chunk数达到阈值
        - flush_to: 返回str（buffer内容），同时清空buffer并写入MessageBuilder
        - clear: 无返回值，仅清空buffer和计数器

    Author: 小沈 2026-05-25
    """

    def __init__(self, max_consecutive: int = 10):
        self.buffer: str = ""
        self.consecutive_count: int = 0
        self.max_consecutive: int = max_consecutive

    def append(self, content: str) -> None:
        self.buffer += content
        self.consecutive_count += 1

    def should_promote(self) -> bool:
        return self.consecutive_count >= self.max_consecutive

    def flush_to(self, builder: "MessageBuilder") -> str:
        result = self.buffer
        if result:
            builder.temp_history.clear()
            builder.add_assistant(result)
        self.clear()
        return result

    def clear(self) -> None:
        self.buffer = ""
        self.consecutive_count = 0
