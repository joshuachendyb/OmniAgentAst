# -*- coding: utf-8 -*-
"""
S1: execute_shell_command — 执行Shell命令（v2 引擎版）— 小欧 2026-07-05

╔══════════════════════════════════════════════════════════════════╗
║                Shell 工具编码链路分析与修复全景                     ║
║                   2026-07-07 北京老陈驱动检查                       ║
╚══════════════════════════════════════════════════════════════════╝

┌──────────────┐
│  shell() 入口 │──── command + shell_type
└──────┬───────┘
       │
       ├── shell_type="powershell" ───────────────────────────────
       │   │
       │   ├── PersistentShell._exec()
       │   │   │
       │   │   ├── [入] stdin.write(cmd.encode("utf-8"))
       │   │   │   │   PS5.1 `-Command -` stdin
       │   │   │   │   ⚡ 实测: 不加BOM PS5.1自动识别UTF-8 ✅
       │   │   │   │   ⚡ 加BOM反而静默失败 ❌ (不修)
       │   │   │   │
        │   │   ├── [子进程] env={PYTHONIOENCODING=utf-8, PYTHONUTF8=1}
        │   │   │   │   2026-07-07 小欧 修复
        │   │   │   │   PYTHONIOENCODING: print()输出中文不抛异常
        │   │   │   │   PYTHONUTF8=1: open()默认用UTF-8避免gbk误读
       │   │   │   │
       │   │   ├── [出] > 替换为 Out-File -Encoding utf8
       │   │   │   │   2026-07-07 小欧 修复
       │   │   │   │   PS5.1用>写UTF-16LE导致中文乱码 → 统一UTF-8
       │   │   │   │
       │   │   └── [读] safe_read_file + .lstrip('\ufeff')
       │   │       2026-07-07 小欧 修复
       │   │       PS5.1 Out-File写BOM头 → 去掉ZWNBSP
       │   │       out/err/code/cwd 全部处理
       │   │
       │   └── PersistentShell 启动: -NoProfile -Command -
       │       (持久进程, 复用避免反复启动开销)
       │
       └── shell_type="cmd" ─────────────────────────────────────
           │
           ├── [入] .bat文件写入 locale.getpreferredencoding()
           │   2026-07-07 小欧 修复
           │   改为gbk匹配cmd.exe OEM代码页,避免中文乱码
           │   (原用utf-8写, cmd.exe按gbk读,中文全乱)
           │
            ├── [子进程] env={PYTHONIOENCODING=utf-8, PYTHONUTF8=1}
            │   2026-07-07 小欧 修复
            │   PYTHONIOENCODING: print()输出中文不崩
            │   PYTHONUTF8=1: open()默认用UTF-8避免gbk误读
           │
           └── [出] proc.communicate() → _decode_bytes_safe()
               utf-8优先(gbk回退, latin-1兜底)
               Python子进程(PYTHONIOENCODING)输出UTF-8直接命中


┌────────────────────────────────────────────────────────────────┐
│  附: 系统级编码加固 (2026-07-07 小欧)                           │
├────────────────────────────────────────────────────────────────┤
│  main.py: sys.stdout.reconfigure(encoding='utf-8')             │
│    → 服务进程本身stdout设UTF-8, 日志/print中文不乱             │
└────────────────────────────────────────────────────────────────┘


【v2 改造】
  - powershell 分支改用 PersistentShell 持久引擎
  - 删除 run_in_background / _background_shells / shell_session
  - 保留 build3 + llm_data 体系不变

铁规1: helper 函数不碰 build3，只在 shell() 主函数包装
铁规2: 工具返回原始 data，前端截断在前端 yield 层
铁规3: 计时仅在 shell() 主函数
"""
import os
import re
import shutil
import subprocess
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional

from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_fc_helper import _decode_bytes_safe
from app.tools.validate.timeout_validator import validate_timeout
from app.utils.logger import logger
from app.tools.tool_constants import (
    ERR_PARAMETER_EMPTY, ERR_PARAMETER_INVALID,
    ERR_SHELL_EXCEPTION, ERR_SHELL_EXEC,
    ERR_SHELL_INJECTION, ERR_SHELL_TIMEOUT,
)


