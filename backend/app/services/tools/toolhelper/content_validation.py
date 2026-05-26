# -*- coding: utf-8 -*-
"""
内容格式验证函数模块

【创建时间】2026-05-25 小健
【用途】为file_tools.py提供内容格式验证功能

包含：
- validate_json_content: 验证JSON内容格式
- validate_csv_content: 验证CSV内容格式
- validate_xml_content: 验证XML内容格式
- validate_html_content: 验证HTML内容格式
- validate_python_content: 验证Python语法
"""

from typing import Optional


def validate_json_content(content: str) -> Optional[str]:
    """验证JSON内容格式 — 小健 2026-05-25

    使用场景:
        write_file写入.json文件前验证

    使用示例:
        error = validate_json_content('{"key": "value"}')
        if error:
            print(f"验证失败: {error}")

    返回数据说明:
        - 返回None表示验证通过
        - 返回str表示错误信息
    """
    import json
    try:
        json.loads(content)
        return None
    except json.JSONDecodeError as e:
        return f"JSON格式验证失败: 第{e.lineno}行第{e.colno}列 - {e.msg}"


def validate_csv_content(content: str, max_check_lines: int = 1000) -> Optional[str]:
    """验证CSV内容格式 — 小健 2026-05-25

    使用场景:
        write_file写入.csv文件前验证

    使用示例:
        error = validate_csv_content('name,age\nAlice,30\nBob,25')
        if error:
            print(f"验证失败: {error}")

    返回数据说明:
        - 返回None表示验证通过
        - 返回str表示错误信息
    """
    import csv
    from io import StringIO
    try:
        reader = csv.reader(StringIO(content))
        row_lengths = []
        for i, row in enumerate(reader):
            if i > max_check_lines:
                break
            if row:
                row_lengths.append(len(row))
        if row_lengths and len(set(row_lengths)) > 1:
            return f"CSV格式警告: 列数不一致(发现{set(row_lengths)}种列数)，写入可能导致数据错位"
        return None
    except Exception as e:
        return f"CSV格式验证失败: {str(e)[:100]}"


def validate_xml_content(content: str) -> Optional[str]:
    """验证XML内容格式 — 小健 2026-05-25

    使用场景:
        write_file写入.xml文件前验证

    使用示例:
        error = validate_xml_content('<root><item>test</item></root>')
        if error:
            print(f"验证失败: {error}")

    返回数据说明:
        - 返回None表示验证通过
        - 返回str表示错误信息
    """
    import xml.etree.ElementTree as ET
    try:
        ET.fromstring(content)
        return None
    except ET.ParseError as e:
        return f"XML格式验证失败: {str(e)[:100]}"


def validate_html_content(content: str) -> Optional[str]:
    """验证HTML内容格式 — 小健 2026-05-25

    使用场景:
        write_file写入.html/.htm文件前验证

    使用示例:
        error = validate_html_content('<html><body>test</body></html>')
        if error:
            print(f"验证失败: {error}")

    返回数据说明:
        - 返回None表示验证通过
        - 返回str表示错误信息
    """
    open_tags = content.count('<')
    close_tags = content.count('>')
    if open_tags != close_tags:
        return f"HTML标记验证警告: '<'({open_tags}个)与'>'({close_tags}个)数量不匹配"
    return None


def validate_python_content(content: str, file_path: Optional[str] = None) -> Optional[str]:
    """验证Python语法 — 小健 2026-05-25

    使用场景:
        write_file写入.py文件前验证

    使用示例:
        error = validate_python_content('print("hello")', 'test.py')
        if error:
            print(f"验证失败: {error}")

    返回数据说明:
        - 返回None表示验证通过
        - 返回str表示错误信息
    """
    try:
        compile(content, file_path or '<string>', 'exec')
        return None
    except SyntaxError as e:
        error_msg = f"Python语法验证失败: 第{e.lineno}行 - {e.msg}"
        if "unterminated string literal" in e.msg:
            error_msg += "；建议：转义字符串请使用raw string r'...'，如 r'\\\\' 代替 '\\\\'"
        elif "invalid character" in e.msg:
            error_msg += "；建议：Python不支持全角标点，请使用半角括号()、逗号,、冒号:、分号;"
        elif "invalid escape sequence" in e.msg:
            error_msg += "；建议：请在字符串前加r前缀使用raw string，或将转义字符双写如 \\\\d → r'\\d'"
        return error_msg
