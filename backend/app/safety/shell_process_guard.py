# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-16 - 小欧 - 新建: shell 进程防护快照组装(无状态纯函数)。
#   本体自 app/safety/tool_safety_checker.py:162-196 逐字搬迁，只改两处:
#   收 pool_pids 参数、_protected_pids 内部自拼改由上游调用方递入。
#   零 import 工具层；不建注册表、不存量（见 [36] 第四章）。
# 2026-10-16 - 小欧 - 文档[36] 第七章: 自杀检查全部归并到本模块(北京老陈裁定)。
#   病根: 自杀检查此前散在三个模块 —— 组装在本文件、判定在 shell_command_process.py、
#   编排又在 tool_safety_checker.py，而第二套(仅 PID 口径)还留在 shell_command_risk.py 的
#   43 条危险模式里。同一条防护链被切成四块，既难审计也易漏(两套口径还不一致)。
#   处置: 判定逻辑 + 全部相关正则 + 第二套 PID 提取一并搬入, 对外只留一个入口
#   check_shell_self_kill(command, pool_pids) -> bool，只答"通过/不通过"；
#   返回值与用户可见文案由调用方(tool_safety_checker)构造 —— 本模块不产 SafetyResult。
#   搬运纪律: AGENTS 1.4 能复制不重写, 全部代码逐字搬迁, 只改 import 与函数名。
"""shell 自杀检查 — 安全层无状态纯函数（零 import 工具层）

用途  : 判断命令要杀的进程是不是自己人（自己 / 父进程 / Shell 池）
调用  : app/safety/tool_safety_checker.py 的 check_before_execute，在 _check_known_risks 之前
对外  : check_shell_self_kill(command, pool_pids) -> bool   ← 唯一入口，只答通过/不通过
"""
import fnmatch
import os
import re
from typing import Optional

from app.logger import logger
from app.safety.shell_command_process import shell_normalize_command


def build_protected_pids(pool_pids: Optional[set] = None) -> set:
    """宿主关键进程 PID 集合（后端自身+父进程+传入的 shell 池快照）— 小欧 2026-10-16

    pool_pids=None 退化为仅自身+父进程，不崩；退化必打 warning 留痕（静默退化=池失护）。
    """
    pids = {os.getpid(), os.getppid()}  # uvicorn --reload 父子双进程，getppid 必带
    if pool_pids:
        pids |= set(pool_pids)
    elif pool_pids is None:  # 三堂会审补：None=上游未递入（留痕）；空集=池空闲（常态，不留痕）
        logger.warning("[shell_process_guard] 未递入池快照，退化为仅自身+父进程")
    return pids


def build_protected_names(pids: set) -> set:
    """受保护进程名集合（由 PID 反查名，防按名杀）— 小欧 2026-10-16

    psutil 不可用/进程已退出时降级为空集（退化为仅 PID 口径），不拖垮安全判定。
    """
    names = set()
    try:
        import psutil
    except ImportError:
        return names
    for pid in pids:
        try:
            names.add(psutil.Process(pid).name())
        except Exception:
            continue
    return names


# ══════════════════════════════════════════════════════════════════════
# 三、杀进程防护: 不可隔离动词 + 受保护进程(2026-10-08 事故驱动)


# 2026-10-08 小欧 前后向断言用 [a-z0-9_-] 字符类而非 \b: \b 会让 kill 命中 "killall"/"taskkill" 内部。


# 2026-10-10 小欧 猎杀#1#2(WMI/CIM 方法杀): Get-WmiObject … $_.Terminate() / Get-CimInstance … Invoke-CimMethod ——
#   动词表(Stop-Process/taskkill/…/kill)与 43 条(无 Get-WmiObject/CIM 口径)全链漏网 → 预检真跑。
#   口径: 只认方法调用点 `.Terminate(`/`.Kill(` 与 cmdlet 名 Invoke-CimMethod, 不认裸词 terminate
#   (正文"terminate the loop"类误伤面大, 取严也要有边)。Get-WmiObject 裸查询(无 Terminate)不认, 它只是读。