# ═══════════════════════════════════════════════════════
#  PowerShell 5.1 &&/|| 翻译（来自小沈 2026-07-05）
# ═══════════════════════════════════════════════════════

_PWSH_CACHE: list = [None]


def _translate_powershell_operators(command: str) -> str:
    """将 && 和 || 翻译为 PowerShell 5.1 兼容语法"""
    if '&&' not in command and '||' not in command:
        return command
    result = []
    i = 0
    n = len(command)
    in_dq = False
    in_sq = False
    depth = 0
    in_lc = False
    in_bc = False
    skip_one = False
    stop = False
    while i < n:
        ch = command[i]
        if skip_one:
            result.append(ch); i += 1; skip_one = False; continue
        if in_lc:
            result.append(ch); i += 1
            if ch == '\n': in_lc = False
            continue
        if in_bc:
            result.append(ch); i += 1
            if ch == '#' and i < n and command[i] == '>':
                result.append('>'); i += 1; in_bc = False
            continue
        if stop:
            result.append(ch); i += 1
            if ch == '\n': stop = False
            continue
        if i + 3 <= n and command[i:i+3] == '--%':
            result.append('--%'); i += 3; stop = True; continue
        if ch == '<' and i + 1 < n and command[i+1] == '#':
            result.append('<#'); i += 2; in_bc = True; continue
        if ch == '$' and i + 1 < n and command[i+1] == '(':
            result.append('$('); i += 2; depth += 1; continue
        if ch == ')' and depth > 0:
            result.append(ch); i += 1; depth -= 1; continue
        if ch == '#':
            result.append(ch); i += 1; in_lc = True; continue
        if ch == '`':
            result.append(ch); i += 1; skip_one = True; continue
        if ch == "'" and depth == 0:
            result.append(ch); i += 1; in_sq = not in_sq; continue
        if ch == '"' and depth == 0:
            result.append(ch); i += 1; in_dq = not in_dq; continue
        in_outer = not in_dq and not in_sq and depth == 0 and not in_lc and not in_bc and not stop
        if in_outer and command[i:i+2] == '&&':
            result.append('; $__ok=$?; if ($__ok) { ')
            i += 2; continue
        if in_outer and command[i:i+2] == '||':
            result.append('; $__ok=$?; if (-not $__ok) { ')
            i += 2; continue
        result.append(ch)
        i += 1
    translated = ''.join(result)
    if '; if ($__ok) { ' in translated or '; if (-not $__ok) { ' in translated:
        translated = '$__ok=$true; ' + translated
        translated = _close_if_blocks(translated)
    return translated


def _close_if_blocks(s: str) -> str:
    """为翻译后的 if 块补上闭合 }"""
    markers = ['; if ($__ok) { ', '; if (-not $__ok) { ']
    positions = []
    for marker in markers:
        start = 0
        while True:
            pos = s.find(marker, start)
            if pos == -1:
                break
            positions.append((pos, marker))
            start = pos + len(marker)
    positions.sort(key=lambda x: x[0], reverse=True)
    for pos, marker in positions:
        after = s[pos + len(marker):]
        next_block = len(after)
        for m in markers:
            p = after.find(m)
            if p != -1 and p < next_block:
                next_block = p
        insert_pos = pos + len(marker) + next_block
        s = s[:insert_pos] + ' }' + s[insert_pos:]
    return s


# ═══════════════════════════════════════════════════════
#  >重定向 UTF-8 转换（来自北京老陈 2026-06-30）
# ═══════════════════════════════════════════════════════

