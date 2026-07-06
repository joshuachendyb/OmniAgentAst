# -*- coding: utf-8 -*-
"""
execute_sql — 执行写操作SQL
【2026-06-22 小健】从 database_tools.py 拆分为独立文件
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import re
import sqlite3
import time as _time_mod
from typing import Any, Dict, List, Optional, Union, Literal, Tuple

from app.utils.logger import logger
from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import ERR_SQL_EXEC
from app.tools.tool_fc_helper import _get_connection, _close_connection


def _check_sql_safety(sql: str, dry_run: bool) -> Tuple[bool, Optional[str], Optional[List[str]]]:
    """统一危险模式检测 + 无WHERE检测 + 拦截决策 — 小沈 2026-05-25"""
    sql_upper = sql.strip().upper()
    DANGEROUS_PATTERN = re.compile(r'\b(DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b', re.IGNORECASE)
    dangerous_matches = DANGEROUS_PATTERN.findall(sql)
    if re.match(r'\s*(DELETE|UPDATE)\s', sql_upper) and 'WHERE' not in sql_upper:
        dangerous_matches.append('NO_WHERE')
    if dangerous_matches:
        warnings = []
        dangerous_to_show = [d for d in dangerous_matches if d != 'NO_WHERE']
        if dangerous_to_show:
            warnings.append(f"危险操作: {dangerous_to_show}")
        if 'NO_WHERE' in dangerous_matches:
            warnings.append("缺少 WHERE 条件")
        return True, f"警告:检测到危险操作 {'+'.join(warnings)},已拦截执行。可使用dry_run=true预演", dangerous_matches
    return False, None, None


def _build_execute_sql_llm_data(exec_code, duration_ms, sql, affected_rows, detail="", hint="",
                                 connection_type="", db_path="", dry_run=False, timeout=0):
    """execute_sql的llm_data构建函数 — 小健 2026-06-22 — 小沈 2026-07-05 新增detail/hint参数 — 小欧 2026-07-05 新增user_params — 小欧 2026-07-06 sql截断200→50 统一"""
    _act_params = {"sql": sql[:50]}  # 小欧 2026-07-06 200→50 统一截断
    if connection_type:
        _act_params["connection_type"] = connection_type
    if db_path:
        _act_params["db_path"] = db_path
    if dry_run:
        _act_params["dry_run"] = dry_run
    if timeout:
        _act_params["timeout"] = timeout
    if exec_code == "error":
        return {
            "summary": f"SQL执行失败: {detail}",
            "action": {"tool": "execute_sql", "tool_zh": "执行", "target": sql[:80], "params": _act_params},
            "status": {"exec_code": "error", "message": detail if detail else "执行失败", "code": ERR_SQL_EXEC, "detail": detail, "hint": hint if hint else "请检查SQL语法"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        return {
            "summary": f"SQL执行警告: 影响{affected_rows}行",
            "action": {"tool": "execute_sql", "tool_zh": "执行", "target": sql[:80], "params": _act_params},
            "status": {"exec_code": "warning", "message": "影响行数超过安全阈值", "code": "WARNING_DB_SAFETY", "detail": f"影响行数{affected_rows}>10000", "hint": "建议缩小条件范围"},
            "duration_ms": duration_ms,
            "metrics": {"affected_rows": {"value": affected_rows, "text": f"{affected_rows}行"}},
        }
    return {
        "summary": f"SQL执行成功, 影响{affected_rows}行",
        "action": {"tool": "execute_sql", "tool_zh": "执行", "target": sql[:80], "params": _act_params},
        "status": {"exec_code": "success", "message": "执行成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"affected_rows": {"value": affected_rows, "text": f"影响{affected_rows}行"}},
    }


def execute_sql(sql: str, connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
                connection_string: Optional[str] = None, db_path: Optional[str] = None,
                dry_run: bool = False, timeout: int = 30000) -> Dict[str, Any]:
    """执行写操作SQL — 小健 2026-06-22 拆分独立文件
    小欧 2026-07-04 修复: 增加None/空字符串校验
    """
    conn = None
    engine = None
    t0 = _time_mod.perf_counter()

    if not isinstance(sql, str) or not sql.strip():
        duration_ms = 0
        llm_data = _build_execute_sql_llm_data("error", duration_ms, sql or "", 0, detail="SQL语句不能为空", hint="请提供有效的SQL语句",
                                                 connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
        return build_error(data={"error_detail": "SQL语句不能为空", "params": {"sql": sql}}, llm_data=llm_data)

    try:
        has_danger, warning_msg, dangerous_list = _check_sql_safety(sql, dry_run)
        if has_danger and not dry_run:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_execute_sql_llm_data("warning", duration_ms, sql, 0,
                                                     connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
            return build_warning(data={"detected": dangerous_list, "suggestion": "检测到危险操作,建议使用 dry_run=true 先验证"}, llm_data=llm_data)

        if dry_run:
            conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
            if conn is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_execute_sql_llm_data("error", duration_ms, sql, 0, detail=conn_error, hint="请检查数据库连接参数",
                                                         connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
                return build_error(data={"error_detail": conn_error, "params": {"connection_type": connection_type, "db_path": db_path}}, llm_data=llm_data)
            syntax_valid = False
            try:
                if connection_type == "sqlite":
                    conn.execute("SAVEPOINT dry_run_check")
                    try:
                        conn.execute(sql)
                    except Exception:
                        syntax_valid = False
                    else:
                        syntax_valid = True
                    finally:
                        conn.execute("ROLLBACK TO SAVEPOINT dry_run_check; RELEASE SAVEPOINT dry_run_check")
                else:
                    from sqlalchemy import text
                    conn.execute(text(sql))
                    syntax_valid = True
            except Exception as e:
                syntax_valid = False
            finally:
                try:
                    conn.close()
                except Exception:
                    logger.warning("[execute_sql] 关闭校验连接失败")
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            if syntax_valid:
                llm_data = _build_execute_sql_llm_data("success", duration_ms, sql, 0,
                                                         connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
                # ---- observation_formatter route -------------------------------------------
                # branch: #21 fallback (key:val) — dry_run path
                # trigger: 无上述20条分支匹配 — sql/dry_run/syntax_valid 不命中专用分支
                # handler: _format_scalar_data(data) — key | value 单行列表
                # file:    observation_formatter.py:214
                # ------------------------------------------------------------------------------
                return build_success(data={"syntax_valid": True}, llm_data=llm_data)
            else:
                llm_data = _build_execute_sql_llm_data("error", duration_ms, sql, 0, detail="SQL语法校验失败", hint="请检查SQL语法",
                                                         connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
                return build_error(data={"dry_run": True, "syntax_valid": False, "error_detail": "SQL语法校验失败"}, llm_data=llm_data)

        conn, engine, conn_error = _get_connection(connection_type, connection_string, db_path, timeout)
        if conn is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_execute_sql_llm_data("error", duration_ms, sql, 0, detail=conn_error, hint="请检查数据库连接参数",
                                                     connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
            return build_error(data={"error_detail": conn_error, "params": {"connection_type": connection_type, "db_path": db_path}}, llm_data=llm_data)

        if connection_type in ("mysql", "postgresql"):
            from sqlalchemy import text
            engine = conn.engine
            result = conn.execute(text(sql))
            affected_rows = result.rowcount
            if affected_rows > 10000:
                conn.rollback()
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_execute_sql_llm_data("warning", duration_ms, sql, affected_rows,
                                                         connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
                return build_warning(data={"action": "rollback"}, llm_data=llm_data)
            conn.commit()
        else:
            cursor = conn.cursor()
            cursor.execute(sql)
            affected_rows = cursor.rowcount
            if affected_rows > 10000:
                conn.rollback()
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_execute_sql_llm_data("warning", duration_ms, sql, affected_rows,
                                                         connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
                return build_warning(data={"action": "rollback"}, llm_data=llm_data)
            conn.commit()

        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_sql_llm_data("success", duration_ms, sql, affected_rows,
                                                 connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
        # =============================================================================
        # 数据设计：affected_rows 从 data 移除，通过 llm_data.metrics 传入 summary
        # summary 示例: "SQL执行成功, 影响5行"
        # — 小欧 2026-07-06 18:46:13
        # =============================================================================
        # ---- observation_formatter route -------------------------------------------
        # branch: #21 fallback (key:val) — normal path
        # trigger: 无上述20条分支匹配 — 仅 action 不命中专用分支
        # handler: _format_scalar_data(data) — key | value 单行列表
        # file:    observation_formatter.py:214
        # ------------------------------------------------------------------------------
        return build_success(data={}, llm_data=llm_data)

    except sqlite3.Error as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_sql_llm_data("error", duration_ms, sql, 0, detail=str(e), hint="请检查SQL语法",
                                                 connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
        if conn:
            try:
                conn.rollback()
            except Exception:
                logger.warning("[execute_sql] sqlite3回滚失败")
        logger.error(f"[execute_sql] ERR_SQL_EXEC: {e}")
        return build_error(data={"error_detail": str(e), "params": {"sql": sql[:200]}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_sql_llm_data("error", duration_ms, sql, 0, detail=str(e), hint="请检查SQL语句和参数",
                                                 connection_type=connection_type, db_path=db_path, dry_run=dry_run, timeout=timeout)
        if conn:
            try:
                conn.rollback()
            except Exception:
                logger.warning("[execute_sql] 回滚失败")
        return build_error(data={"error_detail": str(e), "params": {"sql": sql[:200]}}, llm_data=llm_data)
    finally:
        _close_connection(conn, engine)


__all__ = ["execute_sql"]