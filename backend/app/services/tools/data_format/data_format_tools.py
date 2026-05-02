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
