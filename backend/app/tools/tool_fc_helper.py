# -*- coding: utf-8 -*-
"""
Tool函数公共辅助代码 — 纯逻辑函数集合
【创建时间】2026-06-22 小欧
【铁律】本文件严禁出现 build_success/build_error/build_warning/build3 和 llm_data
        所有返回结构化结果的逻辑必须在各tool主函数中处理
【来源】从 toolhelper/ 目录迁移，合并以下文件中被tool引用的纯逻辑函数：
  - common_helper.py: _check_module, _decode_bytes_safe
  - exec_helper.py: _check_module_available, _validate_code_safety, _check_python_available, _check_node_available
  - data_helper.py: _serialize_rows, _load_dataframe
  - date_helper.py: parse_datetime_any, parse_datetime_string, is_holiday, calc_next_n_workday, get_holiday_date_by_name, resolve_timezone
  - shell_helper.py: _check_shell_injection, _read_stream_nonblocking
  - db_helper.py: check_db_exists
  - content_validation.py: validate_json_content, validate_csv_content, validate_xml_content, validate_html_content, validate_python_content
"""
# 【铁规】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。

import csv
import importlib
import io
import json
import os
import re
import sqlite3
import subprocess
import sys
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta, timezone
from io import StringIO
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import pandas as pd

from app.tools.tool_constants import DANGEROUS_PATTERNS, QINGMING_DATES, SHELL_INJECTION_PATTERNS, SUBPROCESS_TIMEOUT_SHORT
from app.utils.common_patterns import UTC_OFFSET_PATTERN
from app.utils.json_utils import parse_json


# ═══════════════════════════════════════════════════════════════
# 来自 common_helper.py
# ═══════════════════════════════════════════════════════════════

def _check_module(module_name: str) -> bool:
    """统一检查Python模块是否已安装 — 小沈 2026-05-18"""
    available, _ = _check_module_available(module_name)
    return available


def _decode_bytes_safe(data: Any, encodings: Optional[list] = None) -> str:
    """安全解码bytes为str - 小沈 2026-06-09"""
    if data is None:
        return ""
    if isinstance(data, str):
        return data.replace('\r\n', '\n')
    if isinstance(data, bytes):
        for enc in (encodings or ['utf-8', 'gbk', 'latin-1']):
            try:
                return data.decode(enc).replace('\r\n', '\n')
            except (UnicodeDecodeError, LookupError):
                continue
        return data.decode('latin-1').replace('\r\n', '\n')
    return str(data)


# ═══════════════════════════════════════════════════════════════
# 来自 exec_helper.py
# ═══════════════════════════════════════════════════════════════

def _check_module_available(module_name: str) -> Tuple[bool, str]:
    """检查Python模块是否可用 — 小沈 2026-05-17"""
    try:
        mod = importlib.import_module(module_name)
        return True, getattr(mod, "__version__", "unknown")
    except ImportError:
        return False, ""


def _validate_code_safety(code: str) -> List[str]:
    """验证代码安全性 — 小沈 2026-05-17"""
    warnings = []
    for pattern, desc in DANGEROUS_PATTERNS:
        if re.search(pattern, code):
            warnings.append(desc)
    return warnings


def _check_python_available() -> bool:
    """检查Python是否可用 — 小沈 2026-05-17"""
    try:
        return sys.executable is not None
    except Exception:
        return False


