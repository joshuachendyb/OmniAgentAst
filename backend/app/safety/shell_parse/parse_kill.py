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
2026-11-26 - 小欧 - foreach 有界性判定(根治误拦/漏拦): 裸 foreach 从 _UNBOUNDED_RES 移出,
  改由 _classify 的 foreach_bounded 参数控制。新增 _extract_foreach_source(括号平衡扫迭代源)、
  _build_array_vars(整条命令抽 `$var=@(数字列表)`)、_source_bounded(判迭代源有界性)。
  【口径】显式数字数组/数字范围/纯数字数组变量 → 目标静态可枚举(并入 pids, 按 literal 核对保护名单);
  (Get-Process)/Get-CimInstance/wmic/$_/非数字数组变量 → 无界仍硬拦。
  与词法层块感知配合: 块内 `;`/换行不再把 foreach 头与 Kill 拆开, 判定不随排版翻转。


2026-11-26 - 小欧 - 根治 foreach 有界判定的连带漏洞: ①迭代源改用原始段文本提取(引号字符串数组
  不再被涂空误判纯数字有界); ②块体不引用迭代变量时不再借"源有界"豁免——块体内独立全量枚举源
  (Get-Process 无筛选)仍判无界, 堵住"有界源 + 块内全杀"静默放行; ③数组赋值表支持裸数字列表
  (`$ids=1,2`), 与 `@(1,2)` 同等可枚举。


2026-11-26 - 小欧 - 审计补漏(逐壳 ps/bash/cmd 全矩阵实测): ①PowerShell 自动变量 $PID(当前进程PID=自己人)
  纳入无界硬拦; ②`$var=Get-Process -Id <数字>; $var.Kill()` / `-InputObject $var` 对象变量解析为
  literal PID 交保护盾核对; ③opaque(iex/bash -c)引号内显式目标可见时按 literal 抽取核对, 不再
  一律放行(堵 iex "Stop-Process -Id <自身PID>" 自杀漏拦); ④字符串数组 foreach 迭代源抽为 literal
  名字集合, 修正上轮误把普通名字串判 unbounded 的误伤。

2026-11-26 - 小欧 - 二次审计根治: 标量变量间接自杀漏拦(`$id=$PID; Stop-Process -Id $id`
  落 BOUNDED 兜底放行)。新增 _build_scalar_vars(标量赋值表: $v=$PID/数字/别名, 链式
  传递, 键小写)与 _scalar_refs(-Id $var 引用还原), 杀段与上游段均扫: 自身变量硬拦、
  字面 PID 并入 literal 交保护盾; 未定义变量维持 BOUNDED 兜底不误伤。



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

# 无上界信号: $_ / foreach-object 批量 / 求值子表达式 —— 目标集合无上界
# 2026-11-26 小欧 - 裸 foreach 移出本表: 其有界性由 _classify 依迭代源判定(见 _source_bounded),
#   显式数字数组放行、Get-Process/$_/非数字变量仍拦; 其余无界信号不变。
_UNBOUNDED_RES = (
    re.compile(r"\$_"),
    re.compile(r"foreach-object", re.IGNORECASE),
    re.compile(r"%\s*\{"),
    re.compile(r"\$\("),
)
# foreach 语句信号(与 _UNBOUNDED_RES 分开: 有界时豁免, 无界时仍拦) — 小欧 2026-11-26
_FOREACH_SIGNAL_RE = re.compile(r"(?<![a-z0-9_-])foreach(?![a-z0-9_-])", re.IGNORECASE)

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


# foreach 迭代源: `foreach ($x in <源>)` 的 <源> 决定目标是否有界 — 小欧 2026-11-26
_FOREACH_HEAD_RE = re.compile(
    r"(?<![a-z0-9_-])foreach\s*\(\s*\$(?P<var>\w+)\s+in\s+", re.IGNORECASE)
# `$var = @(数字列表)` / `$var = 1,2` 数组赋值: 迭代源是这类变量时可静态枚举
_ARRAY_ASSIGN_RE = re.compile(
    r"\$(?:\{(?P<a>\w+)\}|(?P<b>\w+))\s*=\s*"
    r"(?:@\((?P<body>[^)]*)\)|(?P<bare>\d+(?:\s*,\s*\d+)+))")
# 独立全量枚举源(无 -Name/-Id 等筛选): 出现即无上界, 为 foreach 块体"全杀"兜底 — 小欧 2026-11-26
_MASS_ENUM_RE = re.compile(
    r"(?<![a-z0-9_-])(?:get-process|get-ciminstance\s+win32_process"
    r"|get-wmiobject\s+win32_process|wmic\s+process)\b", re.IGNORECASE)
