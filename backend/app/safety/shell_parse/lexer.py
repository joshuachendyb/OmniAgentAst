# -*- coding: utf-8 -*-
"""shell_parse.lexer — shell 命令词法/预处理层(零权限判定) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: 文档[38] 13.2 概设 §13.2.3.4 流水线 [1]预处理 / [2]语句拆分 落地。
  职责: 换行归一 / $env 展开 / 引号涂空(判动词用) / 语句拆分 / 管道拆分 / 分词 / 路径归一。
  文本级原子复用 shell_command_process 单一真源(shell_blank_out_quotes /
  shell_resolve_env_fragment), 不在本层重复实现(DRY)。
2026-10-18 - 小欧 - [38] 13.2 二次迁移(老陈裁定, 按 §13.1.2 全部移入本包): 路径抽取原子整体自
  shell_command_process 迁入本文件(shell_extract_abs_win_paths 及私有 _SHELL_ABS_WIN_PATH_RES);
  引号涂空/环境变量展开仍复用 shell_command_process(规范化真源, 概设 §13.2.3.8)。

分层: 本文件只做词法, 识别"动作性质"与"抽路径"在 parse_* 各文件, 判定在 shell_path_check。
"""
import os
import re
from typing import List, Optional

from app.safety.shell_command_process import (
    shell_blank_out_quotes,
    shell_resolve_env_fragment,
)

# 三壳标识(与 execute_shell_command 的 shell_type 取值一致)
PS7 = "ps7"
PS5 = "ps5"
CMD = "cmd"
BASH = "bash"
SHELLS = (PS7, PS5, CMD, BASH)

_DRIVE_ABS_RE = re.compile(r"^[a-zA-Z]:[\\/]")

# 壳识别线索(动词识别取三壳并集, 识别偏差不影响取全)
#   ★2026-10-18 小欧 订正: 原注释称"仅用于 flags 语义与 origin 标注"不实 —— origin 由各解析器硬编码
#     (delete/pipe/read/write), flags 取自各自的开关判据, 二者均不读 shell; detect_shell 的返回值
#     仅作 parse_shell_action 的 shell 形参透传, 当前四个解析器均未消费该形参(YAGNI 死参, 见 §14.3)。
_BASH_HINT_RE = re.compile(
    r"(?:^|[;&|]\s*)(?:rm|ls|cat|grep|chmod|chown|cp|mv|sed|awk|touch|mkdir|sudo|bash|sh)\b",
    re.IGNORECASE)
_CMD_HINT_RE = re.compile(
    r"%[a-zA-Z_][a-zA-Z0-9_]*%|\b(?:del|rd|rmdir|copy|move|ren|dir|findstr|where|type|attrib)\b"
    r"|\bfor\s+/f\b|/s\b|/q\b", re.IGNORECASE)

# 语句分隔 / 管道分隔 / 分词
_STMT_SEPS = (";", "&&", "||")
_PIPE_SEP = "|"
_TOKEN_RE = re.compile(r'"[^"]*"|\'[^\']*\'|[^\s"\'<>|;&]+')


def detect_shell(command: str) -> str:
    """识别 shell 类型: ps7/ps5/cmd/bash — 小欧 2026-10-18

    缺省 ps7(与 execute_shell_command 默认一致)。bash 线索优先, 次 cmd, 否则 ps7。
    """
    text = command or ""
    if _BASH_HINT_RE.search(text):
        return BASH
    if _CMD_HINT_RE.search(text):
        return CMD
    return PS7


def prepare(command: str) -> str:
    """流水线 [1] 预处理: 换行归一 + $env 展开, 产出"抽取用文本" — 小欧 2026-10-18

    抽取用文本保留引号原样与真实路径(概设 §13.2.3.4 [1]); 判动作用引号涂空另在
    blank_quotes 内联(保偏移), 由各 parse_* 在动词识别时调用。
    """
    normalized = (command or "").replace("\r\n", " ").replace("\n", " ")
    return shell_resolve_env_fragment(normalized)


def blank_quotes(text: str) -> str:
    """引号内容涂成等长空格(判动作动词专用, 保偏移) — 小欧 2026-10-18"""
    return shell_blank_out_quotes(text or "")


