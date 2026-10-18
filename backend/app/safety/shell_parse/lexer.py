# -*- coding: utf-8 -*-
r"""shell_parse.lexer — shell 命令词法/预处理层(零权限判定) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: shell 命令词法/预处理层(换行归一 / $env 展开 / 引号涂空 / 语句拆分 /
  管道拆分 / 分词 / 路径归一)。文本级原子复用 shell_text_atoms 单一真源(shell_blank_out_quotes /
  shell_resolve_env_fragment), 不在本层重复实现(DRY)。
2026-10-18 - 小欧 - 二次迁移: 路径抽取原子整体自 shell_command_process 迁入本文件
  (shell_extract_abs_win_paths 及私有 _SHELL_ABS_WIN_PATH_RES); 引号涂空/环境变量展开仍复用 shell_text_atoms。

分层: 本文件只做词法, 识别"动作性质"与"抽路径"在 parse_* 各文件, 判定在 shell_path_check。
2026-10-18 - 小欧 - DRY: 新增 pathish / split_source_target(源/目标按文本顺序切分),
  供搬移套与复制套共用, 消除 parse_move 私有重复实现; 新增 redirect_targets(重定向目标剔除);
  _split_respect_quotes 非字符串入参安全返回 []。
2026-10-18 - 小欧 - 源/目标切分修正: 新增 refpath_like 识别"形似相对路径却未解析出"的词条。
  缺陷: pathish 要求 cwd 已知, 故 cwd 缺失时 `Copy-Item a.txt C:\Windows\b.txt` 的源 `a.txt`
  被整条跳过, 其后唯一解析出的绝对路径被当成源 —— 写系统目录的目标被降级成读, 漏拦。
  改法: split_source_target 在无 dest 开关时, 若未解析出的相对路径词条排在已解析路径之前,
  则判定源落空, 已解析的那些全属目标(返回 ([], paths)); 有 dest 开关的分支不受影响。
2026-10-18 - 小欧 - 词法增强: 换行作语句分隔(prepare 保 \n + _STMT_SEPS 补 \n); 盘符相对 `C:xxx`
  按盘根解析不再并入 cwd; 裸路径支持 `\\?\` 前缀、反斜杠/正斜杠 UNC、裸根 `C:\`、含逗号文件名;
  版本号/纯数字点串不再当相对路径。
"""
import os
import re
from typing import List, Optional

#   2026-10-18 小欧: 文本原子已拆入 app.safety.shell_text_atoms(SRP);
#   本文件的依赖改**惰性**(调用期导入), 导入期 lexer 不触发该模块, 与沙箱宽表(shell_sandbox_tables
#   → parse_* → lexer)之间的潜在环彻底解除。原子仍是单一真源(零复制)。
def _blank_out(text: str) -> str:
    from app.safety.shell_text_atoms import shell_blank_out_quotes
    return shell_blank_out_quotes(text)


def _resolve_env(text: str) -> str:
    from app.safety.shell_text_atoms import shell_resolve_env_fragment
    return shell_resolve_env_fragment(text)

# 三壳标识(与 execute_shell_command 的 shell_type 取值一致)
PS7 = "ps7"
PS5 = "ps5"
CMD = "cmd"
BASH = "bash"
SHELLS = (PS7, PS5, CMD, BASH)

_DRIVE_ABS_RE = re.compile(r"^[a-zA-Z]:[\\/]")

# 壳识别线索(动词识别取三壳并集, 识别偏差不影响取全)
#   2026-10-18 小欧 订正: 原注释称"仅用于 flags 语义与 origin 标注"不实; origin 由各解析器硬编码
#     (delete/pipe/read/write), flags 取自各自的开关判据, 二者均不读 shell; detect_shell 的返回值
#     仅作 parse_shell_action 的 shell 形参透传, 当前四个解析器均未消费该形参(YAGNI 死参)。
_BASH_HINT_RE = re.compile(
    r"(?:^|[;&|]\s*)(?:rm|ls|cat|grep|chmod|chown|cp|mv|sed|awk|touch|mkdir|sudo|bash|sh)\b",
    re.IGNORECASE)
_CMD_HINT_RE = re.compile(
    r"%[a-zA-Z_][a-zA-Z0-9_]*%|\b(?:del|rd|rmdir|copy|move|ren|dir|findstr|where|type|attrib)\b"
    r"|\bfor\s+/f\b|/s\b|/q\b", re.IGNORECASE)