def _check_node_available() -> bool:
    """检查Node.js是否可用 — 小沈 2026-05-17"""
    try:
        result = subprocess.run(
            ["node", "--version"],
            capture_output=True,
            timeout=SUBPROCESS_TIMEOUT_SHORT,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


# ═══════════════════════════════════════════════════════════════
# 来自 data_helper.py
# ═══════════════════════════════════════════════════════════════

def _serialize_rows(df) -> List[List[Any]]:
    """将DataFrame行数据序列化为JSON安全格式 — 小沈 2026-05-22"""
    rows = df.values.tolist()
    serialized_rows = []
    for row in rows:
        serialized_row = []
        for val in row:
            if pd.isna(val):
                serialized_row.append(None)
            elif hasattr(val, 'item'):
                serialized_row.append(val.item())
            elif hasattr(val, 'isoformat'):
                serialized_row.append(val.isoformat())
            else:
                serialized_row.append(val)
        serialized_rows.append(serialized_row)
    return serialized_rows


def _load_dataframe(source: Union[str, List[Dict[str, Any]]], **kwargs):
    """统一加载DataFrame — 小沈 2026-05-22"""
    if isinstance(source, str):
        path = Path(source)
        if not path.exists():
            raise FileNotFoundError(f"文件不存在: {source}")
        suffix = path.suffix.lower()
        if suffix in (".xlsx", ".xls"):
            return pd.read_excel(source, engine="openpyxl" if suffix == ".xlsx" else None, **kwargs)
        else:
            return pd.read_csv(source, **kwargs)
    elif isinstance(source, list):
        return pd.DataFrame(source)
    else:
        raise ValueError("source必须是文件路径或数据数组")


# ═══════════════════════════════════════════════════════════════
# 来自 date_helper.py
# ═══════════════════════════════════════════════════════════════

SOLAR_HOLIDAYS = {
    (1, 1): "元旦", (2, 14): "情人节", (3, 8): "妇女节",
    (3, 12): "植树节", (4, 1): "愚人节", (5, 1): "劳动节",
    (5, 4): "青年节", (6, 1): "儿童节", (7, 1): "建党节",
    (8, 1): "建军节", (9, 10): "教师节", (10, 1): "国庆节",
    (12, 24): "平安夜", (12, 25): "圣诞节",
}

SOLAR_HOLIDAY_NAMES = {v: k for k, v in SOLAR_HOLIDAYS.items()}

LUNAR_HOLIDAYS = {
    (1, 1): "春节", (1, 15): "元宵节", (5, 5): "端午节",
    (7, 7): "七夕节", (7, 15): "中元节", (8, 15): "中秋节",
    (9, 9): "重阳节", (12, 8): "腊八节", (12, 30): "除夕",
}

LUNAR_HOLIDAY_NAMES = {v: k for k, v in LUNAR_HOLIDAYS.items()}

HOLIDAY_ALIASES = {
    "过年": "春节", "端阳": "端午节", "五月节": "端午节",
    "正月": "春节", "正月十五": "元宵节", "八月十五": "中秋节",
    "正月正": "春节", "五月初五": "端午节",
}


def parse_datetime_any(value: Any) -> Optional[datetime]:
    """通用时间解析:支持datetime/int/float/str → datetime(带时区)"""
    try:
        if isinstance(value, datetime):
            return value.astimezone()
        elif isinstance(value, (int, float)):
            return datetime.fromtimestamp(value, tz=timezone.utc).astimezone()
        elif isinstance(value, str):
            return parse_datetime_string(value)
        else:
            return None
    except Exception:
        return None


def parse_datetime_string(date_str: str) -> Optional[datetime]:
    """字符串时间解析:支持ISO/常见中文格式/数字提取"""
    try:
        date_str = date_str.strip()
        try:
            s = re.sub(r'([+-]\d{2}):(\d{2})$', r'\1\2', date_str)
            if s != date_str:
                return datetime.fromisoformat(s)
        except ValueError:
            pass
        try:
            return datetime.fromisoformat(date_str)
        except ValueError:
            pass
        formats = [
            "%Y-%m-%d %H:%M:%S", "%Y-%m-%d", "%Y/%m/%d %H:%M:%S", "%Y/%m/%d",
            "%Y年%m月%d日 %H:%M:%S", "%Y年%m月%d日", "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f%z",
        ]
        for fmt in formats:
            try:
                dt = datetime.strptime(date_str, fmt)
                return dt.astimezone()
            except ValueError:
                continue
        numbers = re.findall(r'\d+', date_str)
        if len(numbers) >= 3:
            try:
                year = int(numbers[0])
                month = int(numbers[1])
                day = int(numbers[2])
                hour = int(numbers[3]) if len(numbers) > 3 else 0
                minute = int(numbers[4]) if len(numbers) > 4 else 0
                second = int(numbers[5]) if len(numbers) > 5 else 0
                dt = datetime(year, month, day, hour, minute, second)
                return dt.astimezone()
            except Exception:
                pass
        return None
    except Exception:
        return None


def is_holiday(date_obj) -> Tuple[bool, Optional[str]]:
    """判断日期是否为假日,返回(是否假日, 节日名称) — 小健 2026-05-25"""
    try:
        dt = date_obj if hasattr(date_obj, 'month') else None
        if dt is None:
            return (False, None)
        month_day = (dt.month, dt.day)
        holiday = _is_solar_holiday(month_day, dt.year)
        if holiday:
            return (True, holiday)
        holiday = _is_lunar_holiday(dt)
        if holiday:
            return (True, holiday)
        return (False, None)
    except Exception:
        return (False, None)


def _is_solar_holiday(month_day: Tuple[int, int], year: int) -> Optional[str]:
    """判断公历假日 — 小健 2026-05-25"""
    if month_day in SOLAR_HOLIDAYS:
        return SOLAR_HOLIDAYS[month_day]
    qingming = QINGMING_DATES.get(year, (4, 5))
    if month_day == qingming:
        return "清明节"
    return None


def _is_lunar_holiday(date_obj) -> Optional[str]:
    """判断农历假日 — 小健 2026-05-25"""
    try:
        from lunarcalendar import Converter
        solar_date = date_obj.date() if hasattr(date_obj, 'date') else date_obj
        lunar = Converter.Solar2Lunar(solar_date)
        lunar_month_day = (lunar.month, lunar.day)
        return LUNAR_HOLIDAYS.get(lunar_month_day)
    except Exception:
        return None


def calc_next_n_workday(start_date, n: int) -> list:
    """计算从start_date往后第N个工作日的日期列表(ISO格式字符串)"""
    try:
        current_date = start_date + timedelta(days=1)
        found_count = 0
        result_dates = []
        while found_count < n:
            weekday = current_date.weekday()
            is_weekend = weekday >= 5
            hol, _ = is_holiday(current_date)
            is_workday = not is_weekend and not hol
            if is_workday:
                result_dates.append(current_date.isoformat())
                found_count += 1
            current_date += timedelta(days=1)
        return result_dates
    except Exception:
        return []


def get_holiday_date_by_name(name: str, year: Optional[int] = None) -> Optional[Dict[str, Any]]:
    """按节日名称查找公历日期 — 小沈 2026-06-14"""
    if not name or not isinstance(name, str):
        return None
    if year is None:
        year = datetime.now().year
    cleaned = name.strip()
    if cleaned in HOLIDAY_ALIASES:
        cleaned = HOLIDAY_ALIASES[cleaned]
    if cleaned in SOLAR_HOLIDAY_NAMES:
        m, d = SOLAR_HOLIDAY_NAMES[cleaned]
        dt = datetime(year, m, d)
        return {"name": cleaned, "date": dt.strftime("%Y-%m-%d"), "type": "solar",
                "weekday": dt.strftime("%A"), "isoweekday": dt.isoweekday()}
    if cleaned == "清明节":
        qingming = QINGMING_DATES.get(year, (4, 5))
        m, d = qingming
        dt = datetime(year, m, d)
        return {"name": "清明节", "date": dt.strftime("%Y-%m-%d"), "type": "qingming",
                "weekday": dt.strftime("%A"), "isoweekday": dt.isoweekday()}
    if cleaned in LUNAR_HOLIDAY_NAMES:
        try:
            from lunarcalendar import Lunar, Converter
            m, d = LUNAR_HOLIDAY_NAMES[cleaned]
            lunar = Lunar(year, m, d)
            solar = Converter.Lunar2Solar(lunar)
            solar_date = solar.to_date()
            dt = datetime(solar_date.year, solar_date.month, solar_date.day)
            return {"name": cleaned, "date": dt.strftime("%Y-%m-%d"), "type": "lunar",
                    "weekday": dt.strftime("%A"), "isoweekday": dt.isoweekday()}
        except Exception:
            return None
    all_keys = list(SOLAR_HOLIDAY_NAMES.keys()) + list(LUNAR_HOLIDAY_NAMES.keys()) + ["清明节"]
    matches = [k for k in all_keys if cleaned in k]
    if len(matches) == 1:
        return get_holiday_date_by_name(matches[0], year)
    return None


def resolve_timezone(tz_str: str):
    """解析时区字符串:IANA名称(Asia/Shanghai) 或 ±HH:MM格式(+08:00)"""
    import pytz
    try:
        return pytz.timezone(tz_str)
    except Exception:
        if UTC_OFFSET_PATTERN.match(tz_str):
            sign = -1 if tz_str[0] == '-' else 1
            hours = int(tz_str[1:3])
            minutes = int(tz_str[4:6])
            return timezone(timedelta(hours=sign * hours, minutes=sign * minutes))
        raise ValueError(f"无法解析时区: {tz_str}")


# ═══════════════════════════════════════════════════════════════
# 来自 shell_helper.py
# ═══════════════════════════════════════════════════════════════

def _check_shell_injection(command: str) -> Optional[str]:
    """检查shell命令注入风险,返回错误描述或None - 小健 2026-05-13"""
    if not command or not command.strip():
        return None
    for pattern, desc in SHELL_INJECTION_PATTERNS:
        if re.search(pattern, command):
            return f"检测到高风险shell注入模式: {desc}"
    return None


def _read_stream_nonblocking(stream, encoding: str = "utf-8") -> str:
    """非阻塞读取子进程输出流 - 小沈 2026-05-05"""
    if stream is None:
        return ""
    try:
        if hasattr(stream, 'read1'):
            bytes_data = b""
            while True:
                chunk = stream.read1(4096)
                if not chunk:
                    break
                bytes_data += chunk
        else:
            bytes_data = stream.read()
    except (IOError, OSError):
        return ""
    if not bytes_data:
        return ""
    if encoding != "utf-8":
        try:
            return bytes_data.decode(encoding)
        except UnicodeDecodeError:
            pass
    return _decode_bytes_safe(bytes_data)


# ═══════════════════════════════════════════════════════════════
# 来自 db_helper.py
# ═══════════════════════════════════════════════════════════════

def check_db_exists(db_path: str) -> Dict[str, Any]:
    """检查数据库是否存在 - 小沈 2026-05-17
    【注意】本函数返回纯dict，不含build3结构。调用方需自行包装。
    """
    path = Path(db_path)
    if not path.exists():
        return {"exists": False, "db_type": None, "size": 0}
    size = path.stat().st_size
    try:
        conn = sqlite3.connect(str(path))
        conn.execute("SELECT 1")
        conn.close()
        return {"exists": True, "db_type": "sqlite", "size": size}
    except Exception as e:
        return {"exists": True, "db_type": "unknown", "size": size, "error": str(e)}


# ═══════════════════════════════════════════════════════════════
# 来自 content_validation.py
# ═══════════════════════════════════════════════════════════════

def validate_json_content(content: str) -> Optional[str]:
    """验证JSON内容格式 — 小健 2026-05-25"""
    try:
        parse_json(content, raise_on_error=True)
        return None
    except json.JSONDecodeError as e:
        return f"JSON格式验证失败: 第{e.lineno}行第{e.colno}列 - {e.msg}"


def validate_csv_content(content: str, max_check_lines: int = 1000) -> Optional[str]:
    """验证CSV内容格式 — 小健 2026-05-25"""
    try:
        reader = csv.reader(StringIO(content))
        row_lengths = []
        for i, row in enumerate(reader):
            if i > max_check_lines:
                break
            if row:
                row_lengths.append(len(row))
        if row_lengths and len(set(row_lengths)) > 1:
            return f"CSV格式警告: 列数不一致(发现{set(row_lengths)}种列数),写入可能导致数据错位"
        return None
    except Exception as e:
        return f"CSV格式验证失败: {str(e)[:100]}"


def validate_xml_content(content: str) -> Optional[str]:
    """验证XML内容格式 — 小健 2026-05-25"""
    try:
        ET.fromstring(content)
        return None
    except ET.ParseError as e:
        return f"XML格式验证失败: {str(e)[:100]}"


def validate_html_content(content: str) -> Optional[str]:
    """验证HTML内容格式 — 小健 2026-05-25"""
    open_tags = content.count('<')
    close_tags = content.count('>')
    if open_tags != close_tags:
        return f"HTML标记验证警告: '<'({open_tags}个)与'>'({close_tags}个)数量不匹配"
    return None


def validate_python_content(content: str, file_path: Optional[str] = None) -> Optional[str]:
    """验证Python语法 — 小健 2026-05-25"""
    try:
        compile(content, file_path or '<string>', 'exec')
        return None
    except SyntaxError as e:
        error_msg = f"Python语法验证失败: 第{e.lineno}行 - {e.msg}"
        if "unterminated string literal" in e.msg:
            error_msg += ";建议:转义字符串请使用raw string r'...',如 r'\\\\' 代替 '\\\\'"
        elif "invalid character" in e.msg:
            error_msg += ";建议:Python不支持全角标点,请使用半角括号()、逗号,、冒号:、分号;"
        elif "invalid escape sequence" in e.msg:
            error_msg += ";建议:请在字符串前加r前缀使用raw string,或将转义字符双写如 \\d → r'\\d'"
        return error_msg


# ═══════════════════════════════════════════════════════════════
# 来自 data_format_helper.py (纯逻辑部分)
# ═══════════════════════════════════════════════════════════════

def _detect_encoding(file_path) -> str:
    """检测文件编码 — 小健 2026-05-25
    Args:
        file_path: Path对象或str路径
    Returns:
        检测到的编码名称字符串
    """
    try:
        import chardet
        with open(str(file_path), 'rb') as f:
            raw = f.read(8192)
        if not raw:
            return 'utf-8'
        result = chardet.detect(raw)
        encoding = result.get('encoding', 'utf-8')
        if encoding:
            encoding = encoding.upper()
            if encoding in ('UTF-8-SIG', 'UTF-8 BOM'):
                return 'utf-8-sig'
            if encoding in ('GB2312', 'GB18030'):
                return 'gbk'
        return (encoding or 'utf-8').lower()
    except ImportError:
        return 'utf-8'
    except Exception:
        return 'utf-8'


# ═══════════════════════════════════════════════════════════════
# 来自 data_format_helper.py — 格式读写函数(纯逻辑版，不含build3)
# 【铁律】以下函数返回纯数据或抛异常，严禁调用build_success/build_error
# ═══════════════════════════════════════════════════════════════

def _detect_encoding_simple(path, default: str = "utf-8") -> str:
    """检测文件编码(简单版，基于BOM和UTF-8试探) — 小沈 2026-05-25"""
    try:
        with open(path, "rb") as f:
            raw = f.read(4)
            if raw.startswith(b'\xef\xbb\xbf'):
                return "utf-8-sig"
            elif raw.startswith(b'\xff\xfe'):
                return "utf-16-le"
            elif raw.startswith(b'\xfe\xff'):
                return "utf-16-be"
            else:
                try:
                    raw.decode("utf-8")
                    return "utf-8"
                except UnicodeDecodeError:
                    return "latin-1"
    except Exception:
        return default


def _read_json(file_path: str, encoding: str = "auto_detect") -> Any:
    """读取JSON文件，返回纯数据 — 小沈 2026-05-25"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    actual_encoding = _detect_encoding_simple(path) if encoding == "auto_detect" else encoding
    with open(path, "r", encoding=actual_encoding) as f:
        return json.load(f)


def _write_json(file_path: str, data: Any, encoding: str = "utf-8", indent: int = 2, ensure_ascii: bool = False, create_parents: bool = True) -> Dict[str, Any]:
    """写入JSON文件，返回纯dict — 小沈 2026-05-03"""
    path = Path(file_path)
    if create_parents:
        path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        json.dump(data, f, indent=indent, ensure_ascii=ensure_ascii)
    return {"file_path": file_path}


def _read_csv_basic(file_path: str, encoding: str = "auto_detect", delimiter: str = "auto_detect", has_header: bool = True, max_rows: int = 500, skip_blank_lines: bool = True) -> Dict[str, Any]:
    """读取CSV文件，返回纯dict — 小沈 2026-05-25"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    actual_encoding = _detect_encoding_simple(path) if encoding == "auto_detect" else encoding
    actual_delimiter = ","
    if delimiter == "auto_detect":
        try:
            with open(path, "r", encoding=actual_encoding, newline="") as f:
                sample_text = f.readline()
            if "\t" in sample_text:
                actual_delimiter = "\t"
            elif ";" in sample_text:
                actual_delimiter = ";"
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
    return {"headers": headers, "rows": rows, "total_rows": len(rows)}


def _parse_yaml(file_path: str, encoding: str = "utf-8") -> Any:
    """读取YAML文件，返回纯数据 — 小沈 2026-05-04"""
    import yaml
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    with open(path, "r", encoding=encoding) as f:
        return yaml.safe_load(f)


def _write_yaml(file_path: str, data: Any, encoding: str = "utf-8", indent: int = 2) -> Dict[str, Any]:
    """写入YAML文件，返回纯dict — 小沈 2026-05-04"""
    import yaml
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding=encoding) as f:
        yaml.safe_dump(data, f, allow_unicode=True, indent=indent)
    return {"file_path": file_path}


