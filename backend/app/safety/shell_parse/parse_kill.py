# -*- coding: utf-8 -*-
"""shell_parse.parse_kill — 杀进程/停服务动作解析(解析层, 零权限判定) — 小欧 2026-11-15

编辑历史:
2026-11-15 - 小欧 - 新建(根治): 杀进程防护自 shell_process_guard 的"全文正则叠罗汉"
  迁入解析层, 与 parse_delete/parse_move 同构(复用 lexer 拆语句/拆管道/涂引号/变量代入)。
  目标三态契约: literal(静态可枚举显式目标) / bounded_dynamic(会话内单对象变量) /
  unbounded(目标集合无上界) / opaque(静态不可见: -EncodedCommand/iex 内嵌)。
  同轮修复九处误拦/漏拦: -Id/-Name 被当进程名的假名 bug、helpish 全文门改段内生效、
  CIM -Query 引号隔断、注释与 echo 提及误拦、processid=/Filter 显式 PID 零提取、
  变量目标一律硬拦、iex 内嵌引号杀漏拦。
2026-11-15 - 小欧 - 严格测试整改(73 案矩阵第二轮): ①裸 wmic process list/get 是查询, 从动词表
  移除(误拦运维); ②引号内 kill 无 iex 不触发(Select-String -Pattern "kill" 误拦); ③动词藏引号/
  拼接/[char] 混淆时以归一文参与动词识别, 目标可见按 literal 抽取(此前整体漏网); ④上游段目标
  无条件并入(管道+开关双杀漏拦); ⑤服务杀动词一律 bounded 转确认(服务名非进程名, 静态不可证实);
  ⑥killall/-name 首字符禁 -(防 -9 开关被当目标名); ⑦-InputObject $p 补 bounded; ⑧bash/sh -c
  引号藏杀补 opaque; ⑨pkill 正则模式名补 regex 语义命中(py.* 实杀 python)。
2026-11-15 - 小欧 - 复核整改: ①kill/pkill/killall 仅命令位(段首/&、(后/包装命令后)认动词,
  除 `Select-String -Pattern kill` 误拦(参数值不是命令); ②_strip_quotes 转正 strip_quotes(公开,
  解跨层私有导入); ③动词表按"PowerShell/服务类"与"bash 裸动词"两组分治。

分层: 本文件只解析杀动作并给目标分类; 不判保护名单、不产 SafetyResult(判定在 shell_process_guard)。
"""
import re
from dataclasses import dataclass, field
from typing import List, Optional, Set, Tuple

from app.safety.shell_parse import lexer

LITERAL = "literal"
BOUNDED = "bounded_dynamic"
UNBOUNDED = "unbounded"
OPAQUE = "opaque"
TARGET_KINDS = (LITERAL, BOUNDED, UNBOUNDED, OPAQUE)


@dataclass
class ProcessAction:
    """一次杀进程/停服务动作: 动词 + 目标三态 — 小欧 2026-11-15

    verb        : 杀动词原文(如 stop-process / taskkill / invoke-cimmethod)
    target_kind : literal / bounded_dynamic / unbounded / opaque
    pids/names  : literal 态下静态可枚举的显式目标(其余态为空集)
    """
    verb: str
    target_kind: str
    pids: Set[int] = field(default_factory=set)
    names: Set[str] = field(default_factory=set)

    def __post_init__(self) -> None:
        if self.target_kind not in TARGET_KINDS:
            raise ValueError(f"非法目标三态: {self.target_kind!r}(仅 {'/'.join(TARGET_KINDS)})")


# ══════════════════════════════════════════════════════════════════════
# 段内动词识别(涂引号后的 blanked 文本上判, 引号内字面量不是动词)
# ══════════════════════════════════════════════════════════════════════
# 词边界字符类与 verb_table 同源口径: 路径名/子串不误命中(taskkill 内的 kill、pkill 内的 kill)
_EDGE = r"a-z0-9_.\\/-"


