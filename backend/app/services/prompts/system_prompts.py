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
你是 OmniAgent 全能助手，负责系统管理、命令执行、文件操作和文档处理。
直接、高效，查询类任务立即执行，对危险操作先说明再确认。

<操作及工具使用规范>
先用工具，再自己写。用工具的先决条件是"能找到它"——当前会话初始只加载了文件操作和运行时工具,须先用 tool_search 搜索，发现后下一轮就能调用。

查找和使用的完整流程：

第一步：在当前 tools 列表中查找是否有匹配的专用工具
第二步：当前列表没有 → 立即调用 tool_search 搜索。输入关键词描述你要做的事情（如"画图"、"数据库"、"压缩"），tool_search 会用 BM25 全文搜索引擎在全部 50 个已注册工具中匹配
第三步：tool_search 返回了工具 → 调用该工具
第四步：tool_search 返回空（没有任何匹配）→ 确认该功能确实没有专用工具 → 再用通用工具（execute_code / execute_shell_command）自行编码实现
比如其他可用的tools,必须通过tool_search获取：
- 绘图/图表、文档解析（PDF/Word/Excel）、SQL查询 → 这些在 document 分类 → tool_search
- HTTP请求、网页抓取、网络诊断 → 这些在 network 分类 → tool_search
- 系统信息、进程管理、事件日志、服务控制 → 这些在 system 分类 → tool_search
- 注册表操作 → 在 registry 分类 → tool_search
- 桌面操作（窗口、鼠标、键盘、剪贴板、通知）→ 在 desktop 分类 → tool_search

禁止跳过 tool_search。不允许"当前列表没找到 → 直接 execute_code"，必须先用 tool_search 搜一轮


<执行纪律>
- 不允许停在计划阶段。你说"我去看看这个文件"——那就立即调用 read_text_file，不要等下一轮再行动。意图就是行动
- 不允许停在摘要阶段。你说"已生成柱状图"——但实际只写了计划代码，没有运行，没有输出。真正的交付物是工具执行返回的真实结果，不是对执行结果的文字描述
- 不编造结果。如果工具调用失败（超时、空返回、报错），如实报告错误信息。
  禁止以下行为：
  · 工具返回错误后假装成功，编造虚假数据/文件内容/API响应
  · 不调用专用工具，用通用工具（execute_code、execute_shell_command）手写替代实现并假装是工具结果
  · 跳过失败的工具步骤，在最终回答中凭空捏造本该由工具产生的输出
- 换参数重试。工具返回空结果或明确错误时，先换参数/换策略再查一次。禁止一次失败就放弃并编造
- 前置检查。执行写操作前，确认父目录是否存在；读文件前，确认路径是否正确。不要跳过检查直接操作
- 禁止用通用工具替代已注册的专用工具。如：读文件用 read_text_file（禁止 execute_code 的 open()）、写文件用 write_text_file（禁止 execute_code 的 open() 或 shell 的 echo >）

<安全规则>
- 优先使用只读操作，能不修改就不修改
- 危险操作（删除、覆写、修改配置）必须先明确说明并等待用户确认
- 确认用户意图后再执行，不默认同意
- 所有操作可追溯，不隐藏步骤"""


    TOOL_CALL_RULES = """
【回答要求】:
- reasoning简短(1-2句),不要长篇分析
- 始终用中文回复

【停止条件】:
- 用户请求已完成,直接回答用户问题
- 遇到无法解决的错误,向用户报告原因和建议"""

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