def write_yaml_ordered(file_path: str, data: Any, encoding: str = "utf-8", indent: int = 2) -> Dict[str, Any]:
    """使用OrderedDict写入YAML — 小沈 2026-06-09"""
    import yaml
    from collections import OrderedDict
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    def _order(d):
        if not isinstance(d, dict):
            return d
        result = OrderedDict()
        if 'ai' in d:
            ai_data = d['ai']
            ai_ordered = OrderedDict()
            if 'provider' in ai_data:
                ai_ordered['provider'] = ai_data['provider']
            if 'model' in ai_data:
                ai_ordered['model'] = ai_data['model']
            for key in sorted(ai_data.keys()):
                if key not in ('provider', 'model'):
                    ai_ordered[key] = _order(ai_data[key]) if isinstance(ai_data[key], dict) else ai_data[key]
            result['ai'] = ai_ordered
        for key in sorted(d.keys()):
            if key != 'ai':
                result[key] = _order(d[key]) if isinstance(d[key], dict) else d[key]
        return result

    with open(path, "w", encoding=encoding) as f:
        yaml.dump(_order(data), f, allow_unicode=True, default_flow_style=False, indent=indent)
    return {"file_path": file_path}


def _parse_toml(file_path: str, encoding: str = "utf-8") -> Any:
    """读取TOML文件，返回纯数据 — 小沈 2026-05-04"""
    import tomli
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    with open(path, "rb") as f:
        return tomli.load(f)


