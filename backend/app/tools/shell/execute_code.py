# -*- coding: utf-8 -*-
"""
S4: execute_code — 执行代码片段

从code_execution_tools.py拆分而来 — 小欧 2026-06-22
内聚: _execute_python / _execute_javascript / _js_safety_check / _get_utf8_env
"""
# 【铁规】helper/被调函数(以下划线_开头的函数)只返回raw dict，严禁调用build_success/build_error/build_warning和构建llm_data。
# build3+llm_data只能在tool的main函数(对外公开的函数)中包装。违反此规则的代码视为不合规。

import os
import re as re_mod
import subprocess
import tempfile
import time as _time_mod
from typing import Any, Dict, List, Optional, Tuple

from app.tools.tool_response import build_success, build_error
from app.tools.tool_fc_helper import _decode_bytes_safe
from app.utils.tool_result_formatter import truncate_data_for_frontend
from app.utils.logger import setup_logger
from app.constants import (
    ERR_EXEC_FAILED,
    ERR_EXEC_JS,
    ERR_EXEC_PYTHON,
    ERR_EXEC_TIMEOUT,
    ERR_PARAM_INVALID,
    ERR_SHELL_EXEC_EMPTY_CODE,
    ERR_SHELL_EXEC_INVALID_DIR,
    ERR_SHELL_EXEC_NODE_NOT_FOUND,
    ERR_SHELL_EXEC_PYTHON_NOT_FOUND,
    ERR_UNSAFE_CODE,
)

logger = setup_logger(__name__)