def _edge_alt(verbs: Tuple[str, ...]) -> str:
    return "|".join(re.escape(v) for v in verbs)


# 2026-11-15 小欧 严格测试整改: "wmic process" 从动词表移除(裸 wmic process list/get 是查询,
#  误拦日常运维); 只由 _WMIC_MASS_RE(须 delete / call terminate)认杀。
# 2026-11-15 复核: 可被 &/引号/拼接/[char] 混淆包裹的 PowerShell/服务类动词视字面出现即认;
#  bash 裸动词只在命令位认(段首 / &、( 后 / 包装命令后) —— `Select-String -Pattern kill` 的
#  kill 是参数值, 按命令位区分可除误拦。
_PWSH_VERBS = ("stop-process", "taskkill", "stop-service", "restart-service")
_BASH_VERBS = ("pkill", "killall", "kill")
_CMD_WRAPPERS = r"(?:(?:sudo|exec|env|nohup|command|time|xargs)\s+)*"
_KILL_VERB_RE = re.compile(
    r"(?<![" + _EDGE + r"])(?:" + _edge_alt(_PWSH_VERBS) + r")(?![" + _EDGE + r"])"
    r"|(?:(?:^|(?<=[&(]))\s*" + _CMD_WRAPPERS + r")(?:" + _edge_alt(_BASH_VERBS)
    + r")(?![" + _EDGE + r"])",
    re.IGNORECASE)
# 方法杀: .Kill( / .Terminate( —— Get-WmiObject/CimInstance 管道下游的方法调用点
_METHOD_KILL_RE = re.compile(r"\.\s*(?:terminate|kill)\s*\(", re.IGNORECASE)
# CIM 方法杀: 只认 -MethodName terminate|kill(Create/Get 是启动/查询不是杀, 2026-11-15 口径);
# 在 blanked 文本上判 —— 引号已涂空, -Query "…WHERE…" 不再隔断动词与参数(引号隔断病根)
_CIM_KILL_RE = re.compile(
    r"(?<![a-z0-9_-])invoke-cimmethod(?![a-z0-9_-])[^\"']{0,200}?-methodname\s+(?:terminate|kill)\b",
    re.IGNORECASE)
# wmic 质量动作: 配 delete / call terminate 才是杀(裸 wmic process get 是查询)
_WMIC_MASS_RE = re.compile(
    r"(?<![a-z0-9_-])wmic\s+process\b.*(?<![a-z0-9_-])(?:delete|call\s+terminate)\b",
    re.IGNORECASE | re.DOTALL)
_KILL_DETECT_RE = re.compile(
    "|".join(rx.pattern for rx in (_KILL_VERB_RE, _METHOD_KILL_RE, _CIM_KILL_RE, _WMIC_MASS_RE)),
    re.IGNORECASE)

# 求助/演习只在杀动词所在段生效(全文门是漏拦病根: 任一语句含 -WhatIf 即全局免检)
_HELPISH_RE = re.compile(r"/\?|--help|(?<![a-z0-9_-])-h\b|-whatif\b", re.IGNORECASE)

# 数据提及守卫: echo/write 系的第一实参是数据不是动词(`echo kill` 不是杀进程)
_ECHO_RE = re.compile(
    r"^\s*(?:echo\.?|write-host|write-output|write-debug|write-verbose|write-information|printf)\b",
    re.IGNORECASE)

# 静态不可见: -EncodedCommand / iex 内嵌 / bash -c 引号藏杀 —— 目标不可枚举, 分类为 opaque 交判定层。
# 2026-11-15 口径收敛(用户令): 判定层对 opaque 不硬拦不转确认, 杀不杀由 LLM 依返回信息自决。
# bash/sh -c 的引号内是可执行脚本(`bash -c "kill -9 $$"`), 引号对动词识别是盲区, 须按 opaque
#  分类, 不冒充已解析。
_OPAQUE_RE = re.compile(
    r"(?<![a-z0-9_-])-(?:encodedcommand|enc)\b|(?<![a-z0-9_-])(?:iex|invoke-expression)\b"
    r"|(?<![a-z0-9_-])(?:ba)?sh\s+-c\b",
    re.IGNORECASE)