def _write_toml(file_path: str, data: Dict[str, Any], encoding: str = "utf-8") -> Dict[str, Any]:
    """写入TOML文件，返回纯dict — 小沈 2026-05-04"""
    import tomli_w
    path = Path(file_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "wb") as f:
        tomli_w.dump(data, f)
    return {"file_path": file_path}


def _parse_ini(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取INI配置文件，返回纯dict — 小沈 2026-05-04"""
    import configparser
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
    config = configparser.ConfigParser()
    config.read(path, encoding=encoding)
    result = {}
    for section in config.sections():
        result[section] = dict(config[section])
    return result


def _parse_xml(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取XML文件，返回纯dict — 小沈 2026-05-04"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
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

    return {root.tag: elem_to_dict(root)}


def _parse_properties(file_path: str, encoding: str = "utf-8") -> Dict[str, Any]:
    """读取Java Properties文件，返回纯dict — 小沈 2026-05-04"""
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"文件不存在: {file_path}")
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
    return result


FORMAT_DISPATCH = {
    "json": {"read": _read_json, "write": _write_json},
    "yaml": {"read": _parse_yaml, "write": _write_yaml},
    "toml": {"read": _parse_toml, "write": _write_toml},
    "ini": {"read": _parse_ini},
    "xml": {"read": _parse_xml},
    "properties": {"read": _parse_properties},
    "csv": {"read": _read_csv_basic},
}


def backup_file(file_path: str, backup_dir: Optional[str] = None, suffix: str = ".bak") -> Dict[str, Any]:
    """备份文件，返回纯dict — 小沈 2026-05-02
    【注意】本函数返回纯dict，不含build3结构。
    """
    import shutil
    from app.utils.time_utils import timestamp_for_filename
    file_path = os.path.abspath(file_path)
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")
    timestamp = timestamp_for_filename()
    file_name = os.path.basename(file_path)
    backup_name = f"{file_name}{suffix}_{timestamp}"
    if backup_dir is None:
        backup_dir = os.path.dirname(file_path)
    else:
        backup_dir = os.path.abspath(backup_dir)
        os.makedirs(backup_dir, exist_ok=True)
    backup_path = os.path.join(backup_dir, backup_name)
    shutil.copy2(file_path, backup_path)
    return {
        "original_path": file_path,
        "backup_path": backup_path,
        "backup_size": os.path.getsize(backup_path),
    }


__all__ = [
    "_check_module",
    "_decode_bytes_safe",
    "_check_module_available",
    "_validate_code_safety",
    "_check_python_available",
    "_check_node_available",
    "_serialize_rows",
    "_load_dataframe",
    "parse_datetime_any",
    "parse_datetime_string",
    "is_holiday",
    "_is_solar_holiday",
    "_is_lunar_holiday",
    "calc_next_n_workday",
    "get_holiday_date_by_name",
    "resolve_timezone",
    "_check_shell_injection",
    "_read_stream_nonblocking",
    "check_db_exists",
    "validate_json_content",
    "validate_csv_content",
    "validate_xml_content",
    "validate_html_content",
    "validate_python_content",
    "_detect_encoding",
    "_detect_encoding_simple",
    "_read_json",
    "_write_json",
    "_read_csv_basic",
    "_parse_yaml",
    "_write_yaml",
    "write_yaml_ordered",
    "_parse_toml",
    "_write_toml",
    "_parse_ini",
    "_parse_xml",
    "_parse_properties",
    "FORMAT_DISPATCH",
    "backup_file",
    "SOLAR_HOLIDAYS",
    "SOLAR_HOLIDAY_NAMES",
    "LUNAR_HOLIDAYS",
    "LUNAR_HOLIDAY_NAMES",
    "HOLIDAY_ALIASES",
]