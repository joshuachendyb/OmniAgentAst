# -*- coding: utf-8 -*-
"""
数据格式工具函数模块

【创建时间】2026-05-02 小沈
【设计依据】按新增工具规范流程

【重要】新函数增加规范 - 小沈 2026-05-04
新增函数时必须同步修改以下3个文件：
1. *_tools.py: 函数实现（必须有详细注释）
2. *_schema.py: Pydantic 模型（输入参数定义）
3. *_register.py: 显式注册（description + examples + input_model）

包含：
- read_json: 读取JSON文件
- write_json: 写入JSON文件
- read_csv_basic: 读取CSV文件（基础版）
- parse_yaml: 读取YAML文件
- write_yaml: 写入YAML文件
- parse_toml: 读取TOML文件
- write_toml: 写入TOML文件
- parse_ini: 读取INI文件
- parse_xml: 读取XML文件
- parse_properties: 读取Properties文件

Author: 小沈 - 2026-05-02
"""

import json
import csv
from typing import Dict, Any, List, Union
from pathlib import Path


def read_json(file_path: str, encoding: str = "auto_detect", max_depth: int = 10) -> Dict[str, Any]:
    """读取JSON文件内容 - 小沈 2026-05-03修正，按文档7.4节参数定义
    
    参数：
    - file_path: JSON文件路径（必填）
    - encoding: 文件编码（可选），默认 auto_detect
    - max_depth: 最大解析深度（可选），默认 10
    """
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERROR",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }
        
        actual_encoding = "utf-8"
        if encoding == "auto_detect":
            try:
                with open(path, "rb") as f:
                    raw = f.read(4)
                    if raw.startswith(b'\xef\xbb\xbf'):
                        actual_encoding = "utf-8-sig"
                    elif raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
                        actual_encoding = "utf-16"
                    else:
                        try:
                            raw.decode("utf-8")
                            actual_encoding = "utf-8"
                        except:
                            actual_encoding = "gbk"
            except:
                actual_encoding = "utf-8"
        
        with open(path, "r", encoding=actual_encoding) as f:
            data = json.load(f)
        
        def truncate_dict(d, current_depth=0):
            if current_depth >= max_depth:
                return {"__truncated__": True, "depth": current_depth}
            if isinstance(d, dict):
                return {k: truncate_dict(v, current_depth+1) for k, v in d.items()}
            elif isinstance(d, list):
                return [truncate_dict(item, current_depth+1) for item in d[:100]]
            return d
        
        truncated = False
        if max_depth < 50:
            data, truncated = truncate_dict(data), True
        
        return {
            "code": "SUCCESS",
            "data": data,
            "metadata": {
                "truncated": truncated,
                "max_depth": max_depth,
                "file_path": file_path
            },
            "message": f"成功读取JSON文件: {file_path}"
        }
    except json.JSONDecodeError as e:
        return {
            "code": "ERROR",
            "data": None,
            "message": f"JSON解析失败: {str(e)}"
        }
    except Exception as e:
        return {
            "code": "ERROR",
            "data": None,
            "message": f"读取JSON文件失败: {str(e)}"
        }


def write_json(
    file_path: str,
    data: Union[Dict[str, Any], List[Any]],
    encoding: str = "utf-8",
    indent: int = 2,
    ensure_ascii: bool = False,
    backup_before_write: bool = True,
    create_parents: bool = True,
) -> Dict[str, Any]:
    """写入数据到JSON文件 - 小沈 2026-05-03修正，按文档7.4节参数定义
    
    参数：
    - file_path: JSON文件路径（必填）
    - data: 要写入的数据（必填）
    - encoding: 文件编码（可选），默认 utf-8
    - indent: 缩进空格数（可选），默认 2
    - ensure_ascii: 是否转义非ASCII（可选），默认 false
    - backup_before_write: 写入前备份（可选），默认 true
    - create_parents: 自动创建父目录（可选），默认 true
    """
    import shutil
    from datetime import datetime
    
    try:
        path = Path(file_path)
        
        if backup_before_write and path.exists():
            backup_dir = Path(__file__).parent.parent.parent.parent / "temp" / "json_backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{path.stem}_{timestamp}{path.suffix}"
            shutil.copy2(path, backup_path)
        
        if create_parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding=encoding) as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        
        return {
            "code": "SUCCESS",
            "data": {
                "file_path": file_path,
                "backup_created": backup_before_write and path.exists()
            },
            "message": f"成功写入JSON文件: {file_path}"
        }
    except Exception as e:
        return {
            "code": "ERROR",
            "data": None,
            "message": f"写入JSON文件失败: {str(e)}"
        }