# 范围展开上限(超限仍判有界但不展开具体 pid): 防 1..N 造出超大集合
_FOREACH_RANGE_MAX = 10000

# PowerShell 自动变量 $PID = 当前进程 PID(自己人); 杀它必自杀, 无界硬拦 — 小欧 2026-11-26
_SELF_PID_VAR_RE = re.compile(r"\$(?:\{PID\}|PID\b)", re.IGNORECASE)
# `$var = Get-Process -Id <数字列表>` 对象变量: 变量 Kill 时目标静态可枚举 — 小欧 2026-11-26
_OBJECT_PID_ASSIGN_RE = re.compile(
    r"\$(?:\{(?P<a>\w+)\}|(?P<b>\w+))\s*=\s*get-process\s+-id\s+(?P<ids>[\d,\s]+)",
    re.IGNORECASE)
# `$var = Get-Process -Id $PID` 对象变量(源是自身 PID) — 小欧 2026-11-26
_OBJECT_SELF_ASSIGN_RE = re.compile(
    r"\$(?:\{(?P<a>\w+)\}|(?P<b>\w+))\s*=\s*get-process\s+-id\s+\$(?:\{PID\}|PID\b)",
    re.IGNORECASE)
# 对象变量 Kill 调用点: `$var.Kill()` / `$var.Terminate()` / `-InputObject $var`
# / `-Id $var.Id` / `-Id $var` — 小欧 2026-11-26
_OBJECT_KILL_VAR_RES = (
    re.compile(r"\$(?:\{(\w+)\}|(\w+))\s*\.\s*(?:kill|terminate)\s*\(", re.IGNORECASE),
    re.compile(r"-inputobject\s+\$(?:\{(\w+)\}|(\w+))", re.IGNORECASE),
    re.compile(r"-id\s+\$(?:\{(\w+)\}|(\w+))(?:\s*\.\s*id)?\b", re.IGNORECASE),
)




# 标量变量赋值: `$var = $PID|${PID}`(自身)、`$var = <数字>`(字面PID)、`$var = $other`(别名)。
# 变量间接杀(`$id=$PID; Stop-Process -Id $id`)绕过 `-id $` 的 BOUNDED 兜底漏拦, 须还原目标。
# 交互式变量大小写不敏感(PowerShell 语义), 建表与查表统一小写 — 小欧 2026-11-26
_SCALAR_ASSIGN_RE = re.compile(
    r"\$(?:\{(?P<a>\w+)\}|(?P<b>\w+))\s*=\s*"
    r"(?P<rhs>\$\{PID\}|\$PID\b|\d+|\$\{\w+\}|\$\w+)",
    re.IGNORECASE)
# `-Id $var` 标量引用(不含 `.Id`; `-Id $p.Id` 是对象变量, 归 _OBJECT_KILL_VAR_RES)
_ID_VAR_REF_RE = re.compile(r"-id\s+\$(?:\{(\w+)\}|(\w+))", re.IGNORECASE)



def _build_array_vars(command: str) -> dict:
    """整条命令抽 `$var=@(数字列表)` / `$var=1,2` 数组赋值 — 小欧 2026-11-26

    收纯数字列表(`@(1,2,3)` / 裸 `1,2`); 含表达式/变量的数组(`@($a,$b)` / `@(Get-Process)`)
    记 None = 存在但静态不可枚举, 迭代源引用它时按无界处理(不猜)。build_var_map
    只收字面量字符串赋值, 不覆盖数组赋值, 故单建本表(职责不同: 数组 vs 字符串)。
    """
    out: dict = {}
    for m in _ARRAY_ASSIGN_RE.finditer(command or ""):
        name = m.group("a") or m.group("b")
        if m.group("body") is None:
            bare = m.group("bare") or ""
            out[name] = {int(x) for x in re.split(r"[\s,]+", bare) if x.isdigit()}
            continue
        body = m.group("body").strip()
        if body and re.fullmatch(r"[\d,\s]+", body):
            out[name] = {int(x) for x in re.split(r"[\s,]+", body) if x.isdigit()}
        else:
            out[name] = None
    return out


