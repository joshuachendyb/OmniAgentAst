# ============================================================================
# 旁路排查文件持久化（文件A/B）— 11.7 概要的代码级实现 — 小欧 2026-08-23
#
# 定案要点(11.7):
#   目录 分流(11.8 实现说明④): 调试 app.debug=True → backend/files/{session_id}/{task_id}/
#         正式 → ~/.omniagent/files/{session_id}/{task_id}/  (完整id)
#   文件名 tool_data_{task短12}_{ai_message_id}_{start_time_fs}.jsonl /
#          conv_hist_{task短12}_{ai_message_id}_{start_time_fs}.jsonl
#          (start_time_fs = ISO 冒号':'→'-', Windows 文件名禁':'; header 内 start_time 仍保留 ISO)
#   宽松jsonl: 多行缩进块(indent=2)+空行分段; header/footer 自描述
#   旁路异步尽力而为: 单写者FIFO队列串行化, 写失败仅 error 留痕不阻塞主链路
#
# 编辑历史:
#   2026-08-23 - 小欧 - 初版落地(文档[1] v3.36 11.9 P1 / 设计=11.8.1 全量代码):
#       TaskFileWriter(A/B双文件单写者FIFO)/create_task_writer(H1工厂)/
#       purge_task+purge_session(H7 GC备函数,挂接待物理删除入口)/_files_root(调试分流)
# ============================================================================
from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.logger import logger                      # 与 prompt_logger 同源 logger
from app.utils.time_utils import get_local_iso_timestamp
from app.config import get_config


def _files_root() -> Path:
    """文件根目录环境分流(对齐 logger 惯例: debug→仓库内目录) — 小欧 2026-08-23
    调试(app.debug=True): backend/files/   —— 与 backend/logs/ 同级, 便于开发期查看
    正式(app.debug=False): ~/.omniagent/files/ —— 与 chat_history.db 同根用户级持久
    """
    try:
        if get_config().get("app.debug", False):
            return Path(__file__).resolve().parent.parent / "files"   # backend/files
    except Exception:
        pass
    return Path.home() / ".omniagent" / "files"
_SCHEMA_VERSION = "v1"
# 告警线(原 storage 截断阈值转告警线, 10.6.2 定案) — 仅提示不砍数据
_ALARM_ITEMS = 1000
_ALARM_STR_LEN = 100000


def _short_task_id(task_id: str) -> str:
    """文件名用 task 短 id: 头8+尾4 共12位hex, 去 task- 前缀 — 11.7.4-2"""
    _hex = task_id[5:] if task_id.startswith("task-") else task_id
    return _hex[:8] + _hex[-4:] if len(_hex) > 12 else _hex


def _dump_block(obj: Dict[str, Any]) -> str:
    return json.dumps(obj, ensure_ascii=False, indent=2)


