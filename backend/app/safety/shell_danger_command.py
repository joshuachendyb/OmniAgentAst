# -*- coding: utf-8 -*-
# 2026-10-18 - 小欧 - SafetyResult 契约回迁系统层: import 改 app.safety.safety_result(生产者全在本层, 契约随生产者), 判定/构造零改动。
"""shell 危险命令判定 — 与文件系统路径无关的高危操作，命中即拒绝

★ 本文件**只管一件事**: 这条命令危不危险（与文件路径的读/写/删无关）。
  · 路径的写/读/删除/改权限 → app/safety/shell_command_process.py + delete/write/read_path_check
  · 自杀检查（杀自己人）    → app/safety/shell_process_guard.py
  · 中风险命令（需确认）    → app/safety/shell_command_risk.py

边界铁律（北京老陈 2026-10-16 裁定）:
  本文件与 shell_command_risk.py **零调用关系**，两者都不含任何文件路径判定。

编辑历史（本文件自 shell_command_risk.py 拆分而来，以下为其沿革）:
2026-07-20 - 小欧 - 删 SafetyResult(is_safe=False) 两处 kwarg: SafetyResult 已于 2026-07-18 删除 is_safe 字段, 此处漏改致中危/destructive shell 命令检查 TypeError 崩溃; 删后 blocked/requires_confirmation/safety_level 已正确表达风险意图, 行为不变
2026-07-27 - 小欧 - 补全CMD安全检查模式(diskpart/bcdedit/vssadmin/sc delete等HIGH+med); 所有模式加 # PS / # CMD / # PS+CMD 注释
2026-07-28 - 小欧 - 修复: 新增shell_type参数; 规则加第4元素st_tag("ps"/"cmd"/None); 按shell_type过滤不匹配规则
2026-07-28 - 小欧 - 临时目录清理误伤修复: 新增_TEMP_SAFE_PATTERNS+_is_temp_cleanup（本次已移至 shell_command_process）
2026-07-31 - 小欧 - Shell池进程保护: 新增受保护PID拦截（本次已移至 shell_process_guard）
2026-08-12 - 小欧 - A1越层前置: SafetyResult import 由 app.services.safety.path_tool_safety_checker 改为 app.safety.path_tool_safety_checker
2026-08-12 - 小欧 - A1盲点四: SafetyResult 定义迁入 app/tools/security/safety_result, import 同步更新 — 小欧 2026-08-12
2026-09-18 小欧 - safety_level→severity: ConfirmSpec字段+构造调用+比较全量重命名, 历史注释原文还原(勿改) — 小欧-2026-09-18
2026-09-18 - 小欧 - 实施: 用户可见message改写(逻辑/分级不变) — 小欧-2026-09-18
2026-09-18 小欧 - 7.3.4-C18精化: "不允许降级"改说人话"路径含穿越符号，已阻止"，分级blocked不变 — 小欧-2026-09-18
2026-10-10 小欧 - 新增三壳并集函数: 修预检层规则死代码缺口（单查某个 shell 会漏掉其他标签的规则）— 小欧 2026-10-10
2026-10-14 - 小欧 - 规则仅命中引号内字面量时降为需确认(北京老陈裁定): 修只读查询被误硬拦 — 小欧-2026-10-14
2026-10-16 小欧 - 文档[36] 第五章: 自 app/tools/fundamental/execute_shell_command_safety.py 整文件下沉至 app/safety/
2026-10-16 小欧 - 文档[36] 第七章(北京老陈裁定) 本文件由 shell_command_risk.py 拆分而来:
  ① 只留**与文件路径无关**的 HIGH 规则 14 条(diskpart/bcdedit/format/关机/执行/磁盘写入等);
     文件删除类 8 条(Remove-Item/rm/del/rd/rmdir + Recurse/Force/s 开关)移至 shell_command_process 路径层。
  ② 删本文件内的第二套自杀防护(_extract_* 三函数 + protected_pids 拦截分支) ——
     自杀检查已全部归并 shell_process_guard.check_shell_self_kill，两处各判一套口径不一致(E2E P9-03 教训)。
  ③ 删 protected_pids 形参(随 ② 失效)。④_TEMP_SAFE_PATTERNS/_is_temp_cleanup 移至 shell_command_process。
  ⑤ 彻底删除(老陈裁定"没有风险直接通过"): chmod 777 /、chown : /。
2026-10-18 - 小欧 - 随契约调整同步: HIGH 命中结果补 safety_level="command_block"(高危命令直接拦截, 与中风险需确认区分), 分类由判定点直给而非上层反查文案; 原 severity="dangerous" 与 blocked=True 等价、属重复编码, 一并删。14 条规则表与命中即拒的语义零变更。
"""
import re
from typing import Optional

