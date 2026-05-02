# -*- coding: utf-8 -*-
"""
数据格式工具函数模块

【创建时间】2026-05-02 小沈
【设计依据】按新增工具规范流程

包含：
- read_json: 读取JSON文件
- write_json: 写入JSON文件
- read_csv_basic: 读取CSV文件（基础版）

Author: 小沈 - 2026-05-02
"""

import json
import csv
from typing import Dict, Any, List, Union
from pathlib import Path

from app.services.tools.registry import register_tool, ToolCategory

from app.services.tools.data_format.data_format_schema import (
    ReadJsonInput,
    WriteJsonInput,
    ReadCsvBasicInput,
)


@register_tool(
    name="read_json",
    description="""读取JSON文件内容。

使用场景：
- 读取JSON配置文件
- 解析JSON数据文件
- 获取结构化数据

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_JSON）
- data: JSON数据内容
- message: 操作结果消息""",
    category=ToolCategory.SYSTEM,
    input_model=ReadJsonInput,
    examples=[
        {"file_path": "D:/data/config.json"},
        {"file_path": "D:/data/users.json", "encoding": "utf-8"},
    ]
)
def read_json(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取JSON文件内容 - 小沈 2026-05-02"""
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERR_READ_JSON",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }
        
        with open(path, "r", encoding=encoding) as f:
            data = json.load(f)
        
        return {
            "code": "SUCCESS",
            "data": data,
            "message": f"成功读取JSON文件: {file_path}"
        }
    except json.JSONDecodeError as e:
        return {
            "code": "ERR_READ_JSON",
            "data": None,
            "message": f"JSON解析失败: {str(e)}"
        }
    except Exception as e:
        return {
            "code": "ERR_READ_JSON",
            "data": None,
            "message": f"读取JSON文件失败: {str(e)}"
        }


@register_tool(
    name="write_json",
    description="""写入数据到JSON文件。

使用场景：
- 保存配置到JSON文件
- 导出数据为JSON格式
- 创建结构化数据文件

返回数据说明：
- code: 状态码（SUCCESS/ERR_WRITE_JSON）
- data: 写入的文件路径
- message: 操作结果消息""",
    category=ToolCategory.SYSTEM,
    input_model=WriteJsonInput,
    examples=[
        {"file_path": "D:/data/output.json", "data": {"name": "test", "value": 123}},
        {"file_path": "D:/data/list.json", "data": [1, 2, 3], "indent": 4},
    ]
)
def write_json(
    file_path: str,
    data: Union[Dict[str, Any], List[Any]],
    encoding: str = "utf-8",
    indent: int = 2,
    ensure_ascii: bool = False
) -> Dict[str, Any]:
    """写入数据到JSON文件 - 小沈 2026-05-02"""
    try:
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding=encoding) as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        
        return {
            "code": "SUCCESS",
            "data": file_path,
            "message": f"成功写入JSON文件: {file_path}"
        }
    except Exception as e:
        return {
            "code": "ERR_WRITE_JSON",
            "data": None,
            "message": f"写入JSON文件失败: {str(e)}"
        }


@register_tool(
    name="read_csv_basic",
    description="""读取CSV文件内容（基础版）。

使用场景：
- 读取CSV数据文件
- 导入表格数据
- 解析CSV格式的日志或记录

返回数据说明：
- code: 状态码（SUCCESS/ERR_READ_CSV）
- data: 包含headers和rows的字典
- message: 操作结果消息

注意：这是基础版本，适用于简单的CSV文件。""",
    category=ToolCategory.SYSTEM,
    input_model=ReadCsvBasicInput,
    examples=[
        {"file_path": "D:/data/users.csv"},
        {"file_path": "D:/data/data.tsv", "delimiter": "\t"},
        {"file_path": "D:/data/no_header.csv", "has_header": False},
    ]
)
def read_csv_basic(
    file_path: str,
    encoding: str = "utf-8",
    delimiter: str = ",",
    has_header: bool = True
) -> Dict[str, Any]:
    """读取CSV文件内容（基础版） - 小沈 2026-05-02"""
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERR_READ_CSV",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }
        
        rows = []
        headers = []
        
        with open(path, "r", encoding=encoding, newline="") as f:
            reader = csv.reader(f, delimiter=delimiter)
            
            for i, row in enumerate(reader):
                if i == 0 and has_header:
                    headers = row
                else:
                    rows.append(row)
        
        if not has_header and rows:
            headers = [f"column_{i}" for i in range(len(rows[0]))] if rows else []
        
        return {
            "code": "SUCCESS",
            "data": {
                "headers": headers,
                "rows": rows,
                "row_count": len(rows)
            },
            "message": f"成功读取CSV文件: {file_path}，共 {len(rows)} 行数据"
        }
    except Exception as e:
        return {
            "code": "ERR_READ_CSV",
            "data": None,
            "message": f"读取CSV文件失败: {str(e)}"
        }