def read_csv_basic(
    file_path: str,
    encoding: str = "auto_detect",
    delimiter: str = "auto_detect",
    has_header: bool = True,
    max_rows: int = 500,
    skip_blank_lines: bool = True,
) -> Dict[str, Any]:
    """读取CSV文件内容（基础版）- 小沈 2026-05-03修正，按文档7.4节参数定义
    
    参数：
    - file_path: CSV文件路径（必填）
    - encoding: 文件编码（可选），默认 auto_detect
    - delimiter: 分隔符（可选），默认 auto_detect
    - has_header: 是否有表头（可选），默认 true
    - max_rows: 最大读取行数（可选），默认 500
    - skip_blank_lines: 跳过空行（可选），默认 true
    """
    import csv
    
    try:
        path = Path(file_path)
        if not path.exists():
            return {
                "code": "ERROR",
                "data": None,
                "message": f"文件不存在: {file_path}"
            }
        
        actual_encoding = "utf-8"
        if encoding == "auto_detect":
            try:
                with open(path, "rb") as f:
                    raw = f.read(10)
                    raw.decode("utf-8")
                actual_encoding = "utf-8"
            except:
                actual_encoding = "gbk"
        
        actual_delimiter = ","
        if delimiter == "auto_detect":
            with open(path, "r", encoding=actual_encoding, newline="") as f:
                sample = [f.readline() for _ in range(min(10, sum(1 for _ in open(path, "r", encoding=actual_encoding))))]
                try:
                    sample_text = sample[0] if sample else ""
                    if "\t" in sample_text:
                        actual_delimiter = "\t"
                    elif ";" in sample_text:
                        actual_delimiter = ";"
                    else:
                        actual_delimiter = ","
                except:
                    actual_delimiter = ","
        else:
            actual_delimiter = delimiter
        
        rows = []
        headers = []
        
        with open(path, "r", encoding=actual_encoding, newline="") as f:
            reader = csv.reader(f, delimiter=actual_delimiter)
            
            for i, row in enumerate(reader):
                if skip_blank_lines and not any(cell.strip() for cell in row):
                    continue
                    
                if i == 0 and has_header:
                    headers = row
                else:
                    rows.append(row)
                    if len(rows) >= max_rows:
                        break
        
        if not has_header and rows:
            headers = [f"column_{i}" for i in range(len(rows[0]))] if rows else []
        
        return {
            "code": "SUCCESS",
            "data": {
                "headers": headers,
                "rows": rows,
                "total_rows": len(rows)
            },
            "message": f"成功读取CSV文件: {file_path}，共 {len(rows)} 行"
        }
    except Exception as e:
        return {
            "code": "ERROR",
            "data": None,
            "message": f"读取CSV文件失败: {str(e)}"
        }