from app.safety.safety_result import SafetyResult  # 契约: 安全层单源
from app.logger import logger


SHELL_DANGER_PATTERNS = [
    # ═══════════════════════════════════════════════════════════════════
    # 危险命令(HIGH) - 拒绝执行(blocked=True)
    # 格式: (pattern, desc, level, st_tag) — st_tag: "ps"/"cmd"/None(双兼容)
    # ★全部为与文件系统路径无关的操作；路径的写/读/删不在本表(见文件头边界铁律)
    # ═══════════════════════════════════════════════════════════════════
    # ---- PS ----
    (r"Invoke-Command", "远程/本地执行命令", "HIGH", "ps"),
    (r"Format-Volume", "格式化卷", "HIGH", "ps"),
    (r"Stop-Computer", "关机", "HIGH", "ps"),
    (r"Invoke-Expression", "动态执行命令", "HIGH", "ps"),
    # ---- CMD ----
    (r"\bdiskpart\b", "磁盘分区操作(diskpart)", "HIGH", "cmd"),
    (r"\bbcdedit\b", "引导配置操作(bcdedit)", "HIGH", "cmd"),
    (r"vssadmin\s+delete\s+shadows", "删除卷影副本(vssadmin)", "HIGH", "cmd"),
    (r"\bsc\s+delete\b", "删除服务(sc delete)", "HIGH", "cmd"),
    # ---- PS+CMD ----
    (r"(?<!\w)format\b\s+[A-Za-z]:\s*(?:[/\\]|$)", "格式化磁盘", "HIGH", None),
    (r"\bshutdown\b(?!\s+[/-]a\b)", "关机/重启", "HIGH", None),
    (r"net\s+user\s+\S+.*\/delete", "删除用户", "HIGH", None),
    (r"\bcipher\b\s+/w:", "永久数据销毁(cipher /w)", "HIGH", None),
    # ---- bash ----
    (r"\bdd\s+if=.*\sof=/(?:dev/sd|dev/nvme|dev/mmc)", "直接写磁盘(dd)", "HIGH", "bash"),
    (r"\bmkfs\.\w+\s+/dev/", "格式化(ntfs/ext4/xfs)", "HIGH", "bash"),
]


def check_shell_danger_command(command: str, shell_type: str = "ps7") -> Optional[SafetyResult]:
    """危险命令判定 —— 命中即拒绝(HIGH)

    shell_type: "ps7"/"ps5"/"cmd"/"bash" — 仅匹配该 shell 标签的规则 + 双兼容规则(st_tag=None)。
                要查全 shell 请用 check_shell_danger_command_all_shells(), 不要传 None
                (传 None 会把 ps/cmd/bash 三种标签全跳过, 仅剩双兼容规则生效)。

    2026-10-16 老陈裁定删"降级", 命中即拒无例外: 原 10-14 的"仅命中引号内则降为需确认"两头失灵 ——
        只读查询误伤未消(`Select-String -Pattern "rm -rf"` 仍是需确认), 而真危险
        `powershell -Command "Format-Volume D:"` 反被降级放行(开洞); 再叠加主链 `and _danger.blocked`
        只收 blocked, 降级出的"需确认"被直接丢弃。本层退回直线逻辑。
    """
    normalized = command.replace('\r\n', ' ').replace('\n', ' ')
    for pattern_str, desc, level, st_tag in SHELL_DANGER_PATTERNS:
        if st_tag == "ps" and shell_type not in ("ps7", "ps5"):
            continue
        if st_tag == "cmd" and shell_type != "cmd":
            continue
        if st_tag == "bash" and shell_type != "bash":
            continue
        if not re.search(pattern_str, normalized, re.IGNORECASE):
            continue
        return SafetyResult(
            blocked=True,
            message=f"高风险Shell操作: {desc}，已阻止执行",
            safety_level="command_block",
        )
    return None


def check_shell_danger_command_all_shells(command: str) -> Optional[SafetyResult]:
    """三壳并集: ps7/cmd/bash 各查一遍，命中即返回。 — 小欧 2026-10-10 / 2026-10-16 老陈简化

    供不掌握真实 shell_type 的调用方(如 safety 预检门)使用: 单查某一个 shell 会漏掉
    该 shell 之外标签的规则(实测默认 ps7 下规则仅一半生效)。
    会写死 shell 的调用方(如 execute_shell_command 执行层)应继续传真实 shell_type。

    2026-10-16 老陈裁定: 只答"危险/不危险"，**第一个命中即返回**，不建严重度排序表。
    无任何 shell 命中时返回 None(无风险)。 — 小欧 2026-10-10
    """
    for _st in ("ps7", "cmd", "bash"):
        r = check_shell_danger_command(command, _st)
        if r is not None:
            return r
    return None