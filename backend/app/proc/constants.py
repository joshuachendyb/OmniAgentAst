# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-26 - 小欧 - 新建: 进程域常量单点, 从 app/proc_host/__init__.py 迁入(域包升格后
#   __init__ 不再定义常量); 取值与协议语义零变化。
# 2026-11-26 - 小欧 - 域内常量集中: client 的 13 个与 host 的 pump 收尾等待全部迁入, 去掉
#   下划线(它们是域级不变量, 不是模块私有), 按相互制约关系分组标注; 取值与逻辑零变化。
"""proc — 进程域常量单点(host / client / proc_io 共用)。

【为什么集中】这些不是彼此无关的开关, 而是一套相互制约的"超时/恢复预算体系":
  · 接收截止必须覆盖宿主的收尾(RECV_SLACK ≥ IDLE_JOIN + 杀树/抖动), 否则客户端会把
    还在正常排队的宿主误判为僵死并杀掉, 连累全场在飞命令(2026-11-26 真实 case 复现);
  · 判死 + 重建必须在请求路径的 RECOVERY_BUDGET 内完成, 否则等待方拿不到自愈结果
    (2026-11-26 曾因判死拖到 15s 致 s1_9 用例真回归);
  · 退避/熔断三段共用同一时钟语义, 分散定义必然漂移。
集中到一处才能把约束写在值旁边, 改一个值时看得见受影响的其他值。
"""
# ── 协议 ──
PROTO = 1

# ── 命令超时与接收预算(相互制约, 改其一必须复核其余) ──
DEFAULT_TIMEOUT = 600.0     # 【使用对象】client.run / host._handle / proc_io.run 的 timeout=None 兜底
RECV_SLACK = 5.0            # 接收截止 = 命令 timeout + 本余量; 必须 ≥ IDLE_JOIN + 杀树/时钟抖动
IDLE_JOIN = 3.0             # host pump 收尾等待; 与 RECV_SLACK 是同一条预算链的两端

# ── 连接与启动 ──
CONNECT_TIMEOUT = 3.0       # 单次连接尝试上限
START_WAIT = 5.0            # 拉起宿主后等其就绪的上限
RECOVERY_BUDGET = CONNECT_TIMEOUT + START_WAIT  # 派生: 请求路径等待重建总预算(8s); 判死必须在此内完成
START_RETRY_DELAYS = (0.5, 1.0, 2.0)            # ensure_host 启动期重试间隔(与重建退避语义不同)

# ── 监护 ──
PING_INTERVAL = 5.0         # 监护人巡检间隔
PING_TIMEOUT = 3.0          # 单次 ping 等 pong 上限
PING_RECHECK_GAP = 1.0      # 首次失败后复检间隔: 覆盖瞬时闸门锁, 又不拖慢真僵死恢复

# ── 退避与熔断 ──
BACKOFF = (0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 30.0)  # 重建退避阶梯(秒, 封顶 30)
BREAKER_THRESHOLD = 5       # 连续启动失败达到该值即熔断
BREAKER_COOLDOWN = 30.0     # 熔断冷却(秒); 冷却后半开探测

# ── 流控与日志 ──
MAX_OUTPUT = 64 * 1024 * 1024   # 单命令输出总量上限(字节)
CHUNK_WAIT = 0.2                # 单次 poll 粒度
LOG_THROTTLE = 60.0             # 同因日志去重窗口(秒)

__all__ = [
    "PROTO",
    "DEFAULT_TIMEOUT", "RECV_SLACK", "IDLE_JOIN",
    "CONNECT_TIMEOUT", "START_WAIT", "RECOVERY_BUDGET", "START_RETRY_DELAYS",
    "PING_INTERVAL", "PING_TIMEOUT", "PING_RECHECK_GAP",
    "BACKOFF", "BREAKER_THRESHOLD", "BREAKER_COOLDOWN",
    "MAX_OUTPUT", "CHUNK_WAIT", "LOG_THROTTLE",
]