class TaskFileWriter:
    """单任务的 A/B 双文件写者。

    串行化: 所有磁盘写入经 asyncio.Queue 由唯一 worker 按入队顺序执行(FIFO),
    杜绝并发交错导致半截 JSON 块(11.7.6)。对外接口全部同步非阻塞(仅入队)。
    """

    def __init__(self, session_id: str, task_id: str, ai_message_id: int,
                 start_time_iso: str, model: Optional[Dict[str, Any]]) -> None:
        self.session_id = session_id
        self.task_id = task_id
        self.ai_message_id = ai_message_id
        self._dir = _files_root() / session_id / task_id          # 目录用完整id; 根目录按 app.debug 分流(11.7.4-3)
        self._short = _short_task_id(task_id)
        # #1 修正(2026-08-23): 文件名用 FS 安全时间戳——get_local_iso_timestamp() 含 ':' (如 2026-08-23T09:30:12.123456),
        #   Windows 禁止 ':' 作文件名 → open() 抛 OSError 致文件永远建不出; 故 ':'→'-' 仅作用于文件名,
        #   header 内 start_time 字段仍保留 ISO(见 write_headers, 共用同一 start_time_iso 入参) — 小欧 2026-08-23
        self._start_iso = start_time_iso
        self._start_fs = self._start_iso.replace(":", "-")
        # #12 修正(2026-08-23): 原 f-string 误写 {self.short}(未定义, 只有 self._short) → __init__ 即 AttributeError,
        #   被 create_task_writer 的 except 吞掉降级 return None → 文件A/B 永远建不出(与 #11 同类致命) — 小欧 2026-08-23
        self.path_a = self._dir / f"tool_data_{self._short}_{ai_message_id}_{self._start_fs}.jsonl"
        self.path_b = self._dir / f"conv_hist_{self._short}_{ai_message_id}_{self._start_fs}.jsonl"
        self.model = model or {}
        # #14 修正(2026-08-23): footer.record_count 必须记"实写成功"块数——原直接用入队计数,
        #   磁盘写失败(worker 仅 error 留痕)后 footer 块数>实际块数, 击穿 11.7.9/10-5
        #   "块数对不上=中途崩溃有丢失"的完整性校验语义(写失败与崩溃不可辨) — 小欧 2026-08-23
        #   v3.29: 原 a_count 已随 H4 撤销成死变量(只加不读)删除; b_count 保留(msg_seq 序号语义)
        self.b_count = 0                    # 文件B 已入队消息块数(msg_seq 递增语义)
        self.a_written = 0                  # 文件A 实写成功数据块数(不含 header/footer)→ footer.record_count
        self.b_written = 0                  # 文件B 实写成功消息块数(不含 header/footer)→ footer.record_count
        # #10 修正(2026-08-23): 原 _b_prev 前缀算法在 trim_history 从头部删旧消息时误判存活旧消息为"新增尾部"→重复写;
        #   改为稳定 _msg_id 去重集合(消息由 message_builder 分配自增 _msg_id, 不进 LLM wire) — 小欧 2026-08-23
        self._written_msg_ids: set = set()        # 已写消息稳定ID集合(防头部裁剪后重写)
        self._touched: set = set()                # 已写过路径集合(块间空行分隔; v3.30 终审: __init__ 直初始化, 替代 _enqueue_write 内 getattr 延迟初始化 — KISS)
        self._queue: "asyncio.Queue[Optional[object]]" = asyncio.Queue()
        self._worker = asyncio.create_task(self._worker_loop())
        self._closed = False

    # ---------- 内部: 队列与磁盘 ----------
    async def _worker_loop(self) -> None:
        while True:
            item = await self._queue.get()
            if item is None:                       # 关闭哨兵
                self._queue.task_done()
                return
            coro = item
            try:
                await coro
            except Exception as e:                 # 尽力而为: 失败仅留痕(11.7.6)
                logger.error(f"[file_persist] {self.task_id} 写盘失败(降级不阻塞): "
                             f"{type(e).__name__}: {e!r}")
            finally:
                self._queue.task_done()

    def _enqueue_write(self, path: Path, block: Dict[str, Any], count: str = "") -> None:
        # v3.30 终审: _touched 已在 __init__ 直初始化, 去 getattr 延迟初始化(#7 同纪律: 无废防御) — 小欧 2026-08-23
        sep = "\n" if path in self._touched else ""   # 块间空一行; 首块无前导空行
        self._touched.add(path)

        async def _do() -> None:
            self._dir.mkdir(parents=True, exist_ok=True)
            with open(path, "a", encoding="utf-8") as f:
                f.write(sep + _dump_block(block) + "\n")
            # #14: 仅数据记录块计数(header/footer 不计), 且写成功才计 → footer.record_count=实写数 — 小欧 2026-08-23
            if count == "a":
                self.a_written += 1
            elif count == "b":
                self.b_written += 1

        self._queue.put_nowait(_do())

    # ---------- H1: header ----------
    def write_headers(self) -> None:
        base = {
            "schema_version": _SCHEMA_VERSION,
            "format": "pretty-jsonl",
            "session_id": self.session_id,
            "task_id": self.task_id,               # 完整值(11.7.9-4)
            "message_id": self.ai_message_id,
            "start_time": self._start_iso,         # 复用 __init__ 入参(与文件名同源); 禁调 get_local_iso_timestamp() 以免漂移 — 小欧 2026-08-23
            "model": self.model,
        }
        ha = {**base, "file_type": "tool_data", "block_semantics": "1 block = 1 tool result"}
        hb = {**base, "file_type": "conversation_history", "block_semantics": "1 block = 1 message"}
        self._enqueue_write(self.path_a, ha)
        self._enqueue_write(self.path_b, hb)

    # ---------- H3: 文件A ----------
    def write_tool_block(self, *, step: int, tool_no: int, retry_no: int = 0, tool_name: str,
                         params_raw: Any, params_final: Any,
                         llm_data: Dict[str, Any], data: Any,
                         other_data: Optional[Dict[str, Any]]) -> None:
        """H3: tool_retry_engine 每次尝试回调直接入队落盘(format 前实时写) — 2026-08-23 #B 闭环(裁定②)/v3.29 去 step_id 化(北京老陈:
        实时 loop 写入是关键——工具尝试完成即落盘, 不经暂存不等 DB 落库; 原 stage_tool_block+flush_tool_blocks 两段机制撤销)"""
        blk: Dict[str, Any] = {
            "step": step,                          # 轮次号=该轮 agent.llm_call_count(系统既有字段名, 与 Step/SSE/step_json 同名同源 — 11.7.9-2① v3.29 定案)
            "tool_name": tool_name,
            "params_raw": params_raw,
            "params_final": params_final,
            "llm_data": llm_data,                  # 主体① 全量
            "data": data,                          # 主体② format之前原文
        }
        if other_data:                             # ⑦ 有则写、无则省略该键(11.7.9-2⑦)
            blk["other_data"] = other_data
        # #8 修正(2026-08-23): tool_no 置于①~⑦固定字段序之后, 作并行区分标记(11.7.9-2 同step多tool加tool_no),
        #   不破坏 11.7.9 固定顺序(step→tool_name→params_raw→params_final→llm_data→data→other_data) — 小欧 2026-08-23
        blk["tool_no"] = tool_no
        # #B 闭环(2026-08-23 北京老陈 裁定②): retry_no 置于 tool_no 之后, 作重试区分标记(同工具第几次尝试, 0=首次);
        #   与 tool_no 同性质"标注", 不破坏 11.7.9 固定顺序 — 小欧 2026-08-23
        blk["retry_no"] = retry_no
        self._enqueue_write(self.path_a, blk, count="a")

    # ---------- H2: 文件B ----------
    def append_conv_blocks(self, call_no: int, messages: List[Dict[str, Any]]) -> None:
        """H2: 稳定 _msg_id 去重 — 仅追加未写过的消息块; 结构保真不改写(11.7.10-2)

        call_no 权威 = agent.llm_call_count(react_cycle 在 prepare 之前已自增,
        即本次调用序号); msg_seq = 文件内顺序号(b_count 递增)。
        #10 修正(2026-08-23): 原"前缀算法"在 trim_history 从头部删旧消息时,
        存活旧消息左移致 prev[p]!=messages[p] 于 p=0 即失配 → 整段当作"新增尾部"重写给文件B,
        既违背 11.7.10「零冗余」又破坏"call_no≤N 按 msg_seq 连续前缀"还原;
        改为每条消息带 message_builder 分配的自增 _msg_id(不进 LLM wire),
        已写 _msg_id 入 _written_msg_ids 集合 → 头部裁剪后存活旧消息的 _msg_id 已存在, 绝不重写,
        仅真正新增(_msg_id 未见)的消息追加, 彻底根治重复写 — 小欧 2026-08-23
        """
        for m in messages:
            mid = m.get("_msg_id")
            if mid is None or mid in self._written_msg_ids:
                continue
            blk = {"call_no": call_no, "msg_seq": self.b_count + 1, **m}
            # #13 修正(2026-08-23): _msg_id 是去重内部标记, 不属 11.7.10 定案字段
            #   (顶层标注仅 call_no/msg_seq 两键), 写盘前剔除(与 write_tool_block 剔临时键同一纪律) — 小欧 2026-08-23
            blk.pop("_msg_id", None)
            self.b_count += 1
            self._enqueue_write(self.path_b, blk, count="b")
            self._written_msg_ids.add(mid)

    # ---------- H5: footer ----------
    def finalize(self, status: str) -> None:
        """H5: 任务终态 footer(completed/failed/cancelled); 关闭 worker

        实施修正(小欧 2026-08-23, 文档[1]11.9 P1 发现): footer 块改在队列内惰性构造——
        原 11.8.1 设计在入队时即快照 a_written/b_written(#14 的实写计数在异步 _do 内自增),
        若 finalize 调用时队列尚有未排空数据块(磁盘慢/高频落盘), footer 会记到过期小值,
        击穿 11.7.9/10-5「块数对不上=中途崩溃有丢失」完整性校验; 改为闭包延迟到本块执行时读值
        (FIFO 保证此时全部数据块已处理完), record_count 精确等于实写数 — 小欧 2026-08-23"""
        if self._closed:
            return
        self._closed = True

        async def _do_footer() -> None:
            end_time = get_local_iso_timestamp()
            # #14: record_count 用实写成功计数(a_written/b_written), 非 b_count/a_count 入队计数 — 小欧 2026-08-23
            fa = {"file_type": "tool_data", "footer": True, "end_time": end_time,
                  "status": status, "record_count": self.a_written}
            fb = {"file_type": "conversation_history", "footer": True, "end_time": end_time,
                  "status": status, "record_count": self.b_written}
            for path, blk in ((self.path_a, fa), (self.path_b, fb)):
                sep = "\n" if path in self._touched else ""   # 与数据块同一空行分段纪律
                self._dir.mkdir(parents=True, exist_ok=True)
                with open(path, "a", encoding="utf-8") as f:
                    f.write(sep + _dump_block(blk) + "\n")
                # header/footer 不计入 a_written/b_written(count 语义不变)

        self._queue.put_nowait(_do_footer())
        self._queue.put_nowait(None)               # 哨兵: 排空后 worker 自然退出

    async def drain(self, timeout: float = 5.0) -> None:
        """测试/收尾辅助: 等待队列排空(生产主链路不调用, 保持零等待)"""
        try:
            await asyncio.wait_for(self._queue.join(), timeout=timeout)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 工厂: orchestrator 创建后挂载 agent.file_persist; 失败返回 None(降级无文件) — 尽力而为
