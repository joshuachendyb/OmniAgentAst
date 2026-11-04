# -*- coding: utf-8 -*-
"""shell_text_atoms — shell 命令文本原子与规范化(单一职责 · 零状态 · 零 I/O) — 小欧 2026-10-18

职责: 把 shell 命令文本变换为可判定的形态: 命令拼接归一(判危险前置)、引号涂空(判动词用)、
      $env/%VAR% 片段展开、PowerShell -LiteralPath 包裹。只做文本变换, 不判权限、不判动作。

编辑历史:
2026-10-18 - 小欧 - 新建(SRP): 自 shell_command_process.py 拆出"文本原子与规范化"单一关注点,
  独立成模块; 其余关注点(只读白名单/沙箱越界表/工具分类)另立模块; 函数名与语义零改动(搬运)。
2026-10-18 - 小欧 - 健壮性: shell_blank_out_quotes / shell_normalize_command 非字符串入参原抛
  TypeError, 改为安全返回空串。
2026-10-18 - 小欧 - shell_resolve_env_fragment 补 CMD 形态 %VAR% 展开($env 同政策)。

分层: 本模块是最底层文本原子, 不 import 任何 shell_parse / 权限模块(被 lexer 与判定层复用)。
"""
import os
import re

# ══════════════════════════════════════════════════════════════════════
# 一、危险判定前置归一: 先把"拼出来的动词"还原(2026-10-10 审计)
# ══════════════════════════════════════════════════════════════════════
# 审计实证的绕过: & ('Stop'+'-Process') -Id 5 / $v='Stop'+'-Process'; & $v -Id 5
#   字面量被 + 拆开, _UNCONTAINABLE_RE 查不到连续词, 判定放行 → 预检在宿主真跑 → 后端自杀。
# 本函数只服务"检测", 不服务"执行": 归一只可能让词更易命中、不会让已命中的词消失, 故只增不减。
# 折叠 '+' 必须先于去引号: 'Stop'+'-Process' → 'Stop'-'Process' → Stop-Process。
_CONCAT_PART = r"'[^']*'|\"[^\"]*\"|[A-Za-z0-9_.-]+"
_CONCAT_RE = re.compile(r"(" + _CONCAT_PART + r")\s*\+\s*(" + _CONCAT_PART + r")")
# 2026-10-10 小欧 [char] 拼接: & ([char]83+[char]116+[char]111+[char]112)-Process -Id 5
#   _CONCAT_PART 不认方括号致零折叠, 且括号隔断动词((Stop)-Process 查不到连续词) → 全链漏网预检真跑。
#   解法: 先把 [char]N(十进制)还原为字符, 再剥 ()[]{} 四种噪音括号, 然后走原有折叠。
#   只剥括号(检测专用); 逗号/分号不动(逗号是 PID/多值分隔, 分号是语句分隔, 动不得)。
_CHAR_RE = re.compile(r"\[char\]\s*(\d+)", re.IGNORECASE)
_NOISE_RE = re.compile(r"[(){}\[\]]")


def _decode_char_codes(text: str) -> str:
    """[char]83 → S(十进制; 十六进制 0x 形态暂不覆盖, 见残留)。至不动点(连写嵌套一次消不净)。"""
    prev = None
    while prev != text:
        prev = text
        text = _CHAR_RE.sub(lambda m: chr(int(m.group(1)) & 0x10FFFF), text)
    return text


def shell_normalize_command(command: str) -> str:
    """把字符串拼接折叠、去引号, 使 'Stop'+'-Process' 还原为 Stop-Process — 小欧 2026-10-10

    适用: 仅供静态危险判定前置归一(词表命中前置), 结果不用于执行。
    循环折叠至不动点: 'a'+'b'+'c' 三段拼接一次只能合两段, 单趟必漏。
    2026-10-10 小欧 补: [char]N 解码 + 括号噪音剥离。顺序: 解码 → 剥噪音 → 折叠 → 去引号。
    2026-10-18 小欧: 非字符串入参原抛 TypeError, 改为安全返回空串。
    """
    text = _decode_char_codes(command if isinstance(command, str) else "")
    text = _NOISE_RE.sub("", text)           # 剥括号噪音: (Stop)-Process → Stop-Process
    prev = None
    while prev != text:                      # 每趟至少消掉一个 '+', 必然收敛(不动点退出)
        prev = text
        text = _CONCAT_RE.sub(r"\1\2", text)
    return text.replace("'", "").replace('"', "")


# ══════════════════════════════════════════════════════════════════════
# 二、文本原子: 引号涂空 / $env 展开 / -LiteralPath 包裹
# ══════════════════════════════════════════════════════════════════════
# 引号 span: 只认单/双引号整段(给 shell_blank_out_quotes 涂空用)
_QUOTED_SPAN_RE = re.compile(r"'[^']*'|\"[^\"]*\"")


def shell_blank_out_quotes(text: str) -> str:
    """引号内容涂成等长空格(保偏移)。用于判动词时把 'Select-String -Pattern "del"' 里的 del 排除。

    2026-10-18 小欧: 非字符串入参原抛 TypeError, 改为安全返回空串。
    """
    return _QUOTED_SPAN_RE.sub(lambda m: " " * len(m.group(0)), text if isinstance(text, str) else "")


def shell_resolve_env_fragment(fragment: str) -> str:
    """$env:VAR / %VAR% 片段展开为真实路径(`$env:TEMP\\a.txt` → `C:\\Temp\\a.txt`)。未知变量原样保留。

    2026-10-18 小欧: 补 CMD 形态 `%VAR%` 同步展开, 否则 `%SystemRoot%\\system32\\config\\SAM`
    被拼成含字面 % 的假路径(与 $env 同政策: 仅已知变量展开, 未知原样保留, 不误伤字面 %)。
    """
    def _sub(m):
        val = os.environ.get(m.group(1))
        return val if val is not None else m.group(0)
    text = re.sub(r"\$env:([A-Za-z_][A-Za-z0-9_]*)", _sub, fragment or "")
    return re.sub(r"%([A-Za-z_][A-Za-z0-9_]*)%", _sub, text)


def shell_ps_literal_path(p) -> str:
    """给 PowerShell -LiteralPath 用单引号包裹并转义内嵌单引号(`'` → `''`)。"""
    return "'" + str(p).replace("'", "''") + "'"


__all__ = ["shell_normalize_command", "shell_blank_out_quotes",
           "shell_resolve_env_fragment", "shell_ps_literal_path"]
