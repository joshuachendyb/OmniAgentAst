# -*- coding: utf-8 -*-
"""
数据格式辅助函数模块

【创建时间】2026-05-18 小沈
【来源】从data_format目录迁入，供file_tools.py调用
【恢复 2026-05-29 小沈】恢复被430d1505误删的_read_json/_write_json/_parse_yaml/_write_yaml/_parse_toml/_write_toml/_detect_encoding/_truncate_dict/_read_csv_basic

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
"""

import configparser
import csv
import json
import shutil
import tempfile
from datetime import datetime
from typing import Dict, Any, List, Union, Tuple
from pathlib import Path
import xml.etree.ElementTree as ET

from app.services.tools._response import build_success, build_error
from app.constants import (
    ERR_DOC_READ_JSON,
    ERR_NO_PYYAML,
    ERR_NO_TOMLI,
    ERR_NO_TOMLI_W,
    ERR_PARSE_INI,
    ERR_PARSE_PROPERTIES,
    ERR_PARSE_TOML,
    ERR_PARSE_XML,
    ERR_PARSE_YAML,
    ERR_READ_CSV_BASIC,
    ERR_WRITE_JSON,
    ERR_WRITE_TOML,
    ERR_WRITE_YAML,
)


def _detect_encoding(path: Path, default: str = "utf-8") -> str:
    """检测文件编码 - 小沈 2026-05-25 重构新增"""
    try:
        with open(path, "rb") as f:
            raw = f.read(4)
            if raw.startswith(b'\xef\xbb\xbf'):
                return "utf-8-sig"
            elif raw.startswith(b'\xff\xfe') or raw.startswith(b'\xfe\xff'):
                return "utf-16"
            else:
                try:
                    raw.decode("utf-8")
                    return "utf-8"
                except UnicodeDecodeError:
                    return "gbk"
    except Exception:
        return default


def _truncate_dict(d: Any, max_depth: int = 10, max_list_len: int = 100, current_depth: int = 0) -> Tuple[Any, bool]:
    """截断嵌套字典/列表 - 小沈 2026-05-25 重构新增"""
    if current_depth >= max_depth:
        return {"__truncated__": True, "depth": current_depth}, True
    if isinstance(d, dict):
        result = {}
        any_truncated = False
        for k, v in d.items():
            result[k], t = _truncate_dict(v, max_depth, max_list_len, current_depth + 1)
            any_truncated = any_truncated or t
        return result, any_truncated
    elif isinstance(d, list):
        truncated_list = d[:max_list_len]
        any_truncated = len(d) > max_list_len
        result = []
        for item in truncated_list:
            r, t = _truncate_dict(item, max_depth, max_list_len, current_depth + 1)
            result.append(r)
            any_truncated = any_truncated or t
        return result, any_truncated
    return d, False


def _read_json(file_path: str, encoding: str = "auto_detect", max_depth: int = 10) -> Dict[str, Any]:
    """读取JSON文件内容 - 小沈 2026-05-25 重构"""
    try:
        path = Path(file_path)
        if not path.exists():
            return build_error(ERR_DOC_READ_JSON, f"文件不存在: {file_path}")

        actual_encoding = _detect_encoding(path) if encoding == "auto_detect" else encoding
        with open(path, "r", encoding=actual_encoding) as f:
            data = json.load(f)

        truncated = False
        if max_depth < 50:
            data, truncated = _truncate_dict(data, max_depth)

        return build_success(
            data,
            f"成功读取JSON文件: {file_path}",
            llm_data={"文件": file_path, "内容": data, "已截断": truncated},
            metadata={"truncated": truncated, "max_depth": max_depth, "file_path": file_path},
        )
    except json.JSONDecodeError as e:
        return build_error(ERR_DOC_READ_JSON, f"JSON解析失败: {str(e)}")
    except Exception as e:
        return build_error(ERR_DOC_READ_JSON, f"读取JSON文件失败: {str(e)}")


def _write_json(file_path: str, data: Union[Dict[str, Any], List[Any]], encoding: str = "utf-8", indent: int = 2, ensure_ascii: bool = False, backup_before_write: bool = True, create_parents: bool = True) -> Dict[str, Any]:
    """写入数据到JSON文件 - 小沈 2026-05-03, 修正 2026-05-05"""
    try:
        path = Path(file_path)
        backup_created = False
        if backup_before_write and path.exists():
            backup_dir = Path(tempfile.gettempdir()) / "json_backup"
            backup_dir.mkdir(parents=True, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_path = backup_dir / f"{path.stem}_{timestamp}{path.suffix}"
            shutil.copy2(path, backup_path)
            backup_created = backup_path.exists()
        if create_parents:
            path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding=encoding) as f:
            json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
        return build_success({"file_path": file_path, "backup_created": backup_created}, f"成功写入JSON文件: {file_path}")
    except Exception as e:
        return build_error(ERR_WRITE_JSON, f"写入JSON文件失败: {str(e)}")


