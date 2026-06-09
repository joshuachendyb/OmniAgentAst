# -*- coding: utf-8 -*-
"""
文本处理工具函数 — 小沈 2026-06-09

【公共函数规范】
本文件是公共utility模块,所有文本处理相关公共函数必须在此定义。
禁止在业务代码中重复定义公共函数。

Author: 小沈 - 2026-06-09
"""


def smart_truncate_text(content: str, budget: int, head_ratio: float = 0.6) -> str:
    """智能截断文本 — 小沈 2026-06-09 提取为公用函数
    
    Args:
        content: 待截断文本
        budget: 最大长度预算
        head_ratio: 头部比例（默认0.6）
    
    Returns:
        截断后的文本
    
    功能：
        - 保留头部和尾部，省略中间
        - 确保不超预算
        - 添加省略标记
    """
    if len(content) <= budget:
        return content
    
    OMISSION_TEXT_LEN = 50
    if budget <= OMISSION_TEXT_LEN + 10:
        return content[:budget]
    
    head_budget = int(budget * head_ratio)
    tail_budget = budget - head_budget - OMISSION_TEXT_LEN
    head = content[:head_budget]
    tail = content[-tail_budget:] if tail_budget > 0 else ""
    result = f"{head}\n... [中间省略 {len(content) - budget} 字符] ...\n{tail}"
    
    if len(result) > budget:
        result = result[:budget]
    
    return result


__all__ = [
    "smart_truncate_text",
]