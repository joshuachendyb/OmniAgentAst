# -*- coding: utf-8 -*-
"""
基础 Prompt 模板 - 各意图共享的 Prompt 框架

【创建时间】2026-03-21 小沈
【重构时间】2026-05-07 小沈 — 统一prompt组装架构,消除双轨制
【FC-only重构】2026-06-11 小沈 — 删除OUTPUT_FORMAT/TOOL_REMINDER,纯FC模式

职责:
定义各意图 Prompt 的基类接口和公共规则,各意图的 Prompt 继承此类。
统一管理 System Prompt 的组装顺序,确保所有Agent的prompt结构一致。

组装架构(build_full_system_prompt):
① _get_system_info()         — 公共:系统信息(OS/路径规则,所有意图共享)
② get_core_system_prompt()   — 分类特有:角色定义 + 业务规则(必选)
③ get_tool_details()         — 可选:工具描述 + 示例(由include_tool_details控制)
④ TOOL_CALL_RULES            — 公共:工具调用规则(直接调用,禁止反复讨论)
⑤ get_safety_reminder()      — 分类特有:安全提醒(子类覆盖,默认空)
⑥ get_rollback_instructions()— 公共:回滚说明
⑦ AVOID_REPEAT_RULES         — 公共:避免重复操作

UniversalAgent._get_system_prompt() 追加:
⑧ _build_candidates_hint()   — 动态:候选意图提示
⑨ _build_cross_tool_hint()   — 动态:跨分类工具提示

Author: 小沈 - 2026-03-21
"""

from abc import ABC, abstractmethod
from typing import List


