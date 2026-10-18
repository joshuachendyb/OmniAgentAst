# -*- coding: utf-8 -*-
"""shell_readonly — shell 只读白名单快速通道(单一职责 · 零状态 · 零 I/O) — 小欧 2026-10-18

职责: 判定一条命令是否为"只读命令"(前缀命中白名单且不含任何拼接/子表达式载体), 可免沙箱预检直放。
      **只做只读身份判定, 不判动作、不判权限。**

编辑历史:
2026-10-18 - 小欧 - 新建(SRP): 自 shell_command_process.py 拆出"只读白名单"单一关注点。
  常量更名 SHELL_FAST_CHANNEL_FORBIDDEN → SHELL_READONLY_FORBIDDEN: 它是只读放行的禁用符集。
2026-10-18 - 小欧 - 健壮性: 非字符串入参改 False(不放行); 前缀与禁用符判定统一用 lowered。
2026-10-18 小欧 - 前缀集接入配置面: 新增 get_readonly_prefixes() 读 security.hitl.shell_readonly_prefixes,
  缺键或留空回退内置 SHELL_READONLY_PREFIXES; 原为纯硬编码且设置页无展示, 收紧须改代码发版。
  解析兼容 str / YAML list / 逗号分号换行混合分隔, 空白项丢弃, 读取路径零异常(配置坏值回退默认不致误拦)。
  内置常量保留为唯一兜底真源, 判定逻辑与禁用符集零变更; 注释精简冗余标注, 技术说明原样保留。

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
    # 准入判据(2026-09-18 小欧, 逐条核对安全性, 任意无拼接符后缀仍只读才准入):
    #   准入: git log/diff/show(纯展示); python/node --version(打印即退); npm --version/ls, pip list/show/--version(只读查询);
    #   docker ps/images(只读列表); tasklist/systeminfo/netstat/ver(系统只读展示); ipconfig /all(精确子命令, /flushdns等不匹配);
    #   test-path(纯测试); kubectl get(只读API, 与 read 读敏感文件同政策).
    #   否决: git branch(-D/-M可删分支); ipconfig裸前缀(/release//renew//flushdns可变更网络); gh/set/npm run/pip install/docker exec等(可写).
SHELL_READONLY_FORBIDDEN = ("|", ";", "&", ">", ">>", "$", "(", ")", "`", "<", "\n", "\r")
    # 2026-10-05 小欧 安全修复: 补 $ ( ) 反引号 < 四类载体; 原缺口使
    #   `echo $(Start-Process calc)`/`echo $(net user hacker pass /add)`/`echo `whoami` 既过白名单
    #   (只查前缀)又过沙箱扫描(词表仅含写动词+重定向), 最终直通真机无沙箱。
# 误拒含括号的合法只读命令可接受(转沙箱预检仍能执行), 漏放是真机执行。 — 小欧 2026-10-05


def get_readonly_prefixes() -> tuple:
    """生效的只读白名单前缀 — 小欧 2026-10-18

    真值源 = 配置 `security.hitl.shell_readonly_prefixes`; **缺键或留空 → 用内置 SHELL_READONLY_PREFIXES**,
    即默认行为与接入配置面之前完全一致(纯可观测性/可收紧, 不改默认语义)。

    值形状兼容三种(settings 的 textarea 落盘会把文本按行拆成 YAML list, 而手写 yaml 常是字符串):
      str   → 再按 , ; 换行 拆
      list  → 逐元素取串, 每个元素内部再按 , ; 拆(元素本身可能是"a, b, c"一整行)
    形状不认识 → 用内置默认(fail-safe: 保持既有放行面不突变, 且不因解析失败而误放行未知前缀)

    该前缀集是**免确认 + 免沙箱预检**的双重放行口(三个消费点: safety_gate 跳过 HITL /
    sandbox.executor 跳过预检 / execute_shell_command 执行层放行), 原为纯硬编码且设置页无展示,
    收紧须改代码。接入配置面后收紧仅需改配置, 且清单在设置页可见可审计。

    读取用 get_config()(内部 mtime 缓存), 与 _is_hitl_bypass 同一模式, 不引入额外 IO。
    """
    try:
        from app.config import get_config  # 延迟导入: 本模块是最底层静态判据, 不给上层加导入依赖
        raw = get_config().get("security.hitl.shell_readonly_prefixes", "")
    except Exception:                      # 配置不可读 → 用内置默认, fail-safe 保持既有放行面不突变
        return SHELL_READONLY_PREFIXES
    if isinstance(raw, (list, tuple)):
        chunks = [str(x) for x in raw]
    elif isinstance(raw, str):
        chunks = [raw]
    else:                                   # 数字/布尔等异常形状 → 不猜, 用内置
        return SHELL_READONLY_PREFIXES
    parts: list = []
    for c in chunks:
        for p in c.replace(";", ",").replace("\n", ",").split(","):
            p = p.strip().lower()
            if p:
                parts.append(p)
    return tuple(parts) or SHELL_READONLY_PREFIXES


def is_shell_readonly_whitelisted(command: str) -> bool:
    """只读白名单判定 — 小欧 2026-10-04

    安全放行须先跑 executor._scan_command_danger_intent, 纯路由调用点不适用。
    2026-10-18 小欧: 非字符串入参原抛 AttributeError, 改为 False(不放行);
      前缀与禁用符判定基准统一用 lowered(禁用符集无字母, 行为等价)。
    2026-10-18 小欧: 前缀集改取 get_readonly_prefixes()(可配置), 默认值与原来一致。
    """
    if not isinstance(command, str):
        return False
    lowered = command.strip().lower()
    if not lowered.startswith(get_readonly_prefixes()):
        return False
    return not any(op in lowered for op in SHELL_READONLY_FORBIDDEN)


__all__ = ["SHELL_READONLY_PREFIXES", "SHELL_READONLY_FORBIDDEN",
           "get_readonly_prefixes", "is_shell_readonly_whitelisted"]