_CIM_KILL_RE = re.compile(r"(?<![a-z0-9_-])invoke-cimmethod(?![a-z0-9_-])", re.IGNORECASE)
# 2026-10-10 小欧 猎杀#4(Base64): -EncodedCommand(PS 为 UTF-16LE 的 base64)内容静态不可见, 全链零规则。
#   取严: 见到即转 HITL(用户面对 base64 同样无法有效确认, 属残留风险, 不冒充已解决)。
#   口径: 只认 -EncodedCommand / -enc 全词; -e 单字母不认(撞 -ErrorAction 类, 误伤面大)。


# 2026-10-10 小欧 猎杀#4(Base64): -EncodedCommand(PS 为 UTF-16LE 的 base64)内容静态不可见, 全链零规则。
#   取严: 见到即转 HITL(用户面对 base64 同样无法有效确认, 属残留风险, 不冒充已解决)。
#   口径: 只认 -EncodedCommand / -enc 全词; -e 单字母不认(撞 -ErrorAction 类, 误伤面大)。


# 2026-10-08 小欧 PID 目标提取三形态: Stop-Process -Id / taskkill /PID / kill [-9] PID; 按名与 pkill 返空集。


# —— 按名杀目标提取(2026-10-10 小欧 新增, 审计 P1-3): 补保护盾对真实事故形态的盲区 ————————
# E2E P9-03 事故命令 `Get-Process python | Stop-Process -Force` 是按名杀, _PID_TARGET_RES 只认 -Id,
# 抽出恒为空集 → 原保护盾对事故形态贡献为 0。四个形态: -Name / Get-Process 管道 / taskkill /IM / killall。
# 组装(受保护进程名从哪来)仍归 safety 侧 tool_safety_checker._protected_process_names, 本模块只出纯函数。
_NAME_TOKEN = r"[\w.*?+-]+(?:\.exe)?"

# —— 不可隔离动词与目标提取正则（逐字搬运）—————————————————————
SHELL_HIDDEN_KILL_VERBS = (
    "stop-process", "taskkill", "wmic process",     # 杀进程(致命形态: -Id/-Name/管道/无目标)
    "stop-service", "restart-service",              # 停服务(致命形态: 只 sc/net, 非 Stop-Service)
    "pkill", "killall", "kill",                     # bash 杀进程(不用 \bkill\b 匹配, 否则 pkill)
)
_UNCONTAINABLE_RE = re.compile(
    r"(?<![a-z0-9_-])(?:" + "|".join(re.escape(v) for v in SHELL_HIDDEN_KILL_VERBS) + r")(?![a-z0-9_-])",
    re.IGNORECASE)
_METHOD_KILL_RE = re.compile(r"\.\s*(terminate|kill)\s*\(", re.IGNORECASE)
_ENCODED_RE = re.compile(r"(?<![a-z0-9_-])-(?:encodedcommand|enc)\b", re.IGNORECASE)
_PID_TARGET_RES = (
    re.compile(r"stop-process\W*(?:[\w-]+\s+)*-id\s+([\d,\s]+)", re.IGNORECASE),
    re.compile(r"/pid\s+(\d+)", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])kill\s+(?:-[\w]+\s+)*(\d+)", re.IGNORECASE),
    # 2026-10-10 小欧 猎杀#7(/FI): taskkill /FI "PID eq 123" —— 无 /PID 开关, 旧口径零提取。
    re.compile(r"(?<![a-z0-9_-])\bpid\s+eq\s+(\d+)", re.IGNORECASE),
)
# 管线进杀器: `… | Stop-Process/taskkill/kill…`(有名/有PID 的走正常口径, 这里只管裸的)
_PIPE_KILL_RE = re.compile(r"\|\s*(?:stop-process|taskkill|pkill|killall|kill)\b", re.IGNORECASE)
# 求助与演习: /\?、--help、-h、-WhatIf 形态是"求助/演习"不是"杀进程", 求助让路(不硬拦)
_HELPISH_RE = re.compile(r"/\?|--help|(?<![a-z0-9_-])-h\b|-whatif\b", re.IGNORECASE)
# 引号 span: 兜底只认引号之外的动词, 如 `echo "kill"` 是数据不是动词, 交数据给 HITL, 不到这里 blocked(取严要有边界)
_QUOTED_SPAN_RE = re.compile(r"'[^']*'|\"[^\"]*\"")

