# -*- coding: utf-8 -*-
"""
_merge_thought_text — 从 react_handler_mixin.py 拆出

复制来源: react_handler_mixin.py 第42-48行
Author: 小沈 - 2026-05-31
"""


class MergeThoughtTextMixin:
    """合并thought和content文本"""

    @staticmethod
    def _merge_thought_text(thought: str, content: str) -> str:
        """复制自 react_handler_mixin.py 第42-48行"""
        _val = content
        if thought and thought.strip():
            _val = thought if thought == content else (thought + "\n" + content).strip()
        return _val
