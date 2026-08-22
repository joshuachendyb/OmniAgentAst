# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-07 - 小欧 - 文件由 param_alias_mapper.py 重命名为 tools_alias_mapper.py(名实相符: 既有工具名别名也有参数别名); import处同步更新(registry/tool_retry_engine/action_handler/test)
# 2026-07-20 - 小欧 - 删 output_mode 参数别名映射: grep 已去除 output_mode 参数(默认即 content 模式), 该别名失效, 删除死映射避免误导
# 2026-07-28 - 小欧 - BUG#19: "value":"value"是恒等映射(输入=输出无转换), 空转别名删除
# 2026-08-07 - 小欧 - 新增TOOL_NAME_ALIASES工具名别名映射+normalize_tool_name: LLM常生成变体名(write_text等), 映射到注册名(writetext), 防"工具未注册"误拦截(com-test 03暴露)
# 2026-08-09 - 小欧 - write_xlsx 参数别名 append→append_mode: LLM 常按布尔语义传 append, 实际实现/SCHEMA参数为 append_mode(2026-08-07 P04优化), 无映射会因未知参数被忽略导致追加失效
# 2026-08-09 - 小欧 - TOOL_NAME_ALIASES 新增 writefile/readfile 幻觉名→writetext/readtext: sensenova-flash-lite 将写/读文本工具幻觉为 writefile, 因未注册被安全检查拦截(工具未注册)致 P5-07 任务空转防循环失败; get_tool 归一化后走注册名正常执行, execute_tools 内扩展名纠正再兜底
# 2026-08-09 - 小欧 - TOOL_NAME_ALIASES 新增 writeetext/readetext/editetext(多一个e的拼写幻觉)→writetext/readtext/edittext: sensenova-flash-lite 将 writetext 幻觉为 writeetext, 因未注册被拦截致 COM-08 任务尾部空转防循环失败(与 writefile 同源, 拼写变异变体)
# 2026-08-22 - 小欧 - TOOL_NAME_ALIASES 新增裸名 write/read/edit→writetext/readtext/edittext: COM-05b 实证 LLM 三轮幻觉调用裸名"write"(最自然通用名), 因不在别名表被拦截, 同名 blocked 达3次触发防死循环熔断致任务 FAILED; 归一化后若扩展名为 .docx/.pdf 等仍由 execute_tools 扩展名预检二次路由, 无歧义风险
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
    # 路径参数统一: download 目标参数 destination_path→dest — 小欧 2026-07-12
    "download": {
        "dst": "dest",
        "to": "dest",
        "dst_path": "dest",
        "target": "dest",
        "output": "dest",
        "output_path": "dest",
        "destination_path": "dest",
    },
    # 路径参数统一: screen_capture 输出参数 output_path→dest — 小欧 2026-07-12
    "screen_capture": {
        "output": "dest",
        "output_file": "dest",
        "file": "dest",
        "filepath": "dest",
        "target": "dest",
        "path": "dest",
        "output_path": "dest",
    },
    # 路径参数统一: document 8工具文件参数 file_name→path — 小欧 2026-07-12
    "read_pdf": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "read_docx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "read_pptx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "read_xlsx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "write_docx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "write_xlsx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
        "append": "append_mode",  # LLM 常传 append(布尔), 实际参数为 append_mode — 小欧 2026-08-09
    },
    "write_pdf": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
    },
    "write_pptx": {
        "file_name": "path",
        "filepath": "path",
        "file": "path",
        "file_path": "path",
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
    # 路径参数统一: generate_chart 输出参数 output_path→dest(path→data保留) — 小欧 2026-07-12
    "generate_chart": {
        "output": "dest",
        "output_file": "dest",
        "file": "dest",
        "filepath": "dest",
        "target": "dest",
        "output_path": "dest",
        "path": "data",
        "file_path": "data",
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
    # 路径参数统一: query_sql 数据库路径参数 db_path→path — 小欧 2026-07-12
    "query_sql": {
        "db_path": "path",
        "dbpath": "path",
        "database": "path",
        "database_path": "path",
    },
    # 路径参数统一: execute_sql 数据库路径参数 db_path→path — 小欧 2026-07-12
    "execute_sql": {
        "db_path": "path",
        "dbpath": "path",
        "database": "path",
        "database_path": "path",
    },
    # 路径参数统一: get_db_schema 数据库路径参数 db_path→path — 小欧 2026-07-12
    "get_db_schema": {
        "db_path": "path",
        "dbpath": "path",
        "database": "path",
        "database_path": "path",
    },
    # 路径参数统一: registry_read 键路径参数 key_path→path — 小欧 2026-07-12
    "registry_read": {
        "registry_key": "path",
        "reg_key": "path",
        "regpath": "path",
        "key_path": "path",
        "key": "path",
        "keypath": "path",
        "registry_path": "path",
    },
    # 路径参数统一: registry_write 键路径参数 key_path→path — 小欧 2026-07-12
    "registry_write": {
        "registry_key": "path",
        "reg_key": "path",
        "regpath": "path",
        "key_path": "path",
        "key": "path",
        "data": "value",
    },
    # 路径参数统一: registry_delete 键路径参数 key_path→path — 小欧 2026-07-12
    "registry_delete": {
        "registry_key": "path",
        "reg_key": "path",
        "regpath": "path",
        "key_path": "path",
        "key": "path",
    },
}


# 参数值别名:大众化旧枚举值→规范值 — 小欧 2026-07-11
# 仅当旧值是大众化术语(LLM训练里常见,会自然使用)才需要兼容;自造的旧值不必处理
PARAM_VALUE_ALIASES = {
    "grep": {},
}


# 工具名别名: LLM生成的自然语言变体→注册名 — 小欧 2026-08-07
# 实测: com-test 03中LLM调用"write_text"(带下划线)被系统以"工具未注册"误拦截3次致任务失败。
# 与 PARAM_ALIASES 同款集中映射模式, 只收录实际发生+对称高频变体(YAGNI)。
TOOL_NAME_ALIASES = {
    "write_text": "writetext",
    "read_text": "readtext",
    "edit_text": "edittext",
    "write_text_file": "writetext",
    "read_text_file": "readtext",
    "edit_text_file": "edittext",
    "writefile": "writetext",
    "readfile": "readtext",
    "write": "writetext",
    "read": "readtext",
    "edit": "edittext",
    "writeetext": "writetext",
    "readetext": "readtext",
    "editetext": "edittext",
    "list_directory": "listdir",
    "http_get": "httpget",
    "http_request": "httpget",
}


def normalize_tool_name(tool_name: str) -> str:
    """工具名别名归一化: LLM生成的变体名→注册名 — 小欧 2026-08-07

    与 normalize_params 同模式: 集中映射表 + 日志记录, 便于监控LLM行为。
    无别名命中时原样返回(不改变原工具名语义)。
    """
    if tool_name in TOOL_NAME_ALIASES:
        _canonical = TOOL_NAME_ALIASES[tool_name]
        logger.info(f"[tool_name_alias] {tool_name}→{_canonical}")
        return _canonical
    return tool_name


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
