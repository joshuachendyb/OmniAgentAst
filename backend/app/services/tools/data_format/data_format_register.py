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

# 工具描述（用于注册）- 小沈 2026-05-03修正，按文档7.4节
DESCRIPTIONS = {
    "read_json": """读取并解析 JSON 文件，返回结构化对象。

使用场景：
- 读取 JSON 配置文件时使用
- 解析 JSON 格式的数据文件时使用

参数说明（按文档7.4节）：
- file_path：JSON 文件路径（必填）
- encoding：文件编码（可选），默认 auto_detect
- max_depth：最大解析深度（可选），默认 10

返回 { data: ..., metadata: { truncated: bool } } 结构，绝不破坏原始数据树。""",

    "write_json": """将数据写入 JSON 文件。

使用场景：
- 保存配置到 JSON 文件时使用
- 导出数据为 JSON 格式时使用

参数说明（按文档7.4节）：
- file_path：JSON 文件路径（必填）
- data：要写入的数据（必填）
- encoding：文件编码（可选），默认 utf-8
- indent：缩进空格数（可选），默认 2
- ensure_ascii：是否转义非 ASCII（可选），默认 false
- backup_before_write：写入前备份（可选），默认 true
- create_parents：自动创建父目录（可选），默认 true

备份至会话临时目录，绝不污染原目录。""",

    "read_csv_basic": """使用 Python 标准库 csv 读取 CSV 文件，零依赖，轻量级读取。

使用场景：
- 读取 CSV 格式的数据文件时使用
- 分析表格数据时使用

参数说明（按文档7.4节）：
- file_path：CSV 文件路径（必填）
- encoding：文件编码（可选），默认 auto_detect
- delimiter：分隔符（可选），默认 auto_detect
- has_header：是否有表头（可选），默认 true
- max_rows：最大读取行数（可选），默认 500
- skip_blank_lines：跳过空行（可选），默认 true

Agent 自动探测分隔符与表头，失败自动 fallback 到默认值。""",
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