def parse_yaml(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取YAML文件内容 - 小沈 2026-05-04"""
    try:
        import yaml
        path = Path(file_path)
        if not path.exists():
            return {"code": "ERROR", "data": None, "message": f"文件不存在: {file_path}"}
        
        with open(path, "r", encoding=encoding) as f:
            data = yaml.safe_load(f)
        
        return {"code": "SUCCESS", "data": data, "message": f"成功读取YAML文件: {file_path}"}
    except ImportError:
        return {"code": "ERROR", "data": None, "message": "PyYAML库未安装，请先执行: pip install pyyaml"}
    except Exception as e:
        return {"code": "ERROR", "data": None, "message": f"读取YAML失败: {str(e)}"}


def write_yaml(file_path: str, data: Any, encoding: str = "utf-8", indent: int = 2) -> Dict[str, Any]:
    """写入数据到YAML文件 - 小沈 2026-05-04"""
    try:
        import yaml
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "w", encoding=encoding) as f:
            yaml.safe_dump(data, f, allow_unicode=True, indent=indent)
        
        return {"code": "SUCCESS", "data": {"file_path": file_path}, "message": f"成功写入YAML文件: {file_path}"}
    except ImportError:
        return {"code": "ERROR", "data": None, "message": "PyYAML库未安装，请先执行: pip install pyyaml"}
    except Exception as e:
        return {"code": "ERROR", "data": None, "message": f"写入YAML失败: {str(e)}"}


def parse_toml(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取TOML文件内容 - 小沈 2026-05-04"""
    try:
        import tomli
        path = Path(file_path)
        if not path.exists():
            return {"code": "ERROR", "data": None, "message": f"文件不存在: {file_path}"}
        
        with open(path, "rb") as f:
            data = tomli.load(f)
        
        return {"code": "SUCCESS", "data": data, "message": f"成功读取TOML文件: {file_path}"}
    except ImportError:
        return {"code": "ERROR", "data": None, "message": "tomli库未安装，请先执行: pip install tomli"}
    except Exception as e:
        return {"code": "ERROR", "data": None, "message": f"读取TOML失败: {str(e)}"}


def write_toml(file_path: str, data: Dict[str, Any], encoding: str = "utf-8") -> Dict[str, Any]:
    """写入数据到TOML文件 - 小沈 2026-05-04"""
    try:
        import tomli_w as tomli
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(path, "wb") as f:
            tomli.dump(data, f)
        
        return {"code": "SUCCESS", "data": {"file_path": file_path}, "message": f"成功写入TOML文件: {file_path}"}
    except ImportError:
        return {"code": "ERROR", "data": None, "message": "tomli库未安装，请先执行: pip install tomli"}
    except Exception as e:
        return {"code": "ERROR", "data": None, "message": f"写入TOML失败: {str(e)}"}


def parse_ini(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取INI配置文件 - 小沈 2026-05-04"""
    try:
        import configparser
        path = Path(file_path)
        if not path.exists():
            return {"code": "ERROR", "data": None, "message": f"文件不存在: {file_path}"}
        
        config = configparser.ConfigParser()
        config.read(path, encoding=encoding)
        
        result = {}
        for section in config.sections():
            result[section] = dict(config[section])
        
        return {"code": "SUCCESS", "data": result, "message": f"成功读取INI文件: {file_path}"}
    except Exception as e:
        return {"code": "ERROR", "data": None, "message": f"读取INI失败: {str(e)}"}


def parse_xml(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取XML文件内容 - 小沈 2026-05-04"""
    try:
        import xml.etree.ElementTree as ET
        path = Path(file_path)
        if not path.exists():
            return {"code": "ERROR", "data": None, "message": f"文件不存在: {file_path}"}
        
        tree = ET.parse(path)
        root = tree.getroot()
        
        def elem_to_dict(elem):
            children = list(elem)
            if not children:
                return elem.text
            result = {}
            for child in children:
                child_data = elem_to_dict(child)
                if child.tag in result:
                    if not isinstance(result[child.tag], list):
                        result[child.tag] = [result[child.tag]]
                    result[child.tag].append(child_data)
                else:
                    result[child.tag] = child_data
            return result
        
        data = {root.tag: elem_to_dict(root)}
        return {"code": "SUCCESS", "data": data, "message": f"成功读取XML文件: {file_path}"}
    except Exception as e:
        return {"code": "ERROR", "data": None, "message": f"读取XML失败: {str(e)}"}


def parse_properties(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取Java Properties文件 - 小沈 2026-05-04"""
    try:
        path = Path(file_path)
        if not path.exists():
            return {"code": "ERROR", "data": None, "message": f"文件不存在: {file_path}"}
        
        result = {}
        with open(path, "r", encoding=encoding) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and not line.startswith("!"):
                    if "=" in line:
                        key, val = line.split("=", 1)
                        result[key.strip()] = val.strip()
                    elif ":" in line:
                        key, val = line.split(":", 1)
                        result[key.strip()] = val.strip()
        
        return {"code": "SUCCESS", "data": result, "message": f"成功读取Properties文件: {file_path}"}
    except Exception as e:
        return {"code": "ERROR", "data": None, "message": f"读取Properties失败: {str(e)}"}
    except Exception as e:
        return {
            "code": "ERROR",
            "data": None,
            "message": f"读取CSV文件失败: {str(e)}"
        }
