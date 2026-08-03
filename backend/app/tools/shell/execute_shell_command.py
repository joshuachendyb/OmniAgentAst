# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-15 - 小欧 - 常量归一化治理: shell 输出超长截断改引用 tool_constants.SHELL_OUTPUT_MAX_CHARS(30000→20000), 功能零退化
# 2026-07-20 - 小欧 - 门限治理(shell章6.4): 删除 SHELL_OUTPUT_MAX_CHARS 头尾截断, stdout/stderr 原样全量返回(Tool输出零限制3.7); 显示限量收口 observation_formatter 行×列(OBS_SHELL_MAX_ROWS/CHARS)
# 2026-07-20 - 小欧 - 门限复查: data 仅 {stdout,stderr}(returncode/shell_type/duration_ms 归 llm_data); observation_formatter #11 不再重复渲染 meta(shell_type/duration_ms/rc), 改由 _format_llm_data 在 llm_data 段统一呈现(退出码/耗时/shell类型), 严禁 data 详情与 llm_data 段重复显示; #11 仅渲染 stdout/stderr 原始输出 + 两态截断说明
# 2026-07-20 - 小欧 - 门限复查: cmd 分支补 3.4 硬安全网(与 powershell 分支 safe_read_file 对称): 新增 _safe_truncate_output 对 proc.communicate() 内存输出超 SHELL_OUTLIMIT_RAW_BYTES 仅保留头尾各半, 防下游 OOM/序列化膨胀
# 2026-07-21 - 小欧 - #14 PS版本检测: _translate_powershell_operators 改为无条件执行（删 not _PWSH_CACHE[0] 条件）
# 2026-07-23 - 小欧 - 北京老陈驱动: 新增 _truncate_shell_field
#         head-only+行边界截断(stdout=50000/stderr=20000);
#         tool_constants 新增 SHELL_OUTLIMIT_STDOUT_MAX_CHARS
#         /SHELL_OUTLIMIT_STDERR_MAX_CHARS;
#         formatter #11 读 _truncated 标记;
#         storage MAX_TOOL_RESULT_STR_LEN 提至100000;
# 2026-07-23 - 小欧 - 北京老陈驱动BugFix: output_len 传原始截断前长度而非截断后长度(bug1), 避免 LLM 被误导
# 2026-07-23 - 小欧 - 北京老陈驱动: 删 _safe_truncate_output(10MB 字节截断多余), 改直接 _decode_bytes_safe; 删 SHELL_OUTLIMIT_RAW_BYTES import; tool 层仅保留 _truncate_shell_field 50K/20K 唯一输出截断
# 2026-07-23 - 小欧 - #5 ERR_SHELL_EXEC 退出码释义映射: stderr/stdout全空时返回"退出码127(命令未找到)"等释义, 非纯数字
# 2026-07-24 - 小欧 - 北京老陈驱动BugFix:
#         _build_execute_shell_command_llm_data 重构:
#         问题: ① error分支summary直接嵌入完整_detail(可达20K stderr全文)
#             → LLM观察中"观察:"行与"✖ 错误:"行重复大段内容
#         ② warning分支hint硬编码为""，timeout的详细hint被静默丢失
#         ③ 三分支(提前返回)每次各自拼接param+调_build，代码冗余
#         修复:
#         ① 删stdout_preview/stderr_preview两个参数(YAGNI，截断不在函数内做)
#         ② error分支summary改为从_detail取第一行截断60字符(不再嵌入完整detail)
#         ③ error分支status.detail从stderr_preview[:200]改为_detail(完整detail)
#         ④ warning分支status.hint从""改为透传hint参数(timeout hint不再丢失)
#         ⑤ shell() phase5三分支合并为统一_exec_code+_detail+_hint变量+单次_build调用
#         ⑥ timeout用ERR_SHELL_TIMEOUT错误码+full detail(含超时秒数)
#         ⑦ stderr warning用_stderr_orig_len(截断前长度)替代stderr_str[:200]预览
#         ⑧ error用完整stderr_str/stdout_str(截断后全文)替代stderr_str[:200]预览

