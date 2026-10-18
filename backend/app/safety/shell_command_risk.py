
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-20 - 小欧 - 删 SafetyResult(is_safe=False) 两处 kwarg: SafetyResult 已于 2026-07-18 删除 is_safe 字段, 此处漏改致中危/destructive shell 命令检查 TypeError 崩溃; 删后 blocked/requires_confirmation/safety_level 已正确表达风险意图, 行为不变
# 2026-07-27 - 小欧 - 补全CMD安全检查模式(diskpart/bcdedit/vssadmin/sc delete等HIGH+med); 所有模式加 # PS / # CMD / # PS+CMD 注释
# 2026-07-27 - 小欧 - Bugfix: MEDIUM多命中合并(原只记录首个); 规则分组优化(PS/CMD/PS+CMD); 注释修正(Remove-Item...Recurse标PS+CMD→PS)
# 2026-07-28 - 小欧 - 修复: 新增shell_type参数; 规则加第4元素st_tag("ps"/"cmd"/None); check_shell_command_risk按shell_type过滤不匹配规则
# 2026-07-28 - 小欧 - 临时目录清理误伤修复: 新增_TEMP_SAFE_PATTERNS+_is_temp_cleanup, Remove-Item类HIGH命中时检查目标路径, 若为已知安全临时目录则降级MEDIUM(日志放行), 非临时路径仍HIGH拦截
# 2026-07-28 - 小欧 - shell_type名称改为ps7/ps5/cmd/bash; 新增6条bash安全规则; 过滤逻辑扩展支持ps7/ps5/bash/cmd; _TEMP_SAFE_PATTERNS扩展bash路径
# 2026-07-31 - 小欧 - Shell池进程保护: 新增_extract_stop_process_pids/_extract_taskkill_pids/_extract_bash_kill_pids; check_shell_command_risk加protected_pids参数; Stop-Process/taskkill/kill命中受保护PID时BLOCKED; 三提取函数+拦截点加日志; message优化为"系统保护进程"避免泄露架构细节
# 2026-08-12 - 小欧 - A1越层前置: SafetyResult import 由 app.services.safety.path_tool_safety_checker 改为 app.safety.path_tool_safety_checker(safety 提升为顶层目录, 配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1盲点四: SafetyResult 定义迁入 app/tools/security/safety_result, flow自包含相关工具层, import 同步更新 — 小欧 2026-08-12
# 2026-08-13 - 小欧 - 三堂会审修复#20: 临时目录清理降级被`..`穿越逃逸, Temp\..\important 可降危为MEDIUM确认
#   【病根】_is_temp_cleanup仅对命令串做_TEMP_SAFE_PATTERNS子串匹配, 含 ...\Temp\..\important 仍命中→HIGH递归删除降MEDIUM, 实际目标已逃出临时根
#   【改法】降级前检查normalized含`..`路径穿越标记则不予降危, 直接返回HIGH拦截(blocked=True); 无`..`的明确临时目录清理(如rm -rf $env:TEMP\*)仍降MEDIUM, 无退化
# 2026-08-13 - 小欧 - 三堂会审修复#21: ps7下`rm -rf C:\x`漏检(PS别名Remove-Item -Recurse -Force, 原始串无Recurse/Force词)
#   【病根】PS HIGH规则(原L37-38)要求字面Recurse/Force词, MEDIUM L67也需Force词, `rm -rf`字母flag在ps7下无规则命中(bash规则L57被shell_type过滤)
#   【改法】PS HIGH新增两条字母flag规则: `-[rR][fF]`合并形态与`-[rR]\b.*?-[fF]\b`分离形态; desc含"递归"故临时目录降级逻辑同样生效; 与bash L57口径对齐
#   【说明】文档方案第二条正则(?:Remove-Item|rm|ri|erase|del)\s+.*?\brm\s+-rf\b 需再次rm不成立(首rm已消费), 修正为`-[rR][fF]`合并flag形态
# 2026-09-18 小欧 - safety_level→severity: ConfirmSpec字段+构造调用+比较全量重命名, 历史注释原文还原(勿改) — 小欧-2026-09-18
# 2026-09-18 - 小欧 - 实施: 6处用户可见message改写(逻辑/分级不变)——"高风险Shell操作，含路径穿越，不允许降级"/
#   C19"高风险Shell操作，已阻止执行"/C20-C22"系统保护进程，禁止终止: PID {pid}"/C23"中风险Shell操作，需确认后执行"（半角逗号统一全角） — 小欧-2026-09-18
# 2026-09-18 小欧 - 7.3.4-C18精化(重查挖掘): "不允许降级"为安全内部术语(降危/临时目录豁免机制), 普通用户看不懂;
#   改"路径含穿越符号，已阻止"(说明=命令危险+穿越符号导致不放行+已阻止), 分级blocked不变, 所注参数#20语义保持 — 小欧-2026-09-18
# 2026-10-10 小欧 - 新增 check_shell_command_risk_all_shells(三壳并集): 修预检层21/43条规则死代码缺口。
#   【病根】本函数按第4元素 st_tag 过滤规则, 但调用方 path_tool_safety_checker:319 只传 command,
#          shell_type 吃默认 "ps7" → cmd(14条)/bash(7条)标签规则在预检全被跳过(实测生效22/43),
#          diskpart/sc delete/vssadmin/dd/mkfs/chmod 777/chown/reg add 等预检一律返回 None, 仅执行层才拦。
#   【改法】新增并集函数: ps7/cmd/bash 各跑一遍, 取最高严重度(dangerous>destructive>None);
#          实测召回15条、白名单误伤0/30、日常命令误伤0/24、降级回归0。
#   【为什么不用探测复用】_looks_like_* 探测本身有洞(sc delete 被判 ps7), 并集不依赖探测准确性。
#   【顺带修正】docstring 旧称"None不过滤"与实现相反: None 会把 ps/cmd/bash 三种标签全跳过,
#          仅剩9条双兼容规则(实测), 属假契约, 已改为描述真实行为 — 小欧 2026-10-10
# 2026-10-14 - 小欧 - HIGH 规则仅命中引号内字面量时降为需确认(北京老陈裁定):
#   修只读查询被误硬拦(`Select-String -Pattern "rm -rf" <路径>` 实测 blocked=True)。不剥引号忽略——
#   `powershell -Command "Remove-Item X"` 的危险体就在引号内, 忽略即开洞; 故只降级不豁免, 引号外命中
#   维持原硬拦。降级属安全等级下调, 补 warning log 留痕。
#   遗留(既有缺口, git stash 对比确认非本次引入): cmd `del <file>` 不带 /s 不在 HIGH 词表, 前后均不拦。
# 2026-10-14 - 小欧 - 文档[33] 4.11-D/4.12-A: SafetyResult 改从 app.tools.tool_types 导入; _strip_quoted 改名 mask_quoted_spans(随 4.11-A 迁 shell_static_guard)并同步调用点
# 2026-10-18 - 小欧 - 随契约调整同步: 中风险命中结果补 safety_level="shellparam"(本模块唯一来源, 语义即"中风险命令需人工确认"), 分类由判定点直给而非上层反查文案; 原 severity="risk" 与 needs_confirm=True 等价、属重复编码, 一并删; requires_confirmation 随字段改名, 词表上方功能注释同步。命中条数合并与文案零变更。
# 2026-10-18 - 小欧 - SafetyResult 契约回迁系统层: import 改 app.safety.safety_result(生产者全在本层, 契约随生产者), 判定/构造零改动。
# 2026-10-18 - 小欧 - safety_level 取值单源化(SafetyLevel): shellparam 改 SafetyLevel.SHELL_MEDIUM_RISK, 并写明职责边界 ——
#   本标签只表"与文件路径无关的命令级确认, 作用域=整条命令", 命令内路径的读/写/删权限由 shell_path_check
#   派三线标签承载, 不在本标签职责内。命中条数合并与文案零变更。
"""
shell 中风险命令判定 — 需用户确认，与文件系统路径无关

★ 本文件**只管一件事**: 这条命令属不属于中风险（需确认），且**与文件路径无关**。
  · 危险命令（直接拒绝）→ app/safety/shell_danger_command.py
  · 路径的写/读/删除/改权限 → app/safety/shell_command_process.py + delete/write/read_path_check
  · 自杀检查（杀自己人）→ app/safety/shell_process_guard.py

边界铁律（北京老陈 2026-10-16 裁定）:
  本文件与 shell_danger_command.py **零调用关系**，两者都不含任何文件路径判定。

— 北京老陈 2026-06-27
— 小健 2026-06-27 迁出到独立safety文件
2026-10-16 小欧 - 文档[36] 第七章(北京老陈裁定) 本文件由"分级检查"收敛为**只管中风险**:
  ① HIGH 规则全部移出 → app/safety/shell_danger_command.py(与路径无关的 14 条);
     文件删除类 10 条(Remove-Item/rm/del + Force、del /f)移至 shell_command_process 路径层。
  ② 彻底删除(老陈裁定"没有风险直接通过")6 条: takeown /f、icacls /grant、cacls /grant、
     chmod -R 777、reg add、reg import、reg delete。
  ③ 删本文件内的第二套自杀防护(_extract_* 三函数 + protected_pids 拦截分支) ——
     自杀检查已全部归并 shell_process_guard.check_shell_self_kill, 两处各判一套口径不一致
     (E2E P9-03 的教训: 按名杀事故主实现拦得住、这套只有 PID 口径拦不住)。
  ④ 随之删 protected_pids 形参; _TEMP_SAFE_PATTERNS/_is_temp_cleanup 移至 shell_command_process。
2026-10-16 小欧 - 老陈裁定 severity destructive→risk(纯改名): 沙箱判定已同步; 并删"仅引号内则跳过"判别式, 命中即确认。
"""
import re
from typing import Optional

