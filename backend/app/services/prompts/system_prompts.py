# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - 注释中"项目上下文(OmniAgent.md)"改为"项目规则文件(OmniAgent.md)"
# 2026-07-15 - 小欧 -  修正<铁律-任务复核>①为结论优先(去"必包分步计划",阻断超长final/退化final根因); 新增①D大内容写文件指引; 增强④明示工具失败/异常须含于最终答复文本(吸收原E意图,避DRY重复)
# 2026-07-28 - 小欧 -  压缩系统Prompt文字(~1898→~1300),去冗余修饰/合并重复语义,不改功能
# 2026-07-28 - 小欧 -  TOOL_CALL_RULES: 替换单行【Shell】为 render_shell_section() 多行指引(按 shell_type 动态切换)
# 2026-08-05 - 小欧 - <searchtool-搜备用工具>: 逐类示例改为精简"备用工具类型"一行枚举(文档\数据分析\数据库\网络\系统\进程\注册表\桌面\时间定时), 与tool_retry_engine备用工具命名/register描述对齐
# 2026-08-07 - 小欧 - <searchtool-搜备用工具>: 强化"一次搜多类型"引导,禁止分多次调用searchtool搜不同类型(实测LLM发7个并行searchtool,应合并为1个)
# 2026-08-10 - 小欧 - _get_project_root_info() 扩展: 项目根之外一并注入授权目录(allowed_dirs), 让LLM知晓可合法操作目录(与Safety白名单一致); 未配置allowed_dirs时保持原样只给项目根, 功能零退化 — 北京老陈驱动
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
② _get_project_context()     — 项目规则文件(OmniAgent.md)
③ get_core_system_prompt()   — 角色定义 + 业务规则
④ TOOL_CALL_RULES            — 回答要求+停止条件

Author: 小沈 - 2026-06-14
"""

import re
from app.services.prompts.system_adapter import (
    get_default_shell_code,
    get_system_prompt as get_system_prompt_string,
)
from app.tools.fundamental.shell_prompt_templates import render_shell_section
from app.logger import logger
from app.services.prompts.project_context import load_project_context
from app.config import get_config as get_config_instance


class PromptBuilder:
    """Prompt 构建类 — 组装完整的系统 Prompt"""

    # 以下 get_core_system_prompt 原为 SystemPrompts 子类的唯一实现,扁平化后内联于此
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt — 2026-06-14 小沈 仿Hermes标签分层重写; 2026-06-17 小沈 新增工具选择铁律"""
        return """<角色>
你是 OmniAgent 全能任务助手+资深黑客代码工程师
<能力>
**资深专家**校正意图→确认目标→分解任务→精准选工具
**严谨负责**思虑周详,做正确的事,目标导向-完成每一个任务:A不丢三落四,B不弄虚作假,C不急躁,

<铁规-任务处理>
- 梳理→分解→计划→选工具→填参数→调用
- 梳理:校对意图,梳理完整任务目标数量,复核3遍,不漏需求,不杜撰
- 分解:精准分解任务,囊括每一细节,不错误理解任务
- 计划:周全且合逻辑,最优逻辑层次.以计划执行

<铁律-任务复核>
- ① answer:简洁且用中文
  A 问答型:直接答复
  B 多步型:意图分解+任务分析+依计划执行
  C 结束:总结结构化+产物路径+失败说明,严禁伪造
- ② 复核工具:①参数名/类型/值/格式(路径/目录/content等)是否准确 ②工具是否恰当/可换
- ③ 复核计划:逐项复核3遍-是否按计划执行,目标是否完成

<执行纪律>
- ①用searchtool搜备用工具
- ②禁止绕路用shell逃避安全检查


<searchtool-搜备用工具>
支持单类型和多类型备用工具搜索注入,可传入多类型关键词(如"文档 数据分析 网络")
备用工具类型: 文档\数据分析\数据库\网络\系统\进程\注册表\桌面\时间定时


"""

    _TOOL_CALL_RULES_BASE = """
【Office文件】
-禁用文本工具,不支持.doc.xls.ppt.odt.ods.odp.rtf

【媒体文件】
-禁用文本/office工具

"""

    @property
    def TOOL_CALL_RULES(self) -> str:
        """工具调用规则 + Shell运行环境 — 小沈 2026-07-01  — 北京老陈 2026-07-09 统一Prompt与实际shell匹配"""
        shell_code = get_default_shell_code()
        shell_section = "\n" + render_shell_section(shell_code) + "\n"
        return self._TOOL_CALL_RULES_BASE + shell_section

    def _get_system_info(self) -> str:
        """获取系统信息 — P0-2修复 2026-06-23 小欧: 删除冗余日志(完整prompt已在initialize_run_state记录)"""
        system_info = get_system_prompt_string()
        logger.debug(f"[PromptBuilder] 系统信息长度: {len(system_info)}")
        return system_info

    def _get_project_root_info(self) -> str:
        """获取项目根目录+授权目录信息 — 注入到系统Prompt — 小欧 2026-08-10
        授权目录(app.allowed_dirs): tool在项目根外额外授权访问的工作目录,
        LLM可据此在合法路径内选择操作对象, 避免误触未授权路径被Safety拦截。
        """
        config = get_config_instance()
        root = config.get_project_root()
        allowed = config.get_allowed_dirs()
        text = f"【项目根目录】{root}"
        if allowed:
            dirs = "\n".join(f"  - {d}" for d in allowed)
            text += (
                f"\n【授权目录】除项目根外, 以下目录同样授权 tool 读写删(受Safety边界约束):\n"
                f"{dirs}"
            )
        return text

    def _get_project_context(self) -> str:
        """加载项目上下文"""
        ctx = load_project_context()
        if not ctx:
            return ""
        return f"【项目上下文】:\n{ctx}"

    def build_full_system_prompt(self) -> str:
        """构建完整的系统Prompt — FC-only版

        组装顺序:
        ① get_core_system_prompt()  — 角色+业务规则
        ② _get_project_context()    — 项目规则文件(OmniAgent.md)
        ③ _get_system_info()        — 系统信息(OS/路径规则)
        ④ _get_project_root_info()  — 项目根目录+授权目录
        ⑤ TOOL_CALL_RULES           — 文件类型→工具映射
        """
        parts = [self.get_core_system_prompt()]

        project_ctx = self._get_project_context()
        if project_ctx:
            parts.append(project_ctx)

        parts.append(self._get_system_info())
        parts.append(self._get_project_root_info())
        parts.append(self.TOOL_CALL_RULES)

        result = "\n\n".join(parts)

        # B-2修复 2026-06-25 小欧: 验证tag闭合
        unclosed = re.findall(r'<(\w+)>', result)
        closed = re.findall(r'</(\w+)>', result)
        for tag in set(unclosed):
            if tag not in closed and tag not in ('角色','br','能力','铁规-任务处理','执行纪律','searchtool-搜备用工具'):
                logger.warning(f"[PromptBuilder] tag <{tag}> 可能未闭合")

        return result
