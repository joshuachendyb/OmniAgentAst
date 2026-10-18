# -*- coding: utf-8 -*-
"""shell_readonly — shell 只读白名单快速通道(单一职责 · 零状态 · 零 I/O) — 小欧 2026-10-18

职责: 判定一条命令是否为"只读命令"(前缀命中白名单且不含任何拼接/子表达式载体), 可免沙箱预检直放。
      **只做只读身份判定, 不判动作、不判权限。**

编辑历史:
2026-10-18 - 小欧 - 新建(SRP): 自 shell_command_process.py 拆出"只读白名单"单一关注点。
  常量更名 SHELL_FAST_CHANNEL_FORBIDDEN → SHELL_READONLY_FORBIDDEN: 它是只读放行的禁用符集。
2026-10-18 - 小欧 - 健壮性: 非字符串入参改 False(不放行); 前缀与禁用符判定统一用 lowered。

分层: 最底层静态判据, 不 import 上层(被 executor / tools / services 复用)。
"""

# 判定规则的真实代码落点(全部代码化)
SHELL_READONLY_PREFIXES = ("get-", "ls", "cat", "type", "git status",
                     "echo", "pwd", "dir", "whoami", "hostname",
                     "git log", "git diff", "git show",
                     "python --version", "node --version", "node -v",
                     "npm --version", "npm ls",
                     "pip list", "pip show", "pip --version",
                     "docker ps", "docker images",
                     "tasklist", "ipconfig /all", "systeminfo", "netstat", "ver",
                     "test-path", "kubectl get")     # 只读白名单前缀(五项 + 精化二十一项) — 小欧-2026-09-18
    # 评审纪要(2026-09-18 小欧, 逐条过安全评审, 任意无拼接符后缀仍只读才准入):
    #   准入: git log/diff/show(纯展示); python/node --version(打印即退); npm --version/ls, pip list/show/--version(只读查询);
    #   docker ps/images(只读列表); tasklist/systeminfo/netstat/ver(系统只读展示); ipconfig /all(精确子命令, /flushdns等不匹配);
    #   test-path(纯测试); kubectl get(只读API, 与 read 读敏感文件同政策).
    #   否决: git branch(-D/-M可删分支); ipconfig裸前缀(/release//renew//flushdns可变更网络); gh/set/npm run/pip install/docker exec等(可写).
SHELL_READONLY_FORBIDDEN = ("|", ";", "&", ">", ">>", "$", "(", ")", "`", "<", "\n", "\r")
    # 2026-10-05 小欧 安全修复: 补 $ ( ) 反引号 < 四类载体; 原缺口使
    #   `echo $(Start-Process calc)`/`echo $(net user hacker pass /add)`/`echo `whoami` 既过白名单
    #   (只查前缀)又过沙箱扫描(词表仅含写动词+重定向), 最终直通真机无沙箱。
# 误拒含括号的合法只读命令可接受(转沙箱预检仍能执行), 漏放是真机执行。 — 小欧 2026-10-05


def is_shell_readonly_whitelisted(command: str) -> bool:
    """只读白名单判定 — 小欧 2026-10-04

    安全放行须先跑 executor._scan_command_danger_intent, 纯路由调用点不适用。
    2026-10-18 小欧: 非字符串入参原抛 AttributeError, 改为 False(不放行);
      前缀与禁用符判定基准统一用 lowered(禁用符集无字母, 行为等价)。
    """
    if not isinstance(command, str):
        return False
    lowered = command.strip().lower()
    if not lowered.startswith(SHELL_READONLY_PREFIXES):
        return False
    return not any(op in lowered for op in SHELL_READONLY_FORBIDDEN)


__all__ = ["SHELL_READONLY_PREFIXES", "SHELL_READONLY_FORBIDDEN", "is_shell_readonly_whitelisted"]
