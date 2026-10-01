# 编辑历史:
# 2026-09-06 - 小欧 - 步骤1落盘(文档落码): StreamBuffer 新增 publish 生产者直写——dict()拷贝防调用方副作用
#   + seq=len单调递增 + 持锁cond.notify_all原子唤醒(与agent_runner._append行199-210同模式), 为事件总线
#   paused/resumed 唯一写入入口, 供真HITL / bypass / 沙盘网关 三网关链调用, 支撑文档路径1
# 2026-09-06 - 小欧 - 漏洞加固(task006漏洞分析报告, 北京老陈同意): publish 的 seq=len+event_log.append 移入
#   async with cond 锁内, 与 agent_runner._append 同步收紧, "seq分配+append+notify 持锁原子"注释声明名副其实;
#   防 4C 阶段多生产者直写事件总线时 seq 分配被插入 await 导致重复序号(当前 asyncio 单线程单生产者无实际竞态,
#   seq=len与append间无await点不会协程插队, 属防御性加固零行为变化)
# 2026-09-13 - 小欧 - TDD文案: 改述删除已退役 _append 引用——publish 是 event_log
#   唯一写入口(agent_runner _publish → buffer.publish 同源), _append 全仓已无定义(09-06 退役), 扫码注释残留清理
# 2026-09-29 小欧 - 增 publish_lock（同一任务序号分配与落库不并发交叉）；
#   create_stream_buffer 升为唯一入口 create_task_stream_buffer(带落库能力)，旧入口降纯内存薄壳；
#   reclaim_stream_buffer → reclaim_memory_buffer(300 秒只回收内存，不删 Journal)；
#   get_task_status → get_running_task_status(读内存活跃表，与读数据库终态的那只不同名) — 小欧 2026-09-29
# 2026-10-01 小欧 - 解 [1] A1(运行期逐步落库): StreamBuffer 增 persist_sink 可选 async 回调(由 agent_runner 注入 chat_task_steps 落库路由)，挂在 publish 收口而非调用点——事件有三条发布路径(_emit_publish / handle_action 直连 _buf.publish / _events 批量)，挂调用点必漏 thought/observation；纯内存 publish 与 Journal 版 publish_with_journal 同步承接。sink 调用于 publish_lock 锁外(注入方含 Prompt 日志文件写，持锁会把所有 publish 串行化)，seq 分配与 append 已在锁内原子完成故顺序安全。本模块保持 DB-agnostic，不感知 chat_task_steps
"""
task_state — 运行态任务数据存储 + 只读查询

合并自: task_state_queries
无外部依赖(不导入 task_registry)，专为消除循环导入设计。
小欧 2026-07-10

北京老陈 2026-07-12: 新增 agent_streams/StreamBuffer，将"流态"(事件回放缓冲)
与"控制态"(running_tasks) 分离，支撑前端 SSE 断线重连 — 小欧 2026-07-12
"""

# 2026-10-01 小欧 - 运行期逐步落库(解 [1] A1, 见 doc-10月优化/[1]刷新后显示其他任务结果):
#   StreamBuffer 新增 persist_sink 可选回调, 由 agent_runner 注入 chat_task_steps 落库路由;
#   挂在 publish 收口(三条事件发布路径唯一交点)而非调用点, 否则 handle_action 直连 _buf.publish 的
#   thought/observation 必漏; 纯内存 publish 与 Journal 版 publish_with_journal 同步承接。
#   本模块保持 DB-agnostic: 不感知 chat_task_steps, 落库口径全归注入方。
import asyncio
from dataclasses import dataclass, field
from typing import Any, Awaitable, Callable, Dict, List, Optional
from app.logger import logger          # [63] 3.6.2：降级日志需要（本文件此前无 logger）

running_tasks_lock = asyncio.Lock()
running_tasks: dict[str, dict] = {}


# ============================================================
# 流态缓冲(与控制态 running_tasks 分离) — 北京老陈 2026-07-12 断线重连
# ============================================================