_KILL_NAME_RES = (
    re.compile(r"(?<![a-z0-9_-])-name\s+(" + _NAME_TOKEN + r"(?:\s*,\s*" + _NAME_TOKEN + r")*)", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])/im\s+(" + _NAME_TOKEN + r")", re.IGNORECASE),
    re.compile(r"(?<![a-z0-9_-])killall\s+(" + _NAME_TOKEN + r")", re.IGNORECASE),
    # 2026-10-10 小欧 猎杀#7(/FI): taskkill /FI "IMAGENAME eq X" —— 无 /IM 无 /PID, 旧口径零提取 → 仅HITL。
    re.compile(r"(?<![a-z0-9_-])imagename\s+eq\s+(" + _NAME_TOKEN + r")", re.IGNORECASE),
    # 2026-10-10 小欧 猎杀#8(wmic/WMI 名): `wmic process where name='x' [call terminate|delete]` /
    #   WMI -Filter "name='x'" / CIM -Query "…WHERE Name='x'" —— 名在过滤子句里, 旧口径零提取。
    #   前后向断言挡 hostname/filename("…name" 前是 word 字符则不认)。
    re.compile(r"(?<![a-z0-9_-])name\s*=\s*['\"]?(" + _NAME_TOKEN + r")['\"]?", re.IGNORECASE),
    # 2026-10-10 小欧 猎杀#10(pkill): `pkill [-9] [-f] <模式>` 实参即目标模式, 旧口径零提取。
    #   交 _name_matches 走 fnmatch(模式串与受保护名双向匹配; `.*` 天然全中)。首字符禁 `-`(挡 -9/-f 本身被当成名)。
    re.compile(r"(?<![a-z0-9_-])pkill\s+(?:-[\w]+\s+)*(?:-f\s+)?([A-Za-z0-9_.?*][\w.*?+-]*(?:\.exe)?)",
               re.IGNORECASE),
)


def _strip_quotes(s: str) -> str:
    """去首尾引号(名提取的引号在归一文里已无, 此函数只处理原文残留) — 小欧 2026-10-10"""
    return (s or "").strip().strip("\"'")


def shell_extract_kill_target_names(command: str) -> set:
    """按名杀的进程名目标集合(逗号多值已拆开) — 小欧 2026-10-10

    适用: 供 is_shell_process_kill_protected 补按名口径; 按名形态抽不出 PID(shell_extract_kill_target_pids 返空集),
    只靠 PID 的保护盾会漏。归一化(.exe 去尾 + casefold + 通配)在 _name_matches 内做, 此处只出原样名。
    2026-10-10 小欧 补(猎杀#5#6: 引号名 `-Name "python"` / `/IM "x.exe"` / `-Name 'a','b'` 原文零提取):
      同步扫归一文(归一已去引号), 复用 P1-1 并集模式; 不放宽 token 类(动 token 类会放宽原文口径, 不如并集干净)。
    """
    names = set()
    if shell_has_hidden_kill(command):
        for text in {command or "", shell_normalize_command(command)}:
            for rx in _KILL_NAME_RES:
                for m in rx.finditer(text):
                    names.update(_strip_quotes(n) for n in re.split(r"\s*,\s*", m.group(1)))
            names.update(shell_extract_kill_target_names_from_pipeline(text))
    return {n for n in names if n}


def shell_extract_kill_target_names_from_pipeline(command: str) -> set:
    """`Get-Process <名> | Stop-Process` 管道形态的目标名 — 小欧 2026-10-10

    独立成函数: 该形态不经 -Name 参数, 但正是 P9-03 事故原形, 不抽则保护盾对事故形态依旧为 0。
    """
    out = set()
    for m in re.finditer(r"(?<![a-z0-9_-])get-process\s+((?![\s|;&]*\|)[\w.*?-]+(?:\.exe)?)",
                         command or "", re.IGNORECASE):
        out.add(m.group(1).strip().strip("\"'"))
    return {n for n in out if n}