class BasePrompts(ABC):
    """
    Prompt 模板基类(抽象)
    
    子类必须实现:
    - get_core_system_prompt() → 获取系统级 Prompt(角色+业务规则)
    
    子类可选覆盖:
    - get_tool_details()      → 工具描述+示例(FC模式可跳过,由Schema承载)
    - get_task_prompt()       → 获取任务描述 Prompt
    - get_safety_reminder()   → 获取安全提醒
    
    完整 Prompt 组装入口: build_full_system_prompt()
    
    Author: 小沈 - 2026-06-11 拆分core/tool_details
    """

    def __init__(self):
        self._include_tool_details = True

    @property
    def include_tool_details(self) -> bool:
        return self._include_tool_details

    @include_tool_details.setter
    def include_tool_details(self, value: bool):
        self._include_tool_details = value

    # 【2026-05-07 小沈】通用Tool Call Rules
    # 【2026-06-10 小沈】增强:强制工具调用规则
    # 【2026-06-11 小健】合并SAFETY WARNING(原在OUTPUT_FORMAT),消除SRP/DRY违反
    # 【2026-06-11 小沈】重构:剥离格式规则到OUTPUT_FORMAT,只保留行为规则 — 小沈审查
    # 【FC-only重构 2026-06-11 小沈】移除finish引用,任务完成时直接回复内容
    # 【2026-06-11 小沈】精简:去重"不能只回文字"2句→1句,移除"失败后换方法"(移入AVOID_REPEAT_RULES)
    TOOL_CALL_RULES = """【Tool Call Rules - 工具调用行为规范】:
- 确认用户意图后立即调用工具,不要在thought中反复讨论该用哪个工具
- reasoning简短说明选择理由即可(1-2句),不要写长篇分析
- ❌ 禁止:仅用文字回复而不调用工具 — 用户请求需要实际操作时必须调用工具
- ✅ 正确:确认意图→直接调用→根据结果决定下一步
- 任务完成时直接回复总结内容,无需调用任何工具
- 如果不确定用什么工具,选择最合理的工具并调用,不要用文字回复代替
- 始终用中文回复用户"""

    # 【2026-06-11 小沈】避免重复规则
    # 【2026-06-11 小沈】修正:合并"失败后换方法"(移自TOOL_CALL_RULES),
    #    修复第2条"3次后换"vs第4条"立即换"的矛盾,
    #    统一为"失败就换,3次不同方法都失败则停"
    AVOID_REPEAT_RULES = """
【避免重复规则】
- 同一命令/URL成功后不要重复执行(结果不会变)
- 已获取的信息直接使用,不需要重新获取
- 失败后优先尝试替代方法,而非反复重试同一方法
- 连续3次不同方法都失败,停止尝试并向用户报告"""

    @abstractmethod
    def get_core_system_prompt(self) -> str:
        """
        获取核心系统 Prompt(子类必须实现)
        
        包含本分类特有的核心内容:
        - Agent 角色定义
        - 领域特定的业务规则(如文件互斥参数、text参数规则)
        
        不包含:
        - 工具描述(get_tool_details() 提供)
        - 示例(get_tool_details() 提供)
        - 公共规则(TOOL_CALL_RULES等由基类统一注入)
        
        Returns:
            核心 Prompt 字符串
        """
        pass

    def get_tool_details(self) -> str:
        """
        获取工具描述和示例(可选,FC模式可跳过)
        
        子类可覆盖此方法返回工具描述+示例,
        由 build_full_system_prompt(include_tool_details=...) 控制是否加载。
        
        Returns:
            工具描述和示例字符串,默认为空
        """
        return ""

    def _get_system_info(self) -> str:
        """获取系统信息(中间层注入),所有意图共享 — 小沈 2026-06-11 抽取到公共层"""
        from app.services.prompts.middle import get_system_prompt as get_system_prompt_string
        from app.utils.logger import logger

        system_info = get_system_prompt_string(include_commands=False)
        logger.debug(f"[{self.__class__.__name__}] 系统信息长度: {len(system_info)}")

        from app.utils.prompt_logger import get_prompt_logger
        prompt_logger = get_prompt_logger()
        prompt_logger.log_system_prompt(
            step_name="中间层注入-服务器OS信息",
            prompt_content=system_info,
            source=f"{self.__class__.__name__}._get_system_info()",
            details={
                "系统信息长度": len(system_info),
                "包含内容": "服务器OS、路径格式、命令格式"
            },
            round_number=1
        )
        return system_info

    def get_task_prompt(self, task: str) -> str:
        """获取任务描述 Prompt — P2-21: 公共模式(Task+时间+分类指令)"""
        from app.utils.time_utils import now_str
        time_str = now_str()
        domain = self._get_domain_name()
        steps = self._get_domain_steps()
        extra = self._get_domain_extra_notes()
        parts = [
            f"Task: {task}",
            f"\nCurrent time: {time_str}",
            f"\n请完成此{domain}任务,按以下步骤:",
            steps,
        ]
        if extra:
            parts.append(f"\n{extra}")
        return "\n".join(parts)

    def _get_domain_name(self) -> str:
        return "通用"

    def _get_domain_steps(self) -> str:
        return "1. 分析需要什么操作\n2. 使用合适的工具\n3. 用中文总结结果"

    def _get_domain_extra_notes(self) -> str:
        return ""

    def get_safety_reminder(self) -> str:
        """获取安全提醒(子类覆盖)"""
        return ""

    def get_rollback_instructions(self) -> str:
        """获取回滚说明(公共) - 小沈 2026-06-11 英文→中文"""
        return """操作失败时的处理步骤:
1. 分析失败原因
2. 尝试替代方法(调用其他工具或向用户报告)
3. 向用户清晰报告错误信息"""

    def build_full_system_prompt(self, include_tool_details: bool = None) -> str:
        """构建完整的系统Prompt — FC-only: 无OUTPUT_FORMAT,由API Schema约束格式

        Args:
            include_tool_details: 是否包含工具描述和示例.
                None=使用实例属性 self._include_tool_details 的值.
                True/False=覆盖实例属性.

        组装顺序:
        ① _get_system_info()        — 公共:系统信息(OS/路径规则)
        ② get_core_system_prompt() — 分类特有(角色+业务规则)
        ③ get_tool_details()       — 可选:工具描述+示例(由include_tool_details控制)
        ④ TOOL_CALL_RULES          — 公共:工具调用规则
        ⑤ get_safety_reminder()    — 分类特有:安全提醒
        ⑥ get_rollback_instructions()— 公共:回滚说明
        ⑦ AVOID_REPEAT_RULES       — 公共:避免重复操作

        Returns:
            完整的 System Prompt
        """
        if include_tool_details is not None:
            self._include_tool_details = include_tool_details

        parts = [self._get_system_info()]
        parts.append(self.get_core_system_prompt())
        if self._include_tool_details:
            tool_part = self.get_tool_details()
            if tool_part:
                parts.append(tool_part)
        parts.append(self.TOOL_CALL_RULES)

        safety = self.get_safety_reminder()
        if safety:
            parts.append(safety)

        rollback = self.get_rollback_instructions()
        if rollback:
            parts.append(rollback)

        parts.append(self.AVOID_REPEAT_RULES)

        return "\n\n".join(parts)

    @staticmethod
    def build_tool_descriptions(tool_names: List[str], category_label: str = "") -> str:
        """从 ToolRegistry 动态生成工具描述字符串 — 小沈 2026-05-27

        DRY原则:统一 file_prompts 和 system_prompts 中重复的 _build_tool_descriptions。
        新增/修改工具后自动更新 prompt,无需人工维护模板。

        Args:
            tool_names: 工具名列表
            category_label: 分类标签(如"FILE""SYSTEM"),非空时在开头添加分类标题

        Returns:
            工具描述字符串
        """
        from app.services.tools.registry import tool_registry

        tools = []
        for name in tool_names:
            tool = tool_registry.get_tool(name)
            if tool:
                tools.append(tool)

        if not tools:
            return ""

        lines = []
        if category_label:
            lines.append(f"  以下是 {category_label} 分类下的 {len(tools)} 个工具:")

        for idx, t in enumerate(tools, 1):
            desc = t.description or ""
            desc_first = desc.split(',')[0] if ',' in desc else desc
            lines.append(f"{idx}. {t.name} - {desc}")
            lines.append(f"   - 使用场景: 当需要{desc_first}时")

            input_schema = getattr(t, 'input_schema', None) or {}
            params = input_schema.get('properties', {})
            if params:
                required = input_schema.get('required', [])
                parts = []
                for pname, pinfo in params.items():
                    ptype = pinfo.get('type', 'any')
                    mark = '(必填)' if pname in required else ''
                    param_desc = pinfo.get('description', '')
                    if param_desc:
                        parts.append(f"{pname}({ptype}){mark}:{param_desc}")
                    else:
                        parts.append(f"{pname}({ptype}){mark}")
                lines.append(f"   - 参数: {'; '.join(parts)}")
            lines.append(f"   - 返回: 操作结果")
            lines.append("")

        return "\n".join(lines)


__all__ = [
    "BasePrompts",
]