@dataclass
class StreamBuffer:
    """单个任务的事件回放缓冲 — 小欧 2026-07-12

    event_log: append-only 事件列表，每条含 seq(单调递增序号)
    cond: 生产者追加新事件时唤醒消费者
    done: 生产者结束信号

    journal_backed: 该 buffer 是否挂载了 Journal sink（挂载者才受"同 task_id 单 buffer"约束，
        防两套 publish_lock + 两套 seq 流撞 Journal 主键被 INSERT OR IGNORE 静默吞帧；
        纯内存测试夹具不受此约束，必须每次拿到干净 event_log）— 小欧 2026-09-29
    """
    event_log: List[Dict] = field(default_factory=list)
    cond: asyncio.Condition = field(default_factory=asyncio.Condition)
    done: asyncio.Event = field(default_factory=asyncio.Event)
    publish_lock: asyncio.Lock = field(default_factory=asyncio.Lock)  # [63] 同一 task 的 seq 分配与 Journal 写入不并发交叉（3.5 第 1 步）
    journal_backed: bool = False
    # 运行期逐步落库回调(可选, 由 agent_runner 注入) — 小欧 2026-10-01
    #   签名: async sink(step_dict: dict) -> None。挂在 publish 收口而非调用点, 因事件有三条发布路径
    #   (_emit_publish / handle_action 直连 _buf.publish / _events 批量), 挂调用点必漏(解 [1] A1)。
    #   本模块 DB-agnostic, 不感知 chat_task_steps; 具体落库口径由注入方决定。
    persist_sink: Optional[Callable[[Dict], Awaitable[None]]] = None

    async def publish(self, step_dict: dict) -> int:
        """生产者直写：append + seq + 唤醒消费者。返回seq。
        经 agent_runner._publish 统一走 StreamBuffer.publish(唯一写入口) 同模式：先dict()拷贝防调用方副作用，
        seq分配+append+notify 均须持锁原子完成；cond.notify_all 未持锁调用抛 RuntimeError。
        — 小健-2026-09-05；2026-09-06 小欧 步骤1落盘(文档落码)；2026-09-06 小欧 漏洞加固(seq+append入锁)"""
        step_dict = dict(step_dict)
        async with self.cond:
            step_dict["seq"] = len(self.event_log)
            self.event_log.append(step_dict)
            self.cond.notify_all()
        seq = step_dict["seq"]
        if self.persist_sink is not None:
            await self.persist_sink(step_dict)   # 锁外调用: sink 只做 O(1) 投递, 不持读者锁
        return seq


# 流态缓冲表: task_id -> StreamBuffer(独立于 running_tasks 的生命周期)
agent_streams: dict[str, "StreamBuffer"] = {}


def create_task_stream_buffer(task_id: str, session_id: str, journal_sink=None) -> StreamBuffer:
    """[63] 3.6.2 唯一创建入口（生产链路）：组装 StreamBuffer + Journal sink（保持 DB-agnostic）
    journal_sink 签名: async sink(task_id, session_id, seq, event_type, payload_dict) -> None
    未传 sink 时退化为纯内存 buffer（测试夹具/纯内存场景）
    并发双建同一 task_id 时先到者胜：后到者复用已存在 buffer（sink 以首次注入为准），
    杜绝两套 publish_lock + 两套 seq 流导致 INSERT OR IGNORE 静默吞帧。
    该约束只对挂 Journal 的 buffer 生效；纯内存夹具（journal_sink=None）每次新建，
    否则复用会带上上一轮残留事件，让调用方读到脏 event_log — 小欧 2026-09-29
    """
    existing = agent_streams.get(task_id)
    if existing is not None and existing.journal_backed:
        logger.warning(f"[Journal] buffer 已存在 task={task_id}，复用，不重建")
        return existing
    buf = StreamBuffer(journal_backed=journal_sink is not None)
    agent_streams[task_id] = buf
    if journal_sink is None:
        return buf

    # 降级粘滞：上一帧落库失败后由后续成功帧携带标记，否则回放侧看不到（失败帧自己写不进库）
    state = {"degraded": False}

    async def _journal_write_and_append(d: dict) -> int:
        """落库 → 进内存，顺序固定且不被取消打断（保证 seq 不被复用，见 _publish_with_journal 的 shield）"""
        degraded = False
        for attempt in range(3):                      # [63] 3.5 第 6 步：有限重试
            try:
                await journal_sink(task_id, session_id, d["seq"], d.get("type", ""), d)
                state["degraded"] = False
                break
            except Exception as exc:
                if attempt == 2:
                    degraded = True                   # 重试耗尽才降级，实时流不中断（3.5 第 6 步）
                    state["degraded"] = True
                    logger.warning(f"[Journal] append 失败(已重试3次) task={task_id} seq={d['seq']}: {exc}")
                else:
                    await asyncio.sleep(0.05 * (attempt + 1))  # 50ms/100ms 短退避，不持 cond 锁
        async with buf.cond:
            if degraded or state["degraded"]:
                d["persistence_degraded"] = True     # 前端据此提示"部分过程刷新后不可恢复"
            buf.event_log.append(d)
            buf.cond.notify_all()
        return d["seq"]

    async def _publish_with_journal(step_dict: dict) -> int:
        # 持任务级 publish_lock 而非读者用的 cond：落库的 await 期间不占读者的锁，否则 SQLite
        # 一慢，正在读的 SSE 连接会被一起卡住
        async with buf.publish_lock:
            d = dict(step_dict)
            d["seq"] = len(buf.event_log)
            # 落库走 db.atxn→to_thread：协程被取消时线程仍会跑完并 commit。若不 shield，
            # 取消会落在"已 commit 未 append"之间 → 内存不前进 → 下一帧复用同 seq 被
            # INSERT OR IGNORE 静默吞掉。故把整段放进独立 task 并 shield，取消时等它跑完再传播。
            t = asyncio.ensure_future(_journal_write_and_append(d))
            try:
                seq = await asyncio.shield(t)
            except asyncio.CancelledError:
                # 等落库+入内存完成，保证 seq 连续不被复用；加超时防 SQLite 永久锁死时挂住停机
                _done, _pending = await asyncio.wait([t], timeout=10)
                if _pending:
                    logger.error(f"[Journal] 落库未在 10s 内完成(task={task_id} seq={d['seq']}): 该帧可能丢 Journal")
                raise
        # persist_sink 放锁外调用: 注入方含 Prompt 日志文件写, 持 publish_lock 会把
        # 所有 publish 串行化(小欧 2026-10-01)。seq/append 已在锁内原子完成, 此处顺序安全。
        if buf.persist_sink is not None:
            await buf.persist_sink(d)
        return seq

    buf.publish = _publish_with_journal   # type: ignore[method-assign]
    return buf