def _read_csv_basic(file_path: str, encoding: str = "auto_detect", delimiter: str = "auto_detect", has_header: bool = True, max_rows: int = 500, skip_blank_lines: bool = True) -> Dict[str, Any]:
    """读取CSV文件内容（基础版）- 小沈 2026-05-25 重构"""
    try:
        path = Path(file_path)
        if not path.exists():
            return build_error(ERR_READ_CSV_BASIC, f"文件不存在: {file_path}")

        actual_encoding = _detect_encoding(path) if encoding == "auto_detect" else encoding

        actual_delimiter = ","
        if delimiter == "auto_detect":
            try:
                with open(path, "r", encoding=actual_encoding, newline="") as f:
                    sample_text = f.readline()
                if "\t" in sample_text:
                    actual_delimiter = "\t"
                elif ";" in sample_text:
                    actual_delimiter = ";"
                else:
                    actual_delimiter = ","
            except Exception:
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
        return build_success({"headers": headers, "rows": rows, "total_rows": len(rows)}, f"成功读取CSV文件: {file_path}，共 {len(rows)} 行")
    except Exception as e:
        return build_error(ERR_READ_CSV_BASIC, f"读取CSV文件失败: {str(e)}")


def _parse_yaml(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取YAML文件内容 - 小沈 2026-05-04"""
    try:
        import yaml
        path = Path(file_path)
        if not path.exists():
            return build_error(ERR_PARSE_YAML, f"文件不存在: {file_path}")
        with open(path, "r", encoding=encoding) as f:
            data = yaml.safe_load(f)
        return build_success(data, f"成功读取YAML文件: {file_path}")
    except ImportError:
        return build_error(ERR_NO_PYYAML, "PyYAML未安装，请执行: pip install pyyaml")
    except Exception as e:
        return build_error(ERR_PARSE_YAML, f"读取YAML失败: {str(e)}")


def _write_yaml(file_path: str, data: Any, encoding: str = "utf-8", indent: int = 2) -> Dict[str, Any]:
    """写入数据到YAML文件 - 小沈 2026-05-04"""
    try:
        import yaml
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding=encoding) as f:
            yaml.safe_dump(data, f, allow_unicode=True, indent=indent)
        return build_success({"file_path": file_path}, f"成功写入YAML文件: {file_path}")
    except ImportError:
        return build_error(ERR_NO_PYYAML, "PyYAML未安装，请执行: pip install pyyaml")
    except Exception as e:
        return build_error(ERR_WRITE_YAML, f"写入YAML失败: {str(e)}")


def _parse_toml(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取TOML文件内容 - 小沈 2026-05-04"""
    try:
        import tomli
        path = Path(file_path)
        if not path.exists():
            return build_error(ERR_PARSE_TOML, f"文件不存在: {file_path}")
        with open(path, "rb") as f:
            data = tomli.load(f)
        return build_success(data, f"成功读取TOML文件: {file_path}")
    except ImportError:
        return build_error(ERR_NO_TOMLI, "tomli未安装，请执行: pip install tomli")
    except Exception as e:
        return build_error(ERR_PARSE_TOML, f"读取TOML失败: {str(e)}")


def _write_toml(file_path: str, data: Dict[str, Any], encoding: str = "utf-8") -> Dict[str, Any]:
    """写入数据到TOML文件 - 小沈 2026-05-04, 修正 2026-05-05"""
    try:
        import tomli_w
        path = Path(file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "wb") as f:
            tomli_w.dump(data, f)
        return build_success({"file_path": file_path}, f"成功写入TOML文件: {file_path}")
    except ImportError:
        return build_error(ERR_NO_TOMLI_W, "tomli_w未安装，请执行: pip install tomli-w")
    except Exception as e:
        return build_error(ERR_WRITE_TOML, f"写入TOML失败: {str(e)}")


def _parse_ini(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取INI配置文件 - 小沈 2026-05-04"""
    try:
        path = Path(file_path)
        if not path.exists():
            return build_error(ERR_PARSE_INI, f"文件不存在: {file_path}")
        config = configparser.ConfigParser()
        config.read(path, encoding=encoding)
        result = {}
        for section in config.sections():
            result[section] = dict(config[section])
        return build_success(result, f"成功读取INI文件: {file_path}")
    except Exception as e:
        return build_error(ERR_PARSE_INI, f"读取INI失败: {str(e)}")


def _parse_xml(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取XML文件内容 - 小沈 2026-05-04"""
    try:
        path = Path(file_path)
        if not path.exists():
            return build_error(ERR_PARSE_XML, f"文件不存在: {file_path}")
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
        return build_success(data, f"成功读取XML文件: {file_path}")
    except Exception as e:
        return build_error(ERR_PARSE_XML, f"读取XML失败: {str(e)}")


def _parse_properties(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取Java Properties文件 - 小沈 2026-05-04, 修正 2026-05-05"""
    try:
        path = Path(file_path)
        if not path.exists():
            return build_error(ERR_PARSE_PROPERTIES, f"文件不存在: {file_path}")
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
        return build_success(result, f"成功读取Properties文件: {file_path}")
    except Exception as e:
        return build_error(ERR_PARSE_PROPERTIES, f"读取Properties失败: {str(e)}")
