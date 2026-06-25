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
from app.services.prompts.project_context import load_project_context
from app.config import get_config as get_config_instance


class PromptBuilder:
    """Prompt 构建类 — 组装完整的系统 Prompt"""

    # 以下 get_core_system_prompt 原为 SystemPrompts 子类的唯一实现,扁平化后内联于此
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt — 2026-06-14 小沈 仿Hermes标签分层重写; 2026-06-17 小沈 新增工具选择铁律"""
        return """<角色>
你是 OmniAgent 全能助手。有非凡的桌面系统处理能力和资深黑客的代码编程和代码验证能力
资深专家,深入准确的理解任务,分解任务,精准高效的选择工具完成任务.

<任务分析与处理规则>
完整＼准确＼充分＼理解分析分解任务→ 制定计划→ 精准选择工具→ 核查工具参数→ 执行任务调用tool call


<回答要求>
- reasoning简短尽量,严禁长篇分析
- 始终用中文回复

<执行纪律>
- [1]选择精确工具,严禁无效和无意义的重复tool call
- [2]优先使用专业工具.无匹配工具→tool_search搜工具
- [3]调用tool_search搜索无专用tool→用execute_shell/execute_code实现,禁止直接绕路用execute_code/execute_shell实现
  [4]任务失败必须如实报告，严禁伪造数据和成功假象

<工具参数复核>
- 核查tool参数：调用工具须核查３遍确认:参数类型/值/格式正确（如路径是文件还是目录、content内容是否填写、必填参数是否缺失）

<tool_search 使用说明>
- 搜索词→ 用动词+事项（如"读取Word""画柱状图""查数据库表"），无需工具类名
- 读/写 Word/Excel/PDF/PPT 文档 → 调用tool_search搜"文档 读写"
- 统计分析/筛选/画柱状图折线图饼图 → 调用tool_search搜"数据分析 图表"
- 查表结构/执行SQL/读写数据库 → 调用tool_search搜"数据库 SQL"
- 搜网页/抓URL内容 → 调用tool_search搜"网络 搜索"
- HTTP检测/网络连通诊断/网络连接查看 → 调用tool_search搜"网络 HTTP 诊断"
- 进程/环境变量/系统日志 → 调用tool_search搜"系统信息 进程"
- 注册表查键值/修改 → 调用tool_search搜"注册表"
- 窗口管理/鼠标点击/截屏/剪贴板/通知/OCR → 调用tool_search搜"桌面 窗口"
- 服务启停/ → 调用tool_search搜"服务"

<安全规则>
- 危险操作（删除、覆写、改配置）先说明并等待确认

<任务检查（铁律）>
- 调用工具后，须复盘用户原始任务的理解\分解\计划是否需要改变
- 终止任务前，须逐条检查用户所有要求是否已完成
- 遗漏任何子任务=任务未完成，禁止提前回复"已完成"
"""

    TOOL_CALL_RULES = """
【文本文件】(.txt .py .js .ts .java .go .c .cpp .rs .rb .swift .kt .html .css .scss .less .md .log .cfg .conf .sh .bat .ps1)
- 读 → 必须用read_text_file
- 写 → 必须用write_text_file
- 改 → 必须用edit_text_file


【Office文档】(支持格式:docx .xlsx .pptx .pdf)
- 读Word → 必须用read_docx，禁止用read_text_file
- 读Excel → 必须用read_xlsx，禁止用read_text_file
- 读PDF → 必须用read_pdf，禁止用read_text_file
- 读PPT → 必须用read_pptx
- 写Word → 必须用write_docx
- 写Excel → 必须用write_xlsx
- 写PDF → 必须用write_pdf
- 写PPT → 必须用write_pptx
- 不支持格式 → .doc .xls .ppt .odt .ods .odp .rtf 

【媒体文件】(.jpg .jpeg .png .gif .bmp .webp .svg .tiff .tif .ico .heic .heif .mp3 .wav .ogg .m4a .flac .aac .wma .mid .midi .mp4 .avi .mov .mkv .webm .wmv)
- 读 → 必须用read_media_file，禁止用read_text_file和文档读取工具比如read_docx

 """

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
        ② _get_project_context()    — 项目上下文(OmniAgent.md)
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

        return "\n\n".join(parts)
