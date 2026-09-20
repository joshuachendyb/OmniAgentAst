# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-20 - 小欧 - 新建: [55] 12.7② 跨任务文件写仲裁(跨会话并行安全核心, X2 落地)。
#   仅仲裁不强制: 冲突返回占用者信息, 由工具层(TaskFileWriter)决定告警/排队/拒绝, 杜绝静默覆盖。
# 2026-09-20 - 小欧 - A-2/A-3 修复: 新增 claim_write 上下文管理器(A-2 供各写工具统一取-释登记),
#   新增 ARBITER_CLAIM_TTL 惰性过期回收(A-3 僵死占用不再永久锁死后续写入)。
"""
file_write_arbiter — 跨任务/跨会话文件写仲裁(进程内单例)

职责(X2 落地, [55] 12.1 P1): 记录并检查「正在被谁写入」的文件集合。
- 线程安全: threading.Lock 保护登记表(sync 工具在 asyncio 事件循环线程内以同步调用执行, 线程锁正确)。
- 不强制阻断: 冲突时返回占用者 (task_id, acquired_at), 调用方按策略处理, arbiter 绝不自动覆盖。
小欧 2026-07-05(参考 file_state 既有持久口径) / 2026-09-20 扩展
"""
import contextlib
import threading
import time as _time
from pathlib import Path
from typing import Dict, Iterator, Optional, Tuple

from app.logger import logger

# {resolved_path_str: {"task_id": str, "acquired_at": float}}
_write_claims: Dict[str, Dict] = {}
_claims_lock = threading.Lock()

# A-3: 占用租约 TTL(秒) — 超过该时长的登记视为僵死, acquire/who 惰性回收, 防永久毒点 — 小欧 2026-09-20
ARBITER_CLAIM_TTL = 1800.0


def _is_claim_stale(claim: Dict) -> bool:
    """判定登记是否过期(僵死: 持有超 TTL 且非本人续租) — 小欧 2026-09-20"""
    return (_time.time() - claim.get("acquired_at", 0.0)) > ARBITER_CLAIM_TTL


def acquire_write(file_path: str, task_id: str) -> Optional[str]:
    """登记文件正被 task_id 写入 → 返回 None=登记成功(无冲突); str=冲突, 返回占用者 task_id — 小欧 2026-09-20
    A-3: 锁内检查既有登记是否僵死(超TTL), 过期则回收允许新任务覆盖登记。"""
    key = str(Path(file_path).resolve())
    with _claims_lock:
        holder = _write_claims.get(key)
        if holder is not None and holder["task_id"] != task_id and not _is_claim_stale(holder):
            return holder["task_id"]
        _write_claims[key] = {"task_id": task_id, "acquired_at": _time.time()}
        return None


def release_write(file_path: str, task_id: str) -> None:
    """任务写完释放登记(仅释放本人占用, 防跨任务误删) — 小欧 2026-09-20"""
    key = str(Path(file_path).resolve())
    with _claims_lock:
        holder = _write_claims.get(key)
        if holder is not None and holder["task_id"] == task_id:
            del _write_claims[key]


def who_writes(file_path: str) -> Optional[Tuple[str, float]]:
    """查询当前占用者(task_id, acquired_at), 无占用返回 None — 小欧 2026-09-20
    A-3: 过期僵死占用视同已释放(惰性回收), 返回 None。"""
    key = str(Path(file_path).resolve())
    with _claims_lock:
        holder = _write_claims.get(key)
        if holder is None or _is_claim_stale(holder):
            return None
        return (holder["task_id"], holder["acquired_at"])


@contextlib.contextmanager
def claim_write(file_path: str, task_id: str) -> Iterator[Optional[str]]:
    """A-2: 统一登记-执行-释放上下文管理器 — 供各写工具主函数包裹写操作路径(Dry: 消灭各处重复 try/finally)。
    yield 占用者(task_id 或 None)供调用方决定告警策略; finally 无条件 release 本人占用 — 小欧 2026-09-20"""
    owner = acquire_write(file_path, task_id)
    try:
        yield owner
    finally:
        release_write(file_path, task_id)


__all__ = ["acquire_write", "release_write", "who_writes", "claim_write", "ARBITER_CLAIM_TTL"]
