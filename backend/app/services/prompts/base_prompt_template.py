# -*- coding: utf-8 -*-
"""
基础 Prompt 模板 - 各意图共享的 Prompt 框架

【创建时间】2026-03-21 小沈
【重构时间】2026-05-07 小沈 — 统一prompt组装架构,消除双轨制
【FC-only重构】2026-06-11 小沈 — 删除OUTPUT_FORMAT/TOOL_REMINDER,纯FC模式

职责:
定义各意图 Prompt 的基类接口和公共规则,各意图的 Prompt 继承此类。
统一管理 System Prompt 的组装顺序,确保所有Agent的prompt结构一致。

组装架构(build_full_system_prompt) — FC-only版:
① _get_system_info()         — 公共:系统信息(OS/路径规则,所有意图共享)
② _get_project_context()     — 公共:项目上下文(README.md)
③ get_core_system_prompt()   — 分类特有:角色定义 + 业务规则(必选)
④ TOOL_CALL_RULES             — 公共:回答要求+停止条件

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

    TOOL_CALL_RULES = """【回答要求】:
- reasoning简短(1-2句),不要长篇分析
- 始终用中文回复

【停止条件】:
- 用户请求已完成,直接回答用户问题
- 遇到无法解决的错误,向用户报告原因和建议"""

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

    def _get_project_context(self) -> str:
        """加载项目上下文(README.md) — 小沈 2026-06-11"""
        from app.services.prompts.project_context import load_project_context
        ctx = load_project_context()
        if not ctx:
            return ""
        return f"【项目上下文】:\n{ctx}"

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

    def build_full_system_prompt(self, include_tool_details: bool = None) -> str:
        """构建完整的系统Prompt — FC-only版

        组装顺序:
        ① _get_system_info()        — 公共:系统信息(OS/路径规则)
        ② _get_project_context()    — 公共:项目上下文(README.md)
        ③ get_core_system_prompt() — 分类特有(角色+业务规则)
        ④ TOOL_CALL_RULES           — 公共:回答要求+停止条件
        """
        if include_tool_details is not None:
            self._include_tool_details = include_tool_details

        parts = [self._get_system_info()]

        project_ctx = self._get_project_context()
        if project_ctx:
            parts.append(project_ctx)

        parts.append(self.get_core_system_prompt())
        parts.append(self.TOOL_CALL_RULES)

        return "\n\n".join(parts)

    @staticmethod
    def build_tool_descriptions(tool_names: List[str], category_label: str = "") -> str:
        """从 ToolRegistry 动态生成工具描述字符串 — 小沈 2026-05-27

        DRY原则:统一各prompt子类中重复的 _build_tool_descriptions。
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

            critical = getattr(t, 'critical_notes', '')
            if critical:
                lines.append(f"   - ⚠️ CRITICAL: {critical}")
            forbidden = getattr(t, 'forbidden', '')
            if forbidden:
                lines.append(f"   - ❌ FORBIDDEN: {forbidden}")

            lines.append(f"   - 返回: 操作结果")

            _meta = getattr(t, 'metadata', None)
            if _meta:
                if _meta.critical_notes:
                    lines.append(f"   ⚠ 注意: {_meta.critical_notes}")
                if _meta.usage_hint:
                    lines.append(f"   💡 提示: {_meta.usage_hint}")
                if _meta.forbidden:
                    lines.append(f"   🚫 禁止: {_meta.forbidden}")
            lines.append("")

        return "\n".join(lines)


__all__ = [
    "BasePrompts",
]
