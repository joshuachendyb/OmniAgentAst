# -*- coding: utf-8 -*-
"""
数据格式辅助函数模块

【创建时间】2026-05-18 小沈
【来源】从data_format目录迁入，供file_tools.py调用

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