def shell_has_hidden_kill(command: str) -> bool:
    """命令是否含不可隔离动词(杀进程/停服务) — 小欧 2026-10-08

    适用: shell 沙箱预检前静态判定, 命中转 HITL 不得 run(预检在宿主真跑, 跑即防线自破)。
    排除: Stop-Computer/Format-Volume/shutdown 已是 HIGH 级, 安全检查阶段就 blocked, 收录即重复(DRY)。
    2026-10-10 小欧 补: 原文与归一文取并集(拼接还原的 'Stop'+'-Process' 原文查不到, 归一后查得到)。
    2026-10-10 小欧 补(猎杀#1#2#4): .Terminate()/.Kill() 方法调用、Invoke-CimMethod、-EncodedCommand
      同视为不可隔离意图(前两者全链漏网预检真跑; Base64 内容不可见, 转 HITL 为残留风险)。
    """
    if not command:
        return False
    norm = shell_normalize_command(command)
    return (bool(_UNCONTAINABLE_RE.search(command)) or bool(_UNCONTAINABLE_RE.search(norm))
            or bool(_METHOD_KILL_RE.search(command)) or bool(_CIM_KILL_RE.search(command))
            or bool(_ENCODED_RE.search(command)))


def shell_extract_kill_target_pids(command: str) -> set:
    """命令显式指定的杀进程目标 PID 集合 — 小欧 2026-10-08

    覆盖 Stop-Process -Id a,b / taskkill /PID n / kill [-9] n; 按名与管线形态枚举不了, 返回空集。
    2026-10-10 小欧 补: 同样取原文与归一文并集, 覆盖 & ('Stop-Process') -Id n 这类带引号形态。
    """
    pids = set()
    for text in {command or "", shell_normalize_command(command)}:
        for rx in _PID_TARGET_RES:
            for m in rx.finditer(text):
                pids.update(int(x) for x in re.split(r"[\s,]+", m.group(1)) if x.isdigit())
    return pids


def _name_matches(target: str, protected_names: set) -> bool:
    """杀进程目标名是否命中受保护进程名 — 小欧 2026-10-10

    口径: 统一去 .exe 后缀 + casefold(PowerShell -Name 用无后缀名, taskkill /IM 用带后缀镜像名);
    含通配符走 fnmatch(PowerShell -Name python* / pkill -f 支持通配)。
    """
    norm = lambda s: (s or "").strip().casefold().removesuffix(".exe")
    tgt = norm(target)
    if not tgt:
        return False
    for name in protected_names or ():
        pname = norm(name)
        if not pname:
            continue
        if fnmatch.fnmatch(pname, tgt) or fnmatch.fnmatch(tgt, pname):
            return True
    return False


def is_shell_process_kill_protected(command: str, protected_pids: set, protected_names: set = None) -> bool:
    """命令目标是否命中受保护进程 — 小欧 2026-10-08

    适用: 阻止杀宿主关键进程(后端自身/父进程/shell 池), 命中即 blocked。
    取值: protected_pids/protected_names 均由调用方注入(组装归 safety 侧 tool_safety_checker, 见 8.4)。
    2026-10-10 小欧 增按名匹配(审计 P1-3): 事故命令 `Get-Process python | Stop-Process -Force`
      属按名杀, 原实现只抽显式 PID 恒返空集, 保护盾对真实事故形态贡献为 0;
      补 protected_names 后该形态才拦得住。签名新增第三参(可选, 不传则退化为仅 PID 口径)。
    2026-10-10 小欧 增无目标兜底(猎杀#9): 见 _unscoped_process_kill。
    """
    if not command:
        return False
    if protected_pids and (shell_extract_kill_target_pids(command) & set(protected_pids)):
        return True
    if _unscoped_process_kill(command):
        return True
    if not protected_names:
        return False
    return any(_name_matches(target, protected_names)
               for target in shell_extract_kill_target_names(command))


