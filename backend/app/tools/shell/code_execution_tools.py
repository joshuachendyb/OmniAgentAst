# -*- coding: utf-8 -*-
"""
Code Execution 工具函数模块 - 代码执行工具
【设计说明 2026-06-17 北京老陈确认】本文件是按工具分类聚合的实现文件，文件大是正常设计。

【2026-06-21 小健】Phase 1 builder改造: build_success/error适配新3字段签名

包含:
- execute_code: 统一代码执行(python/javascript)

Author: 小沈 - 2026-05-02
"""

import os
import subprocess
import tempfile
import time as _time_mod
from typing import Optional
import re as re_mod

from app.tools.shell.shell_schema import ExecuteCodeInput
from app.utils.tool_result_formatter import format_output_for_llm, truncate_data_for_frontend
from app.tools.tool_response import build_success, build_error
from app.utils.logger import setup_logger
from app.tools.toolhelper.common_helper import _decode_bytes_safe
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


def _get_utf8_env():
    """获取强制UTF-8的环境变量副本 — 小沈 2026-05-06"""
    env = os.environ.copy()
    env['PYTHONUTF8'] = '1'
    env['PYTHONIOENCODING'] = 'utf-8'
    return env


def _build_exec_code_llm(exec_code: str, duration_ms: int, language: str, returncode: int, stdout_preview: str, stderr_preview: str) -> dict:
    """execute_code的llm_data构建函数 — 小健 2026-06-21"""
    if exec_code == "error":
        detail = f"退出码{returncode}" if returncode is not None else "执行异常"
        return {
            "summary": f"{language}代码执行失败（{detail}）",
            "action": {"tool": "execute_code", "tool_zh": "执行代码", "target": language, "params": {"language": language}},
            "status": {"exec_code": "error", "message": f"代码执行失败({detail})", "code": ERR_EXEC_FAILED, "detail": stderr_preview[:200] if stderr_preview else "", "hint": "请检查代码语法和逻辑"},
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


def execute_code(
    code: str,
    language: str = "python",
    timeout: int = 30,
    working_dir: Optional[str] = None,
) -> dict:
    """统一代码执行入口 — 小健 2026-06-21 builder改造"""
    if language == "python":
        return _execute_python(code=code, timeout=timeout, working_dir=working_dir, safety_check=True)
    elif language == "javascript":
        return _execute_javascript(code=code, timeout=timeout, working_dir=working_dir, safety_check=True)
    else:
        llm_data = _build_exec_code_llm("error", 0, language, -1, "", "")
        llm_data["status"]["code"] = ERR_PARAM_INVALID
        llm_data["status"]["hint"] = "可选: python/javascript"
        return build_error(data={"error_detail": f"不支持的语言: {language}", "params": {"language": language}}, llm_data=llm_data)


def _execute_python(code: str, timeout: int = 30, working_dir: Optional[str] = None, safety_check: bool = True) -> dict:
    """执行Python代码 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    if not code or not code.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_exec_code_llm("error", duration_ms, "python", -1, "", "")
        llm_data["status"]["code"] = ERR_SHELL_EXEC_EMPTY_CODE
        return build_error(data={"error_detail": "code不能为空", "params": {"language": "python"}}, llm_data=llm_data)
    if working_dir is not None and not os.path.isdir(working_dir):
        try:
            os.makedirs(working_dir, exist_ok=True)
        except OSError as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_exec_code_llm("error", duration_ms, "python", -1, "", "")
            llm_data["status"]["code"] = ERR_SHELL_EXEC_INVALID_DIR
            return build_error(data={"error_detail": f"工作目录创建失败: {working_dir}", "params": {"working_dir": working_dir}}, llm_data=llm_data)
    if safety_check:
        from app.tools.toolhelper.exec_helper import _validate_code_safety
        warnings = _validate_code_safety(code)
        if warnings:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_exec_code_llm("error", duration_ms, "python", -1, "", "")
            llm_data["status"]["code"] = ERR_UNSAFE_CODE
            llm_data["status"]["hint"] = "移除危险操作后重试"
            return build_error(data={"error_detail": f"代码存在安全风险: {', '.join(warnings)}", "params": {"warnings": warnings}}, llm_data=llm_data)
    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name

        try:
            result = subprocess.run(
                ['python', temp_file],
                capture_output=True,
                cwd=working_dir,
                timeout=timeout,
                env=_get_utf8_env()
            )

            stdout_str = _decode_bytes_safe(result.stdout)
            stderr_str = _decode_bytes_safe(result.stderr)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

            if result.returncode == 0:
                data = truncate_data_for_frontend({"stdout": stdout_str, "stderr": stderr_str, "returncode": result.returncode})
                llm_data = _build_exec_code_llm("success", duration_ms, "python", result.returncode, stdout_str[:200], stderr_str[:200])
                return build_success(data=data, llm_data=llm_data)
            else:
                data = truncate_data_for_frontend({"stdout": stdout_str, "stderr": stderr_str, "returncode": result.returncode})
                llm_data = _build_exec_code_llm("error", duration_ms, "python", result.returncode, stdout_str[:200], stderr_str[:200])
                return build_error(data=data, llm_data=llm_data)

        except subprocess.TimeoutExpired as e:
            _partial_stdout = _decode_bytes_safe(e.stdout)
            _partial_stderr = _decode_bytes_safe(e.stderr)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = truncate_data_for_frontend({"stdout": _partial_stdout, "stderr": _partial_stderr, "returncode": -1})
            llm_data = _build_exec_code_llm("error", duration_ms, "python", -1, _partial_stdout[:200], _partial_stderr[:200])
            llm_data["status"]["code"] = ERR_EXEC_TIMEOUT
            llm_data["status"]["hint"] = "可增大timeout或优化代码性能"
            return build_error(data=data, llm_data=llm_data)
        finally:
            try:
                os.unlink(temp_file)
            except OSError as e:
                logger.warning(f"删除临时文件失败: {temp_file}, 错误: {e}")

    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_exec_code_llm("error", duration_ms, "python", -1, "", "")
        llm_data["status"]["code"] = ERR_SHELL_EXEC_PYTHON_NOT_FOUND
        return build_error(data={"error_detail": "未找到Python环境", "params": {"language": "python"}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_exec_code_llm("error", duration_ms, "python", -1, "", "")
        llm_data["status"]["code"] = ERR_EXEC_PYTHON
        return build_error(data={"error_detail": str(e), "params": {"language": "python"}}, llm_data=llm_data)


_JS_DANGEROUS_PATTERNS = [
    (r'require\s*\(\s*["\']child_process["\']\s*\)', 'require("child_process") - 可能执行系统命令'),
    (r'require\s*\(\s*["\']fs["\']\s*\)', 'require("fs") - 可能操作文件系统'),
    (r'process\.exit\s*\(', 'process.exit() - 可能终止进程'),
    (r'eval\s*\(', 'eval() - 可能执行任意代码'),
]


def _js_safety_check(code: str) -> Optional[str]:
    """JS安全检查 — 小健 2026-05-25"""
    for pattern, desc in _JS_DANGEROUS_PATTERNS:
        if re_mod.search(pattern, code):
            return f"安全检查: 检测到危险模式 {desc}"
    return None


def _execute_javascript(code: str, timeout: int = 30, working_dir: Optional[str] = None, safety_check: bool = True) -> dict:
    """执行JavaScript代码 — 小健 2026-06-21 builder改造"""
    t0 = _time_mod.perf_counter()
    if not code or not code.strip():
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_exec_code_llm("error", duration_ms, "javascript", -1, "", "")
        llm_data["status"]["code"] = ERR_SHELL_EXEC_EMPTY_CODE
        return build_error(data={"error_detail": "code不能为空", "params": {"language": "javascript"}}, llm_data=llm_data)

    if safety_check:
        err = _js_safety_check(code)
        if err:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_exec_code_llm("error", duration_ms, "javascript", -1, "", "")
            llm_data["status"]["code"] = ERR_UNSAFE_CODE
            llm_data["status"]["hint"] = "移除危险操作后重试"
            return build_error(data={"error_detail": err, "params": {"language": "javascript"}}, llm_data=llm_data)

    if working_dir is not None and not os.path.isdir(working_dir):
        try:
            os.makedirs(working_dir, exist_ok=True)
        except OSError as e:
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            llm_data = _build_exec_code_llm("error", duration_ms, "javascript", -1, "", "")
            llm_data["status"]["code"] = ERR_SHELL_EXEC_INVALID_DIR
            return build_error(data={"error_detail": f"工作目录创建失败: {working_dir}", "params": {"working_dir": working_dir}}, llm_data=llm_data)

    try:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.js', delete=False, encoding='utf-8') as f:
            f.write(code)
            temp_file = f.name

        try:
            result = subprocess.run(
                ['node', temp_file],
                capture_output=True,
                cwd=working_dir,
                timeout=timeout,
                env=_get_utf8_env()
            )

            stdout_str = _decode_bytes_safe(result.stdout)
            stderr_str = _decode_bytes_safe(result.stderr)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)

            if result.returncode == 0:
                data = truncate_data_for_frontend({"stdout": stdout_str, "stderr": stderr_str, "returncode": result.returncode})
                llm_data = _build_exec_code_llm("success", duration_ms, "javascript", result.returncode, stdout_str[:200], stderr_str[:200])
                return build_success(data=data, llm_data=llm_data)
            else:
                data = truncate_data_for_frontend({"stdout": stdout_str, "stderr": stderr_str, "returncode": result.returncode})
                llm_data = _build_exec_code_llm("error", duration_ms, "javascript", result.returncode, stdout_str[:200], stderr_str[:200])
                return build_error(data=data, llm_data=llm_data)

        except subprocess.TimeoutExpired as e:
            _partial_stdout = _decode_bytes_safe(e.stdout)
            _partial_stderr = _decode_bytes_safe(e.stderr)
            duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
            data = truncate_data_for_frontend({"stdout": _partial_stdout, "stderr": _partial_stderr, "returncode": -1})
            llm_data = _build_exec_code_llm("error", duration_ms, "javascript", -1, _partial_stdout[:200], _partial_stderr[:200])
            llm_data["status"]["code"] = ERR_EXEC_TIMEOUT
            llm_data["status"]["hint"] = "可增大timeout或优化代码性能"
            return build_error(data=data, llm_data=llm_data)
        finally:
            try:
                os.unlink(temp_file)
            except OSError as e:
                logger.warning(f"删除临时文件失败: {temp_file}, 错误: {e}")

    except FileNotFoundError:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_exec_code_llm("error", duration_ms, "javascript", -1, "", "")
        llm_data["status"]["code"] = ERR_SHELL_EXEC_NODE_NOT_FOUND
        return build_error(data={"error_detail": "未找到Node.js环境", "params": {"language": "javascript"}}, llm_data=llm_data)
    except Exception as e:
        duration_ms = int((_time_mod.perf_counter() - t0) * 1000)
        llm_data = _build_exec_code_llm("error", duration_ms, "javascript", -1, "", "")
        llm_data["status"]["code"] = ERR_EXEC_JS
        return build_error(data={"error_detail": str(e), "params": {"language": "javascript"}}, llm_data=llm_data)