# 2026-07-25 - 小欧 - 截断治理: cmd_short签名移至末尾(不破坏positional传参, 保持向后兼容); main函数入口构造cmd_short + 8处传参cmd_short=cmd_short;  45行cmd_short内部fallback保留
# 2026-07-25 - 小欧 - 三堂会审修复bug×5:
#         ① fallback硬编码command[:35]/[-15:]/[:50]→改用EXECUTE_SHELL_OUTPARM_LIMIT_CMD常量
#         ② main缩写条件len>50→>_cmd_limit（防常量改后阈值不同步）
#         ③ tail=15硬编码→模块级_SHELL_CMD_TAIL常量
#         ④ head从原50(=命令总预览)修复为35(=50-15), 恢复35+15=50原内容预算(原main错误改为50+15=65超预算)
#         ⑤ build函数cmd_short删fallback+加assert强制传参(禁止backward: 保留默认值""因Python参数顺序约束, assert拦截不传参旧调用)
# 2026-07-25 - 小欧 - summary去stderr关联: error分支summary不再嵌_err_summary, summary纯摘要不拖detail; 删truncate_summary import
# 2026-07-25 - 小欧 - cmd_short改keyword-only强制传参: 删`=""`默认值+`*,`分隔, Python解释器级别强制传参(禁止backward彻底贯彻); 删assert因不再需要
# 2026-07-26 - 小沈 - 欧阳报告: 新增_auto_fix_powershell_syntax自动修复块内.Property→$_.Property(阶段1.5)
# 2026-07-27 - 小欧 - CMD增强: _resolve_safe_cwd安全回退+tempdir保底; CMD分支poll loop代替communicate阻塞; taskkill /T /F杀进程树; 阶段标注【PS专属|CMD专属|通用】; _auto_fix_cmd_syntax修复$env:VAR→%VAR%; _sanitize_env过滤API key泄露子进程
# 2026-07-27 - 小欧 - Bugfix×5: _close_if_blocks嵌套花括号深度计数; warning分支detail字段逻辑取反; bat_path加引号防空格; _PWSH_CACHE死代码删除; 阶段1.5重复执行消除
# 2026-07-27 - 小欧 - 重构: _sanitize_env常量提为模块级; cwd不存在改报错为自动回退; PS分支engine.exec传env=_sanitize_env()
# 2026-07-28 - 小欧 - 欧阳task005一轮修复4bug: BUG-03截断前存_stderr_for_diag; BUG-05删command死参数; BUG-06删_PWSH_CACHE死代码; BUG-07删cwd回退外层重复日志
# 2026-07-28 - 小欧 - 欧阳task005二轮修复4bug: BUG-02 CMD超时改立即杀进程; BUG-04深度计数简化为存在性检查; BUG-08良性stderr白名单扩展; BUG-09 safety检查传shell_type
# 2026-07-28 - 小欧 - 抽取 _kill_and_read_output 消除CMD超时两处重复代码
#         _close_if_blocks 改用深度计数+引号感知, 避免字符串内}误判
#         _cmd_powershell_mismatch_hint 补充英文匹配, 兼容非中文系统
# 2026-07-28 - 小欧 - shell_type名称改为ps7/ps5/cmd/bash; 默认ps7; 新增bash执行分支+_find_bash; 新增_auto_fix_bash_syntax;
#         _cmd_powershell_mismatch_hint→_shell_mismatch_hint全面覆盖4种shell; 路由4路分支; 语法修复4路; ps7不翻译&&(BUG#2)
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
       ├── shell_type in ("ps7","ps5") ────────────────────────────
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
       ├── shell_type="cmd" ─────────────────────────────────────
       │   │
       │   ├── [入] .bat文件写入 locale.getpreferredencoding()
       │   │   2026-07-07 小欧 修复
       │   │   改为gbk匹配cmd.exe OEM代码页,避免中文乱码
       │   │   (原用utf-8写, cmd.exe按gbk读,中文全乱)
       │   │
       │   ├── [子进程] env={PYTHONIOENCODING=utf-8, PYTHONUTF8=1}
       │   │   2026-07-07 小欧 修复
       │   │   PYTHONIOENCODING: print()输出中文不崩
       │   │   PYTHONUTF8=1: open()默认用UTF-8避免gbk误读
       │   │
       │   └── [出] proc.communicate() → _decode_bytes_safe()
       │       utf-8优先(gbk回退, latin-1兜底)
       │       Python子进程(PYTHONIOENCODING)输出UTF-8直接命中
       │
       └── shell_type="bash" ────────────────────────────────────
           │
           ├── [入] subprocess.Popen 直接传递命令字符串
           │    使用 -l 登录 shell, 自动加载 .bashrc
           │
           ├── [子进程] env 同主进程(无需设置PYTHONIOENCODING)
           │    Git Bash: /usr/bin/bash.exe
           │    WSL: /bin/bash (通过 WindowsApps 代理)
           │
           └── [出] proc.communicate() → _decode_bytes_safe()
               stdout/stderr 以 UTF-8 解码


┌────────────────────────────────────────────────────────────────┐
│  附: 系统级编码加固 (2026-07-07 小欧)                           │
├────────────────────────────────────────────────────────────────┤
│  main.py: sys.stdout.reconfigure(encoding='utf-8')             │
│    → 服务进程本身stdout设UTF-8, 日志/print中文不乱             │
└────────────────────────────────────────────────────────────────┘