_PROCESS_KILL_VERBS = (
    "stop-process", "taskkill", "wmic process",     # PS/CMD 侧(停服务动词不在此列)
    "pkill", "killall", "kill",                     # bash 侧
)


_PROCESS_KILL_VERB_RE = re.compile(
    r"(?<![a-z0-9_-])(?:" + "|".join(re.escape(v) for v in _PROCESS_KILL_VERBS) + r")(?![a-z0-9_-])",
    re.IGNORECASE)
# 管线进杀器: `… | Stop-Process/taskkill/kill…`(有名/有PID 的走正常口径, 这里只管裸的)


# 管线进杀器: `… | Stop-Process/taskkill/kill…`(有名/有PID 的走正常口径, 这里只管裸的)


# 求助与演习开关: /?、--help、-WhatIf —— 这些形状不杀生, 兜底必须让路


# 引号 span: 兜底只认引号之外的动词 —— `echo "kill"` 纯提及必须留在 HITL, 不许升 blocked(取严但可确认)。


def _wmic_mass_action(text: str) -> bool:
    """wmic process 配 delete / call terminate 即质量动作(裸 `wmic process [get …]` 查询不在此列)。"""
    return (bool(re.search(r"(?<![a-z0-9_-])wmic\s+process\b", text, re.IGNORECASE))
            and bool(re.search(r"(?<![a-z0-9_-])(?:delete|call\s+terminate)\b", text, re.IGNORECASE)))


def _unscoped_process_kill(command: str) -> bool:
    """无目标杀进程形 → True(直接 blocked)。2026-10-10 小欧 猎杀#9 —

    病根: 管线裸杀(`Get-Process | Stop-Process`)、无参 taskkill、wmic 质量动作、
    `kill %1`、`kill -9 $(…)` 等静态抽不出任何目标(PID/名皆空), 用户面对弹窗同样
    枚举不出目标, 确认无意义; 且目标集合无上界(含后端自身可能)。
    边界:
      · 有名/有 PID(无论是否受保护)走原口径, 不由此函数拦截(HITL 由上游定);
      · 停服务动词(Stop-Service/Restart-Service)不在此列 —— `Stop-Service x` 的 x 即目标, 作用域明确;
      · 求助与演习(/ ?, --help, -WhatIf)让路, 不拦;
      · wmic 裸查询(`wmic process [get …]`)让路, 只拦配 delete/call terminate 的质量动作。
    """
    text = command or ""
    if _HELPISH_RE.search(text):
        return False
    bare = _QUOTED_SPAN_RE.sub("", text)   # 兜底只认引号之外的动词(`echo "kill"` 留 HITL)
    if not (_PROCESS_KILL_VERB_RE.search(bare) or _METHOD_KILL_RE.search(bare)
            or _CIM_KILL_RE.search(bare)):
        return False
    if shell_extract_kill_target_pids(command) or shell_extract_kill_target_names(command):
        return False                                            # 有目标 → 走原口径
    if _PIPE_KILL_RE.search(bare):
        return True                                             # 管线裸杀
    if re.search(r"(?<![a-z0-9_-])taskkill\b", bare, re.IGNORECASE):
        # 无 /IM /PID /FI, 或 /FI 抽不出目标(如 STATUS 全杀) —— 到此目标恒空, 皆无界质量动作
        return True
    if _wmic_mass_action(bare):
        return True                                             # wmic 质量动作
    if _METHOD_KILL_RE.search(bare) or _CIM_KILL_RE.search(bare):
        return True                                             # 方法杀/CIM 无名 → 无界
    if re.search(r"(?<![a-z0-9_-])(?:stop-process|pkill|killall|kill)\b", bare, re.IGNORECASE):
        return True                                             # 裸杀器(`kill %1`/`kill -9 $(…)` 之类)
    return False


