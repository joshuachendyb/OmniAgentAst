# -*- coding: utf-8 -*-
"""
ChunkBuffer — chunk拼接、阈值检测、flush管理 — 小沈 2026-05-25

消除 run_stream 和 react_sse_wrapper 中3处重复的chunk flush逻辑。
"""

from __future__ import annotations

from typing import TYPE_CHECKING

# 【3.9修复 北京老陈 2026-05-31】阈值统一从constants.py读取
from app.constants import MAX_CONSECUTIVE_CHUNKS

if TYPE_CHECKING:
    from app.services.agent.message_builder import MessageBuilder

# chunk累积超时：连续收到多少个chunk未触发promote则强制停止
# 防止LLM持续返回chunk导致无限循环
MAX_CHUNKS_WITHOUT_PROMOTE = 50


class ChunkBuffer:
    """管理chunk拼接、阈值检测、flush到message_builder

    使用场景:
        - run_stream中chunk内容的累积和阈值检测
        - react_sse_wrapper中SSE chunk的累积逻辑
        - 所有需要"累积→阈值检测→flush"模式的场景

    使用示例:
        buffer = ChunkBuffer(max_consecutive=5)
        buffer.append("hello")
        buffer.append(" world")
        if buffer.should_promote():
            content = buffer.flush_to(message_builder)

    返回数据说明:
        - append: 无返回值，修改内部状态
        - should_promote: 返回bool，True表示连续chunk数达到阈值
        - should_force_stop: 返回bool，True表示累积超时需强制停止
        - flush_to: 返回str（buffer内容），同时清空buffer并写入MessageBuilder
        - clear: 无返回值，仅清空buffer和计数器

    Author: 小沈 2026-05-25
    """

    def __init__(self, max_consecutive: int = MAX_CONSECUTIVE_CHUNKS):
        self.buffer: str = ""
        self.consecutive_count: int = 0
        self.max_consecutive: int = max_consecutive

    def append(self, content: str) -> None:
        self.buffer += content
        self.consecutive_count += 1

    def should_promote(self) -> bool:
        """连续chunk数达到阈值时返回True"""
        return self.consecutive_count >= self.max_consecutive

    def should_force_stop(self) -> bool:
        """chunk累积超时需强制停止时返回True
        
        【3.9修复 北京老陈 2026-05-31】防止LLM持续返回chunk导致无限循环
        只有连续chunk未触发promote时才计数，promote后重置
        """
        return self.consecutive_count >= MAX_CHUNKS_WITHOUT_PROMOTE

    def flush(self) -> str:
        """清空buffer并返回内容 — 纯buffer管理
        
        【3.9修复 北京老陈 2026-05-31】分离buffer管理和builder操作（SLAP）
        """
        result = self.buffer
        self.clear()
        return result

    def flush_to(self, builder: "MessageBuilder") -> str:
        """清空buffer、写入builder、返回内容 — 兼容旧接口
        
        注意：此方法混合了buffer管理和builder操作，新代码应使用flush()
        """
        result = self.buffer
        if result:
            builder.temp_history.clear()
            builder.add_assistant(result)
        self.clear()
        return result

    def clear(self) -> None:
        self.buffer = ""
        self.consecutive_count = 0