def _convert_redirect_to_utf8(command: str, cwd: Optional[str] = None) -> None:
    """Shell >重定向输出文件自动转为UTF-8"""
    target = _parse_redirect_path(command, cwd)
    if not target or not target.exists() or not target.is_file():
        return
    if target.stat().st_size > 1048576:
        return
    from app.tools.file.file_encoding import get_file_encoding
    result = get_file_encoding(str(target))
    encoding = result.get("data", {}).get("encoding", "") if result else ""
    if encoding in ("", "utf-8", "utf-8-sig", "ascii"):
        return
    try:
        with open(target, 'r', encoding=encoding, errors='replace') as f:
            content = f.read()
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)
        logger.info(f"[Shell] >重定向文件自动转UTF-8: {target} (原编码:{encoding})")
    except Exception as e:
        logger.warning(f"[Shell] >重定向文件转UTF-8失败: {target}: {e}")


def _parse_redirect_path(command: str, cwd: Optional[str] = None) -> Optional[Path]:
    """解析Shell命令中 >重定向的目标文件路径"""
    cleaned = re.sub(r'["\'][^"\']*["\']', '', command)
    m = re.search(r'(?<![<>])>(?!>)\s*(\S+)', cleaned)
    if not m:
        return None
    path_str = m.group(1)
    if '?' in path_str or '*' in path_str or '|' in path_str:
        return None
    p = Path(path_str)
    if not p.is_absolute():
        base = Path(cwd) if cwd else Path.cwd()
        p = base / p
    return p


# ═══════════════════════════════════════════════════════
#  llm_data 构建（来自小欧 2026-06-22）
# ═══════════════════════════════════════════════════════

def _build_execute_shell_command_llm_data(
    exec_code: str, duration_ms: int, command: str = "", returncode: int = 0,
    stdout_preview: str = "", stderr_preview: str = "", shell_type: str = "powershell",
    err_code: str = "", detail: str = "", timeout: int = 0, cwd: str = "",
    output_len: int = 0, stderr_len: int = 0, hint: str = "",
) -> Dict[str, Any]:
    """execute_shell_command 的 llm_data 构建函数 — 小欧 2026-07-05 新增hint"""
    cmd_short = (command[:60] + "..." + command[-37:]) if command and len(command) > 100 else (command[:100] if command else "")
    _act_params = {"command": cmd_short}
    if shell_type:
        _act_params["shell_type"] = shell_type
    if timeout:
        _act_params["timeout"] = timeout
    if cwd:
        _act_params["cwd"] = cwd
    if exec_code == "error":
        _detail = detail or (f"退出码{returncode}" if returncode is not None else "执行异常")
        return {
            "summary": f"执行Shell命令{cmd_short}，失败: {_detail}",
            "action": {"tool": "shell", "tool_zh": "执行", "target": cmd_short, "params": _act_params},
            "status": {"exec_code": "error", "message": "执行失败", "code": err_code or ERR_SHELL_EXEC, "detail": detail or (stderr_preview[:200] if stderr_preview else ""), "hint": hint if hint else "请检查命令语法和参数"},
            "duration_ms": duration_ms,
            "metrics": {},
        }
    if exec_code == "warning":
        _warn_msg = detail or f"退出码{returncode}，标准错误{stderr_len}字符"
        return {
            "summary": f"执行Shell命令{cmd_short}，部分成功,提示说明: {_warn_msg}",
            "action": {"tool": "shell", "tool_zh": "执行", "target": cmd_short, "params": _act_params},
            "status": {"exec_code": "warning", "message": "执行成功（有警告）", "code": err_code or "", "detail": "" if detail else f"退出码{returncode}，标准错误{stderr_len}字符", "hint": hint},
            "duration_ms": duration_ms,
            "metrics": {"exit_code": {"value": returncode, "text": f"退出码{returncode}"}},
        }
    return {
        "summary": f"执行Shell命令{cmd_short}，成功: 退出码{returncode}，输出{output_len}字符",
        "action": {"tool": "shell", "tool_zh": "执行", "target": cmd_short, "params": _act_params},
        "status": {"exec_code": "success", "message": "执行成功", "code": "", "detail": "", "hint": ""},
        "duration_ms": duration_ms,
        "metrics": {"exit_code": {"value": returncode, "text": f"退出码{returncode}"}},
    }


# ═══════════════════════════════════════════════════════
#  shell() — 主函数（v2 引擎版）
# ═══════════════════════════════════════════════════════

