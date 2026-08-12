# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-21 - 小欧 - query_sql limit: schema暴露limit字段给LLM, 加范围校验
# 2026-07-21 - 小欧 - Bug修: 删_format_table死代码; 多条SQL; 查询超时; if limit→is not None; 增量fetch
# 2026-07-21 - 小欧 - Bug修: logger加到关键路径; str(sql)防非字符串; timeout→is not None; truncated标记; MySQL/PG增量fetch+超时已知限制
# 2026-07-21 - 小欧 - 复核修复(Bug1-5): DRY重复truncated_reason→公共; connection_type/path改回if x:防空值; 先判断后append防截断误报
# 2026-07-21 - 小欧 - 入参即信任: 内部 limit 校验上界 OBS_MAX_DISPLAY_ITEMS→1000（同步 schema le=1000）
# 2026-07-24 - 小欧 - 修复: WITH绕过只读检测(括号深度扫描CTE防WITH...UPDATE) + columns[:5]提取OBS常量
# 2026-07-25 - 小欧 - 截断治理: str(sql)[:50](5处logger) → QUERY_SQL_INER_LOG_SQL 命名常量
# 2026-07-26 - 小欧 - 迁移: sql_error_hint/hint_for_data_error导入从tool_constants改为file_path_checker(配合函数迁移)
# 2026-07-31 - 小欧 - CRITICAL: WITH CTE体绕过只读检测修复。原代码跳过CTE括号体仅检查外层SELECT, 导致 `WITH malicious AS (DELETE FROM users) SELECT * FROM malicious` 通过检测。补充CTE体内容的DML/DDL关键字扫描 | py_compile ✓
# 2026-07-31 - 小欧 - 只读安全增强(Bug②/⑤/⑲): PRAGMA写操作检测(赋值=或非只读白名单拒绝); 检测前剥离注释与字符串字面量(修复"-- SELECT"前导注释误拒、'a;b'字符串分号误判、SET note='WHERE'漏判); timeout None/<=0 防御
# 2026-08-13 - 小欧 - A5职责拆分: hint_* 错误提示函数/导入源改 app.tools.toolhelper.error_hints
"""
query_sql — 执行只读SQL查询
【2026-06-22 小健】从 database_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import re  # 2026-07-31 小欧: CTE体写操作检测
import sqlite3
import threading
import time as _time_mod
from typing import Any, Dict, Optional, Literal  # 2026-07-31 小欧: 移除未使用 Union, List

from app.logger import logger
from app.tools.tool_response import build_success, build_error
from app.tools.tool_constants import ERR_SQL_EXEC, QUERY_SQL_OUTPARM_LIMIT_SQL, OBS_QUERY_SQL_PREVIEW_COLUMNS, QUERY_SQL_INER_LOG_SQL  # 2026-07-31 小欧: 移除未使用 OBS_MAX_DISPLAY_ITEMS
from app.tools.toolhelper.error_hints import sql_error_hint, hint_for_data_error
from app.tools.tool_fc_helper import _get_connection, _close_connection, _strip_sql_comments_and_strings  # 2026-07-31 小欧: Bug②⑤注释/字符串剥离修复引入


# 2026-07-31 小欧: Bug② PRAGMA只读白名单 — 仅放行纯只读PRAGMA, 其余(含赋值=形式)一律拒绝, 防 user_version/journal_mode 等写操作借PRAGMA白名单执行
_READONLY_PRAGMAS = {
    "table_info", "table_xinfo", "table_list", "index_list", "index_info", "index_xinfo",
    "foreign_key_list", "foreign_key_check", "integrity_check", "quick_check",
    "compile_options", "database_list", "collation_list", "freelist_count", "page_count",
    "function_list", "module_list", "pragma_list", "schema_version", "user_version",
    "application_id",
}


def _is_write_pragma(sql: str) -> bool:
    """判断PRAGMA语句是否为写操作 — 小欧 2026-07-31 Bug②修复
       规则: 含=赋值 或 名称不在只读白名单 → 判定为写操作拒绝
    """
    clean = _strip_sql_comments_and_strings(sql)
    upper = clean.strip().upper()
    m = re.match(r'PRAGMA\s+([a-zA-Z_][a-zA-Z0-9_]*)', upper)
    if not m:
        return True
    name = m.group(1).lower()
    if '=' in upper:
        return True
    return name not in _READONLY_PRAGMAS


def _build_query_sql_llm_data(exec_code, duration_ms, sql, row_count, columns, detail="", hint="",
                               connection_type="", path="", limit=0, timeout=0,
                               truncated=False, truncated_reason=""):
    """query_sql的llm_data构建函数 — 小健 2026-06-22 — 小沈 2026-07-05 新增detail/hint参数 — 小欧 2026-07-05 新增user_params — 小欧 2026-07-24 主函数入口统一截断，build函数不再截断"""
    _act_params = {"sql": sql}
    if connection_type:
        _act_params["connection_type"] = connection_type
    if path:
        _act_params["path"] = path
    if limit is not None:
        _act_params["limit"] = limit
    if timeout is not None:
        _act_params["timeout"] = timeout
    _target = path or connection_type or "database"
    if exec_code == "error":
        return {
            "summary": f"查询{_target}，失败: {detail}",
            "action": {"tool": "query_sql", "tool_zh": "查询", "target": sql, "params": _act_params},
            "status": {"exec_code": "error", "message": detail if detail else "查询失败", "code": ERR_SQL_EXEC, "detail": detail, "hint": hint if hint else "请检查SQL语法"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    _preview_cols = columns[:OBS_QUERY_SQL_PREVIEW_COLUMNS]
    col_text = ", ".join(_preview_cols)
    if len(columns) > OBS_QUERY_SQL_PREVIEW_COLUMNS:
        col_text += "..."
    return {
        "summary": f"查询{_target}，成功: {row_count}行, 列: {col_text}",
        "action": {"tool": "query_sql", "tool_zh": "查询", "target": sql, "params": _act_params},
        "status": {"exec_code": "success", "message": "查询成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"row_count": {"value": row_count, "text": f"{row_count}行"}, "columns": {"value": _preview_cols, "text": f"列: {col_text}"}},
        "truncated": truncated,
        "truncated_reason": truncated_reason,
    }


def query_sql(sql: str, connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
              connection_string: Optional[str] = None, path: Optional[str] = None,
              limit: int = 50, timeout: int = 15000) -> Dict[str, Any]:
    """执行只读SQL查询 — 小健 2026-06-22 拆分独立文件
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    conn = None
    engine = None
    t0 = _time_mod.perf_counter()

    if not isinstance(sql, str) or not sql.strip():
        duration_ms = 0
        llm_data = _build_query_sql_llm_data("error", duration_ms, sql or "", 0, [], detail="SQL语句不能为空", hint="请提供有效的SQL语句",
                                               connection_type=connection_type, path=path, limit=limit, timeout=timeout)
        return build_error(data={}, llm_data=llm_data)

    # 2026-07-31 小欧: 修复 limit=None 缺护前 crash(TypeError)。Schema允许Optional[int]=None, 但实现未做None保护
    if limit is None:
        limit = 50
    if limit < 1 or limit > 1000:
        duration_ms = 0
        llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [],
                                               detail=f"limit必须在1~1000之间",
                                               hint=f"请设置1到1000之间的limit值",
                                               connection_type=connection_type, path=path, limit=limit, timeout=timeout)
        return build_error(data={}, llm_data=llm_data)

    # 2026-07-31 小欧: Bug⑲ timeout防御 — None回默认, <=0拒绝(防 threading.Timer(0) 立即触发 conn.interrupt)
    if timeout is None:
        timeout = 15000
    if timeout <= 0:
        duration_ms = 0
        llm_data = _build_query_sql_llm_data("error", duration_ms, sql, 0, [],
                                               detail=f"timeout必须大于0(单位毫秒)",
                                               hint=f"请设置正数timeout,建议15000",
                                               connection_type=connection_type, path=path, limit=limit, timeout=timeout)
        return build_error(data={}, llm_data=llm_data)

    _sql_preview = sql[:QUERY_SQL_OUTPARM_LIMIT_SQL]

    try:
        clean_sql = _strip_sql_comments_and_strings(sql)  # 2026-07-31 小欧: Bug⑤ 剥离注释/字符串字面量后再做只读检测
        sql_upper = clean_sql.strip().upper()
        if sql_upper.startswith("WITH"):
            _rest = sql_upper[4:].strip()
            if _rest.startswith("RECURSIVE"):
                _rest = _rest[9:].strip()
            _i = 0
            while _i < len(_rest):
                while _i < len(_rest) and _rest[_i] in ' ,\t\r\n':
                    _i += 1
                if _i >= len(_rest):
                    break
                _start = _i
                while _i < len(_rest) and (_rest[_i].isalpha() or _rest[_i].isdigit() or _rest[_i] == '_'):
                    _i += 1
                _word = _rest[_start:_i]
                while _i < len(_rest) and _rest[_i] in ' \t\r\n':
                    _i += 1
                if _i + 2 <= len(_rest) and _rest[_i:_i+2].upper() == 'AS' and (_i + 2 >= len(_rest) or not _rest[_i + 2].isalpha()):
                    _i += 2
                    while _i < len(_rest) and _rest[_i] in ' \t\r\n':
                        _i += 1
                    if _i < len(_rest) and _rest[_i] == '(':
                        _depth = 1
                        _body_start = _i + 1
                        _i += 1
                        while _i < len(_rest) and _depth > 0:
                            if _rest[_i] == '(':
                                _depth += 1
                            elif _rest[_i] == ')':
                                _depth -= 1
                            _i += 1
                        _cte_body = _rest[_body_start:_i-1]  # 2026-07-31 小欧: 捕获CTE体内容(括号内)
                        # 检查CTE体内是否含写操作 — 小欧 2026-07-31
                        if re.search(r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b', _cte_body):
                            _cte_danger = re.search(r'\b(INSERT|UPDATE|DELETE|DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b', _cte_body).group(1)
                            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                            logger.warning("query_sql WITH CTE体含写操作: keyword=%s, sql=%s", _cte_danger, str(sql)[:QUERY_SQL_INER_LOG_SQL])
                            llm_data = _build_query_sql_llm_data("error", duration_ms, _sql_preview, 0, [], detail=f"只读查询不支持WITH CTE体含写操作({_cte_danger})", hint="如需写操作请使用execute_sql工具",
                                                                   connection_type=connection_type, path=path, limit=limit, timeout=timeout)
                            return build_error(data={}, llm_data=llm_data)
                        continue
                if _word not in ("SELECT", "SHOW", "DESCRIBE", "PRAGMA", "EXPLAIN"):
                    attempted_type = _word
                    duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                    logger.warning("query_sql WITH后含写操作: attempted_type=%s, sql=%s", attempted_type, str(sql)[:QUERY_SQL_INER_LOG_SQL])
                    llm_data = _build_query_sql_llm_data("error", duration_ms, _sql_preview, 0, [], detail=f"只读查询不支持WITH+{attempted_type}操作", hint="如需写操作请使用execute_sql工具",
                                                           connection_type=connection_type, path=path, limit=limit, timeout=timeout)
                    return build_error(data={}, llm_data=llm_data)
                break
        elif not sql_upper.startswith(("SELECT", "SHOW", "DESCRIBE", "PRAGMA", "EXPLAIN")):
            attempted_type = clean_sql.split()[0].upper() if clean_sql.strip() else "未知"
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            logger.warning("query_sql非只读语句: attempted_type=%s, sql=%s", attempted_type, str(sql)[:QUERY_SQL_INER_LOG_SQL])
            llm_data = _build_query_sql_llm_data("error", duration_ms, _sql_preview, 0, [], detail=f"只读查询不支持{attempted_type}操作", hint="如需写操作请使用execute_sql工具",
                                                   connection_type=connection_type, path=path, limit=limit, timeout=timeout)
            return build_error(data={}, llm_data=llm_data)

        # 2026-07-31 小欧: Bug② PRAGMA写操作检测 — 赋值=或非只读白名单一律拒绝, 防 user_version/journal_mode 等写操作借白名单执行
        if sql_upper.startswith("PRAGMA") and _is_write_pragma(clean_sql):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            logger.warning("query_sql PRAGMA写操作: sql=%s", str(sql)[:QUERY_SQL_INER_LOG_SQL])
            llm_data = _build_query_sql_llm_data("error", duration_ms, _sql_preview, 0, [], detail="只读查询不支持写操作PRAGMA(赋值或非只读PRAGMA)", hint="如需修改数据库设置请使用execute_sql工具",
                                                   connection_type=connection_type, path=path, limit=limit, timeout=timeout)
            return build_error(data={}, llm_data=llm_data)

        if ';' in clean_sql.strip().rstrip(';'):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            logger.warning("query_sql多条语句: sql=%s", str(sql)[:QUERY_SQL_INER_LOG_SQL])
            llm_data = _build_query_sql_llm_data("error", duration_ms, _sql_preview, 0, [], detail="不支持多条SQL语句，请只传一条SELECT语句", hint="一次只能执行一条SELECT语句，多条请多次调用query_sql",
                                                   connection_type=connection_type, path=path, limit=limit, timeout=timeout)
            return build_error(data={}, llm_data=llm_data)

        conn, engine, conn_error = _get_connection(connection_type, connection_string, path, timeout)
        if conn is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            logger.warning("query_sql连接失败: error=%s, connection_type=%s", conn_error, connection_type)
            llm_data = _build_query_sql_llm_data("error", duration_ms, _sql_preview, 0, [], detail=conn_error, hint="请检查数据库连接参数",
                                                   connection_type=connection_type, path=path, limit=limit, timeout=timeout)
            return build_error(data={}, llm_data=llm_data)

        results = []
        truncated = False
        truncated_reason = ""
        if connection_type in ("mysql", "postgresql"):
            # 【已知限制】MySQL/PostgreSQL查询超时 — KISS原则，记录为已知限制
            # MySQL: 需要KILL QUERY <process_id>，需额外连接，复杂度高
            # PostgreSQL: 需要pg_cancel_backend(<pid>)，需superuser权限
            # 当前仅SQLite支持conn.interrupt()中断查询
            from sqlalchemy import text
            engine = conn.engine
            result = conn.execute(text(sql))
            columns = list(result.keys()) if hasattr(result, 'keys') else []
            for row in result:
                if len(results) >= limit:
                    truncated = True
                    break
                results.append(dict(zip(columns, row)))
        else:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            _timer = threading.Timer(timeout / 1000, conn.interrupt)
            _timer.start()
            try:
                cursor.execute(sql)
                columns = [desc[0] for desc in cursor.description] if cursor.description else []
                for row in cursor:
                    if len(results) >= limit:
                        truncated = True
                        break
                    results.append(dict(row))
            finally:
                _timer.cancel()
        if truncated:
            truncated_reason = f"已截断：结果超过{limit}行限制，仅返回前{limit}行"

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        logger.info("query_sql执行完成: rows=%d, truncated=%s, duration=%dms, connection_type=%s",
                     len(results), truncated, duration_ms, connection_type)
        data = {"columns": columns, "rows": results, "truncated": truncated, "truncated_reason": truncated_reason}
        llm_data = _build_query_sql_llm_data("success", duration_ms, _sql_preview, len(results), columns,
                                               connection_type=connection_type, path=path, limit=limit, timeout=timeout,
                                               truncated=truncated, truncated_reason=truncated_reason)
        # =============================================================================
        # 数据设计：total 从 data 移除，行数通过 llm_data.metrics（key:row_count）传入 summary
        # summary 示例: "查询返回10行, 列: id, name"
        # — 小欧 2026-07-06 18:46:13
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #5 rows
        # trigger: "rows" in data — rows 是 List[list|dict]
        # handler: _format_rows(data["rows"], data.get("columns"))
        # file:    observation_formatter.py:140-142
        # ------------------------------------------------------------------------------
        return build_success(data=data, llm_data=llm_data)

    except sqlite3.Error as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        logger.warning("query_sql SQLite异常: error=%s, sql=%s", str(e), str(sql)[:QUERY_SQL_INER_LOG_SQL])
        llm_data = _build_query_sql_llm_data("error", duration_ms, _sql_preview, 0, [], detail=str(e), hint=sql_error_hint(e),
                                               connection_type=connection_type, path=path, limit=limit, timeout=timeout)
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        logger.error("query_sql异常: error=%s, sql=%s", str(e), str(sql)[:QUERY_SQL_INER_LOG_SQL])
        llm_data = _build_query_sql_llm_data("error", duration_ms, _sql_preview, 0, [], detail=str(e), hint=hint_for_data_error(e),
                                               connection_type=connection_type, path=path, limit=limit, timeout=timeout)
        return build_error(data={}, llm_data=llm_data)
    finally:
        _close_connection(conn, engine)


__all__ = ["query_sql"]