def create_stream_buffer(task_id: str) -> "StreamBuffer":
    """[63] 3.6.2 测试夹具薄壳：委托生产唯一入口（sink=None 纯内存退化），单一实现零重复（DRY）
    生产代码禁止裸调本入口 — 小欧 2026-09-29"""
    return create_task_stream_buffer(task_id, "", None)


def get_stream_buffer(task_id: str) -> Optional["StreamBuffer"]:
    """获取任务的流态缓冲,不存在返回 None — 小欧 2026-07-12"""
    return agent_streams.get(task_id)


def reclaim_memory_buffer(task_id: str) -> None:
    """[63] 3.8 改名：只回收内存缓冲（event_log/cond/done），不触碰 chat_stream_events Journal — 小欧 2026-09-29"""
    agent_streams.pop(task_id, None)


async def check_cancelled(task_id: str) -> bool:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return bool(task and task.get("cancelled"))


async def check_paused(task_id: str) -> bool:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return bool(task and task.get("paused"))


async def check_was_paused(task_id: str) -> bool:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return bool(task and task.get("_was_paused"))


async def get_running_task_status(task_id: str) -> Optional[str]:
    """[63] v1.33 命名裁定：读**内存 running_tasks 活跃表**的 status（None=不在活跃表）；
    与 stream_event_journal.get_persisted_task_status（读 DB chat_tasks 持久终态）语义域正交，
    北京老陈裁定"绝不允许同名"故改名。— 小欧 2026-09-29"""
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get("status") if task else None


async def is_task_running(task_id: str) -> bool:
    async with running_tasks_lock:
        return task_id in running_tasks


async def get_cancel_request_time(task_id: str) -> Optional[float]:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get("cancel_request_time") if task else None


async def get_pause_event(task_id: str) -> Optional[asyncio.Event]:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get("_pause_event") if task else None


async def get_task_field(task_id: str, field: str) -> Any:
    async with running_tasks_lock:
        task = running_tasks.get(task_id)
        return task.get(field) if task else None


__all__ = [
    "running_tasks_lock", "running_tasks",
    "agent_streams", "StreamBuffer",
    "create_task_stream_buffer", "create_stream_buffer", "get_stream_buffer", "reclaim_memory_buffer",
    "check_cancelled", "check_paused", "check_was_paused",
    "get_running_task_status", "is_task_running",
    "get_cancel_request_time", "get_pause_event", "get_task_field",
]