# 无上界信号: $_ / foreach 批量 / 求值子表达式 —— 目标集合无上界
_UNBOUNDED_RES = (
    re.compile(r"\$_"),
    re.compile(r"(?<![a-z0-9_-])foreach(?![a-z0-9_-])", re.IGNORECASE),
    re.compile(r"foreach-object", re.IGNORECASE),
    re.compile(r"%\s*\{"),
    re.compile(r"\$\("),
)

# 有界动态信号: 会话内单对象变量(目标存在但静态不可证实, 转 HITL 确认)
_DYN_RES = (
    re.compile(r"-id\s+\$", re.IGNORECASE),
    re.compile(r"/pid\s+(?:%\w+%|\$)", re.IGNORECASE),
    re.compile(r"\bpid\s+eq\s+\$", re.IGNORECASE),
    re.compile(r"\bprocessid\s*=\s*\$", re.IGNORECASE),
    re.compile(r"-name\s+\$", re.IGNORECASE),
    re.compile(r"/im\s+\$", re.IGNORECASE),
    # 2026-11-15 严格测试整改: -InputObject $p 单对象变量, 目标存在但静态不可证实 → HITL
    re.compile(r"-inputobject\s+\$", re.IGNORECASE),
)

# ══════════════════════════════════════════════════════════════════════
# 显式目标提取(kill 段 + 上游段并扫: CIM -Filter / Get-Process 管道的目标在上游)
# ══════════════════════════════════════════════════════════════════════
_NAME_TOKEN = r"[\w.*?+-]+(?:\.exe)?"

_PID_RES = (
    re.compile(r"stop-process\W*(?:[\w-]+\s+)*-id\s+([\d,\s]+)", re.IGNORECASE),
    re.compile(r"/pid\s+([\d,\s]+)", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])kill\s+(?:-[\w]+\s+)*([\d,\s]+)", re.IGNORECASE),
    re.compile(r"\bpid\s+eq\s+([\d,\s]+)", re.IGNORECASE),
    # wmic/CIM 过滤子句里的显式 PID(`where processid=1234` / -Filter "ProcessId=1234")
    re.compile(r"\bprocessid\s*=\s*['\"]?([\d,\s]+)['\"]?", re.IGNORECASE),
    re.compile(r"\bprocessid\s+eq\s+([\d,\s]+)", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])get-process\s+-id\s+([\d,\s]+)", re.IGNORECASE),
)

_NAME_RES = (
    re.compile(r"(?<![a-z0-9_-])-name\s+((?!-)" + _NAME_TOKEN + r"(?:\s*,\s*" + _NAME_TOKEN + r")*)",
               re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])/im\s+(" + _NAME_TOKEN + r")", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])killall\s+((?!-)" + _NAME_TOKEN + r")", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])imagename\s+eq\s+(" + _NAME_TOKEN + r")", re.IGNORECASE),
    # wmic/CIM 过滤子句名(`where name='x'` / -Filter "Name='x'"); 前向断言挡 hostname/filename
    re.compile(r"(?<![a-z0-9_-])name\s*=\s*['\"]?(" + _NAME_TOKEN + r")['\"]?", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])processname\s*=\s*['\"]?(" + _NAME_TOKEN + r")['\"]?", re.IGNORECASE),
    # pkill 实参即目标模式; 首字符禁 -(挡 -9/-f 本身被当成名)
    re.compile(r"(?<![a-z0-9_-])pkill\s+(?:-[\w]+\s+)*(?:-f\s+)?([A-Za-z0-9_.?*][\w.*?+-]*(?:\.exe)?)",
               re.IGNORECASE),
    # Get-Process 管道上游显式名(事故原形); 首字符禁 -(堵 -Id/-Name 被当进程名的假名 bug)
    re.compile(r"(?<![a-z0-9_-])get-process\s+((?!-)" + _NAME_TOKEN + r"(?:\s*,\s*" + _NAME_TOKEN
               + r")*)", re.IGNORECASE),
    # 停服务目标: `Stop-Service spooler` 的实参即服务名; 首字符禁 -(不吞开关)
    re.compile(r"(?<![a-z0-9_-])(?:stop-service|restart-service)\s+((?!-)" + _NAME_TOKEN + r")",
               re.IGNORECASE),
)

