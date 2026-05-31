# -*- coding: utf-8 -*-
"""
Prompt组装器 — 统一入口，按固定顺序编排三层Prompt贡献

三层编排顺序：
  ① SystemAdapter.build_context()  — 系统自适应（OS/路径/命令格式）
  ② BasePrompts.build_full_system_prompt() — 分类框架（角色+工具+示例+公共规则）
  ③ Mixin动态追加 — 候选意图提示 + 跨分类工具提示

调用方只需调 build_system_prompt()，不关心三层细节。
实现 SRP（Prompt构建单一职责）+ SLAP（调用方不了解三层拼接细节）

Author: 小沈 - 2026-05-27
"""

from typing import List, Optional

from app.services.prompts.base_prompt_template import BasePrompts


class PromptAssembler:
    """
    Prompt组装器

    按固定顺序编排三层Prompt贡献，对外暴露build_system_prompt()单一入口。
    """

    def __init__(
        self,
        prompts: BasePrompts,
        candidates: Optional[List[str]] = None,
        category_name: str = "",
    ):
        """
        初始化Prompt组装器

        Args:
            prompts: BasePrompts子类实例（分类框架）
            candidates: 候选意图列表（运行时动态）
            category_name: 分类显示名（运行时动态）
        """
        self._prompts = prompts
        self._candidates = candidates or []
        self._category_name = category_name

    def build_candidates_hint(self) -> str:
        """构建候选意图提示"""
        if not self._candidates:
            return ""
        candidates_list = ", ".join(self._candidates)
        return (
            f"\n\n【候选意图】已识别出以下可能的意图类别: {candidates_list}。"
            "你可以根据实际任务需要，访问任意候选分类的工具。"
        )

    def build_cross_tool_hint(self) -> str:
        """构建跨分类工具提示"""
        if not self._category_name:
            return ""
        return (
            f"\n\n【注意】除了{self._category_name}工具，你还可以使用其他分类的工具。"
            "根据任务需要自由选择合适的工具，不受初始分类限制。"
        )

    def build_system_prompt(self) -> str:
        """
        构建完整system prompt（唯一入口）

        编排顺序：
        ① BasePrompts.build_full_system_prompt() — 分类框架（含SystemAdapter中间层）
        ② 候选意图提示（运行时动态）
        ③ 跨分类工具提示（运行时动态）

        Returns:
            完整的System Prompt字符串
        """
        base = self._prompts.build_full_system_prompt()
        return (
            base
            + self.build_candidates_hint()
            + self.build_cross_tool_hint()
        )


__all__ = [
    "PromptAssembler",
]
