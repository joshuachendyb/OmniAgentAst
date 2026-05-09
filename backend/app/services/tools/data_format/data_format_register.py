# -*- coding: utf-8 -*-
"""
Data Format Register - 数据格式工具注册点

【架构规范】2026-05-02 小沈
- 使用 tool_registry.register() 显式注册所有数据格式工具
- 工具函数从 data_format_tools.py 导入
- Pydantic 模型从 data_format_schema.py 导入

【工具列表】（共10个）
1. read_json - 读取JSON文件
2. write_json - 写入JSON文件
3. read_csv_basic - 读取CSV文件（基础版）
4. parse_yaml - 读取YAML文件
5. write_yaml - 写入YAML文件
6. parse_toml - 读取TOML文件
7. write_toml - 写入TOML文件
8. parse_ini - 读取INI文件
9. parse_xml - 读取XML文件
10. parse_properties - 读取Properties文件

创建时间: 2026-05-02
更新时间: 2026-05-04
"""

# ============================================================
# 数据格式工具注册 - 使用 Pydantic 模型（按文档设计）
# ============================================================
from app.services.tools.registry import tool_registry, ToolCategory
from app.utils.logger import logger

from app.services.tools.data_format.data_format_schema import (
    ReadJsonInput,
    WriteJsonInput,
    ReadCsvBasicInput,
    ParseYamlInput,
    WriteYamlInput,
    ParseTomlInput,
    WriteTomlInput,
    ParseIniInput,
    ParseXmlInput,
    ParsePropertiesInput,
)

from app.services.tools.data_format.data_format_tools import (
    read_json,
    write_json,
    read_csv_basic,
    parse_yaml,
    write_yaml,
    parse_toml,
    write_toml,
    parse_ini,
    parse_xml,
    parse_properties,
)

# 工具描述（用于注册）- 小沈 2026-05-04 完善
DESCRIPTIONS = {
    "read_json": """读取并解析 JSON 文件，返回结构化对象。

【使用场景】
- 读取 JSON 配置文件时使用
- 解析 JSON 格式的数据文件时使用
- 当需要处理嵌套 JSON 结构时使用


【返回数据】
- code: SUCCESS / ERROR
- data: { parsed_data }
- message: 操作结果消息""",

"write_json": """将数据写入 JSON 文件。

【使用场景】
- 保存配置到 JSON 文件时使用
- 导出数据为 JSON 格式时使用
- 当需要 Pretty Print 输出时使用


【返回数据】
- code: SUCCESS / ERROR
- data: { file_path }
- message: 操作结果消息""",



    "read_csv_basic": """使用 Python 标准库 csv 读取 CSV 文件，零依赖，轻量级读取。

【使用场景】
- 读取 CSV 格式的数据文件时使用
- 分析表格数据时使用
- 处理带分隔符的文本文件时使用


【返回数据】
- code: SUCCESS / ERROR
- data: { headers, rows, total_rows }
- message: 操作结果消息""",

    "parse_yaml": """读取 YAML 文件内容。

【使用场景】
- 读取 YAML 配置文件时使用
- 解析配置结构时使用


【返回数据】
- code: SUCCESS / ERROR
- data: { parsed_data }
- message: 操作结果消息""",

    "write_yaml": """写入数据到YAML文件。

使用场景：
- 保存配置到 YAML 文件时使用""",

    "parse_toml": """读取TOML文件内容。

使用场景：
- 读取 TOML 配置文件时使用（如 pyproject.toml）""",

    "write_toml": """写入数据到TOML文件。

使用场景：
- 保存配置到 TOML 文件时使用""",

    "parse_ini": """读取INI配置文件内容。

使用场景：
- 读取 INI 配置文件时使用""",

    "parse_xml": """读取XML文件内容。

使用场景：
- 读取 XML 配置文件时使用""",

    "parse_properties": """读取Java Properties文件内容。

使用场景：
- 读取 Java properties 配置文件时使用""",
}

