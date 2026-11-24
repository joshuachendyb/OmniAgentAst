# -*- coding: utf-8 -*-
# 2026-11-24 商量 - 新建: 生命周期事件总线。解决"订阅键是 task_id 但 task_id 会变"——
#   后台 shell 命令完成后 resume_session_with_notice 会新建 task_id + 新 StreamBuffer,
#   前端锚在旧 task_id 上不知有新任务, 只能靠 ChatPage 每 3 秒查 SQLite(GET /sessions/{id}/tasks)
#   轮询发现, 代价是最大 3 秒延迟、后台标签页被浏览器节流、每 3 秒一次库查询。
#   本模块提供比 task 更长寿的广播通道: 业务单点播报"任务起停/HITL 待处理"信封,
#   前端一条常驻 SSE(GET /chat/events)即时接流。
# 编辑历史:
# 2026-11-24 商量 - 初版: 全局单总线 + 事件带 session_id —— 本机单用户形态下连接数最省(1 条),
#   顶栏跨会话感知天然支持; 多用户时按 user 拆 dict[user_id, EventBus] 即可, 事件契约不变。
"""
event_bus — 生命周期事件总线（纯内存 · 无 seq · 可丢）

与 StreamBuffer 的分工（两者不可合并）:
  StreamBuffer(按 task_id): 承载 AI 正文(thought/工具/回答), 有 seq + Journal + after_seq 续传, 不许丢;
  本模块(全局)            : 只承载"变更信封", 无 seq、不落库、允许丢 —— 丢了由前端重连对账兜底
                            (拉 GET /sessions/tasks/running 与本地锚点比对, 不一致则重新锚定)。

可靠性模型 = at-least-once 播报 + 幂等对账:
  · 订阅者队列满时弃最旧保最新(慢消费者不拖垮生产者);
  · ring 缓冲保留最近 N 条供短暂断线补发(优化项, 非可靠性依赖);
  · 真正的可靠性来自对账 —— 与推送只负责叫醒、真相以 Journal + after_seq 为准的同哲学。

设计约束: publish 必须同步、无 await、O(订阅者数), 允许在 asyncio.Lock 内调用
  (任务诞生广播发生在 task_registry.register_task 的锁内)。
"""
import asyncio
import time
from collections import deque
from typing import Any, Deque, Dict, List, Optional, Set

from app.logger import logger

# 单订阅者队列上限: 满了弃最旧, 防慢消费者拖垮生产者
_SUB_QUEUE_MAX = 256
# 环形缓冲容量: 短暂断线(< N 条事件)可精确补发
_RING_SIZE = 32
# 心跳间隔(秒): SSE 端点据此保活, 同时作为"客户端断开检测"的节拍器
HEARTBEAT_SECONDS = 20


class EventBus:
    """全局事件总线: 单生产者(业务单点) → 多订阅者(每条 SSE 连接) — 商量 2026-11-24"""

    def __init__(self) -> None:
        self._subscribers: Set[asyncio.Queue] = set()
        self._recent: Deque[Dict[str, Any]] = deque(maxlen=_RING_SIZE)
        self._next_id = 0
        # epoch: 本进程内总线纪元。前端凭它判断"手里的 last_event_id 是否还属于当前总线",
        # 进程重启后 epoch 变化 → 前端丢弃陈旧 last_event_id, 直接走对账。
        self._epoch = int(time.time() * 1000)

    @property
    def epoch(self) -> int:
        return self._epoch

    def subscribe(self) -> "asyncio.Queue[Dict[str, Any]]":
        """新增订阅者, 返回其专属队列 — 商量 2026-11-24"""
        q: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue(maxsize=_SUB_QUEUE_MAX)
        self._subscribers.add(q)
        logger.info(f"[EventBus] 新订阅者, 在线 {len(self._subscribers)} 个")
        return q

    def unsubscribe(self, q: "asyncio.Queue[Dict[str, Any]]") -> None:
        self._subscribers.discard(q)
        logger.info(f"[EventBus] 订阅者离开, 在线 {len(self._subscribers)} 个")

    def replay_since(self, last_event_id: int) -> List[Dict[str, Any]]:
        """重连补发: ring 内 event_id > last_event_id 的事件; 空结果由对账兜底 — 商量 2026-11-24"""
        return [e for e in self._recent if e["event_id"] > last_event_id]

    def publish(
        self,
        event_type: str,
        payload: Dict[str, Any],
        session_id: Optional[str] = None,
    ) -> None:
        """广播一条信封 — 同步、无 await、O(订阅者数), 可在 asyncio.Lock 内调用 — 商量 2026-11-24"""
        self._next_id += 1
        ev: Dict[str, Any] = {
            "event_id": self._next_id,
            "type": event_type,
            "session_id": session_id,
            "data": payload,
        }
        self._recent.append(ev)
        for q in tuple(self._subscribers):
            try:
                q.put_nowait(ev)
            except asyncio.QueueFull:
                # 慢消费者: 弃最旧保最新 —— 信封可丢, 对账兜底(绝不让生产者被拖住)
                try:
                    q.get_nowait()
                    q.put_nowait(ev)
                except Exception:  # 队列在竞态窗口内被取空, 忽略即可
                    pass


#: 全局单总线 — 商量 2026-11-24
bus = EventBus()


def publish_event(
    event_type: str,
    payload: Dict[str, Any],
    session_id: Optional[str] = None,
) -> None:
    """业务播报入口 — 同步, 任何层任何时刻可调(含锁内); 播报失败绝不影响主流程 — 商量 2026-11-24"""
    try:
        bus.publish(event_type, payload, session_id)
    except Exception as e:
        logger.warning(f"[EventBus] 播报失败 type={event_type}: {e}")


def publish_for_task(
    event_type: str,
    task_id: str,
    payload: Optional[Dict[str, Any]] = None,
) -> None:
    """按 task_id 反查 session_id 后播报 — 供 HITL 等只知 task_id 的调用点使用 — 商量 2026-11-24

    task 已从注册表移除(收尾窗口)时 session_id 为 None: 前端主要按全局唯一的 task_id 匹配,
    session_id 仅用于顶栏跨会话感知, 缺失不致命。
    """
    from app.services.task.task_state import running_tasks

    task = running_tasks.get(task_id)
    session_id = task.get("session_id") if task else None
    data = dict(payload or {})
    data["task_id"] = task_id
    publish_event(event_type, data, session_id)


#: 事件类型常量 —— 与前端 sessionEventsStore 的 switch 一一对应, 改名须同步两端
EVENT_TASK_STARTED = "task_started"
EVENT_TASK_ENDED = "task_ended"
EVENT_TASK_STATUS_CHANGED = "task_status_changed"
EVENT_HITL_PENDING = "hitl_pending"
EVENT_HITL_SETTLED = "hitl_settled"

__all__ = [
    "EventBus",
    "bus",
    "publish_event",
    "publish_for_task",
    "HEARTBEAT_SECONDS",
    "EVENT_TASK_STARTED",
    "EVENT_TASK_ENDED",
    "EVENT_TASK_STATUS_CHANGED",
    "EVENT_HITL_PENDING",
    "EVENT_HITL_SETTLED",
]