def _split_respect_quotes(text: str, seps) -> List[str]:
    """按给定分隔符在"引号外"切分文本(引号内的分隔符不算) — 小欧 2026-10-18

    手写扫描而非正则: 正则无法可靠区分引号内外; 涂空引号会连路径一起抹掉,
    故在此按位置切分(保留路径原文), 动词识别由各 parse_* 另对片段涂空。
    """
    out: List[str] = []
    buf: List[str] = []
    i, n, quote = 0, len(text), None
    while i < n:
        ch = text[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            buf.append(ch)
            i += 1
            continue
        matched = None
        for s in seps:
            if text.startswith(s, i):
                matched = s
                break
        if matched:
            out.append("".join(buf))
            buf = []
            i += len(matched)
            continue
        buf.append(ch)
        i += 1
    out.append("".join(buf))
    return [x.strip() for x in out if x.strip()]


def split_statements(text: str) -> List[str]:
    """流水线 [2] 语句拆分: 按 ; && || 与引号外切分 — 小欧 2026-10-18"""
    return _split_respect_quotes(text, _STMT_SEPS)


def split_pipeline(statement: str) -> List[str]:
    """把一条语句按单竖线拆成管道各段(引号外) — 小欧 2026-10-18"""
    return _split_respect_quotes(statement, (_PIPE_SEP,))


def tokenize(statement: str) -> List[str]:
    """按空白/引号/元字符切词(去首尾引号) — 小欧 2026-10-18"""
    return [t.strip("\"'") for t in _TOKEN_RE.findall(statement or "")]


def to_absolute(path: str, cwd: Optional[str]) -> Optional[str]:
    """把路径归一为绝对路径; 无法绝对化(相对且无 cwd)返回 None — 小欧 2026-10-18

    盘符绝对路径(正/反斜杠)直接 normpath; ~ 走 expanduser; 相对需 cwd 基准。
    """
    if not path:
        return None
    p = shell_resolve_env_fragment(path)
    if _DRIVE_ABS_RE.match(p):
        return os.path.normpath(p)
    if p.startswith("~"):
        return os.path.expanduser(p)
    if cwd:
        return os.path.normpath(os.path.join(cwd, p))
    return None


def _relative_tokens(statement: str) -> List[str]:
    """相对路径候选词条: 非开关、含分隔符或点号 — 小欧 2026-10-18"""
    out: List[str] = []
    for tok in tokenize(statement):
        if not tok or tok[0] in "-/":
            continue
        if "\\" in tok or "/" in tok or "." in tok:
            out.append(tok)
    return out


# 绝对路径抽取原子(单一真源) — 2026-10-18 小欧 [38] 13.2 自 shell_command_process 迁入(老陈裁定)
_SHELL_ABS_WIN_PATH_RES = [
    # 引号区先完整取出(两条): 只在**确实位于引号内**时才允许空格, 故用
    #   「非引号字符 + 引号内任意字符」的组合匹配, 避免把裸路径间的空格也当成路径的一部分
    #   (实测 `C:\a C:\b` 曾被吞成 'C:\a C:\b' 一个路径)。
    re.compile(r'"[a-zA-Z]:\\[^"]*"'),          # 双引号内反斜杠盘符路径
    re.compile(r'"[a-zA-Z]:/[^"]*"'),           # 双引号内正斜杠盘符路径(C:/ 同属越界写, 防逃逸)
    re.compile(r"'[a-zA-Z]:\\[^']*'"),          # 单引号内盘符路径
    # 裸路径(引号外): 遇空白或分隔符即止; 反斜杠与正斜杠盘符同认
    re.compile(r"[a-zA-Z]:[\\/][^\s\"'<>|;,)&]+"),
]


def shell_extract_abs_win_paths(text: str) -> List[str]:
    """抽取命令中的全部绝对路径 — 小欧 2026-10-14

    引号区先完整取出(含首尾引号, 取出后剥掉), 裸路径**只在引号区之外**扫描:
    否则同一段引号路径会被裸正则再截断成 `E:\\my`(实测误拦已授权目录 `E:\\my proj`,
    且 failed_path 报错路径)。裸路径不得跨空白, 否则 `C:\\a C:\\b` 会被吞成一个路径。
    去重保序。
    """
    quoted: List[str] = [m.strip("\"'")
                        for rx in _SHELL_ABS_WIN_PATH_RES[:3] for m in rx.findall(text)]
    bare = _SHELL_ABS_WIN_PATH_RES[3].findall(shell_blank_out_quotes(text))
    found: List[str] = []
    for p in quoted + bare:
        p = p.strip().rstrip("\\")
        if p and p.lower() not in [x.lower() for x in found]:
            found.append(p)
    return found


def extract_paths(statement: str, cwd: Optional[str]) -> List[str]:
    """抽语句内路径: 绝对路径(盘符)+ 相对路径(cwd 已知时补抽) — 小欧 2026-10-18

    绝对路径复用 shell_extract_abs_win_paths(引号区完整取出, 防截断);
    相对路径仅在 cwd 已知时按基准绝对化, 无 cwd 的相对路径不入清单(交沙箱预检)。
    """
    found = list(shell_extract_abs_win_paths(statement))
    if cwd:
        lowered = {x.lower() for x in found}
        for tok in _relative_tokens(statement):
            absolute = to_absolute(tok, cwd)
            if absolute and absolute.lower() not in lowered:
                found.append(absolute)
                lowered.add(absolute.lower())
    return found


__all__ = [
    "PS7", "PS5", "CMD", "BASH", "SHELLS",
    "detect_shell", "prepare", "blank_quotes",
    "split_statements", "split_pipeline", "tokenize",
    "to_absolute", "extract_paths", "shell_extract_abs_win_paths",
]
