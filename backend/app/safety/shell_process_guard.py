# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-16 - 小欧 - 新建: shell 进程防护快照组装(无状态纯函数)。
#   本体自 app/safety/path_tool_safety_checker.py 逐字搬迁, 只改两处:
#   收 pool_pids 参数、_protected_pids 内部自拼改由上游调用方递入。
#   零 import 工具层; 不建注册表、不存量。
# 2026-10-16 - 小欧 - 自杀检查全部归并到本模块。
#   自杀检查此前散在三个模块: 组装在本文件、判定在 shell_command_process.py、
#   编排又在 path_tool_safety_checker.py, 而第二套(仅 PID 口径)还留在 shell_command_risk.py 的
#   43 条危险模式里。同一条防护链被切成四块, 既难审计也易漏(两套口径还不一致)。
#   处置: 判定逻辑 + 全部相关正则 + 第二套 PID 提取一并搬入, 对外只留一个入口
#   check_shell_self_kill(command, pool_pids) -> bool, 只答"通过/不通过";
#   返回值与用户可见文案由调用方(path_tool_safety_checker)构造 — 本模块不产 SafetyResult。
#   搬运纪律: 能复制不重写, 全部代码逐字搬迁, 只改 import 与函数名。
# 2026-11-03 小欧 - 池快照缺失退化提示 WARNING→INFO(退化兜底非故障, 仍留日志可查)
# 2026-11-15 小欧 - 两处误拦修复: ①_CIM_KILL_RE 只认裸词 invoke-cimmethod, Invoke-CimMethod -MethodName Create(启动进程)被误判成杀 → 收紧为必须 -MethodName terminate|kill; ②_unscoped 方法杀兜底对单变量目标($p.Kill(), 对象唯一有界)不再硬拦 → $_/foreach 批量形态仍拦, 单变量让路 HITL
# 2026-11-15 小欧 - 根治重构(复核九处误拦/漏拦判定: 三段全文正则各自为政+三套 PID 提取并存):
#   判定层改消费解析层 shell_parse.parse_kill 的 ProcessAction 目标三态
#   (literal/bounded_dynamic/unbounded/opaque), 与路径防护 PathAction 同构。
#   删除: _UNCONTAINABLE_RE/_PID_TARGET_RES/_KILL_NAME_RES/_PIPE_KILL_RE/_HELPISH_RE/
#   _QUOTED_SPAN_RE/_METHOD_KILL_RE/_ENCODED_RE/_CIM_KILL_RE/_wmic_mass_action/
#   _unscoped_process_kill/管线名提取/第二套三套 PID 提取(解析层单一真源, DRY)。
#   判定矩阵: literal 未中保护名单→pass; bounded_dynamic/opaque 未中→HITL(经 shell_has_hidden_kill);
#   unbounded 或命中保护名单→blocked。helpish 只在杀动词所在段生效(全文门漏拦病根已除)。
# 2026-11-15 小欧 - 严格测试整改: _name_matches 补 regex 语义兜底 — pkill -f 模式是正则
#   (`pkill -9 -f "py.*"` 实杀 python), fnmatch 把 `.` 当字面量判不中 → 漏拦; 取严只多拦不漏拦。
# 2026-11-15 小欧 - 口径收敛(用户令): 保护范围收到最小 — 硬拦只保"杀自己人"(自身/父/Shell池,
#   按PID与自身镜像名), 无上界杀(必波及自身)仍拦; 系统关键进程(新名单 SYSTEM_PROTECTED_PROCESS_NAMES)
#   与服务杀转 HITL; 其余杀进程(用户程序/第三方/变量/混淆形态)一律放行不提示, 杀不杀由 LLM 依
#   返回信息自决。shell_has_hidden_kill 正名 shell_kill_needs_hitl(只答"目标是否系统关键"), 旧名零残留。

# 2026-11-15 小欧 - 规范整改(按 10 规范): 删生产零消费者的 SHELL_HIDDEN_KILL_VERBS 与
#   shell_extract_kill_target_pids/names(YAGNI/DRY, 词表与提取单一真源在解析层); 清 F401 未用导入
#   (BOUNDED/ProcessAction/_strip_quotes); strip_quotes 在解析层转正后本模块不再跨层引用私有符号。

"""shell 自杀检查 — 安全层无状态纯函数（零 import 工具层）

用途  : 判断命令要杀的进程是不是自己人（自己 / 父进程 / Shell 池）
调用  : app/safety/path_tool_safety_checker.py 的 check_before_execute，在 _check_known_risks 之前
对外  : check_shell_self_kill(command, pool_pids) -> bool   唯一入口, 只答通过/不通过
"""
import fnmatch
import os
import re
from typing import Optional

from app.logger import logger
from app.safety.shell_parse.parse_kill import (
    LITERAL,
    OPAQUE,
    UNBOUNDED,
    parse_kill_actions,
)


def build_protected_pids(pool_pids: Optional[set] = None) -> set:
    """宿主关键进程 PID 集合（后端自身+父进程+传入的 shell 池快照）— 小欧 2026-10-16

    pool_pids=None 退化为仅自身+父进程, 不崩; 退化必留日志(INFO 档可查, 静默退化=池失护)。
    """
    pids = {os.getpid(), os.getppid()}  # uvicorn --reload 父子双进程，getppid 必带
    if pool_pids:
        pids |= set(pool_pids)
    elif pool_pids is None:  # None=上游未递入(告警); 空集=池空闲(常态, 不告警)
        logger.info("[shell_process_guard] 未递入池快照，退化为仅自身+父进程")  # 2026-11-03 小欧: 退化兜底非故障, 降 INFO
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