def _build_object_vars(command: str) -> Tuple[dict, set]:
    """抽 `$var=Get-Process -Id <数字>` 对象变量(PID 可枚举)与源为 $PID 的变量 — 小欧 2026-11-26

    返回 (var→PID集合, 源为 $PID 的变量名集合)。`$var.Kill()` / `-InputObject $var`
    引用这些变量时, 目标可静态还原为 PID 交保护盾核对; 源为 $PID 的变量必自杀, 单列硬拦。
    """
    pids_map: dict = {}
    self_vars: set = set()
    for m in _OBJECT_PID_ASSIGN_RE.finditer(command or ""):
        name = m.group("a") or m.group("b")
        pids_map[name] = {int(x) for x in re.split(r"[\s,]+", m.group("ids")) if x.isdigit()}
    for m in _OBJECT_SELF_ASSIGN_RE.finditer(command or ""):
        self_vars.add(m.group("a") or m.group("b"))
    return pids_map, self_vars



def _build_scalar_vars(command: str) -> Tuple[dict, set]:
    """抽标量变量赋值 `$v=$PID`(自身) / `$v=<数字>`(字面PID) / `$v=$w`(别名) — 小欧 2026-11-26

    返回 (var→PID集合, 源为 $PID 的变量名集合), 键统一小写(PowerShell 变量名大小写不敏感)。
    别名按赋值链传递(`$a=$PID; $b=$a` 中 $b 亦自身); 无法解析的(表达式/未定义)不收录,
    引用处维持 `-Id $` 的 bounded_dynamic 兜底, 不误伤。
    """
    raw: dict = {}
    for m in _SCALAR_ASSIGN_RE.finditer(command or ""):
        name = (m.group("a") or m.group("b")).lower()
        rhs = m.group("rhs")
        low = rhs.lower()
        if low in ("$pid", "${pid}"):
            raw[name] = "self"
        elif rhs.isdigit():
            raw[name] = {int(rhs)}
        else:
            raw[name] = ("alias", rhs.lstrip("$").strip("{}").lower())
    pids_map: dict = {}
    self_vars: set = set()
    for name in raw:
        cur, seen = name, set()
        while cur not in seen:
            seen.add(cur)
            val = raw.get(cur)
            if val == "self":
                self_vars.add(name)
                break
            if isinstance(val, set):
                pids_map[name] = val
                break
            if isinstance(val, tuple) and val[0] == "alias":
                cur = val[1]
                continue
            break
    return pids_map, self_vars


def _scalar_refs(text: str, scalar_pids: dict, scalar_self: set) -> Tuple[Set[int], bool]:
    """扫 `-Id $var` 标量引用, 还原字面 PID / 标记自身变量命中 — 小欧 2026-11-26"""
    extra: Set[int] = set()
    hit = False
    for m in _ID_VAR_REF_RE.finditer(text or ""):
        var = (m.group(1) or m.group(2)).lower()
        if var in scalar_pids:
            extra |= scalar_pids[var]
        if var in scalar_self:
            hit = True
    return extra, hit



def _extract_foreach(seg: str) -> Optional[Tuple[str, str, str]]:
    """取 foreach 迭代变量名/迭代源/块体(括号+引号感知扫描) — 小欧 2026-11-26

    在原始段(未涂引号)上扫: `foreach ($x in <源>)` 的 <源> 可能自带括号(`@(1,2)` /
    `(Get-Process)`), 正则非贪婪会在第一个 `)` 处误截, 故用深度计数切出完整源。
    引号内的括号不参与计数, 源文本保留引号原文 —— 涂空文本会把 `"a","b"` 误涂成 `,`
    而误判为纯数字有界(病根)。返回 (变量名, 源表达式, 源之后的块体文本); 头不完整返回 None。
    """
    m = _FOREACH_HEAD_RE.search(seg or "")
    if not m:
        return None
    var = m.group("var")
    i, n, depth, quote = m.end(), len(seg), 0, None
    start = i
    while i < n:
        ch = seg[i]
        if quote:
            if ch == quote:
                quote = None
            i += 1
            continue
        if ch in ("'", '"'):
            quote = ch
            i += 1
            continue
        if ch == "(":
            depth += 1
        elif ch == ")":
            if depth == 0:
                return var, seg[start:i], seg[i + 1:]
            depth -= 1
        i += 1
    return None


def _body_is_mass_enum(body: str) -> bool:
    """块体是否为无筛选的全量枚举源(Get-Process 等) — 小欧 2026-11-26

    全量枚举源出现且整段没抽到任何 -Name/-Id 显式目标 → 无上界, 不得被有界
    迭代源豁免(`foreach ($p in @(1,2)) { Get-Process | Stop-Process }` 的块体与
    $p 无关, 是全量杀, 必须仍判无界)。有显式名/ID 的枚举(Get-Process chrome)不算全量。
    """
    if not _MASS_ENUM_RE.search(body or ""):
        return False
    return not (_extract_names(body) or _extract_pids(body))


