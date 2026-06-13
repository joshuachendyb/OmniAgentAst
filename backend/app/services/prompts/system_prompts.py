# -*- coding: utf-8 -*-
"""
PromptBuilder — 唯一的 Prompt 构建类

【创建时间】2026-03-21 小沈
【重构时间】2026-05-07 小沈 — 统一prompt组装架构,消除双轨制
【FC-only重构】2026-06-11 小沈 — 删除OUTPUT_FORMAT/TOOL_REMINDER,纯FC模式
【扁平化重构】2026-06-14 小沈 — 去抽象基类,内联唯一子类SystemPrompts

职责:
构建 UniversalAgent 的完整 System Prompt。

组装架构(build_full_system_prompt) — FC-only版:
① _get_system_info()         — 系统信息(OS/路径规则)
② _get_project_context()     — 项目上下文(OmniAgent.md)
③ get_core_system_prompt()   — 角色定义 + 业务规则
④ TOOL_CALL_RULES            — 回答要求+停止条件

Author: 小沈 - 2026-06-14
"""

from app.services.prompts.system_adapter import get_system_prompt as get_system_prompt_string
from app.utils.logger import logger
from app.utils.prompt_logger import get_prompt_logger
from app.services.prompts.project_context import load_project_context


class PromptBuilder:
    """Prompt 构建类 — 组装完整的系统 Prompt"""

    TOOL_CALL_RULES = """【回答要求】:
- reasoning简短(1-2句),不要长篇分析
- 始终用中文回复

【停止条件】:
- 用户请求已完成,直接回答用户问题
- 遇到无法解决的错误,向用户报告原因和建议"""

    # 以下 get_core_system_prompt 原为 SystemPrompts 子类的唯一实现,扁平化后内联于此
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt"""
        return """你是一个系统全能助手,负责命令执行、系统查询、时间操作和文件管理。

【操作规则】:
- 查询类: 直接执行,无需确认
- 执行命令/运行代码: 先说明,等用户确认后再执行
- 删除/覆写/修改配置: 必须先获用户明确同意

【能力范围】:
- 系统信息查询: get_system_info, event_log, list_processes, get_env
- 进程管理: kill_process (需确认)
- 服务管理: service_control (需确认)
- 任务管理: task_control (需确认)
- 环境变量: set_env (需确认,危险操作)
- 注册表操作: registry_control (需确认,危险操作)

【安全原则】:
- 优先使用只读操作
- 危险操作必须确认
- 记录所有操作日志"""

    def _get_system_info(self) -> str:
        """获取系统信息"""
        system_info = get_system_prompt_string()
        logger.debug(f"[PromptBuilder] 系统信息长度: {len(system_info)}")

        prompt_logger = get_prompt_logger()
        prompt_logger.log_system_prompt(
            step_name="中间层注入-服务器OS信息",
            prompt_content=system_info,
            source="PromptBuilder._get_system_info()",
            details={
                "系统信息长度": len(system_info),
                "包含内容": "服务器OS、路径格式、命令格式"
            },
            round_number=1
        )
        return system_info

    def _get_project_context(self) -> str:
        """加载项目上下文"""
        ctx = load_project_context()
        if not ctx:
            return ""
        return f"【项目上下文】:\n{ctx}"

    def build_full_system_prompt(self) -> str:
        """构建完整的系统Prompt — FC-only版

        组装顺序:
        ① _get_system_info()        — 系统信息(OS/路径规则)
        ② _get_project_context()    — 项目上下文
        ③ get_core_system_prompt()  — 角色+业务规则
        ④ TOOL_CALL_RULES           — 回答要求+停止条件
        """
        parts = [self._get_system_info()]

        project_ctx = self._get_project_context()
        if project_ctx:
            parts.append(project_ctx)

        parts.append(self.get_core_system_prompt())
        parts.append(self.TOOL_CALL_RULES)

        return "\n\n".join(parts)


__all__ = [
    "PromptBuilder",
]