# 仅通配无实名的目标(`*` / `.*`) = 全中, 无上界
_WILDCARD_ALL_RE = re.compile(r"^[.*?]+$")


def strip_quotes(s: str) -> str:
    """去首尾引号(名提取的引号在归一文里已无, 此函数只处理原文残留) — 小欧 2026-10-10"""
    return (s or "").strip().strip("\"'")


def strip_comment(text: str, shell: str) -> str:
    """剥注释: ps/bash 引号外 `#` 截断; cmd 整行 rem/:: 剔除 — 小欧 2026-11-15

    注释里的动词不是动词(`Get-Date; # Stop-Process 曾用过` 不该触发杀判定)。
    cmd 的 `#` 非注释字符(可出现在路径), 不按 # 处理。
    """
    if not text:
        return ""
    if shell == lexer.CMD:
        kept = []
        for line in text.split("\n"):
            s = line.lstrip()
            if s.lower().startswith("rem ") or s.startswith("::"):
                continue
            kept.append(line)
        return "\n".join(kept)
    out: List[str] = []
    quote = None
    for ch in text:
        if quote:
            out.append(ch)
            if ch == quote:
                quote = None
            continue
        if ch in ("'", '"'):
            quote = ch
            out.append(ch)
            continue
        if ch == "#":
            break
        out.append(ch)
    return "".join(out)


def _extract_pids(text: str) -> Set[int]:
    pids: Set[int] = set()
    for rx in _PID_RES:
        for m in rx.finditer(text):
            pids.update(int(x) for x in re.split(r"[\s,]+", m.group(1)) if x.isdigit())
    return pids


def _extract_names(text: str) -> Set[str]:
    names: Set[str] = set()
    for rx in _NAME_RES:
        for m in rx.finditer(text):
            names.update(strip_quotes(n) for n in re.split(r"\s*,\s*", m.group(1)))
    return {n for n in names if n and not _WILDCARD_ALL_RE.match(n)}


def _segment_targets(seg: str, normalized: str) -> Tuple[Set[int], Set[str]]:
    """单段显式目标: 原文与归一文并扫(拼接/去引号形态靠归一文还原) — 小欧 2026-11-15"""
    from app.safety.shell_text_atoms import shell_normalize_command
    text = normalized if normalized is not None else shell_normalize_command(seg)
    return _extract_pids(seg) | _extract_pids(text), _extract_names(seg) | _extract_names(text)


def _classify(verb: str, seg_blanked: str, pids: Set[int], names: Set[str]) -> str:
    """目标三态判定 — 小欧 2026-11-15

    优先级: opaque(不可见) > unbounded(无上界信号) > literal(有显式目标) >
            bounded_dynamic(单对象变量: -Id $v 或方法调用 $p.Kill()) > unbounded(兜底无界)。
    2026-11-15 严格测试整改: 服务杀动词(Stop-Service/Restart-Service)一律 bounded —
    服务名不是进程名, 静态不可证实安全, 显式目标也须转人工确认。
    """
    if _OPAQUE_RE.search(seg_blanked):
        return OPAQUE
    if any(rx.search(seg_blanked) for rx in _UNBOUNDED_RES):
        return UNBOUNDED
    if verb in ("stop-service", "restart-service"):
        return BOUNDED
    if pids or names:
        return LITERAL
    if _METHOD_KILL_RE.search(seg_blanked) or any(rx.search(seg_blanked) for rx in _DYN_RES):
        return BOUNDED
    return UNBOUNDED


