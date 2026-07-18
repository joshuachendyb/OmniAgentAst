# -*- coding: utf-8 -*-
"""
ChunkBuffer — chunk拼接、阈值检测、flush管理 — 小沈 2026-05-25

消除 run_react_cycle 和 react_sse_wrapper 中3处重复的chunk flush逻辑。
"""

# 编辑历史:
# 2026-07-18 小欧 #6 fix: 删除重复定义的should_force_stop(44-51)与含未定义变量content的buggy clear(62-66); 运行时正确版(68-75/77-79)保留
# 2026-07-18 小欧 #46 fix: max_without_promote→max_chunks_before_stop，消除误导命名
# 【3.9修复 北京老陈 2026-05-31】阈值统一从constants.py读取
from app.constants import MAX_CONSECUTIVE_CHUNKS, MAX_CHUNKS_WITHOUT_PROMOTE  # noqa: F401 - 作为默认值使用


class ChunkBuffer:
    """管理chunk拼接、阈值检测、flush管理 — 小沈 2026-05-25

    使用场景:
        - run_react_cycle中chunk内容的累积和阈值检测
        - react_sse_wrapper中SSE chunk的累积逻辑
        - 所有需要"累积→阈值检测→flush"模式的场景

    返回数据说明:
        - append: 无返回值,修改内部状态
        - should_promote: 返回bool,True表示连续chunk数达到阈值(历史接口,当前引擎未使用)
        - should_force_stop: 返回bool,True表示累积超时需强制停止
        - flush: 返回str(buffer内容),同时清空buffer(历史接口,当前引擎未使用)
        - clear: 无返回值,仅清空buffer和计数器

    Author: 小沈 2026-05-25
    """

    # #46 fix: max_without_promote→max_chunks_before_stop 消除误导名 — 小欧 2026-07-18
    def __init__(self, max_consecutive: int = MAX_CONSECUTIVE_CHUNKS, max_chunks_before_stop: int = MAX_CHUNKS_WITHOUT_PROMOTE):
        self.buffer: str = ""
        self.consecutive_count: int = 0
        self.max_consecutive: int = max_consecutive
        self.max_chunks_before_stop: int = max_chunks_before_stop  # #46 fix: 原max_without_promote

    def append(self, content: str) -> None:
        self.buffer += content
        self.consecutive_count += 1

    def should_promote(self) -> bool:
        """连续chunk数达到阈值时返回True"""
        return self.consecutive_count >= self.max_consecutive

    def flush(self) -> str:
        """清空buffer并返回内容 — 纯buffer管理
        
        【3.9修复 北京老陈 2026-05-31】分离buffer管理和builder操作(SLAP)
        """
        result = self.buffer
        self.clear()
        return result

    def should_force_stop(self) -> bool:
        """chunk累积超时需强制停止时返回True

        【3.9修复 北京老陈 2026-05-31】防止LLM持续返回chunk导致无限循环
        小沈 2026-07-13: 计数器仅在 clear() 时重置(收到完整 response 时调用),
        不存在单独的 promote/flush 路径; 原注释声称"promote后重置"是误导, 已删除死代码。
        """
        return self.consecutive_count >= self.max_chunks_before_stop

    def clear(self) -> None:
        self.buffer = ""
        self.consecutive_count = 0