# 引号字符串列表(迭代源): `"a","b"` / `'a','b'`, 整段须仅由引号串与逗号空白组成 — 小欧 2026-11-26
_STR_LIST_RE = re.compile(
    r"^\s*(?:'[^']*'|\"[^\"]*\")(?:\s*,\s*(?:'[^']*'|\"[^\"]*\"))*\s*$")


def _source_bounded(source: str, array_vars: dict) -> Tuple[bool, Set[int], Set[str]]:
    """判 foreach 迭代源是否有界; 有界时返回可枚举 PID/名字集合 — 小欧 2026-11-26

    有界(True): 显式数字数组 `@(1,2)` / 括号数字列表 `(1,2)` / 裸数字列表 `1,2`
      → PID 即列表; 数字范围 `1..N`(N≤上限)→ 展开, 超上限判有界但不展开;
      数字数组变量 `$var`(取值表命中纯数字)→ PID 即该数组;
      引号字符串列表 `"a","b"` / `'a','b'` → 名字即列表(交保护盾核对, 不误伤普通名)。
    无界(False): `$var` 未命中/非数字数组、`$_`/`$( )`、
      Get-Process/Get-CimInstance/Get-WmiObject/wmic 及任何其它表达式 —— 保守判无界。
    """
    raw = (source or "").strip()
    s = strip_quotes(raw)
    var = re.fullmatch(r"\$(\w+)", s) or re.fullmatch(r"\$\{(\w+)\}", s)
    if var:
        pids = array_vars.get(var.group(1))
        return (True, set(pids), set()) if pids else (False, set(), set())
    inner = s
    paren = re.fullmatch(r"@?\((.*)\)", raw, re.DOTALL)
    if paren:
        inner = paren.group(1).strip()
    rng = re.fullmatch(r"(\d+)\s*\.\.\s*(\d+)", inner)
    if rng:
        lo, hi = int(rng.group(1)), int(rng.group(2))
        if 0 <= lo <= hi and hi - lo <= _FOREACH_RANGE_MAX:
            return True, set(range(lo, hi + 1)), set()
        return True, set(), set()
    if inner and re.fullmatch(r"[\d,\s]+", inner):
        return True, {int(x) for x in re.split(r"[\s,]+", inner) if x.isdigit()}, set()
    # 引号字符串列表: 用保留引号的原文判定, 抽为 literal 名字集合(自身名硬拦, 普通名放行)
    str_src = paren.group(1).strip() if paren else raw
    if _STR_LIST_RE.match(str_src):
        str_names = {a or b for a, b in re.findall(r"'([^']*)'|\"([^\"]*)\"", str_src)}
        str_names = {n for n in str_names if n and not _WILDCARD_ALL_RE.match(n)}
        if str_names:
            return True, set(), str_names
    return False, set(), set()


