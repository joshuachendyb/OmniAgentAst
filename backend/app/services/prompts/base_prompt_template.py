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

from app.services.prompts.system_adapter import get_system_prompt as get_system_prompt_string
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger
from app.services.prompts.project_context import load_project_context


class BasePrompts(ABC):
    """
    Prompt 模板基类(抽象)
    
    子类必须实现:
    - get_core_system_prompt() → 获取系统级 Prompt(角色+业务规则)

    完整 Prompt 组装入口: build_full_system_prompt()
    
    Author: 小沈 - 2026-06-11 拆分core/tool_details
    """

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
        - 公共规则(TOOL_CALL_RULES等由基类统一注入)
        
        Returns:
            核心 Prompt 字符串
        """
        pass

    def _get_system_info(self) -> str:
        """获取系统信息(中间层注入),所有意图共享 — 小沈 2026-06-11 抽取到公共层"""
        system_info = get_system_prompt_string(include_commands=False)
        logger.debug(f"[{self.__class__.__name__}] 系统信息长度: {len(system_info)}")

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
        ctx = load_project_context()
        if not ctx:
            return ""
        result = f"【项目上下文】:\n{ctx}"
        return result

    def build_full_system_prompt(self) -> str:
        """构建完整的系统Prompt — FC-only版

        组装顺序:
        ① _get_system_info()        — 公共:系统信息(OS/路径规则)
        ② _get_project_context()    — 公共:项目上下文(README.md)
        ③ get_core_system_prompt() — 分类特有(角色+业务规则)
        ④ TOOL_CALL_RULES           — 公共:回答要求+停止条件
        """
        parts = [self._get_system_info()]

        project_ctx = self._get_project_context()
        if project_ctx:
            parts.append(project_ctx)

        parts.append(self.get_core_system_prompt())
        parts.append(self.TOOL_CALL_RULES)

        full_prompt = "\n\n".join(parts)
        return full_prompt


__all__ = [
    "BasePrompts",
]
