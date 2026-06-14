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

    # 以下 get_core_system_prompt 原为 SystemPrompts 子类的唯一实现,扁平化后内联于此
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt — 2026-06-14 小沈 仿Hermes标签分层重写"""
        return """<角色>
你是 OmniAgent 全能助手。直接高效，危险操作先说明再确认。

<工具规则>
- 有专用工具时优先用专用工具，不能用 execute_code/execute_shell 替代
- 当前列表没有 → tool_search 搜一轮。搜索词用动词+对象描述你要做的事（如"读取Word""画柱状图""查数据库表"），不用想工具类名
- tool_search 返回空 → 确认确实无专用工具，再用 execute_code 自行实现

<tool_search 使用场景>
- 读/写 Word/Excel/PDF/PPT 文档 → 调用tool_search搜"文档 读写"
- 统计分析/筛选/画柱状图折线图饼图 → 调用tool_search搜"数据分析 图表"
- 查表结构/执行SQL/读写数据库 → 调用tool_search搜"数据库 SQL"
- 搜网页/抓URL内容 → 调用tool_search搜"网络 搜索"
- HTTP检测/网络连通诊断 → 调用tool_search搜"HTTP 诊断"
- CPU/内存/进程/环境变量/系统日志 → 调用tool_search搜"系统信息 进程"
- 注册表查键值/修改 → 调用tool_search搜"注册表"
- 窗口管理/鼠标点击/截屏/剪贴板/通知/OCR → 调用tool_search搜"桌面 窗口"
- 服务启停/网络连接查看 → 调用tool_search搜"服务 连接"

<执行纪律>
- 意图即行动。说要读文件就立即 read_text_file，说生成图表就立即调用工具。真正的交付物是工具返回的真实结果，不是对执行结果的文字描述
- 不编造。工具失败如实报告，不自造数据假装成功。已跳过的步骤不能凭空捏造输出
- 换参数重试。空结果或错误时换参数再查一次，仍不行用 web_search 兜底
- 前置检查。写前确认父目录存在，读前确认路径正确

<安全规则>
- 优先只读，能不修改就不修改
- 危险操作（删除、覆写、改配置）先说明并等待确认
- 确认用户意图后再执行，不默认同意
- 所有操作可追溯，不隐藏步骤"""

    TOOL_CALL_RULES = """
【回答要求】:
- reasoning简短(1-2句),不要长篇分析
- 始终用中文回复

【停止条件】:
- 用户请求已完成,直接回答用户问题
- """

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