# ---------------------------------------------------------------------------
def create_task_writer(session_id: str, task_id: str, ai_message_id: int,
                       start_time_iso: str, model: Optional[Dict[str, Any]]) -> Optional[TaskFileWriter]:
    """H1: assistant 消息分配时调用——建目录+双header+挂载 agent.file_persist(stream_orchestrator 调用)"""
    try:
        w = TaskFileWriter(session_id, task_id, ai_message_id, start_time_iso, model)
        w.write_headers()
        logger.info(f"[file_persist] 文件A/B 就绪(task={task_id}): dir={w._dir}")
        return w
    except Exception as e:
        logger.error(f"[file_persist] create_task_writer 失败(task={task_id}, 降级为无排查文件): "
                     f"{type(e).__name__}: {e!r}")
        return None


# ---------- GC(11.7.8): 挂靠物理清理时机(软删除不触发) ----------
def purge_task(session_id: str, task_id: str) -> None:
    """彻底删除单任务目录(物理清理时调用).

    #2 修正(2026-08-23): 原代码调用未定义的 finalize_task(task_id, status="purged") → 物理清理即 NameError;
    且 GC 时已无 writer 引用, footer 随目录删除无意义, 故直接 rmtree. 终态任务已由 H5 finalize 写 footer 并
    关闭 writer; 活跃任务遭物理删属异常路径, 残留未落盘块随目录删除, 不补救(best-effort). — 小欧 2026-08-23
    """
    shutil.rmtree(_files_root() / session_id / task_id, ignore_errors=True)
    logger.info(f"[file_persist] purge_task: {_files_root() / session_id / task_id}")


def purge_session(session_id: str) -> None:
    """彻底删除整个会话目录(会话物理 DELETE / 保留策略清理时调用)"""
    shutil.rmtree(_files_root() / session_id, ignore_errors=True)
    logger.info(f"[file_persist] purge_session: {_files_root() / session_id}")
