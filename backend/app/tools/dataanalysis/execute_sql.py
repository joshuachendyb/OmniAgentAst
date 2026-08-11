# -*- coding: utf-8 -*-
"""
execute_sql — 执行写操作SQL
【2026-06-22 小健】从 database_tools.py 拆分为独立文件
【2026-07-23 小欧】#6 fix: 扩展CREATE豁免+_AFFECTED_ROWS_LIMIT常量+affected_rows=-1防御
   【病根】①豁免仅CREATE TABLE/VIEW IF NOT EXISTS, 漏INDEX/TRIGGER/TEMP TABLE(约60%误拦)
          ②affected_rows>10000三处硬编码(DRY违规), 且-1不被处理
   【改法】①扩展豁免: CREATE INDEX/TRIGGER安全放行, TEMP TABLE/VIEW有IF NOT EXISTS放行
          ②_AFFECTED_ROWS_LIMIT模块常量替代3处10000硬编码
          ③isinstance防御affected_rows=-1场景
   【合规】DRY(常量消重)+KISS-DIRECT(if/elif直线扩展,不引入分级抽象)+YAGNI(模块常量不跨文件)
【2026-07-24 小欧】修复: _sql_preview前置防空SQL漏截断 + timeout判断用is not None防0跳过
【2026-07-26 小欧】迁移: sql_error_hint/hint_for_data_error导入从tool_constants改为file_path_checker(配合函数迁移)
【2026-08-07 小欧】P01+P02优化(北京老陈驱动 task001): ①新增confirm_ddl参数 — 显式确认后放行裸DDL(白名单_DDL_ONLY_TYPES: CREATE/DROP/ALTER/TRUNCATE/GRANT/REVOKE, 防未来新增安全类型误放行); ②_build_execute_sql_llm_data补confirm_ddl传参(observation可见); ③危险提示文案优化 — 无WHERE时引导补WHERE/dry_run, 条件拼接消除warnings为空时的冗余逗号
【2026-08-09 小欧】task006 P1落地: dry_run分支保留sqlite3异常(dry_run_error), 校验失败detail带异常原文+hint走sql_error_hint精准分支(多语句识别), 替代笼统"SQL语法校验失败/请检查SQL语法"
【2026-08-09 小欧】task005核查P3落地: dry_run外层except加`if dry_run_error is None`保护 — 仅内层无异常时才用外层异常, 保留内层原始SQL语法错误(信息不丢失, 符合异常可追溯规范); 病根: SAVEPOINT/ROLLBACK失败(连接损坏)无条件覆盖内层已捕获异常
【2026-08-11 小欧】三堂会审复核落地(P2-7): 删除外层except无条件syntax_valid=False覆写 — 内层语法校验已通过(syntax_valid=True)时,
   外层SAVEPOINT/ROLLBACK/RELEASE失败(连接异常)不再误报"SQL语法校验失败"; syntax_valid仅反映内层真实校验结果, 增强不退化
"""
# 【铁规1】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。
# 【铁规2】工具返回原始data，禁止调用truncate_data_for_frontend。截断只能在前端yield层。
# 【铁规3】计时(duration_ms计算)只能在tool的主函数中，严禁在子函数/helper中计时。
import re
import sqlite3
import time as _time_mod
from typing import Any, Dict, List, Optional, Literal, Tuple  # 2026-07-31 小欧: 移除未使用 Union

from app.logger import logger
from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_constants import ERR_SQL_EXEC, EXECUTE_SQL_OUTPARM_LIMIT_SQL
from app.tools.validate.file_path_checker import sql_error_hint, hint_for_data_error
from app.tools.tool_fc_helper import _get_connection, _close_connection, _strip_sql_comments_and_strings  # 2026-07-31 小欧: Bug①注释绕过修复引入

# #6: 影响行数安全阈值(模块级常量,DRY消除3处硬编码) — 小欧 2026-07-23
_AFFECTED_ROWS_LIMIT = 10000
# 2026-07-31 小欧: DDL关键字模式, 供 _check_sql_safety 与 MySQL dry_run DDL拒绝共用(DRY) — Bug③
_DDL_PATTERN = re.compile(r'\b(DROP|TRUNCATE|ALTER|CREATE|GRANT|REVOKE)\b', re.IGNORECASE)