【v2 改造】
  - ps7/ps5 分支改用 PersistentShell 持久引擎
  - 删除 run_in_background / _background_shells / shell_session
  - 保留 build3 + llm_data 体系不变

铁规1: helper 函数不碰 build3，只在 shell() 主函数包装
铁规2: 工具返回原始 data，前端截断在前端 yield 层
铁规3: 计时仅在 shell() 主函数
"""
# 小欧 - 2026-07-15: 新增success_codes参数+退出码判断改为`==0 or in`追加式,0永远成功
import locale
import os
import re
import shutil
import subprocess
import tempfile
import time as _time_mod
from pathlib import Path
from typing import Any, Dict, Optional, Literal

from app.tools.file.file_encoding import get_file_encoding
from app.tools.shell.execute_shell_command_safety import check_shell_command_risk
from app.tools.shell.shell_engine import PersistentShell
from app.tools.tool_response import build_success, build_error, build_warning
from app.tools.tool_fc_helper import _decode_bytes_safe
from app.tools.validate.timeout_validator import validate_timeout
from app.logger import logger

from app.tools.tool_constants import (
    ERR_PARAMETER_EMPTY, ERR_PARAMETER_INVALID,
    ERR_SHELL_EXCEPTION, ERR_SHELL_EXEC,
    ERR_SHELL_INJECTION, ERR_SHELL_TIMEOUT,
    EXECUTE_SHELL_OUTPARM_LIMIT_CMD,
    SHELL_OUTLIMIT_STDOUT_MAX_CHARS,
    SHELL_OUTLIMIT_STDERR_MAX_CHARS,
    SUBPROCESS_TIMEOUT_SHORT,
)


# ── 敏感环境变量过滤常量 — 小欧 2026-07-27 ──
_STATIC_BLOCK = frozenset({
    "OPENAI_API_KEY", "ANTHROPIC_API_KEY", "ANTHROPIC_TOKEN",
    "AZURE_OPENAI_API_KEY", "GOOGLE_API_KEY", "DEEPSEEK_API_KEY",
    "MISTRAL_API_KEY", "GROQ_API_KEY", "TOGETHER_API_KEY",
    "PERPLEXITY_API_KEY", "COHERE_API_KEY", "FIREWORKS_API_KEY",
    "XAI_API_KEY", "OPENROUTER_API_KEY",
    "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_SESSION_TOKEN",
    "GH_TOKEN", "GITHUB_TOKEN",
})
_DYNAMIC_SUFFIXES = ("_API_KEY", "_TOKEN", "_SECRET", "_PASSWORD")


def _sanitize_env(base_env: Optional[Dict[str, str]] = None) -> Dict[str, str]:
    """过滤子进程环境变量, 移除API key等敏感变量 — 小欧 2026-07-27

    - 静态块列表: 已知LLM/KB服务API key
    - 动态匹配: *_API_KEY / *_TOKEN / *_SECRET (以免遗漏自定义provider)
    返回过滤后拷贝, 不影响原dict。
    """
    src = base_env or dict(os.environ)
    result: Dict[str, str] = {}
    for k, v in src.items():
        if k.upper() in _STATIC_BLOCK:
            logger.debug(f"[Shell] 过滤敏感env: {k}")
            continue
        if any(k.upper().endswith(suf) for suf in _DYNAMIC_SUFFIXES):
            logger.debug(f"[Shell] 过滤敏感env(动态): {k}")
            continue
        result[k] = v
    return result


# ── cmd_short 缩写常量（头部字数 = 总预算 - 尾部保留） ──
_SHELL_CMD_TAIL = 15
_SHELL_CMD_HEAD = EXECUTE_SHELL_OUTPARM_LIMIT_CMD - _SHELL_CMD_TAIL

# ═══════════════════════════════════════════════════════
#  CWD 安全回退（参考 Hermes _resolve_safe_cwd）
# ═══════════════════════════════════════════════════════


def _resolve_safe_cwd(cwd: str) -> str:
    """cwd不存在时沿路径上溯找第一个存在的目录, 全不可达则回退临时目录 — 小欧 2026-07-27

    保证始终返回非空字符串, 调用方无需判断None。"""
    if cwd and os.path.isdir(cwd):
        return cwd
    parent = os.path.dirname(cwd) if cwd else ""
    while parent:
        if os.path.isdir(parent):
            logger.warning(f"[Shell] cwd不存在, 回退: {cwd} → {parent}")
            return parent
        next_parent = os.path.dirname(parent)
        if next_parent == parent:
            break
        parent = next_parent
    logger.warning(f"[Shell] cwd不存在且无可用上级目录, 回退临时目录: {cwd} → {tempfile.gettempdir()}")
    return tempfile.gettempdir()


# ═══════════════════════════════════════════════════════
#  PowerShell 5.1 &&/|| 翻译（来自小沈 2026-07-05）
# ═══════════════════════════════════════════════════════


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
        if ch == '`':
            result.append(ch); i += 1; skip_one = True; continue
        if ch == "'" and depth == 0:
            result.append(ch); i += 1; in_sq = not in_sq; continue
        if ch == '"' and depth == 0:
            result.append(ch); i += 1; in_dq = not in_dq; continue
        if ch == '#' and not in_dq and not in_sq and depth == 0:
            result.append(ch); i += 1; in_lc = True; continue
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
    """为翻译后的if块补上闭合} — 深度计数+引号感知(避免字符串字面量中的}误判) — 小欧 2026-07-28"""
    markers = ['; if ($__ok) { ', '; if (-not $__ok) { ']
    poses = []
    for marker in markers:
        pos = 0
        while True:
            pos = s.find(marker, pos)
            if pos == -1:
                break
            poses.append(pos)
            pos += len(marker)
    poses.sort(reverse=True)
    for pos in poses:
        marker = next(m for m in markers if s[pos:pos + len(m)] == m)
        after = s[pos + len(marker):]
        end = len(after)
        for m in markers:
            p = after.find(m)
            if p != -1 and p < end:
                end = p
        depth = 0
        has_closing = False
        in_str = None
        for ch in after[:end]:
            if in_str:
                if ch == in_str:
                    in_str = None
            else:
                if ch in ('"', "'"):
                    in_str = ch
                elif ch == '{':
                    depth += 1
                elif ch == '}':
                    if depth == 0:
                        has_closing = True
                        break
                    depth -= 1
        if not has_closing:
            s = s[:pos + len(marker) + end] + ' }' + s[pos + len(marker) + end:]
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
    """解析Shell命令中 >/>> 重定向的目标文件路径"""
    cleaned = re.sub(r'["\'][^"\']*["\']', '', command)
    m = re.search(r'(?<![<>])>+\s*(\S+)', cleaned)
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
    shell_type: str = "ps7",
    err_code: str = "", detail: str = "", timeout: int = 0, cwd: str = "",
    output_len: int = 0, stderr_len: int = 0, hint: str = "",
    *,
    cmd_short: str,
) -> Dict[str, Any]:
    """execute_shell_command 的 llm_data 构建函数
    cmd_short: 命令预览（由调用者构造传入）"""
    logger.debug(f"[Shell] _build llm: cmd_len={len(command)}, exec_code={exec_code}, rc={returncode}")
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
            "summary": f"执行Shell命令{cmd_short}，失败",
            "action": {"tool": "shell", "tool_zh": "执行", "target": cmd_short, "params": _act_params},
            "status": {"exec_code": "error", "message": "执行失败", "code": err_code or ERR_SHELL_EXEC, "detail": _detail, "hint": hint if hint else "请检查命令语法和参数"},
            "duration_ms": duration_ms,
            "metrics": {"exit_code": {"value": returncode, "text": f"退出码{returncode}"}},
        }
    if exec_code == "warning":
        _warn_msg = detail or f"退出码{returncode}，标准错误{stderr_len}字符"
        return {
            "summary": f"执行Shell命令{cmd_short}，部分成功,提示说明: {_warn_msg}",
            "action": {"tool": "shell", "tool_zh": "执行", "target": cmd_short, "params": _act_params},
            "status": {"exec_code": "warning", "message": "执行成功（有警告）", "code": err_code or "", "detail": detail or f"退出码{returncode}，标准错误{stderr_len}字符", "hint": hint},
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


def _fix_encoding(text: str) -> str:
    """编码修复：检测并修复中文乱码 — 小沈 2026-07-08  — 北京老陈 2026-07-09 修复:去掉CJK双通道检测(会产生误报)"""
    if not text:
        return text
    try:
        text.encode('utf-8')
        return text
    except UnicodeEncodeError:
        for enc in ('gbk', 'gb2312', 'latin-1'):
            try:
                return text.encode('latin-1').decode(enc)
            except (UnicodeEncodeError, UnicodeDecodeError):
                continue
        return text


# 注意: OBS_SHELL_MAX_ROWS×OBS_SHELL_MAX_ROW_CHARS=200K
#       展示上限, tool截断50K目前保守对齐,
#       试用后再视需调整(北京老陈 2026-07-23)
def _truncate_shell_field(text: str, max_chars: int) -> tuple[str, bool]:
    """shell 工具输出截断(head-only+行边界): 超 max_chars 保留文首至最近行尾, 末尾追加截断说明 — 小欧 2026-07-23
    注意: OBS_SHELL_MAX_ROWS(200)×OBS_SHELL_MAX_ROW_CHARS(1000)=200K 是formatter展示上限;
          tool截断50K(stdout)/20K(stderr)为存储保护值, 低于展示上限; 试用后按需调整(北京老陈 2026-07-23)"""
    if len(text) <= max_chars:
        return text, False
    cut = text[:max_chars].rfind('\n')
    if cut <= 0:
        cut = max_chars
    head = text[:cut]
    note = f"\n...[shell输出截断: 原文{len(text)}字符, 保留{cut}字符]...\n"
    return head + note, True


# 已知良性stderr模式白名单（不触发warning）— 小欧 2026-07-08
_BENIGN_STDERR_PATTERNS = [
    "Non-authoritative answer",
    "DeprecationWarning",
    "UserWarning",
    "FutureWarning",
    "Info:",
    "Note:",
]

def _filter_benign_stderr(stderr: str) -> str:
    """过滤已知良性stderr行 — 小欧 2026-07-08"""
    if not stderr:
        return ""
    lines = stderr.splitlines()
    filtered = [l for l in lines if not any(p in l for p in _BENIGN_STDERR_PATTERNS)]
    return "\n".join(filtered)


def _shell_mismatch_hint(shell_type: str, stderr: str) -> str:
    """检测shell语法混用，返回针对性hint — 小欧 2026-07-28"""
    _not_found = r'(不是内部或外部命令|不是可运行的程序|not recognized|not an internal|is not recognized|not a valid command|command not found)'
    if not re.search(_not_found, stderr, re.IGNORECASE):
        return ""
    if shell_type == "cmd":
        return "命令可能包含PowerShell语法，建议设置shell_type='ps7'或shell_type='ps5'"
    elif shell_type in ("ps7", "ps5"):
        return "命令可能包含CMD语法，建议设置shell_type='cmd'"
    elif shell_type == "bash":
        return "命令可能包含Windows本地语法，建议设置shell_type='ps7'或shell_type='cmd'"
    return ""


def _auto_fix_cmd_syntax(command: str) -> str:
    """自动修复LLM生成的CMD命令中已知错误模式 — 小欧 2026-07-27

    当前覆盖：
    - $env:VAR → %VAR%（LLM常把PS环境变量语法带到CMD）"""
    if not command:
        return command
    fixed = re.sub(r'\$env:(\w+)', r'%\1%', command)
    if fixed != command:
        logger.warning(f"[Shell] 自动修复CMD语法: $env:VAR→%VAR%, cmd={command[:100]}")
        return fixed
    return command


def _auto_fix_powershell_syntax(command: str) -> str:
    """自动修复LLM生成的PowerShell命令中已知错误模式 — 小沈 2026-07-26

    当前覆盖：
    - 脚本块{...}内 .Property → $_.Property（LLM常漏写$_）"""
    if not command:
        return command
    # { .Property → { $_.Property (花括号开头的.缺$_)
    # 必须排除 {{.Name}} 转义双花括号(模板语法),用(?<!\{)\{(?!\{)确保仅匹配单{ — 小沈 2026-07-26
    if re.search(r'(?<!\{)\{(?!\{)\s*\.\w+', command):
        fixed = re.sub(r'(?<!\{)\{(?!\{)\s*\.(\w+)', r'{ $_.\1', command)
        if fixed != command:
            logger.warning(f"[Shell] 自动修复PS语法: 块内.Property→$_.Property, cmd={command[:100]}")
            return fixed
    return command


def _auto_fix_bash_syntax(command: str) -> str:
    """自动修复LLM生成的Bash命令中已知错误模式 — 小欧 2026-07-28

    当前覆盖：
    - python3 → python（仅Windows，本机无python3命令）"""
    if not command or sys.platform != "win32":
        return command
    fixed = re.sub(r'\bpython3\b', 'python', command)
    if fixed != command:
        logger.warning(f"[Shell] 自动修复bash语法: python3→python, cmd={command[:100]}")
        return fixed
    return command


def _find_bash() -> Optional[str]:
    """查找可用bash解释器（Git Bash->bin/bash.exe, 其次PATH中的bash, 最后SHELL环境变量中找bash）— 小欧 2026-07-28"""
    git = shutil.which("git")
    if git:
        git_bash = os.path.join(os.path.dirname(os.path.dirname(git)), "bin", "bash.exe")
        if os.path.isfile(git_bash):
            return git_bash
    path_bash = shutil.which("bash")
    if path_bash:
        return path_bash
    shell_env = os.environ.get("SHELL")
    if shell_env and os.path.isfile(shell_env) and 'bash' in os.path.basename(shell_env).lower():
        return shell_env
    return None


# ═══════════════════════════════════════════════════════
#  _kill_and_read_output — 超时后杀进程+读残存输出 (DRY抽取)
# ═══════════════════════════════════════════════════════

def _kill_and_read_output(proc: subprocess.Popen) -> tuple[bytes, bytes]:
    """CMD超时后 杀进程树 + 等退出 + 读残存 stdout/stderr — 小欧 2026-07-28"""
    try:
        subprocess.run(
            ["taskkill", "/T", "/F", "/PID", str(proc.pid)],
            capture_output=True, timeout=SUBPROCESS_TIMEOUT_SHORT,
        )
    except Exception:
        proc.kill()
    proc.wait(timeout=SUBPROCESS_TIMEOUT_SHORT)
    try:
        stdout_b = proc.stdout.read() if proc.stdout else b""
    except Exception:
        stdout_b = b""
    try:
        stderr_b = proc.stderr.read() if proc.stderr else b""
    except Exception:
        stderr_b = b""
    return stdout_b, stderr_b


# ═══════════════════════════════════════════════════════
#  shell() — 主函数（v2 引擎版）
# ═══════════════════════════════════════════════════════

def shell(
    command: str, shell_type: Literal["ps7", "ps5", "cmd", "bash", None] = "ps7",
    timeout: int = 60, cwd: Optional[str] = None,
    success_codes: Optional[list[int]] = None,
) -> Dict[str, Any]:
    """执行 Shell 命令（v2: 持久引擎版）

    参数:
        command:     命令字符串
        shell_type:  "ps7"(默认), "ps5", "cmd" 或 "bash"
        timeout:     超时秒数，默认 60，范围 1-600
        cwd:         工作目录绝对路径

    返回:
        build_success / build_error / build_warning 标准格式
        data: {stdout, stderr}（原始输出; returncode/shell_type/duration_ms 仅在 llm_data, 不在 data）
        llm_data: 完整 status/metrics/summary（含 returncode/exit_code、shell_type、duration_ms）
    """
    # ── 阶段 1【通用】: 参数校验 ──
    timeout_valid, timeout_err, _ = validate_timeout(timeout, "shell")
    t0 = _time_mod.perf_counter()
    _cmd_limit = EXECUTE_SHELL_OUTPARM_LIMIT_CMD
    cmd_short = (command[:_SHELL_CMD_HEAD] + "..." + command[-_SHELL_CMD_TAIL:]) if command and len(command) > _cmd_limit else (command[:_cmd_limit] if command else "(空命令)")

    if not timeout_valid:
        llm = _build_execute_shell_command_llm_data("error", 0, command, -1,
            shell_type or "", ERR_PARAMETER_INVALID, timeout_err,
            timeout=timeout, cwd=cwd or "", hint="请检查timeout参数", cmd_short=cmd_short)
        return build_error(data={}, llm_data=llm)

    if shell_type not in ("ps7", "ps5", "cmd", "bash", None):
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command, -1,
            shell_type or "", ERR_PARAMETER_INVALID, "shell_type仅支持ps7/ps5/cmd/bash",
            timeout=timeout, cwd=cwd or "", hint="shell_type仅支持ps7/ps5/cmd/bash", cmd_short=cmd_short)
        return build_error(data={}, llm_data=llm)

    cmd = command.strip() if command else ""
    if not cmd:
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command, -1,
            shell_type or "", ERR_PARAMETER_EMPTY, "要执行的命令不能为空",
            timeout=timeout, cwd=cwd or "", hint="请提供要执行的命令", cmd_short=cmd_short)
        return build_error(data={}, llm_data=llm)

    if "\x00" in (command or ""):
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, -1,
            shell_type or "", ERR_PARAMETER_INVALID, "命令包含空字符(null byte),拒绝执行",
            timeout=timeout, cwd=cwd or "", hint="命令不能包含空字符(null byte)", cmd_short=cmd_short)
        return build_error(data={}, llm_data=llm)

    if cwd and not os.path.isdir(cwd):
        cwd = _resolve_safe_cwd(cwd)

    # ── 阶段 1.5【PS7/PS5专属】: 语法自动修复 — 小沈 2026-07-26, 小欧 2026-07-27 ──
    if shell_type in ("ps7", "ps5") or shell_type is None:
        _fixed = _auto_fix_powershell_syntax(cmd)
        if _fixed != cmd:
            cmd = _fixed

    # ── 阶段 1.6【CMD专属】: 语法自动修复 — 小欧 2026-07-27 ──
    if shell_type == "cmd":
        _fixed = _auto_fix_cmd_syntax(cmd)
        if _fixed != cmd:
            cmd = _fixed

    # ── 阶段 1.7【bash专属】: 语法自动修复 — 小欧 2026-07-28 ──
    if shell_type == "bash":
        _fixed = _auto_fix_bash_syntax(cmd)
        if _fixed != cmd:
            cmd = _fixed

    # ── 阶段 2【通用】: 安全检查 ──
    safety = check_shell_command_risk(cmd, shell_type or "ps7")
    if safety:
        d = int((_time_mod.perf_counter() - t0) * 1000)
        if safety.blocked:
            llm = _build_execute_shell_command_llm_data("error", d, -1,
                shell_type or "", ERR_SHELL_INJECTION, safety.message,
                timeout=timeout, cwd=cwd or "", hint="命令被安全规则拦截", cmd_short=cmd_short)
            return build_error(data={}, llm_data=llm)
        if safety.requires_confirmation:
            logger.warning(f"[Shell] 中风险命令已放行（需用户确认）: {safety.message}")

    # ── 阶段 3【PS/CMD分支】: 执行 ──
    try:
        if shell_type in ("ps7", "ps5") or shell_type is None:  # ── 【PS7/PS5专属】: 持久进程引擎; None视为ps7 — 小欧 2026-07-28 ──
            # BUG#2修复: ps7原生支持&&, 不需要翻译; ps5需要翻译&&→;if($?){cmd2} — 小欧 2026-07-28
            if shell_type == "ps5":
                cmd = _translate_powershell_operators(cmd)
            # Format-Table输出追加Out-String -Width 4096，避免PS5.1默认80列截断 — 小欧 2026-07-08
            if re.search(r'(?i)(?:^|\|)\s*Format-Table\b', cmd):
                cmd += " | Out-String -Width 4096"

            engine = PersistentShell.get_instance(cwd, shell_type)
            result = engine.exec(cmd, timeout, env=_sanitize_env())
            stdout_str = _fix_encoding(result.get("stdout", ""))
            stderr_str = _fix_encoding(result.get("stderr", ""))
            returncode = result.get("exit_code", -1)
            timed_out = result.get("timed_out", False)

        elif shell_type == "cmd":  # ── 【CMD专属】: .bat + subprocess ──
            # 写入 temp .bat 执行，绕过 cmd.exe /c 的引号解析 bug — 小欧 2026-07-05
            # cmd.exe读.bat用的是系统OEM编码(中文Win=gbk)，utf-8写入会乱 — 小欧 2026-07-07
            bat_encoding = locale.getpreferredencoding()
            bat_fd, bat_path = tempfile.mkstemp(suffix='.bat', text=True)
            try:
                with os.fdopen(bat_fd, 'w', encoding=bat_encoding, errors='replace') as f:
                    f.write('@echo off\r\n')
                    f.write(cmd + '\r\n')
                    f.write('exit /b %errorlevel%\r\n')
                child_env = _sanitize_env()
                child_env.update({"PYTHONIOENCODING": "utf-8", "PYTHONUTF8": "1"})
                proc = subprocess.Popen(
                    f'"{bat_path}"', shell=True, stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE, cwd=cwd, env=child_env,)
                timed_out = False
                try:
                    # poll loop代替communicate(timeout): 防止start /b子进程持管道
                    # 导致communicate挂满整个timeout — 参考Hermes _wait_for_process, 2026-07-27 小欧
                    _deadline = _time_mod.time() + timeout
                    _poll_sleep = 0.1
                    while _time_mod.time() < _deadline and proc.poll() is None:
                        _time_mod.sleep(min(_poll_sleep, max(0, _deadline - _time_mod.time())))
                        _poll_sleep = min(_poll_sleep * 2, 1.0)
                    if proc.poll() is None:
                        timed_out = True
                        stdout_b, stderr_b = _kill_and_read_output(proc)
                    else:
                        stdout_b, stderr_b = proc.communicate(timeout=SUBPROCESS_TIMEOUT_SHORT)
                except subprocess.TimeoutExpired:
                    timed_out = True
                    stdout_b, stderr_b = _kill_and_read_output(proc)
            finally:
                try:
                    os.unlink(bat_path)
                except OSError:
                    pass
            stdout_str = _fix_encoding(_decode_bytes_safe(stdout_b))
            stderr_str = _fix_encoding(_decode_bytes_safe(stderr_b))
            returncode = proc.returncode if proc.returncode is not None else -1

        else:  # ── 【bash专属】: subprocess + 登录shell ──
            bash_exe = _find_bash()
            if not bash_exe:
                d = int((_time_mod.perf_counter() - t0) * 1000)
                llm = _build_execute_shell_command_llm_data("error", d, -1,
                    shell_type or "", ERR_SHELL_EXCEPTION, "bash解释器未找到(Git Bash/WSL)",
                    timeout=timeout, cwd=cwd or "", hint="请检查Git Bash或WSL是否安装", cmd_short=cmd_short)
                return build_error(data={}, llm_data=llm)
            child_env = _sanitize_env()
            proc = subprocess.Popen(
                [bash_exe, "-l", "-c", cmd],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                cwd=cwd, env=child_env,
            )
            timed_out = False
            try:
                stdout_b, stderr_b = proc.communicate(timeout=timeout)
            except subprocess.TimeoutExpired:
                timed_out = True
                stdout_b, stderr_b = _kill_and_read_output(proc)
            stdout_str = _fix_encoding(_decode_bytes_safe(stdout_b))
            stderr_str = _fix_encoding(_decode_bytes_safe(stderr_b))
            returncode = proc.returncode if proc.returncode is not None else -1

        # ── 阶段 4【通用】: 后处理(UTF-8 编码修复) ──
        # 小欧 2026-07-20: 依 3.7 铁律删除 SHELL_OUTPUT_MAX_CHARS 头尾截断; 工具输出截断收口于阶段 4.5(50K/20K) — 2026-07-23 小欧更新
        if returncode == 0 and '>' in command:
            _convert_redirect_to_utf8(command, cwd)

        d = int((_time_mod.perf_counter() - t0) * 1000)
        # ── 阶段 4.5【通用】: Tool 输出截断 — 小欧 2026-07-23 ──
        _stdout_orig_len = len(stdout_str)
        _stderr_orig_len = len(stderr_str)
        _stderr_for_diag = stderr_str[:2000] if len(stderr_str) > 2000 else stderr_str  # 截断前保存原始值用于诊断(如PS/CMD混用检测) — 小欧 2026-07-28
        stdout_str, stdout_trunc = _truncate_shell_field(stdout_str, SHELL_OUTLIMIT_STDOUT_MAX_CHARS)
        stderr_str, stderr_trunc = _truncate_shell_field(stderr_str, SHELL_OUTLIMIT_STDERR_MAX_CHARS)
        data: Dict[str, Any] = {
            "stdout": stdout_str, "stderr": stderr_str,
        }
        if stdout_trunc or stderr_trunc:
            data["_truncated"] = True

        # ── 阶段 5【通用】: 构建 llm_data（截断已由阶段4.5统一处理，此处只判定状态+构建detail+调1次）
        _EXIT_CODE_MEANING = {
            1: "通用错误", 2: "命令语法错误", 3: "配置错误",
            5: "拒绝访问", 127: "命令未找到", 9009: "命令未找到(cmd)",
            3221225786: "程序崩溃(STATUS_DATATYPE_MISALIGNMENT)",
        }
        _exec_code = "success"
        _err_code = ""
        _detail = ""
        _hint = ""

        if timed_out:
            _exec_code = "warning"
            _err_code = ERR_SHELL_TIMEOUT
            _detail = f"命令执行超时({timeout}秒)"
            _hint = "命令执行超时，建议: 1. 增大timeout参数 2. 简化命令 3. 分步执行"
        elif returncode == 0 or returncode in (success_codes or []):
            stderr_clean = stderr_str.strip()
            if stderr_clean:
                benign_filtered = _filter_benign_stderr(stderr_str)
                if not benign_filtered.strip():
                    data["stderr"] = ""
                else:
                    _exec_code = "warning"
                    _detail = f"退出码{returncode}，标准错误{_stderr_orig_len}字符"
        else:
            _exec_code = "error"
            _err_code = ERR_SHELL_EXEC
            _detail = (stderr_str if stderr_str.strip()
                       else (stdout_str if stdout_str.strip()
                             else f"退出码{returncode}({_EXIT_CODE_MEANING.get(returncode, '未知错误')})"))
            if stderr_str.strip():
                if re.search(r"(command not found|not recognized|'[^']+' is not recognized)", stderr_str, re.IGNORECASE):
                    _detail = f"[命令未找到] {_detail}"
                elif re.search(r"(syntax error|语法错误|parse error|unexpected token)", stderr_str, re.IGNORECASE):
                    _detail = f"[语法错误] {_detail}"
                elif re.search(r"(permission denied|access denied|拒绝访问|elevated)", stderr_str, re.IGNORECASE):
                    _detail = f"[权限错误] {_detail}"
            _hint = _shell_mismatch_hint(shell_type, _stderr_for_diag) or "请检查命令语法和参数"

        # 只调 1 次 _build_..._llm_data
        llm = _build_execute_shell_command_llm_data(
            _exec_code, d, returncode,
            shell_type or "", _err_code, _detail,
            timeout=timeout, cwd=cwd or "",
            output_len=_stdout_orig_len, stderr_len=_stderr_orig_len, hint=_hint,
            cmd_short=cmd_short,
        )
        if _exec_code == "error":
            return build_error(data=data, llm_data=llm)
        if _exec_code == "warning":
            return build_warning(data=data, llm_data=llm)
        return build_success(data=data, llm_data=llm)

    except Exception as e:
        d = int((_time_mod.perf_counter() - t0) * 1000)
        llm = _build_execute_shell_command_llm_data("error", d, command, -1,
            shell_type or "", ERR_SHELL_EXCEPTION, str(e),
            timeout=timeout, cwd=cwd or "", hint="命令执行异常,请检查命令和系统环境", cmd_short=cmd_short)
        return build_error(data={}, llm_data=llm)