# ══════════════════════════════════════════════════════════════════════
# 第二套 PID 提取（自 shell_command_risk.py 逐字搬迁 · 2026-10-16 第七章）
# 病根: 这三套原是 43 条危险模式里的 C20-C22 拦截点用, 与主实现的 PID 提取**各写一份**,
#   口径还不一样(这三套只认 PID, 主实现还认进程名与无目标兜底)。同一防护两处实现, 易漏。
# 处置: 一并归并本模块; 原 C20-C22 规则本体仍留在 SHELL_DANGEROUS_PATTERNS(那是"危险分级",
#   与"杀的是不是自己人"是两回事), 但它的自杀拦截改由 check_shell_self_kill 统一承担。
# ══════════════════════════════════════════════════════════════════════
def _extract_stop_process_pids(command: str) -> set:
    """从 Stop-Process -Id 5092,19128 提取目标PID集合 — 小欧 2026-07-31"""
    m = re.search(r'Stop-Process\s+(?:.*?\s)?-Id\s+([\d,\s]+)', command, re.IGNORECASE)
    if not m:
        return set()
    pids = {int(x) for x in re.split(r'[\s,]+', m.group(1)) if x.isdigit()}
    logger.debug(f"[Shell安全] _extract_stop_process_pids: command={command[:80]}, 提取PID={pids}")
    return pids


def _extract_taskkill_pids(command: str) -> set:
    """从 taskkill /F /PID 5092 提取目标PID集合 — 小欧 2026-07-31"""
    pids = {int(x) for x in re.findall(r'/PID\s+(\d+)', command, re.IGNORECASE)}
    logger.debug(f"[Shell安全] _extract_taskkill_pids: command={command[:80]}, 提取PID={pids}")
    return pids


def _extract_bash_kill_pids(command: str) -> set:
    """从 bash kill 1234 / kill -9 1234 提取目标PID集合 — 小欧 2026-07-31"""
    m = re.search(r'\bkill\b\s+(?:-\d+\s+)*(\d+(?:\s+\d+)*)', command)
    if not m:
        return set()
    pids = {int(x) for x in m.group(1).split()}
    logger.debug(f"[Shell安全] _extract_bash_kill_pids: command={command[:80]}, 提取PID={pids}")
    return pids


# ══════════════════════════════════════════════════════════════════════
# 对外唯一入口
# ══════════════════════════════════════════════════════════════════════
def check_shell_self_kill(command: str, pool_pids: Optional[set] = None) -> bool:
    """这条命令会不会杀掉自己人 — 小欧 2026-10-16（[36] 第七章 · 北京老陈裁定归并）

    干什么用: 自杀检查唯一入口。由 tool_safety_checker.check_before_execute 在
              **_check_known_risks 之前**调用 —— 自杀与路径无关且一旦执行后续检查皆无意义
              (E2E P9-03 录到过后端自杀事故), 故须排在所有路径/危险判定之前。

    返回    : True = 会自杀(**不通过**, 调用方据此拒绝执行)；False = 通过。
              ★只答通过/不通过, 不产 SafetyResult、不出文案 —— 那是调用方的职责(SRP)。

    覆盖    : 三种口径合并判定(原先散在两处实现, 口径不一致):
              ① 按 PID   —— 主实现 _PID_TARGET_RES + 第二套 Stop-Process/taskkill/bash 三套
              ② 按进程名 —— -Name / /IM / killall / pkill / WMI 过滤子句 / Get-Process 管道
              ③ 无目标兜底 —— 管线裸杀 / 无参 taskkill / wmic 质量动作 / 方法杀 / 裸杀器
    """
    if not command:
        return False
    pids = build_protected_pids(pool_pids)
    names = build_protected_names(pids)
    # 主实现: PID + 进程名 + 无目标兜底(按名杀与无界动作只有它拦得住)
    if is_shell_process_kill_protected(command, pids, names):
        return True
    # 第二套: 仅 PID 口径(原 C20-C22 拦截点), 补主实现的形态盲区
    for extract, label in ((_extract_stop_process_pids, "Stop-Process"),
                           (_extract_taskkill_pids, "taskkill"),
                           (_extract_bash_kill_pids, "kill")):
        hit = extract(command) & pids
        if hit:
            logger.warning(f"[shell_process_guard] {label} 目标PID {hit} 为系统保护进程, 禁止杀死")
            return True
    return False