def _check_sql_safety(sql: str) -> Tuple[bool, Optional[str], Optional[List[str]]]:
    """统一危险模式检测 + 无WHERE检测 + 拦截决策 — 小沈 2026-05-25
       #6: 删dry_run死参数(函数体内从未使用,调用方自行过滤) — 小欧 2026-07-23
       2026-07-31 小欧: Bug①修复 — 检测前剥离注释与字符串字面量, "DELETE FROM t -- WHERE id=1" 注释绕过无WHERE检测,
       关联修复: 字符串字面量内含关键字(如 SET note='WHERE')不再漏判
    """
    clean_sql = _strip_sql_comments_and_strings(sql)
    sql_upper = clean_sql.strip().upper()
    dangerous_matches = _DDL_PATTERN.findall(clean_sql)
    if re.match(r'\s*(DELETE|UPDATE)\s', sql_upper) and 'WHERE' not in sql_upper:
        dangerous_matches.append('NO_WHERE')
    # #6: CREATE豁免 — CREATE INDEX/TRIGGER 安全放行, TEMP TABLE/VIEW 有 IF NOT EXISTS 放行 — 小欧 2026-07-23
    if 'CREATE' in dangerous_matches:
        if re.search(r'CREATE\s+(UNIQUE\s+)?INDEX\s+', clean_sql, re.IGNORECASE):
            dangerous_matches = [d for d in dangerous_matches if d != 'CREATE']
        elif re.search(r'CREATE\s+TRIGGER\s+', clean_sql, re.IGNORECASE):
            dangerous_matches = [d for d in dangerous_matches if d != 'CREATE']
        elif re.search(r'CREATE\s+(TEMP\s+|TEMPORARY\s+)?TABLE\s+IF\s+NOT\s+EXISTS', clean_sql, re.IGNORECASE):
            dangerous_matches = [d for d in dangerous_matches if d != 'CREATE']
        elif re.search(r'CREATE\s+VIEW\s+IF\s+NOT\s+EXISTS', clean_sql, re.IGNORECASE):
            dangerous_matches = [d for d in dangerous_matches if d != 'CREATE']
    # #6: DROP IF EXISTS 豁免(DROP TABLE/VIEW/INDEX IF EXISTS 语义安全) — 小欧 2026-07-23
    if 'DROP' in dangerous_matches:
        if re.search(r'DROP\s+(TABLE|VIEW|INDEX|TRIGGER)\s+IF\s+EXISTS', clean_sql, re.IGNORECASE):
            dangerous_matches = [d for d in dangerous_matches if d != 'DROP']
    if dangerous_matches:
        warnings = []
        dangerous_to_show = [d for d in dangerous_matches if d != 'NO_WHERE']
        if dangerous_to_show:
            warnings.append(f"危险操作: {dangerous_to_show}")
        if 'NO_WHERE' in dangerous_matches:
            warnings.append("缺少 WHERE 条件")
            # 提示如何补充WHERE或dry_run预演 — 小欧 2026-08-07
            hint = "已拦截整表操作。如需清空请带 WHERE（如 DELETE FROM t WHERE 1=1）或先 dry_run=true 确认"
        else:
            hint = "可使用 dry_run=true 预演"
        # dangerous_to_show为空时(仅有NO_WHERE)warnings为空,'+'.join([])产生空串致冗余逗号,改用条件拼接 — 小欧 2026-08-07
        _warn_str = f"危险操作: {'+'.join(warnings)}" if warnings else "整表操作"
        return True, f"警告:检测到{_warn_str},已拦截执行。{hint}", dangerous_matches
    return False, None, None