def _classify(verb: str, seg_blanked: str, pids: Set[int], names: Set[str],
              foreach_bounded: bool = False, foreach_ok: bool = False,
              self_pid_hit: bool = False) -> str:
    """目标三态判定 — 小欧 2026-11-15

    优先级: opaque(不可见) > unbounded(无上界信号) > literal(有显式目标) >
            bounded_dynamic(单对象变量: -Id $v 或方法调用 $p.Kill()) > unbounded(兜底无界)。
    2026-11-15 严格测试整改: 服务杀动词(Stop-Service/Restart-Service)一律 bounded —
    服务名不是进程名, 静态不可证实安全, 显式目标也须转人工确认。
    2026-11-26 小欧 - foreach 有界性: foreach_ok=True(块体已解析: 引用有界迭代变量, 或为与
    迭代变量无关的确定操作)时豁免 foreach 无界信号; 无界迭代源(Get-Process/$_/非数字变量)或
    块体内独立全量枚举源仍走 unbounded 硬拦。foreach_bounded=True 兜底转确认(源有界但未展开)。
    其余无界信号($_/foreach-object/%{/$( ))不受影响, 始终优先。
    """
    if self_pid_hit:
        return UNBOUNDED
    if _OPAQUE_RE.search(seg_blanked):
        return OPAQUE
    if any(rx.search(seg_blanked) for rx in _UNBOUNDED_RES):
        return UNBOUNDED
    if _FOREACH_SIGNAL_RE.search(seg_blanked) and not foreach_ok:
        return UNBOUNDED
    if verb in ("stop-service", "restart-service"):
        return BOUNDED
    if pids or names:
        return LITERAL
    if foreach_bounded:
        return BOUNDED
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
    array_vars = _build_array_vars(command)
    object_vars, self_obj_vars = _build_object_vars(command)
    scalar_pids, scalar_self = _build_scalar_vars(command)
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
                # 静态不可见(-EncodedCommand/iex/bash -c): 显式目标可见时按 literal 交保护盾核对,
                # 不可见才分类 opaque 放行(杀不杀由 LLM 自决)。堵 iex "Stop-Process -Id <自身PID>"
                # 一类"目标其实静态可见却被 opaque 一律放行"的自杀漏拦。
                m = _OPAQUE_RE.search(blanked)
                op_pids, op_names = _segment_targets(seg, shell_normalize_command(seg))
                if op_pids or op_names:
                    actions.append(ProcessAction(m.group(0).lower(), LITERAL, op_pids, op_names))
                else:
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
            # 2026-11-26 小欧 - 对象变量 Kill 目标解析: `$p=Get-Process -Id <数字>; $p.Kill()`
            # / `-InputObject $p` 目标静态可枚举, 并入 PID 交保护盾核对(堵变量自杀漏拦)。
            # 源为 $PID 的对象变量必自杀, 记 self_pid_hit 硬拦。
            self_pid_hit = False
            for rx in _OBJECT_KILL_VAR_RES:
                for m in rx.finditer(seg):
                    var = m.group(1) or m.group(2)
                    if var in object_vars:
                        pids = pids | object_vars[var]
                    if var in self_obj_vars:
                        self_pid_hit = True
            # 2026-11-26 小欧 - 标量变量间接: `$id=$PID; Stop-Process -Id $id` /
            # `$target=<数字>; Stop-Process -Id $target` 还原目标(自身硬拦 / 字面PID 交保护盾),
            # 堵 `-Id $var` 落 BOUNDED 兜底的变量间接自杀漏拦。
            sc_pids, sc_self = _scalar_refs(seg, scalar_pids, scalar_self)
            pids = pids | sc_pids
            if sc_self:
                self_pid_hit = True
            # PowerShell 自动变量 $PID = 当前进程 PID(自己人), 出现在杀段或上游段即硬拦
            if shell in ("ps7", "ps5") and _SELF_PID_VAR_RE.search(seg):
                self_pid_hit = True
            # 2026-11-26 小欧 - foreach 有界性: 仅在块体确实消费有界迭代变量时并入 PID 并豁免;
            #   块体与迭代变量无关且为全量枚举(Get-Process)时不得豁免, 否则全杀被误判放行
            foreach_bounded = False
            foreach_ok = False
            fe = _extract_foreach(seg)
            if fe is not None:
                fe_var, fe_source, fe_body = fe
                body_refs = re.search(
                    r"\$\{?%s(?![a-z0-9_])" % re.escape(fe_var), fe_body, re.IGNORECASE)
                if body_refs:
                    bounded, src_pids, src_names = _source_bounded(fe_source, array_vars)
                    if bounded:
                        foreach_bounded = True
                        foreach_ok = True
                        pids = pids | src_pids
                        names = names | src_names
                elif not _body_is_mass_enum(fe_body):
                    foreach_ok = True
            # 2026-11-15 小欧 严格测试整改: 上游段目标无条件并入(`Get-Process python |
            #  Stop-Process -Name node` 管道与 -Name 各杀各的, 只看杀段会漏 python)
            blanked_all = blanked
            for upstream in segments[:idx]:
                up_pids, up_names = _segment_targets(upstream, shell_normalize_command(upstream))
                pids, names = pids | up_pids, names | up_names
                blanked_all += " ; " + lexer.blank_quotes(upstream)
                if shell in ("ps7", "ps5") and _SELF_PID_VAR_RE.search(upstream):
                    self_pid_hit = True
                up_sc_pids, up_sc_self = _scalar_refs(upstream, scalar_pids, scalar_self)
                pids = pids | up_sc_pids
                if up_sc_self:
                    self_pid_hit = True
            verb = verb_hit.group(0).lower()
            if _WMIC_MASS_RE.search(blanked):
                verb = "wmic process"
            actions.append(ProcessAction(
                verb,
                _classify(verb, blanked_all, pids, names, foreach_bounded, foreach_ok,
                          self_pid_hit),
                pids, names))
    return actions


__all__ = [
    "ProcessAction", "LITERAL", "BOUNDED", "UNBOUNDED", "OPAQUE", "TARGET_KINDS",
    "parse_kill_actions", "strip_comment", "strip_quotes",
]
