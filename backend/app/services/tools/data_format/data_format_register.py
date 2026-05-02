# -*- coding: utf-8 -*-
"""
Data Format Register - 数据格式工具注册点

【架构规范】2026-05-02 小沈
- 使用 tool_registry.register() 显式注册所有数据格式工具
- 工具函数从 data_format_tools.py 导入
- Pydantic 模型从 data_format_schema.py 导入

【工具列表】（共3个）
1. read_json - 读取JSON文件
2. write_json - 写入JSON文件
3. read_csv_basic - 读取CSV文件（基础版）

创建时间: 2026-05-02
更新时间: 2026-05-02
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
)

from app.services.tools.data_format.data_format_tools import (
    read_json,
    write_json,
    read_csv_basic,
)

# 工具描述（用于注册）
DESCRIPTIONS = {
    "read_json": """读取JSON文件内容。

使用场景：
- 读取JSON配置文件
- 解析JSON数据文件
- 获取结构化数据

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_JSON）
- data: JSON数据内容
- message: 操作结果消息""",

    "write_json": """写入数据到JSON文件。

使用场景：
- 保存配置到JSON文件
- 导出数据为JSON格式
- 创建结构化数据文件

返回数据说明：
- code: 状态码（SUCCESS/ERR_WRITE_JSON）
- data: 写入的文件路径
- message: 操作结果消息""",

    "read_csv_basic": """读取CSV文件内容（基础版）。

使用场景：
- 读取CSV数据文件
- 导入表格数据
- 解析CSV格式的日志或记录

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_CSV）
- data: 包含headers和rows的字典
- message: 操作结果消息

注意：这是基础版本，适用于简单的CSV文件。""",
}

# 工具使用示例
EXAMPLES = {
    "read_json": [
        {"file_path": "D:/data/config.json"},
        {"file_path": "D:/data/users.json", "encoding": "utf-8"},
    ],
    "write_json": [
        {"file_path": "D:/data/output.json", "data": {"name": "test", "value": 123}},
        {"file_path": "D:/data/list.json", "data": [1, 2, 3], "indent": 4},
    ],
    "read_csv_basic": [
        {"file_path": "D:/data/users.csv"},
        {"file_path": "D:/data/data.tsv", "delimiter": "\t"},
        {"file_path": "D:/data/no_header.csv", "has_header": False},
    ],
}

# 工具名到 Pydantic 模型的映射
TOOL_INPUT_MODELS = {
    "read_json": ReadJsonInput,
    "write_json": WriteJsonInput,
    "read_csv_basic": ReadCsvBasicInput,
}

# 工具名到实现函数的映射
TOOL_IMPLEMENTATIONS = {
    "read_json": read_json,
    "write_json": write_json,
    "read_csv_basic": read_csv_basic,
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


# 触发注册
_register_data_format_tools()


__all__ = [
    "read_json",
    "write_json",
    "read_csv_basic",
]