def _build_execute_sql_llm_data(exec_code, duration_ms, sql, affected_rows, detail="", hint="",
                                 connection_type="", path="", dry_run=False, timeout=0, confirm_ddl=False):
    """execute_sql的llm_data构建函数 — 小健 2026-06-22 — 小沈 2026-07-05 新增detail/hint参数 — 小欧 2026-07-05 新增user_params — 小欧 2026-07-24 主函数入口统一截断，build函数不再截断 — 小欧 2026-08-07 新增confirm_ddl传参"""
    _act_params = {"sql": sql}
    if connection_type:
        _act_params["connection_type"] = connection_type
    if path:
        _act_params["path"] = path
    if dry_run:
        _act_params["dry_run"] = dry_run
    if timeout is not None:
        _act_params["timeout"] = timeout
    if confirm_ddl:
        _act_params["confirm_ddl"] = confirm_ddl
    _target = path or connection_type or "database"
    if exec_code == "error":
        return {
            "summary": f"执行{_target}，失败: {detail}",
            "action": {"tool": "execute_sql", "tool_zh": "执行", "target": sql, "params": _act_params},
            "status": {"exec_code": "error", "message": detail if detail else "执行失败", "code": ERR_SQL_EXEC, "detail": detail, "hint": hint if hint else "请检查SQL语法"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        if isinstance(affected_rows, (int, float)) and affected_rows > _AFFECTED_ROWS_LIMIT:
            msg = "影响行数超过安全阈值"
            detail_msg = f"影响行数{affected_rows}>{_AFFECTED_ROWS_LIMIT}，已回滚"
            hint_msg = "建议缩小条件范围"
        else:
            msg = "检测到危险SQL操作"
            detail_msg = f"检测到危险SQL操作（{sql}），已回滚"
            hint_msg = "建议使用 dry_run=true 先验证"
        return {
            "summary": f"执行{_target}，{detail_msg}",
            "action": {"tool": "execute_sql", "tool_zh": "执行", "target": sql, "params": _act_params},
            "status": {"exec_code": "warning", "message": msg, "code": "WARNING_DB_SAFETY", "detail": detail_msg, "hint": hint_msg},
            "duration_ms": duration_ms,
            "metrics": {"affected_rows": {"value": affected_rows, "text": f"{affected_rows}行"}},
        }
    return {
        "summary": f"执行{_target}，成功: 影响{affected_rows}行",
        "action": {"tool": "execute_sql", "tool_zh": "执行", "target": sql, "params": _act_params},
        "status": {"exec_code": "success", "message": "执行成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"affected_rows": {"value": affected_rows, "text": f"影响{affected_rows}行"}},
    }


def execute_sql(sql: str, connection_type: Literal["sqlite", "mysql", "postgresql"] = "sqlite",
                connection_string: Optional[str] = None, path: Optional[str] = None,
                dry_run: bool = False, timeout: int = 30000,
                confirm_ddl: bool = False) -> Dict[str, Any]:
    """执行写操作SQL — 小健 2026-06-22 拆分独立文件
    小欧 2026-07-04 修复: 增加None/空字符串校验
    小欧 2026-08-07 新增confirm_ddl参数: 显式确认后放行裸DDL(白名单)
    """
    conn = None
    engine = None
    t0 = _time_mod.perf_counter()
    _sql_preview = (sql or "")[:EXECUTE_SQL_OUTPARM_LIMIT_SQL]

    if not isinstance(sql, str) or not sql.strip():
        duration_ms = 0
        llm_data = _build_execute_sql_llm_data("error", duration_ms, _sql_preview, 0, detail="SQL语句不能为空", hint="请提供有效的SQL语句",
                                                  connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
        return build_error(data={}, llm_data=llm_data)

    # 2026-07-31 小欧: Bug⑲ timeout防御 — None回默认, <=0拒绝(避免连接超时0/异常) — 与query_sql对齐
    if timeout is None:
        timeout = 30000
    if timeout <= 0:
        duration_ms = 0
        llm_data = _build_execute_sql_llm_data("error", duration_ms, _sql_preview, 0, detail="timeout必须大于0(单位毫秒)", hint="请设置正数timeout,建议30000",
                                                  connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
        return build_error(data={}, llm_data=llm_data)

    try:
        has_danger, warning_msg, dangerous_list = _check_sql_safety(sql)
        # confirm_ddl=true: 用户显式确认后放行裸 CREATE/DROP（危险列表仅为已知 DDL 类型时）
        # 白名单判断(非排除法): 只有 _DDL_ONLY_TYPES 中的类型才被 confirm_ddl 放行,
        # 未来新增安全类型(如 SQL_INJECTION)不会误放行 — 小欧 2026-08-07
        _DDL_ONLY_TYPES = {"CREATE", "DROP", "ALTER", "TRUNCATE", "GRANT", "REVOKE"}
        _ddl_only = dangerous_list and all(d in _DDL_ONLY_TYPES for d in dangerous_list)
        if has_danger and not dry_run and not (confirm_ddl and _ddl_only):
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_execute_sql_llm_data("warning", duration_ms, _sql_preview, 0,
                                                     connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
            # #6: blocked路径SQL未执行,metrics不清affected_rows,防LLM误以为"执行了影响0行" — 小欧 2026-07-23
            llm_data["metrics"] = {}
            return build_warning(data={"detected": dangerous_list, "suggestion": "检测到危险操作,建议使用 dry_run=true 先验证"}, llm_data=llm_data)

        if dry_run:
            conn, engine, conn_error = _get_connection(connection_type, connection_string, path, timeout)
            if conn is None:
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_execute_sql_llm_data("error", duration_ms, _sql_preview, 0, detail=conn_error, hint="请检查数据库连接参数",
                                                          connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
                return build_error(data={}, llm_data=llm_data)
            syntax_valid = False
            dry_run_refused = None  # 2026-07-31 小欧: Bug③ MySQL DDL拒绝理由
            dry_run_error = None  # 2026-08-09 小欧: task006 P1 保留校验异常供精准hint(多语句等)
            try:
                if connection_type == "sqlite":
                    conn.execute("SAVEPOINT dry_run_check")
                    try:
                        conn.execute(sql)
                    except Exception as _e:
                        syntax_valid = False
                        dry_run_error = _e  # 2026-08-09 小欧: 保留sqlite3异常, 供"one statement at a time"精准识别
                    else:
                        syntax_valid = True
                    finally:
                        conn.execute("ROLLBACK TO SAVEPOINT dry_run_check")
                        conn.execute("RELEASE SAVEPOINT dry_run_check")
                else:
                    from sqlalchemy import text
                    # Bug③修复: MySQL DDL隐式自动提交,dry_run无法安全预演(如 DROP TABLE 会真实删表) — 直接拒绝
                    if connection_type == "mysql" and _DDL_PATTERN.search(_strip_sql_comments_and_strings(sql)):
                        dry_run_refused = "MySQL dry_run无法安全预演DDL语句(DDL隐式自动提交)"
                    else:
                        # 显式事务+回滚: MySQL/PG 的 DML 与 PG 的事务性 DDL 均可安全预演
                        trans = conn.begin()
                        try:
                            conn.execute(text(sql))
                            syntax_valid = True
                        except Exception as _e:
                            syntax_valid = False
                            dry_run_error = _e  # 2026-08-09 小欧: 保留异常供精准hint
                        finally:
                            trans.rollback()
            except Exception as e:
                # 2026-08-09 小欧: task005核查P3 — 仅内层无异常时才用外层异常, 保留内层原始SQL错误(信息不丢失);
                #   病根: SAVEPOINT/ROLLBACK等外层操作失败(连接损坏)会无条件覆盖内层已捕获的SQL语法异常
                # 2026-08-11 小欧(P2-7): 删除无条件 syntax_valid=False 覆写 — 内层语法校验已通过(syntax_valid=True)时,
                #   外层SAVEPOINT/ROLLBACK/RELEASE失败属连接异常, 不再误报"SQL语法校验失败"; syntax_valid仅反映内层真实校验结果
                if dry_run_error is None:
                    dry_run_error = e
            finally:
                try:
                    conn.close()
                except Exception:
                    logger.warning("[execute_sql] 关闭校验连接失败")
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            if dry_run_refused:
                llm_data = _build_execute_sql_llm_data("error", duration_ms, _sql_preview, 0, detail=dry_run_refused, hint="请在目标库直接执行,或改用sqlite连接预演",
                                                          connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
                return build_error(data={}, llm_data=llm_data)
            if syntax_valid:
                llm_data = _build_execute_sql_llm_data("success", duration_ms, _sql_preview, 0,
                                                          connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
                # ---- observation_formatter route -------------------------------------------
                # branch: #21 fallback (key:val) — dry_run path
                # trigger: 无上述20条分支匹配 — sql/dry_run/syntax_valid 不命中专用分支
                # handler: _format_scalar_data(data) — key | value 单行列表
                # file:    observation_formatter.py:214
                # ------------------------------------------------------------------------------
                return build_success(data={"syntax_valid": True}, llm_data=llm_data)
            else:
                # 2026-08-09 小欧: task006 P1 — detail带异常原文, hint走sql_error_hint精准分支(多语句等), 替代笼统提示
                _dry_detail = f"SQL语法校验失败: {dry_run_error}" if dry_run_error else "SQL语法校验失败"
                llm_data = _build_execute_sql_llm_data("error", duration_ms, _sql_preview, 0, detail=_dry_detail,
                                                          hint=sql_error_hint(dry_run_error) if dry_run_error else "请检查SQL语法",
                                                          connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
                return build_error(data={}, llm_data=llm_data)

        conn, engine, conn_error = _get_connection(connection_type, connection_string, path, timeout)
        if conn is None:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_execute_sql_llm_data("error", duration_ms, _sql_preview, 0, detail=conn_error, hint="请检查数据库连接参数",
                                                     connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
            return build_error(data={}, llm_data=llm_data)

        if connection_type in ("mysql", "postgresql"):
            from sqlalchemy import text
            engine = conn.engine
            result = conn.execute(text(sql))
            affected_rows = result.rowcount
            if isinstance(affected_rows, (int, float)) and affected_rows > _AFFECTED_ROWS_LIMIT:
                conn.rollback()
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_execute_sql_llm_data("warning", duration_ms, _sql_preview, affected_rows,
                                                         connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
                return build_warning(data={"action": "rollback"}, llm_data=llm_data)
            conn.commit()
        else:
            cursor = conn.cursor()
            cursor.execute(sql)
            affected_rows = cursor.rowcount
            if isinstance(affected_rows, (int, float)) and affected_rows > _AFFECTED_ROWS_LIMIT:
                conn.rollback()
                duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
                llm_data = _build_execute_sql_llm_data("warning", duration_ms, _sql_preview, affected_rows,
                                                         connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
                return build_warning(data={"action": "rollback"}, llm_data=llm_data)
            conn.commit()

        # #6: affected_rows=-1(DDL) clamp到0, 防"影响-1行" — 小欧 2026-07-23
        _ar_success = affected_rows if isinstance(affected_rows, (int, float)) and affected_rows >= 0 else 0
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_sql_llm_data("success", duration_ms, _sql_preview, _ar_success,
                                                  connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout,
                                                  confirm_ddl=confirm_ddl)  # confirm_ddl 传参, observation可见 — 小欧 2026-08-07
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
        llm_data = _build_execute_sql_llm_data("error", duration_ms, _sql_preview, 0, detail=str(e), hint=sql_error_hint(e),
                                                  connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
        if conn:
            try:
                conn.rollback()
            except Exception:
                logger.warning("[execute_sql] sqlite3回滚失败")
        logger.warning(f"[execute_sql] ERR_SQL_EXEC: {e}")
        return build_error(data={}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_execute_sql_llm_data("error", duration_ms, _sql_preview, 0, detail=str(e), hint=hint_for_data_error(e),
                                                  connection_type=connection_type, path=path, dry_run=dry_run, timeout=timeout)
        if conn:
            try:
                conn.rollback()
            except Exception:
                logger.warning("[execute_sql] 回滚失败")
        return build_error(data={}, llm_data=llm_data)
    finally:
        _close_connection(conn, engine)


__all__ = ["execute_sql"]