from app.safety.safety_result import SafetyLevel, SafetyResult  # 契约: 安全层单源
from app.logger import logger


SHELL_MEDIUM_PATTERNS = [
    # ═══════════════════════════════════════════════════════════════════
    # 中风险命令(MEDIUM) - 需用户确认(needs_confirm=True)
    # 格式: (pattern, desc, level, st_tag) — st_tag: "ps"/"cmd"/None(双兼容)
    # ★全部为与文件系统路径无关的操作；路径的写/读/删不在本表(见文件头边界铁律)
    # ═══════════════════════════════════════════════════════════════════
    # ---- PS ----
    (r"Restart-Computer", "重启", "MEDIUM", "ps"),
    (r"Set-ExecutionPolicy", "修改执行策略", "MEDIUM", "ps"),
    (r"Stop-Process\s+.*\bForce\b", "强制停止进程", "MEDIUM", "ps"),
    (r"Start-Process", "启动任意进程", "MEDIUM", "ps"),
    # ---- CMD ----
    (r"wmic\s+process\b", "WMIC进程操作(wmic process)", "MEDIUM", "cmd"),
    (r"net\s+(stop|start)\b", "停止/启动服务(net stop/start)", "MEDIUM", "cmd"),
    (r"\bsc\s+(stop|start)\b", "停止/启动服务(sc stop/start)", "MEDIUM", "cmd"),
    (r"\bsc\s+config\b", "修改服务配置(sc config)", "MEDIUM", "cmd"),
    # ---- PS+CMD ----
    (r"taskkill\s+/f", "强制杀进程", "MEDIUM", None),
    # ---- bash ----
    (r"\bkill\b\s", "kill进程(bash)", "MEDIUM", "bash"),
]

