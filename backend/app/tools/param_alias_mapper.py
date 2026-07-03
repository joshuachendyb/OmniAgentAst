# -*- coding: utf-8 -*-
"""
参数名别名映射 - 解决LLM返回参数名不匹配问题

小欧 2026-06-27

设计原则：
1. 对LLM友好：容错性强，不因参数名错误而失败
2. 对开发者透明：映射逻辑在工具执行前处理
3. 易于维护：别名映射表集中管理
4. 可扩展：支持添加新的别名映射
5. 有日志记录：记录映射情况，便于监控LLM行为
"""

from typing import Dict, Any, Tuple
from app.utils.logger import logger


PARAM_ALIASES = {
    "read_text_file": {
        "path": "file_path",
        "filepath": "file_path",
        "file": "file_path",
        "filename": "file_path",
        "file_name": "file_path",
    },
    "write_text_file": {
        "path": "file_path",
        "filepath": "file_path",
        "file": "file_path",
        "filename": "file_path",
        "file_name": "file_path",
    },
    "edit_text_file": {
        "path": "file_path",
        "filepath": "file_path",
        "file": "file_path",
        "filename": "file_path",
        "file_name": "file_path",
    },
    "read_media_file": {
        "path": "file_path",
        "filepath": "file_path",
        "file": "file_path",
        "filename": "file_path",
        "file_name": "file_path",
    },
    "list_directory": {
        "path": "dir_path",
        "dir": "dir_path",
        "directory": "dir_path",
        "folder": "dir_path",
        "dirpath": "dir_path",
    },
    "search_files": {
        "dir": "search_dir",
        "path": "search_dir",
        "directory": "search_dir",
        "folder": "search_dir",
        "search_path": "search_dir",
    },
    "grep_file_content": {
        "dir": "search_dir",
        "path": "search_dir",
        "directory": "search_dir",
        "folder": "search_dir",
        "search_path": "search_dir",
    },
    "compress_files": {
        "src": "source",
        "from": "source",
        "src_path": "source",
        "source_path": "source",
        "dst": "destination",
        "to": "destination",
        "dst_path": "destination",
        "target": "destination",
        "output": "destination",
    },
    "extract_archive": {
        "src": "source",
        "from": "source",
        "src_path": "source",
        "archive": "source",
        "archive_path": "source",
        "dst": "destination",
        "to": "destination",
        "dst_path": "destination",
        "target": "destination",
        "output": "destination",
    },
    "move_file": {
        "src": "source",
        "from": "source",
        "src_path": "source",
        "source_path": "source",
        "dst": "destination",
        "to": "destination",
        "dst_path": "destination",
        "target": "destination",
    },
    "copy_file": {
        "src": "source",
        "from": "source",
        "src_path": "source",
        "source_path": "source",
        "dst": "destination",
        "to": "destination",
        "dst_path": "destination",
        "target": "destination",
    },
    "delete_file": {
        "path": "source",
        "file": "source",
        "filepath": "source",
        "file_path": "source",
        "target": "source",
    },
    "rename_file": {
        "src": "source",
        "from": "source",
        "src_path": "source",
        "source_path": "source",
        "dst": "destination",
        "to": "destination",
        "dst_path": "destination",
        "new_name": "destination",
    },
    "shell": {
        "workdir": "cwd",
        "work_dir": "cwd",
        "working_directory": "cwd",
        "directory": "cwd",
    },
    "runcode": {
        "workdir": "working_dir",
        "work_dir": "working_dir",
        "working_directory": "working_dir",
        "directory": "working_dir",
        "cwd": "working_dir",
    },
    "download_file": {
        "dst": "destination_path",
        "to": "destination_path",
        "dst_path": "destination_path",
        "target": "destination_path",
        "output": "destination_path",
        "output_path": "destination_path",
    },
    "screen_capture": {
        "output": "output_path",
        "output_file": "output_path",
        "file": "output_path",
        "filepath": "output_path",
        "target": "output_path",
    },
    "read_pdf": {
        "path": "file_name",
        "filepath": "file_name",
        "file": "file_name",
        "file_path": "file_name",
    },
    "read_docx": {
        "path": "file_name",
        "filepath": "file_name",
        "file": "file_name",
        "file_path": "file_name",
    },
    "read_pptx": {
        "path": "file_name",
        "filepath": "file_name",
        "file": "file_name",
        "file_path": "file_name",
    },
    "read_xlsx": {
        "path": "file_name",
        "filepath": "file_name",
        "file": "file_name",
        "file_path": "file_name",
    },
    "write_docx": {
        "path": "file_name",
        "filepath": "file_name",
        "file": "file_name",
        "file_path": "file_name",
    },
    "write_xlsx": {
        "path": "file_name",
        "filepath": "file_name",
        "file": "file_name",
        "file_path": "file_name",
    },
    "write_pdf": {
        "path": "file_name",
        "filepath": "file_name",
        "file": "file_name",
        "file_path": "file_name",
    },
    "write_pptx": {
        "path": "file_name",
        "filepath": "file_name",
        "file": "file_name",
        "file_path": "file_name",
    },
    "http_request": {
        "link": "url",
        "address": "url",
        "endpoint": "url",
    },
    "fetch_webpage": {
        "link": "url",
        "address": "url",
        "endpoint": "url",
    },
    "create_task": {
        "program": "command",
        "path": "command",
        "executable": "command",
    },
    "generate_chart": {
        "output": "output_path",
        "output_file": "output_path",
        "file": "output_path",
        "filepath": "output_path",
        "target": "output_path",
        "data": "file_path",
        "path": "file_path",
    },
    "analyze_data": {
        "path": "file_path",
        "filepath": "file_path",
        "file": "file_path",
        "filename": "file_path",
        "file_name": "file_path",
    },
    "filter_data": {
        "path": "file_path",
        "filepath": "file_path",
        "file": "file_path",
        "filename": "file_path",
        "file_name": "file_path",
    },
    "query_sql": {
        "path": "db_path",
        "dbpath": "db_path",
        "database": "db_path",
        "database_path": "db_path",
    },
    "execute_sql": {
        "path": "db_path",
        "dbpath": "db_path",
        "database": "db_path",
        "database_path": "db_path",
    },
    "get_db_schema": {
        "path": "db_path",
        "dbpath": "db_path",
        "database": "db_path",
        "database_path": "db_path",
    },
    "registry_read": {
        "path": "key_path",
        "keypath": "key_path",
        "key": "key_path",
        "registry_path": "key_path",
    },
    "registry_write": {
        "path": "key_path",
        "keypath": "key_path",
        "key": "key_path",
        "registry_path": "key_path",
    },
    "registry_delete": {
        "path": "key_path",
        "keypath": "key_path",
        "key": "key_path",
        "registry_path": "key_path",
    },
}