def shell(
    command: str, shell_type: Optional[str] = "powershell",
    timeout: int = 60, cwd: Optional[str] = None,
) -> Dict[str, Any]:
    """执行 Shell 命令（v2: 持久引擎版）

    参数:
        command:     PowerShell/CMD 命令
        shell_type:  "powershell"(默认) 或 "cmd"
        timeout:     超时秒数，默认 60，范围 1-600
        cwd:         工作目录绝对路径

    返回:
        build_success / build_error / build_warning 标准格式
        data: {stdout, stderr, returncode, shell_type, duration_ms}
        llm_data: 完整 status/metrics/summary
    """
    # ── 阶段 1: 参数校验 ──
    timeout_valid, timeout_err, _ = validate_timeout(timeout, "shell")
    t0 = _time_mod.perf_counter()

    if not timeout_valid:
        llm = _build_execute_shell_command_llm_data("error", 0, command, -1, "", "",
            shell_type or "", ERR_PARAMETER_INVALID, timeout_err,
            timeout=timeout, cwd=cwd or "", hint="请检查timeout参数")
        return build_error(data={}, llm_data=llm)

    if shell_type not in ("powershell", "cmd", None):
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command, -1, "", "",
            shell_type or "", ERR_PARAMETER_INVALID, "shell_type仅支持powershell/cmd",
            timeout=timeout, cwd=cwd or "", hint="shell_type仅支持powershell/cmd")
        return build_error(data={}, llm_data=llm)

    cmd = command.strip() if command else ""
    if not cmd:
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command, -1, "", "",
            shell_type or "", ERR_PARAMETER_EMPTY, "要执行的命令不能为空",
            timeout=timeout, cwd=cwd or "", hint="请提供要执行的命令")
        return build_error(data={}, llm_data=llm)

    if cwd is not None and not os.path.isdir(cwd):
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command, -1, "", "",
            shell_type or "", ERR_PARAMETER_INVALID, f"工作目录不存在: {cwd}",
            timeout=timeout, cwd=cwd or "", hint="请检查工作目录路径")
        return build_error(data={}, llm_data=llm)

    # ── 阶段 2: 安全检查 ──
    from app.tools.shell.execute_shell_command_safety import check_shell_command_risk
    safety = check_shell_command_risk(cmd)
    if safety and safety.blocked:
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command, -1, "", "",
            shell_type or "", ERR_SHELL_INJECTION, safety.message,
            timeout=timeout, cwd=cwd or "", hint="命令被安全规则拦截")
        return build_error(data={}, llm_data=llm)

    # ── 阶段 3: 执行 ──
    try:
        if shell_type == "powershell":
            if _PWSH_CACHE[0] is None:
                _PWSH_CACHE[0] = bool(shutil.which("pwsh.exe"))
            if not _PWSH_CACHE[0] and ('&&' in cmd or '||' in cmd):
                cmd = _translate_powershell_operators(cmd)

            from app.tools.shell.shell_engine import PersistentShell
            engine = PersistentShell.get_instance(cwd)
            result = engine.exec(cmd, timeout)
            stdout_str = result.get("stdout", "")
            stderr_str = result.get("stderr", "")
            returncode = result.get("exit_code", -1)
            timed_out = result.get("timed_out", False)

        else:  # cmd
            # 写入 temp .bat 执行，绕过 cmd.exe /c 的引号解析 bug — 小欧 2026-07-05
            import locale
            import tempfile
            # cmd.exe读.bat用的是系统OEM编码(中文Win=gbk)，utf-8写入会乱 — 小欧 2026-07-07
            bat_encoding = locale.getpreferredencoding()
            bat_fd, bat_path = tempfile.mkstemp(suffix='.bat', text=True)
            try:
                with os.fdopen(bat_fd, 'w', encoding=bat_encoding, errors='replace') as f:
                    f.write('@echo off\r\n')
                    f.write(cmd + '\r\n')
                    f.write('exit /b %errorlevel%\r\n')
                # 设PYTHONIOENCODING保证子Python进程输出中文不崩 — 小欧 2026-07-07
                # PYTHONUTF8=1让open()默认用UTF-8而非gbk,避免读UTF-8代码文件乱码 — 小欧 2026-07-07
                child_env = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"}
                proc = subprocess.Popen(
                    bat_path, shell=True, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, cwd=cwd, env=child_env,)
                timed_out = False
                try:
                    stdout_b, stderr_b = proc.communicate(timeout=timeout)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    proc.kill()
                    proc.wait(timeout=5)
                    stdout_b, stderr_b = b"", b""
            finally:
                try:
                    os.unlink(bat_path)
                except OSError:
                    pass
            stdout_str = _decode_bytes_safe(stdout_b)
            stderr_str = _decode_bytes_safe(stderr_b)
            returncode = proc.returncode if proc.returncode is not None else -1

        # ── 阶段 4: 后处理 ──
        if returncode == 0 and '>' in command:
            _convert_redirect_to_utf8(command, cwd)

        MAX_OUTPUT = 30000
        if len(stdout_str) > MAX_OUTPUT:
            stdout_str = stdout_str[:MAX_OUTPUT // 2] + "\n...[截断]...\n" + stdout_str[-MAX_OUTPUT // 2:]
        if len(stderr_str) > MAX_OUTPUT:
            stderr_str = stderr_str[:MAX_OUTPUT // 2] + "\n...[截断]...\n" + stderr_str[-MAX_OUTPUT // 2:]

        d = int((_time_mod.perf_counter() - t0) * 1000)
        data = {
            "stdout": stdout_str, "stderr": stderr_str,
        }

        # ── 阶段 5: 构建 build3 + llm_data ──
        if timed_out:
            llm = _build_execute_shell_command_llm_data("warning", d, command,
                returncode, stdout_str[:200], stderr_str[:200],
                shell_type or "", ERR_SHELL_TIMEOUT, f"命令执行超时({timeout}秒)",
                timeout=timeout, cwd=cwd or "", hint="可增大timeout参数重试")
            return build_warning(data=data, llm_data=llm)

        if returncode == 0:
            if stderr_str.strip():
                llm = _build_execute_shell_command_llm_data("warning", d, command,
                    returncode, stdout_str[:200], stderr_str[:200], shell_type or "",
                    timeout=timeout, cwd=cwd or "",
                    output_len=len(stdout_str), stderr_len=len(stderr_str))
                # ---- observation_formatter route -------------------------------------------
                # branch: #11 shell stdout
                # trigger: "stdout" in data — stdout/stderr/returncode/shell_type/duration_ms
                # handler: _format_shell_result(data)
                # file:    observation_formatter.py:180-182
                # ------------------------------------------------------------------------------
                return build_warning(data=data, llm_data=llm)
            llm = _build_execute_shell_command_llm_data("success", d, command,
                returncode, stdout_str[:200], stderr_str[:200], shell_type or "",
                timeout=timeout, cwd=cwd or "",
                output_len=len(stdout_str), stderr_len=len(stderr_str))
            # ---- observation_formatter route -------------------------------------------
            # branch: #11 shell stdout
            # trigger: "stdout" in data — stdout/stderr/returncode/shell_type/duration_ms
            # handler: _format_shell_result(data)
            # file:    observation_formatter.py:180-182
            # ------------------------------------------------------------------------------
            return build_success(data=data, llm_data=llm)

        err_detail = stderr_str[:200] if stderr_str.strip() else f"退出码{returncode}"
        llm = _build_execute_shell_command_llm_data("error", d, command,
            returncode, stdout_str[:200], stderr_str[:200],
            shell_type or "", ERR_SHELL_EXEC, err_detail,
            timeout=timeout, cwd=cwd or "", hint="请检查命令语法和参数")
        return build_error(data={}, llm_data=llm)

    except Exception as e:
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command, -1, "", "",
            shell_type or "", ERR_SHELL_EXCEPTION, str(e),
            timeout=timeout, cwd=cwd or "", hint="命令执行异常,请检查命令和系统环境")
        return build_error(data={}, llm_data=llm)
