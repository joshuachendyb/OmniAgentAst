# -*- coding: utf-8 -*-
"""
Env Check Register - 环境检查工具注册点

【架构规范】2026-05-02 小沈
- env_check_register.py: 显式注册（tool_registry.register）
- env_check_tools.py: 工具函数实现（无装饰器）
- env_check_schema.py: Pydantic 模型

【2026-05-02 小沈重构】
- 从 @register_tool 装饰器注册改为显式注册（tool_registry.register）
- 按 shell_register.py 模式重写

【2026-05-17 小沈】P1-6: 9→5工具注册
- 4个检查工具取消LLM暴露，下沉为toolhelper/exec_helper.py内部Helper：
  - check_python_available → _check_python_available
  - validate_code_safety → _validate_code_safety
  - check_node_available → _check_node_available
  - check_module_available → _check_module_available
- 保留5个文档验证工具仍为LLM可见（验证外部文件而非内部环境）

创建时间: 2026-05-02
更新时间: 2026-05-17 小沈 P1-6
"""

from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.environment.env_check_schema import (
    ValidateCsvFormatInput,
    ValidateChartDataInput,
    CheckPdfReadableInput,
    CheckDocxReadableInput,
    CheckXlsxReadableInput,
)

from app.services.tools.environment.env_check_tools import (
    validate_csv_format,
    validate_chart_data,
    check_pdf_readable,
    check_docx_readable,
    check_xlsx_readable,
)

ENV_CHECK_TOOL_DESCRIPTIONS = {
    "validate_csv_format": """验证CSV文件格式是否正确。

使用场景：
- 当用户需要确认CSV文件格式是否正确时使用
- 当用户在读取CSV前需要验证文件完整性时使用


返回数据说明：
- code: 状态码(SUCCESS)
- data.valid: CSV格式是否正确(bool)
- data.errors: 错误信息列表(list[str])
- message: 结果消息""",
    "validate_chart_data": """验证图表数据格式是否正确。

使用场景：
- 当用户需要确认图表数据格式是否正确时使用
- 当用户在生成图表前需要验证数据时使用


返回数据说明：
- code: 状态码(SUCCESS)
- data.valid: 数据格式是否正确(bool)
- data.errors: 错误信息列表(list[str])
- message: 结果消息""",
    "check_pdf_readable": """检查PDF文件是否可读。

使用场景：
- 当用户需要确认PDF文件是否可读取时使用
- 当用户在读取PDF前需要验证文件是否损坏时使用


返回数据说明：
- code: 状态码(SUCCESS)
- data.readable: PDF是否可读(bool)
- data.page_count: 页数(int，可读时)
- data.error: 错误信息(str，不可读时)
- message: 结果消息""",
    "check_docx_readable": """检查Word文件是否可读。

使用场景：
- 当用户需要确认Word文件是否可读取时使用
- 当用户在读取Word前需要验证文件是否损坏时使用


返回数据说明：
- code: 状态码(SUCCESS)
- data.readable: Word是否可读(bool)
- data.paragraph_count: 段落数(int，可读时)
- data.error: 错误信息(str，不可读时)
- message: 结果消息""",
    "check_xlsx_readable": """检查Excel文件是否可读。

使用场景：
- 当用户需要确认Excel文件是否可读取时使用
- 当用户在读取Excel前需要验证文件是否损坏时使用


返回数据说明：
- code: 状态码(SUCCESS)
- data.readable: Excel是否可读(bool)
- data.sheet_names: 工作表名列表(list[str]，可读时)
- data.error: 错误信息(str，不可读时)
- message: 结果消息""",
}

ENV_CHECK_TOOL_EXAMPLES = {
    "validate_csv_format": [{"file_path": "D:/data/users.csv"}],
    "validate_chart_data": [{"data": {"labels": ["A", "B"], "values": [10, 20]}}],
    "check_pdf_readable": [{"file_path": "D:/documents/report.pdf"}],
    "check_docx_readable": [{"file_path": "D:/documents/report.docx"}],
    "check_xlsx_readable": [{"file_path": "D:/data/report.xlsx"}],
}


def _register_env_check_tools():
    """
    【2026-05-02 小沈】显式注册所有环境检查工具
    【2026-05-17 小沈】P1-6: 9→5，4个检查工具下沉为toolhelper/exec_helper.py
    只注册5个文档验证工具（validate_csv/chart/check_pdf/docx/xlsx）
    """
    tool_methods = {
        "validate_csv_format": validate_csv_format,
        "validate_chart_data": validate_chart_data,
        "check_pdf_readable": check_pdf_readable,
        "check_docx_readable": check_docx_readable,
        "check_xlsx_readable": check_xlsx_readable,
    }

    TOOL_INPUT_MODELS = {
        "validate_csv_format": ValidateCsvFormatInput,
        "validate_chart_data": ValidateChartDataInput,
        "check_pdf_readable": CheckPdfReadableInput,
        "check_docx_readable": CheckDocxReadableInput,
        "check_xlsx_readable": CheckXlsxReadableInput,
    }

    for name, method in tool_methods.items():
        desc = ENV_CHECK_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = ENV_CHECK_TOOL_EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.ENVIRONMENT,
            implementation=method,
            version="1.0.0",
            input_model=input_model,
            examples=examples,
        )
        logger.info(f"[env_check_register] 已注册工具: {name}, 使用 Pydantic 模型: {input_model.__name__}, examples: {len(examples)}个")


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False  # 守护变量，供显式调用时使用

__all__ = ["_register_env_check_tools"]
