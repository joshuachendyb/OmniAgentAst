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

创建时间: 2026-05-02
更新时间: 2026-05-02
"""

from app.services.tools.registry import register_tool, ToolCategory, tool_registry
from app.utils.logger import logger

from app.services.tools.environment.env_check_schema import (
    ValidateCodeSafetyInput,
    CheckModuleAvailableInput,
    ValidateCsvFormatInput,
    ValidateChartDataInput,
    CheckPdfReadableInput,
    CheckDocxReadableInput,
    CheckXlsxReadableInput,
)

from app.services.tools.environment.env_check_tools import (
    check_python_available,
    validate_code_safety,
    check_node_available,
    check_module_available,
    validate_csv_format,
    validate_chart_data,
    check_pdf_readable,
    check_docx_readable,
    check_xlsx_readable,
)

ENV_CHECK_TOOL_DESCRIPTIONS = {
    "check_python_available": """检查Python环境是否可用。

使用场景：
- 当用户需要确认Python环境是否安装时使用
- 当用户在执行Python代码前需要验证环境时使用

返回数据说明：
- code: 状态码(SUCCESS)
- data.available: Python环境是否可用(bool)
- data.version: Python版本号(str)
- data.executable: Python可执行路径(str)
- message: 结果消息""",
    "validate_code_safety": """验证代码安全性，防止危险操作。

使用场景：
- 当用户需要检查代码是否安全时使用
- 当用户想要在执行代码前进行安全验证时使用


返回数据说明：
- code: 状态码(SUCCESS)
- data.safe: 代码是否安全(bool)
- data.warnings: 安全风险列表(list[str])
- data.warning_count: 风险数量(int)
- message: 结果消息""",
    "check_node_available": """检查Node.js环境是否可用。

使用场景：
- 当用户需要确认Node.js环境是否安装时使用
- 当用户在执行JavaScript代码前需要验证环境时使用

返回数据说明：
- code: 状态码(SUCCESS)
- data.available: Node.js环境是否可用(bool)
- data.version: Node.js版本号(str)
- message: 结果消息""",
    "check_module_available": """检查Python模块是否已安装。

使用场景：
- 当用户需要确认某个Python模块是否已安装时使用
- 当用户在导入模块前需要验证是否可用时使用


返回数据说明：
- code: 状态码(SUCCESS)
- data.available: 模块是否已安装(bool)
- data.version: 模块版本号(str)
- message: 结果消息""",
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
    "check_python_available": [{}],
    "validate_code_safety": [{"code": "import os; os.system('dir')"}],
    "check_node_available": [{}],
    "check_module_available": [{"module_name": "pandas"}],
    "validate_csv_format": [{"file_path": "D:/data/users.csv"}],
    "validate_chart_data": [{"data": {"labels": ["A", "B"], "values": [10, 20]}}],
    "check_pdf_readable": [{"file_path": "D:/documents/report.pdf"}],
    "check_docx_readable": [{"file_path": "D:/documents/report.docx"}],
    "check_xlsx_readable": [{"file_path": "D:/data/report.xlsx"}],
}


def _register_env_check_tools():
    """
    【2026-05-02 小沈】显式注册所有环境检查工具
    优先使用 Pydantic 模型自动生成 OpenAI Schema，无模型则使用 input_schema
    """
    tool_methods = {
        "check_python_available": check_python_available,
        "validate_code_safety": validate_code_safety,
        "check_node_available": check_node_available,
        "check_module_available": check_module_available,
        "validate_csv_format": validate_csv_format,
        "validate_chart_data": validate_chart_data,
        "check_pdf_readable": check_pdf_readable,
        "check_docx_readable": check_docx_readable,
        "check_xlsx_readable": check_xlsx_readable,
    }

    TOOL_INPUT_MODELS = {
        "validate_code_safety": ValidateCodeSafetyInput,
        "check_module_available": CheckModuleAvailableInput,
        "validate_csv_format": ValidateCsvFormatInput,
        "validate_chart_data": ValidateChartDataInput,
        "check_pdf_readable": CheckPdfReadableInput,
        "check_docx_readable": CheckDocxReadableInput,
        "check_xlsx_readable": CheckXlsxReadableInput,
    }

    TOOL_INPUT_SCHEMAS = {
        "check_python_available": {"type": "object", "properties": {}, "required": []},
        "check_node_available": {"type": "object", "properties": {}, "required": []},
    }

    for name, method in tool_methods.items():
        desc = ENV_CHECK_TOOL_DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        input_schema = TOOL_INPUT_SCHEMAS.get(name)
        examples = ENV_CHECK_TOOL_EXAMPLES.get(name, [])

        if input_model:
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
        else:
            tool_registry.register(
                name=name,
                description=desc,
                category=ToolCategory.ENVIRONMENT,
                implementation=method,
                version="1.0.0",
                input_schema=input_schema,
                examples=examples,
            )
            logger.info(f"[env_check_register] 已注册工具: {name}, 使用 input_schema, examples: {len(examples)}个")


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False
if not _initialized:
    _register_env_check_tools()
    _initialized = True


__all__ = [
    "check_python_available",
    "validate_code_safety",
    "check_node_available",
    "check_module_available",
    "validate_csv_format",
    "validate_chart_data",
    "check_pdf_readable",
    "check_docx_readable",
    "check_xlsx_readable",
]