# 语句分隔 / 管道分隔 / 分词
#   2026-10-18 小欧: 补 "\n" 作语句分隔; 换行在 ps/cmd/bash 三壳都终结一条命令,
#   原 prepare 把 \n 压成空格, 使 `cd C:\safe\nrmdir C:\Windows\Temp` 合并成一条而漏判后者。
_STMT_SEPS = (";", "&&", "||", "\n")
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

    抽取用文本保留引号原样与真实路径; 判动作用引号涂空另在
    blank_quotes 内联(保偏移), 由各 parse_* 在动词识别时调用。
    2026-10-18 小欧: 换行归为语句边界(保留 \n), 不再压成空格(防两条命令合并漏判)。
    """
    normalized = (command or "").replace("\r\n", "\n")
    return _resolve_env(normalized)


def blank_quotes(text: str) -> str:
    """引号内容涂成等长空格(判动作动词专用, 保偏移) — 小欧 2026-10-18"""
    return _blank_out(text or "")


def _split_respect_quotes(text: str, seps) -> List[str]:
    """按给定分隔符在"引号外"切分文本(引号内的分隔符不算) — 小欧 2026-10-18

    手写扫描而非正则: 正则无法可靠区分引号内外; 涂空引号会连路径一起抹掉,
    故在此按位置切分(保留路径原文), 动词识别由各 parse_* 另对片段涂空。
    2026-10-18 小欧: 非字符串入参原抛 TypeError(len(None)), 改为安全返回 []。
    """
    if not isinstance(text, str):
        return []
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
    p = _resolve_env(path)
    if _DRIVE_ABS_RE.match(p):
        return os.path.normpath(p)
    # 2026-10-18 小欧: 盘符相对路径 `C:xxx`(冒号后无分隔符)不是 cwd 相对; 原被
    #   os.path.join(cwd, "C:xxx") 并进 cwd, 造出 `C:\proj\Windows\...` 假路径而误判/漏判。
    #   按该盘根解析为 `C:\xxx`(该盘当前目录未知, 取盘根为稳妥上界)。
    if re.match(r"^[a-zA-Z]:(?![\\/])", p):
        return os.path.normpath(p[0] + ":\\" + p[2:])
    if p.startswith("~"):
        return os.path.expanduser(p)
    if cwd:
        return os.path.normpath(os.path.join(cwd, p))
    return None


def _relative_tokens(statement: str) -> List[str]:
    """相对路径候选词条: 非开关, 含分隔符(或含点但非纯数字版本号) — 小欧 2026-10-18

    2026-10-18 小欧: 版本号(3.11.4)/纯数字点串原被当相对路径, 造出 cwd 下假路径;
    改为要求含分隔符, 或含点但非 `[\\d.]+` 形态(如 file.txt 保留)。
    """
    out: List[str] = []
    for tok in tokenize(statement):
        if not tok or tok[0] in "-/":
            continue
        if "\\" in tok or "/" in tok:
            out.append(tok)
        elif "." in tok and not re.fullmatch(r"[\d.]+", tok):
            out.append(tok)
    return out


# 绝对路径抽取原子(单一真源) — 2026-10-18 小欧 [38] 13.2 自 shell_command_process 迁入
_SHELL_ABS_WIN_PATH_RES = [
    # 引号区先完整取出(三条): 只在**确实位于引号内**时才允许空格, 故用
    #   「非引号字符 + 引号内任意字符」的组合匹配, 避免把裸路径间的空格也当成路径的一部分
    #   (实测 `C:\a C:\b` 曾被吞成 'C:\a C:\b' 一个路径)。
    re.compile(r'"[a-zA-Z]:\\[^"]*"'),          # 双引号内反斜杠盘符路径
    re.compile(r'"[a-zA-Z]:/[^"]*"'),           # 双引号内正斜杠盘符路径(C:/ 同属越界写, 防逃逸)
    re.compile(r"'[a-zA-Z]:\\[^']*'"),          # 单引号内盘符路径
    # 裸盘符路径(引号外) — 2026-10-18 小欧: 允许空尾(裸根 `C:\`); 允许 `\\?\` 扩展长度前缀;
    #   逗号是 Windows 合法文件名字符, 不再排除。
    re.compile(r"(?:[\\][\\]\?[\\])?[a-zA-Z]:[\\/][^\s\"'<>|;)&]*"),
    # 反斜杠 UNC: \\srv\share\...
    re.compile(r"\\\\[^\\\s\"'<>|;,)&]+\\[^\s\"'<>|;,)&]*"),
    # 正斜杠 UNC/绝对: //srv/share/...
    re.compile(r"//[^/\s\"'<>|;,)&]+/[^\s\"'<>|;,)&]*"),
]


def shell_extract_abs_win_paths(text: str) -> List[str]:
    r"""抽取命令中的全部绝对路径 — 小欧 2026-10-14

    引号区先完整取出(含首尾引号, 取出后剥掉), 裸路径**只在引号区之外**扫描:
    否则同一段引号路径会被裸正则再截断成 `E:\my`(实测误拦已授权目录 `E:\my proj`,
    且 failed_path 报错路径)。裸路径不得跨空白, 否则 `C:\a C:\b` 会被吞成一个路径。
    去重保序。2026-10-18 小欧: 裸路径支持多模式(盘符含 `\\?\` 前缀 / 反斜杠 UNC / 正斜杠 UNC)。
    """
    quoted: List[str] = [m.strip("\"'")
                        for rx in _SHELL_ABS_WIN_PATH_RES[:3] for m in rx.findall(text)]
    masked = _blank_out(text)
    bare: List[str] = []
    for rx in _SHELL_ABS_WIN_PATH_RES[3:]:
        bare.extend(rx.findall(masked))
    found: List[str] = []
    for p in quoted + bare:
        p = p.strip().rstrip("\\")
        if not p:
            continue
        # 裸盘符根 `C:\` rstrip 后退化为 `C:`, 补回分隔符(避免与盘符相对 `C:xxx` 混淆)
        if re.fullmatch(r"[a-zA-Z]:", p):
            p += "\\"
        if p.lower() not in [x.lower() for x in found]:
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


def pathish(token: str, cwd: Optional[str]) -> bool:
    """词条是否像路径: 盘符绝对, 或 cwd 已知时的相对路径候选 — 小欧 2026-10-18"""
    if not token or token[0] in "-/":
        return False
    if _DRIVE_ABS_RE.match(token):
        return True
    return bool(cwd) and ("\\" in token or "/" in token or "." in token)


_REFPATH_RE = re.compile(r'^[\w.\-]+(?:[\\/][\w.\-]+)*$')


def refpath_like(token: str) -> bool:
    """词条是否形似**相对路径/文件名**(无盘符, 但有扩展名或分隔符) — 小欧 2026-10-18

    pathish 对"相对路径"要求 cwd 已知, 故 cwd 缺失时 `a.txt` 这类源被整条跳过,
    导致其后唯一解析出的绝对路径被当成**源**(`Copy-Item a.txt C:\\Windows\\b.txt`
    → 目标被判成读 → 写系统目录漏拦)。本函数专用于识别"本应解析出源却因缺 cwd 落空"的词条。
    """
    if not token or token[0] in "-/":
        return False
    if _DRIVE_ABS_RE.match(token):
        return False
    return bool(_REFPATH_RE.match(token)) and ("." in token or "\\" in token or "/" in token)


def split_source_target(statement: str, cwd: Optional[str],
                        dest_switches) -> "tuple[List[str], List[str]]":
    """搬移/复制类: 按文本顺序切出 (源清单, 目标清单) — 小欧 2026-10-18

    开关 dest_switches(如 -Destination/-NewName/-Dest)之后为全部目标; 否则首个路径为源、
    余为目标。复用本层 tokenize/to_absolute/pathish 单一真源(搬移与复制两套共用, 消重复)。

    2026-10-18 修复: 源为相对路径且 cwd 缺失时, 源解析不出被跳过, 原本会把其后唯一
    解析出的绝对路径当作**源**(目标被降级成读, 写系统目录漏拦)。故此处识别"形似相对路径
    却未解析出"的词条 —— 若它排在已解析路径之前, 则已解析的那些全是**目标**, 源置空。
    """
    tokens = tokenize(statement)
    paths = []
    for i, token in enumerate(tokens):
        if not pathish(token, cwd):
            continue
        absolute = to_absolute(token, cwd)
        if absolute:
            paths.append((i, absolute))
    if not paths:
        return [], []
    dest_idx = next((i for i, t in enumerate(tokens)
                     if t.lower() in dest_switches), None)
    if dest_idx is None:
        ref_idx = next((i for i, t in enumerate(tokens) if refpath_like(t)), None)
        if ref_idx is not None and ref_idx < paths[0][0]:
            return [], [p for _, p in paths]      # 源落空(相对且无 cwd) → 已解析的全属目标
        return [paths[0][1]], [p for _, p in paths[1:]]
    sources = [p for i, p in paths if i < dest_idx] or [p for _, p in paths]
    targets = [p for i, p in paths if i > dest_idx]
    return sources, targets


_REDIRECT_TOKEN_RE = re.compile(r'\s*("[^"]*"|\'[^\']*\'|[^\s"\'<>|;&]+)')


def redirect_targets(statement: str, cwd: Optional[str]) -> List[str]:
    """抽重定向目标(`>`/`>>` 之后的首个词条)归一为绝对路径 — 小欧 2026-10-18

    用于把重定向目标从删除/搬移抽取里剔除(其性质是写, 不该落删线)。
    引号内的 `>` 先涂空(保偏移)排除; `>&1` 之类无路径词条自然不匹配。
    """
    mask = blank_quotes(statement)
    out: List[str] = []
    for m in re.finditer(r">>?", mask):
        m2 = _REDIRECT_TOKEN_RE.match(statement[m.end():])
        if not m2:
            continue
        absolute = to_absolute(m2.group(1).strip("\"'"), cwd)
        if absolute and absolute.lower() not in [x.lower() for x in out]:
            out.append(absolute)
    return out


__all__ = [
    "PS7", "PS5", "CMD", "BASH", "SHELLS",
    "detect_shell", "prepare", "blank_quotes",
    "split_statements", "split_pipeline", "tokenize",
    "to_absolute", "extract_paths", "shell_extract_abs_win_paths",
    "pathish", "refpath_like", "split_source_target", "redirect_targets",
]