# 系统关键进程名单(2026-11-15 口径收敛): 杀这些才转 HITL; 不含宿主自身镜像名(那归杀自己人硬拦)
SYSTEM_PROTECTED_PROCESS_NAMES = frozenset({
    "system", "smss", "csrss", "wininit", "winlogon", "services",   # Windows 内核/会话/服务
    "lsass", "svchost", "dwm", "fontdrvhost",                       # 安全/服务宿主/桌面合成
    "init", "systemd",                                              # bash 侧 1 号进程
})


def _name_matches(target: str, protected_names: set) -> bool:
    """杀进程目标名是否命中受保护进程名 — 小欧 2026-10-10

    口径: 统一去 .exe 后缀 + casefold(PowerShell -Name 用无后缀名, taskkill /IM 用带后缀镜像名);
    含通配符走 fnmatch(PowerShell -Name python* / pkill -f 支持通配)。
    2026-11-15 严格测试整改: pkill -f 的模式是正则(`pkill -9 -f "py.*"` 实杀 python)，
    fnmatch 把 `.` 当字面量判不中 → 漏拦; 增补 regex 语义兜底(取严, 只多拦不漏拦)。
    """
    def norm(s):
        return (s or "").strip().casefold().removesuffix(".exe")
    tgt = norm(target)
    if not tgt:
        return False
    for name in protected_names or ():
        pname = norm(name)
        if not pname:
            continue
        if fnmatch.fnmatch(pname, tgt) or fnmatch.fnmatch(tgt, pname):
            return True
        try:
            if re.fullmatch(tgt, pname):
                return True
        except re.error:
            continue
    return False


def shell_kill_needs_hitl(command: str) -> bool:
    """杀目标是否系统关键进程/服务(转 HITL 确认, 不得 run) — 小欧 2026-11-15(口径收敛)

    口径(用户令): 保护范围最小化 — 只有"目标可能是系统关键进程"才弹窗确认:
      1) 服务杀动词(Stop-Service/Restart-Service): 服务由系统托管, 一律转确认;
      2) literal 显式目标命中 SYSTEM_PROTECTED_PROCESS_NAMES(系统关键进程名单);
      3) 其余(普通进程/变量目标/混淆形态)一律 False 放行 — 杀不杀由 LLM 依返回信息自决。
    消费方: sandbox/executor._scan_command_danger_intent(预检不真跑)。
    """
    if not command:
        return False
    for action in parse_kill_actions(command):
        if action.verb in ("stop-service", "restart-service"):
            return True
        if action.target_kind == LITERAL:
            if any(_name_matches(target, SYSTEM_PROTECTED_PROCESS_NAMES)
                   for target in action.names):
                return True
    return False


def is_shell_process_kill_protected(command: str, protected_pids: set, protected_names: set = None) -> bool:
    """命令目标是否命中"杀自己人"(自身/父/Shell池)或无上界杀形 — 小欧 2026-11-15(口径收敛)

    判定矩阵(硬拦只保自己, 2026-11-15 用户令):
      命中保护 PID/自身镜像名 → blocked(杀自己人)
      unbounded               → blocked(无上界必波及自身)
      其余(literal 普通进程/bounded_dynamic/opaque) → False 放行, 不提示;
        系统关键进程的 HITL 由 shell_kill_needs_hitl 承担, 杀不杀普通进程由 LLM 自决。
    取值: protected_pids/protected_names 均由调用方注入(组装归 safety 侧 path_tool_safety_checker)。
    """
    if not command:
        return False
    protected_pids = set(protected_pids or ())
    for action in parse_kill_actions(command):
        if action.target_kind == OPAQUE:
            continue
        if protected_pids and (action.pids & protected_pids):
            return True
        if action.target_kind == UNBOUNDED:
            return True
        if action.target_kind == LITERAL and protected_names:
            if any(_name_matches(target, protected_names) for target in action.names):
                return True
    return False


# ══════════════════════════════════════════════════════════════════════
# 对外唯一入口
# ══════════════════════════════════════════════════════════════════════
def check_shell_self_kill(command: str, pool_pids: Optional[set] = None) -> bool:
    """这条命令会不会杀掉自己人 — 小欧 2026-10-16 / 2026-11-15 根治重构

    干什么用: 自杀检查唯一入口。由 path_tool_safety_checker.check_before_execute 在
              _check_known_risks 之前调用 — 自杀与路径无关且一旦执行后续检查皆无意义
              (曾录到过后端自杀事故), 故须排在所有路径/危险判定之前。

    返回    : True = 会自杀(不通过, 调用方据此拒绝执行); False = 通过。
              只答通过/不通过, 不产 SafetyResult、不出文案 — 那是调用方的职责(SRP)。

    覆盖    : 判定矩阵(2026-11-15 口径收敛, 解析层 parse_kill 单一真源):
              1) 命中保护 PID/自身镜像名(杀自己人)或 unbounded(无上界必波及自身) → blocked
              2) 系统关键进程/服务杀的 HITL 由 shell_kill_needs_hitl 承担, 不在本入口
              3) 其余(普通进程/变量目标/混淆形态) → 放行不提示, 杀不杀由 LLM 自决
    """
    if not command:
        return False
    pids = build_protected_pids(pool_pids)
    names = build_protected_names(pids)
    return is_shell_process_kill_protected(command, pids, names)