def _build_execute_code_llm_data(
    exec_code: str, duration_ms: int, language: str = "", returncode: int = 0,
    stdout_preview: str = "", stderr_preview: str = "",
    err_code: str = "", detail: str = "",
) -> Dict[str, Any]:
    """execute_code的llm_data构建函数 — 小欧 2026-06-22"""
    if exec_code == "error":
        _detail = detail or (f"退出码{returncode}" if returncode is not None else "执行异常")
        return {
            "summary": f"{language}代码执行失败（{_detail}）",
            "action": {"tool": "execute_code", "tool_zh": "执行代码", "target": language, "params": {"language": language}},
            "status": {"exec_code": "error", "message": f"代码执行失败({_detail})", "code": err_code or ERR_EXEC_FAILED, "detail": stderr_preview[:200] if stderr_preview else "", "hint": "请检查代码语法和逻辑"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    warning = "（有警告输出）" if stderr_preview and stderr_preview.strip() else ""
    return {
        "summary": f"{language}代码执行成功{warning}",
        "action": {"tool": "execute_code", "tool_zh": "执行代码", "target": language, "params": {"language": language}},
        "status": {"exec_code": "success", "message": f"代码执行成功{warning}", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"returncode": {"value": returncode, "text": f"退出码{returncode}"}},
    }


def _get_utf8_env() -> dict:
    """获取强制UTF-8的环境变量副本 — 小欧 2026-06-22"""
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


_JS_DANGEROUS_PATTERNS: List[Tuple[str, str]] = [
    (r'require\s*\(\s*["\']child_process["\']\s*\)', 'require("child_process") - 可能执行系统命令'),
    (r'require\s*\(\s*["\']fs["\']\s*\)', 'require("fs") - 可能操作文件系统'),
    (r'process\.exit\s*\(', 'process.exit() - 可能终止进程'),
    (r'eval\s*\(', 'eval() - 可能执行任意代码'),
]


def _js_safety_check(code: str) -> Optional[str]:
    """JS安全检查 — 小欧 2026-06-22"""
    for pattern, desc in _JS_DANGEROUS_PATTERNS:
        if re_mod.search(pattern, code):
            return f"安全检查: 检测到危险模式 {desc}"
    return None


def _execute_python(code: str, timeout: int = 30, working_dir: Optional[str] = None, safety_check: bool = True) -> Dict[str, Any]:
    """执行Python代码 — 小欧 2026-06-22
    返回原始字典，不调用build3，不含llm_data — 北京老陈 2026-06-22
    """
    t0 = _time_mod.perf_counter()
    if not code or not code.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return {"success": False, "error_detail": "code参数不能为空", "params": {"language": "python"}, "duration_ms": duration_ms}
    if working_dir is not None and not os.path.isdir(working_dir):
        try:
            os.makedirs(working_dir, exist_ok=True)
        except OSError:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            return {"success": False, "error_detail": f"工作目录创建失败: {working_dir}", "params": {"working_dir": working_dir}, "duration_ms": duration_ms}
    if safety_check:
        from app.tools.tool_fc_helper import _validate_code_safety
        warnings = _validate_code_safety(code)
        if warnings:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            return {"success": False, "error_detail": f"代码存在安全风险: {', '.join(warnings)}", "params": {"warnings": warnings}, "duration_ms": duration_ms}
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        try:
            result = subprocess.run(['python', temp_file], capture_output=True, cwd=working_dir, timeout=timeout, env=_get_utf8_env())
            stdout_str = _decode_bytes_safe(result.stdout)
            stderr_str = _decode_bytes_safe(result.stderr)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            if result.returncode == 0:
                return {"success": True, "output": stdout_str, "error": stderr_str, "returncode": result.returncode, "duration_ms": duration_ms, "params": {"language": "python"}}
            return {"success": False, "output": stdout_str, "error": stderr_str, "returncode": result.returncode, "duration_ms": duration_ms, "params": {"language": "python"}}
        except subprocess.TimeoutExpired as e:
            _partial_stdout = _decode_bytes_safe(e.stdout)
            _partial_stderr = _decode_bytes_safe(e.stderr)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            return {"success": False, "error_detail": "执行超时", "output": _partial_stdout, "error": _partial_stderr, "returncode": -1, "duration_ms": duration_ms, "params": {"language": "python", "timeout": timeout}}
        finally:
            try:
                os.unlink(temp_file)
            except OSError:
                pass
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return {"success": False, "error_detail": "未找到Python环境", "params": {"language": "python"}, "duration_ms": duration_ms}
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return {"success": False, "error_detail": str(e), "params": {"language": "python"}, "duration_ms": duration_ms}


def _execute_javascript(code: str, timeout: int = 30, working_dir: Optional[str] = None, safety_check: bool = True) -> Dict[str, Any]:
    """执行JavaScript代码 — 小欧 2026-06-22
    返回原始字典，不调用build3，不含llm_data — 北京老陈 2026-06-22
    """
    t0 = _time_mod.perf_counter()
    if not code or not code.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return {"success": False, "error_detail": "code参数不能为空", "params": {"language": "javascript"}, "duration_ms": duration_ms}
    if safety_check:
        err = _js_safety_check(code)
        if err:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            return {"success": False, "error_detail": err, "params": {"language": "javascript"}, "duration_ms": duration_ms}
    if working_dir is not None and not os.path.isdir(working_dir):
        try:
            os.makedirs(working_dir, exist_ok=True)
        except OSError:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            return {"success": False, "error_detail": f"工作目录创建失败: {working_dir}", "params": {"working_dir": working_dir}, "duration_ms": duration_ms}
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name
        try:
            result = subprocess.run(['node', temp_file], capture_output=True, cwd=working_dir, timeout=timeout, env=_get_utf8_env())
            stdout_str = _decode_bytes_safe(result.stdout)
            stderr_str = _decode_bytes_safe(result.stderr)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            if result.returncode == 0:
                return {"success": True, "output": stdout_str, "error": stderr_str, "returncode": result.returncode, "duration_ms": duration_ms, "params": {"language": "javascript"}}
            return {"success": False, "output": stdout_str, "error": stderr_str, "returncode": result.returncode, "duration_ms": duration_ms, "params": {"language": "javascript"}}
        except subprocess.TimeoutExpired as e:
            _partial_stdout = _decode_bytes_safe(e.stdout)
            _partial_stderr = _decode_bytes_safe(e.stderr)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            return {"success": False, "error_detail": "执行超时", "output": _partial_stdout, "error": _partial_stderr, "returncode": -1, "duration_ms": duration_ms, "params": {"language": "javascript", "timeout": timeout}}
        finally:
            try:
                os.unlink(temp_file)
            except OSError:
                pass
    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return {"success": False, "error_detail": "未找到Node.js环境", "params": {"language": "javascript"}, "duration_ms": duration_ms}
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        return {"success": False, "error_detail": str(e), "params": {"language": "javascript"}, "duration_ms": duration_ms}


def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30,
    working_dir: Optional[str] = None,
) -> Dict[str, Any]:
    """统一代码执行入口 — 小健 2026-06-21 — 小欧 2026-06-22 独立文件
    包装辅助函数结果，构建build3和llm_data — 北京老陈 2026-06-22
    """
    if language == "python":
        result = _execute_python(code=code, timeout=timeout, working_dir=working_dir, safety_check=True)
    elif language == "javascript":
        result = _execute_javascript(code=code, timeout=timeout, working_dir=working_dir, safety_check=True)
    else:
        duration_ms = 0
        llm_data = _build_execute_code_llm_data("error", duration_ms, language, -1, err_code=ERR_PARAM_INVALID, detail=f"不支持的语言: {language}")
        llm_data["status"]["hint"] = "可选: python/javascript"
        return build_error(data={"error_detail": f"不支持的语言: {language}", "params": {"language": language}}, llm_data=llm_data)
    
    # 包装辅助函数结果
    duration_ms = result.get("duration_ms", 0)
    if result.get("success"):
        # 成功情况
        output = result.get("output", "")
        error = result.get("error", "")
        returncode = result.get("returncode", 0)
        llm_data = _build_execute_code_llm_data("success", duration_ms, language, returncode, output[:200], error[:200])
        data = truncate_data_for_frontend({"stdout": output, "stderr": error, "returncode": returncode})
        return build_success(data=data, llm_data=llm_data)
    else:
        # 失败情况
        error_detail = result.get("error_detail", "")
        params = result.get("params", {})
        if "output" in result:
            # 有输出的失败（如返回码非零）
            output = result.get("output", "")
            error = result.get("error", "")
            returncode = result.get("returncode", -1)
            llm_data = _build_execute_code_llm_data("error", duration_ms, language, returncode, output[:200], error[:200])
            data = truncate_data_for_frontend({"stdout": output, "stderr": error, "returncode": returncode})
        else:
            # 无输出的失败（如参数错误、环境问题）
            llm_data = _build_execute_code_llm_data("error", duration_ms, language, -1, err_code=ERR_EXEC_FAILED, detail=error_detail)
            llm_data["status"]["hint"] = "可选: python/javascript" if "language" in params else ""
            data = {"error_detail": error_detail, "params": params}
        return build_error(data=data, llm_data=llm_data)