def check_shell_risk_command(command: str, shell_type: str = "ps7") -> Optional[SafetyResult]:
    """中风险命令判定 —— 命中即需用户确认(MEDIUM)

    shell_type: "ps7"/"ps5"/"cmd"/"bash" — 仅匹配该 shell 标签的规则 + 双兼容规则(st_tag=None)。
                要查全 shell 请用 check_shell_risk_command_all_shells(), 不要传 None
                (传 None 会把 ps/cmd/bash 三种标签全跳过, 仅剩双兼容规则生效)。

    2026-10-16 老陈裁定: 本函数只管 MEDIUM；HIGH 已全部移至 shell_danger_command.check_shell_danger_command；
    路径的写/读/删除/改权限不在本表(见 shell_command_process)；自杀检查见 shell_process_guard。
    """
    medium_hits = []
    normalized = command.replace('\r\n', ' ').replace('\n', ' ')
    for pattern_str, desc, level, st_tag in SHELL_MEDIUM_PATTERNS:
        if st_tag == "ps" and shell_type not in ("ps7", "ps5"):
            continue
        if st_tag == "cmd" and shell_type != "cmd":
            continue
        if st_tag == "bash" and shell_type != "bash":
            continue
        if not re.search(pattern_str, normalized, re.IGNORECASE):
            continue
        if desc in medium_hits:
            continue
        medium_hits.append(desc)
    if medium_hits:
        combined = "、".join(medium_hits)
        logger.warning(f"[Shell中风险] 中风险操作: {combined}")
        return SafetyResult(
            blocked=False,
            needs_confirm=True,
            message=f"中风险Shell操作: {combined}，需确认后执行",
            safety_level=SafetyLevel.SHELL_MEDIUM_RISK,
        )
    return None


def check_shell_risk_command_all_shells(command: str) -> Optional[SafetyResult]:
    """中风险命令检查(三壳并集) - ps7/cmd/bash 各查一遍。 — 小欧 2026-10-10

    供不掌握真实 shell_type 的调用方(如 safety 预检门)使用: 单查某一个 shell 会漏掉
    该 shell 之外标签的规则。
    会写死 shell 的调用方(如 execute_shell_command 执行层)应继续传真实 shell_type。

    2026-10-16 老陈裁定(去掉 _SEVERITY_RANK 排序): 中风险层只有一种结果 ——
      命中即 needs_confirm, 不命中就是 None。
      既然只有"命中/不命中", 直接返回第一个即可, 不必建严重度排序表(多余的间接层)。
    无任何 shell 命中时返回 None(无风险)。 — 小欧 2026-10-10
    """
    for _st in ("ps7", "cmd", "bash"):
        r = check_shell_risk_command(command, _st)
        if r is not None:
            return r                     # 命中即返回: 同一 shell 的多个命中已在函数内合并为一条
    return None