# 工具使用示例 - 小沈 2026-05-03修正，按文档7.4节
EXAMPLES = {
    "read_json": [
        {"file_path": "D:/config/settings.json"},
        {"file_path": "D:/data/users.json", "encoding": "utf-8", "max_depth": 5},
    ],
    "write_json": [
        {"file_path": "D:/output/data.json", "data": {"name": "test", "value": 123}},
        {"file_path": "D:/output/list.json", "data": [1, 2, 3], "indent": 4},
        {"file_path": "D:/output/config.json", "data": {"key": "value"}, "encoding": "utf-8", "ensure_ascii": False, "backup_before_write": True, "create_parents": True},
    ],
    "read_csv_basic": [
        {"file_path": "D:/data/users.csv"},
        {"file_path": "D:/data/data.tsv", "encoding": "utf-8", "delimiter": "\t"},
        {"file_path": "D:/data/no_header.csv", "has_header": False, "max_rows": 100},
    ],
    "parse_yaml": [
        {"file_path": "D:/config/app.yaml"},
    ],
    "write_yaml": [
        {"file_path": "D:/config/app.yaml", "data": {"key": "value"}},
    ],
    "parse_toml": [
        {"file_path": "D:/config/pyproject.toml"},
    ],
    "write_toml": [
        {"file_path": "D:/config/app.toml", "data": {"section": {"key": "value"}}},
    ],
    "parse_ini": [
        {"file_path": "D:/config/app.ini"},
    ],
    "parse_xml": [
        {"file_path": "D:/config/app.xml"},
    ],
    "parse_properties": [
        {"file_path": "D:/config/app.properties"},
    ],
}

# 工具名到 Pydantic 模型的映射
TOOL_INPUT_MODELS = {
    "read_json": ReadJsonInput,
    "write_json": WriteJsonInput,
    "read_csv_basic": ReadCsvBasicInput,
    "parse_yaml": ParseYamlInput,
    "write_yaml": WriteYamlInput,
    "parse_toml": ParseTomlInput,
    "write_toml": WriteTomlInput,
    "parse_ini": ParseIniInput,
    "parse_xml": ParseXmlInput,
    "parse_properties": ParsePropertiesInput,
}

# 工具名到实现函数的映射
TOOL_IMPLEMENTATIONS = {
    "read_json": read_json,
    "write_json": write_json,
    "read_csv_basic": read_csv_basic,
    "parse_yaml": parse_yaml,
    "write_yaml": write_yaml,
    "parse_toml": parse_toml,
    "write_toml": write_toml,
    "parse_ini": parse_ini,
    "parse_xml": parse_xml,
    "parse_properties": parse_properties,
}


def _register_data_format_tools():
    """
    显式注册所有数据格式工具 - 小沈 2026-05-02
    使用 tool_registry.register() 逐一注册
    """
    for name, implementation in TOOL_IMPLEMENTATIONS.items():
        desc = DESCRIPTIONS.get(name, "")
        input_model = TOOL_INPUT_MODELS.get(name)
        examples = EXAMPLES.get(name, [])

        tool_registry.register(
            name=name,
            description=desc,
            category=ToolCategory.DATA_FORMAT,
            implementation=implementation,
            version="1.0.0",
            input_model=input_model,
            examples=examples
        )
        logger.info(
            f"[data_format_register] 已注册工具: {name}, "
            f"Pydantic模型: {input_model.__name__ if input_model else 'None'}, "
            f"examples: {len(examples)}个"
        )


# 【修复 2026-05-07 小沈】守护模式：只首次import时注册，防止重复注册
_initialized = False
if not _initialized:
    _register_data_format_tools()
    _initialized = True


__all__ = [
    "read_json",
    "write_json",
    "read_csv_basic",
    "parse_yaml",
    "write_yaml",
    "parse_toml",
    "write_toml",
    "parse_ini",
    "parse_xml",
    "parse_properties",
]
