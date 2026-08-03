# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - 注释中"项目上下文(OmniAgent.md)"改为"项目规则文件(OmniAgent.md)"
# 2026-07-15 - 小欧 -  修正<铁律-任务复核>①为结论优先(去"必包分步计划",阻断超长final/退化final根因); 新增①D大内容写文件指引; 增强④明示工具失败/异常须含于最终答复文本(吸收原E意图,避DRY重复)
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
    get_default_shell_name,
    get_pwsh_version,
    get_system_prompt as get_system_prompt_string,
)
from app.logger import logger
from app.services.prompts.project_context import load_project_context
from app.config import get_config as get_config_instance


class PromptBuilder:
    """Prompt 构建类 — 组装完整的系统 Prompt"""

    # 以下 get_core_system_prompt 原为 SystemPrompts 子类的唯一实现,扁平化后内联于此
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt — 2026-06-14 小沈 仿Hermes标签分层重写; 2026-06-17 小沈 新增工具选择铁律"""
        return """<角色>
你是 OmniAgent 全能助手。非凡的任务处理能力和资深黑客级代码编程和测试能力
<能力>
**资深专家**校正任务描述,梳理任务意图,准确确认任务目标,分解任务,精准高效选择工具
**优良品格**思虑周详严谨,高度责任心,正确的做事情,以完成任务为最高目标;A不丢三落四,B不弄虚作假,C不急躁,

<铁规-分析计划>
- 梳理任务→ 分解任务→ 计划任务→ 选择精准工具→ 填写合理参数→ 调用工具
- 梳理任务:校对任务,意图分解,梳理清晰\完整的任务条目和目标,复核3遍,严禁**猜测**自以为是**错误理解**任务
- 分解任务:优美的分解任务,囊括每一个细节,绝不遗漏,猜测,错误理解任务的每一处细节.
- 计划任务:计划必须周全且符合**逻辑**,阶段和分步计划必须**最优优雅**的逻辑层次.严禁漏遗漏一个**需求**细节要求**,严禁**杜撰**虚假**任务

<铁律-任务复核>
- ① answer:简洁且必须用中文
  A 问答型任务:直接答复
  B 多步型任务:必须包括意图分解+任务分析+分步计划
  C 任务结束:最终输出文本只给结构化任务总结+产物路径指引.
  D 任务总结:须简明扼要.包括计划任务的完成情况汇总+失败的任务或工具情况说明.严禁伪造数据和成功假象
- ② 复核工具--针对任务复核3遍工具是否恰当,工具调用计划是否最优,是否更换工具或者参数
- ③ 复核任务--每一项任务和每一步计划完成后 逐一复核3遍用户任务的要求和子任务是否准确和正确的完成

<执行纪律>
- ①选择精确工具,严禁无效和无意义的重复tool call
- ②优先使用直接工具.无匹配工具→searchtool搜工具
- ③调用searchtool搜索无直接可用tool→用shell
- ④禁止直接绕路用shell实现绕过安全检查

<复核工具参数>
- 核查tool参数：调用工具须核查３遍确认:参数名称/类型/值/格式正确（如路径是文件还是目录、content内容是否填写、必填参数是否缺失）

<searchtool-搜直接工具>
- 直接工具的搜索词=任务关键词
- 读/写 Word/Excel/PDF/PPT 文档 → 用searchtool搜"文档 读写"
- 统计分析/筛选/图表生成分析 →调用searchtool搜"数据分析 图表"
- 查数据库表结构/执行SQL/读写数据库 → 用searchtool搜"数据库 SQL"
- 搜网页/抓URL内容/网络处理 → 用searchtool搜"网络 搜索 http"
- 进程/环境变量/系统日志/注册表/服务启停 → 用searchtool搜"系统信息 进程 注册表 任务"
- 窗口管理/鼠标点击/截屏/剪贴板/OCR → 用searchtool搜"桌面 窗口"

"""

    _TOOL_CALL_RULES_BASE = """
【Office工具】(支持格式:docx .xlsx .pptx .pdf),禁止用文本工具
- 读写Word → 必须用read_docx或write_docx
- 读写Excel → 必须用read_xlsx，write_xlsx
- 读写PDF → 必须用read_pdf，write_pdf
- 读写PPT → 必须用read_pptx,write_pptx
- 不支持格式 → .doc .xls .ppt .odt .ods .odp .rtf 

【媒体工具】(.jpg .jpeg .png .gif .bmp .webp .svg .tiff .tif .ico .heic .heif .mp3 .wav .ogg .m4a .flac .aac .wma .mid .midi .mp4 .avi .mov .mkv .webm .wmv)
- 读 → 必须用readmedia，禁止用readtext和office文档读取工具比.

 """

    @property
    def TOOL_CALL_RULES(self) -> str:
        """工具调用规则 + Shell运行环境 — 小沈 2026-07-01  — 北京老陈 2026-07-09 统一Prompt与实际shell匹配"""
        default_shell = get_default_shell_name()
        pwsh_ver = get_pwsh_version()
        pwsh_line = f"pwsh.exe {pwsh_ver} 已安装" if pwsh_ver else "pwsh.exe 未安装"
        shell_rules = f"""
【Shell 运行环境】
- 默认 Shell: {default_shell}
- {pwsh_line}

"""
        return self._TOOL_CALL_RULES_BASE + shell_rules

    def _get_system_info(self) -> str:
        """获取系统信息 — P0-2修复 2026-06-23 小欧: 删除冗余日志(完整prompt已在initialize_run_state记录)"""
        system_info = get_system_prompt_string()
        logger.debug(f"[PromptBuilder] 系统信息长度: {len(system_info)}")
        return system_info

    def _get_project_root_info(self) -> str:
        """获取项目根目录信息 — 注入到系统Prompt"""
        config = get_config_instance()
        root = config.get_project_root()
        return f"【项目根目录】{root}"

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
        ④ _get_project_root_info()  — 项目根目录
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
            if tag not in closed and tag not in ('角色', 'br', '能力', '铁规-分析计划', '执行纪律', '复核工具参数', 'searchtool-搜直接工具'):
                logger.warning(f"[PromptBuilder] tag <{tag}> 可能未闭合")

        return result