def parse_kill_actions(command: str, shell_type: Optional[str] = None) -> List[ProcessAction]:
    """把一条 shell 命令解析为杀进程/停服务动作清单 — 小欧 2026-11-15

    流程: 预处理 → 逐语句(剥注释/变量代入) → 逐管道段 → 段内识别杀动词 →
          目标提取(kill 段 + 上游段并扫) → 三态分类。
    空清单 = 无杀动作。本层只解析、不判权限。
    """
    if not isinstance(command, str) or not command.strip():
        return []
    from app.safety.shell_text_atoms import shell_normalize_command
    shell = shell_type if shell_type in lexer.SHELLS else lexer.detect_shell(command)
    actions: List[ProcessAction] = []
    for statement in lexer.split_statements(lexer.prepare(command)):
        statement = strip_comment(statement, shell)
        if not statement.strip():
            continue
        statement = lexer.substitute_vars(statement, lexer.build_var_map(command))
        segments = lexer.split_pipeline(statement)
        for idx, seg in enumerate(segments):
            blanked = lexer.blank_quotes(seg)
            if _ECHO_RE.search(blanked):
                continue                      # 数据提及段: 非杀动作
            if _OPAQUE_RE.search(blanked):
                # 静态不可见(-EncodedCommand/iex): 分类为 opaque 交判定层, 不冒充已解析;
                # 判定层按口径收敛令(2026-11-15)放行, 杀不杀由 LLM 自决
                m = _OPAQUE_RE.search(blanked)
                actions.append(ProcessAction(m.group(0).lower(), OPAQUE))
                continue
            if _HELPISH_RE.search(blanked):
                continue                      # 求助/演习段: 非杀动作(只在杀动词所在段生效)
            verb_hit = _KILL_DETECT_RE.search(blanked)
            raw_hit = _KILL_DETECT_RE.search(seg)
            normalized = shell_normalize_command(seg)
            # 2026-11-15 严格测试整改: 归一文(去拼接/[char]混淆)必须参与动词识别 —
            #  ('Stop'+'-Process') / [char]83+... 在原文与涂空文里都不连续, 只查这两文必漏
            norm_hit = _KILL_DETECT_RE.search(normalized)
            if not verb_hit:
                hit = raw_hit or norm_hit
                if hit:
                    # 动词被混淆/藏引号但目标可见(`& ('Stop-Process') -Id 5`)按 literal 抽目标;
                    # 目标也不可见(iex/bash -c 藏杀)才 opaque 转确认;
                    # 无 iex 且引号内 kill 是数据(Select-String -Pattern "kill")不触发
                    pids, names = _segment_targets(seg, normalized)
                    if pids or names:
                        actions.append(ProcessAction(hit.group(0).lower(), LITERAL, pids, names))
                    elif _OPAQUE_RE.search(blanked):
                        actions.append(ProcessAction(hit.group(0), OPAQUE))
                continue
            pids, names = _segment_targets(seg, normalized)
            # 2026-11-15 小欧 严格测试整改: 上游段目标无条件并入(`Get-Process python |
            #  Stop-Process -Name node` 管道与 -Name 各杀各的, 只看杀段会漏 python)
            blanked_all = blanked
            for upstream in segments[:idx]:
                up_pids, up_names = _segment_targets(upstream, shell_normalize_command(upstream))
                pids, names = pids | up_pids, names | up_names
                blanked_all += " ; " + lexer.blank_quotes(upstream)
            verb = verb_hit.group(0).lower()
            if _WMIC_MASS_RE.search(blanked):
                verb = "wmic process"
            actions.append(ProcessAction(verb, _classify(verb, blanked_all, pids, names), pids, names))
    return actions


__all__ = [
    "ProcessAction", "LITERAL", "BOUNDED", "UNBOUNDED", "OPAQUE", "TARGET_KINDS",
    "parse_kill_actions", "strip_comment", "strip_quotes",
]