def normalize_params(tool_name: str, params: Dict[str, Any]) -> Tuple[Dict[str, Any], bool]:
    """
    规范化参数名 - 将LLM返回的参数名映射为Schema要求的参数名

    Args:
        tool_name: 工具名称
        params: LLM返回的参数字典

    Returns:
        (normalized_params, has_mapping)
        - normalized_params: 规范化后的参数字典
        - has_mapping: 是否发生了映射
    """
    if not params:
        return params, False

    if tool_name not in PARAM_ALIASES:
        return params, False

    aliases = PARAM_ALIASES[tool_name]
    normalized = {}
    has_mapping = False
    mapped_keys = []

    for key, value in params.items():
        if key in aliases:
            normalized_key = aliases[key]
            if normalized_key in params and normalized_key != key:
                logger.debug(
                    f"[param_alias] {tool_name}: 参数 '{key}' 被忽略，"
                    f"因为规范名称 '{normalized_key}' 已存在"
                )
                continue

            normalized[normalized_key] = value
            has_mapping = True
            mapped_keys.append(f"{key}→{normalized_key}")
        else:
            normalized[key] = value

    if has_mapping:
        logger.info(
            f"[param_alias] {tool_name}: 参数名映射 {mapped_keys}"
        )

    return normalized, has_mapping


def get_param_aliases(tool_name: str) -> Dict[str, str]:
    """获取工具的参数别名映射"""
    return PARAM_ALIASES.get(tool_name, {})


def add_param_alias(tool_name: str, alias: str, canonical: str) -> None:
    """
    添加参数别名

    Args:
        tool_name: 工具名称
        alias: 别名（LLM可能返回的名称）
        canonical: 规范名称（Schema要求的名称）
    """
    if tool_name not in PARAM_ALIASES:
        PARAM_ALIASES[tool_name] = {}
    PARAM_ALIASES[tool_name][alias] = canonical
    logger.info(f"[param_alias] 添加别名: {tool_name}.{alias} → {canonical}")


def get_all_aliases() -> Dict[str, Dict[str, str]]:
    """获取所有工具的参数别名映射"""
    return PARAM_ALIASES.copy()
