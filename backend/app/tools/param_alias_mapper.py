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
from app.logger import logger


PARAM_ALIASES = {
    # 路径参数统一为path后,旧规范名(file_path/dir_path/search_dir)降级为别名 — 小欧 2026-07-11
    "readtext": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
    },
    "writetext": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
    },
    "edittext": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
    },
    "readmedia": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
    },
    # 修正: 注册名为listdir(原写成list_directory,别名从未生效) — 小欧 2026-07-11
    "listdir": {
        "dir_path": "path",
        "dir": "path",
        "directory": "path",
        "folder": "path",
        "dirpath": "path",
    },
    "tree": {
        "dir_path": "path",
        "dir": "path",
        "directory": "path",
        "folder": "path",
        "dirpath": "path",
    },
    "find": {
        "search_dir": "path",
        "dir": "path",
        "directory": "path",
        "folder": "path",
        "search_path": "path",
    },
    "grep": {
        "dir": "path",
        "directory": "path",
        "folder": "path",
        "search_dir": "path",
        "search_path": "path",
    },
    # 路径参数统一为path/dest后,旧规范名(source/destination)及同义别名降级为别名 — 小欧 2026-07-12
    "compress": {
        "src": "path",
        "from": "path",
        "src_path": "path",
        "source_path": "path",
        "source": "path",
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "target": "dest",
        "output": "dest",
        "destination": "dest",
    },
    "extract": {
        "src": "path",
        "from": "path",
        "src_path": "path",
        "source_path": "path",
        "source": "path",
        "archive": "path",
        "archive_path": "path",
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "target": "dest",
        "output": "dest",
        "destination": "dest",
    },
    "move": {
        "src": "path",
        "from": "path",
        "src_path": "path",
        "source_path": "path",
        "source": "path",
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "target": "dest",
        "destination": "dest",
    },
    "copy": {
        "src": "path",
        "from": "path",
        "src_path": "path",
        "source_path": "path",
        "source": "path",
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "target": "dest",
        "destination": "dest",
    },
    "delete": {
        "file": "path",
        "filepath": "path",
        "file_path": "path",
        "target": "path",
        "source": "path",
    },
    "rename": {
        "src": "path",
        "from": "path",
        "src_path": "path",
        "source_path": "path",
        "source": "path",
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "new_name": "dest",
        "destination": "dest",
    },
    "shell": {
        "workdir": "cwd",
        "work_dir": "cwd",
        "working_directory": "cwd",
        "directory": "cwd",
    },
    "download": {
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
    "httpget": {
        "link": "url",
        "address": "url",
        "endpoint": "url",
    },
    "fetchpage": {
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
        "file_path": "data",
        "path": "data",
    },
    # 路径参数统一为path后,旧规范名(file_path)降级为别名 — 小欧 2026-07-11
    "analyze_data": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
    },
    "filter_data": {
        "file_path": "path",
        "filepath": "path",
        "file": "path",
        "filename": "path",
        "file_name": "path",
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


# 参数值别名:大众化旧枚举值→规范值 — 小欧 2026-07-11
# 仅当旧值是大众化术语(LLM训练里常见,会自然使用)才需要兼容;自造的旧值不必处理
PARAM_VALUE_ALIASES = {
    "grep": {
        # files_with_matches 是 grep/ripgrep 标准术语(-l/--files-with-matches),LLM常用
        "output_mode": {"files_with_matches": "only_files"},
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

    if tool_name not in PARAM_ALIASES and tool_name not in PARAM_VALUE_ALIASES:
        return params, False

    aliases = PARAM_ALIASES.get(tool_name, {})
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

    # 参数值别名映射(在名映射后、schema校验前) — 小欧 2026-07-11
    value_aliases = PARAM_VALUE_ALIASES.get(tool_name, {})
    if value_aliases:
        mapped_values = []
        for pname, vmap in value_aliases.items():
            if pname in normalized and normalized[pname] in vmap:
                old_v = normalized[pname]
                normalized[pname] = vmap[old_v]
                has_mapping = True
                mapped_values.append(f"{pname}:{old_v}→{vmap[old_v]}")
        if mapped_values:
            logger.info(
                f"[param_alias] {tool_name}: 参数值映射 {mapped_values}"
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
