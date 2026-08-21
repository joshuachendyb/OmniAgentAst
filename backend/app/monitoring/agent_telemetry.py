# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-20 - 小欧 - 新建: 任务级遥测采集独立模块(11.2-B/C + 11.3, 见 [1] 13.2.2.1)。
#   设计定位(北京老陈 2026-08-20 指示: 监控代码独立放 app/monitoring/)：本模块不依赖 agent 内部实现细节,
#   仅读取 agent 公开属性与 message_builder 既有能力; 全部"新增状态 + stats/context_overview 计算 + 落库聚合"
#   都在本文件, 核心 agent 文件仅薄钩子调用。
# 2026-08-20 - 小欧 - P0-1 修复: on_llm_call 补 model/provider 参数并在 _llm_calls dict 写入,
#   防 persist_llm_calls 读 r["model"] KeyError(见 [1] 13.2 三堂会审 P0-1)。
#   P1-2 修复: build_context_overview 的 injected_ratio clamp 到 min(injected, estimated)/max(estimated,1),
#   防 trim 后 estimated_tokens < injected_tokens 时 ratio 超 1.0 与 11.2-C "0~1" 矛盾。
# 2026-08-20 - 小欧 - 真实缺陷复核三遍修复: ①B1: finalize 的 context_truncated 改任务级判定(self._trim_count>0),
#   原读 _overview["truncated"]=末轮瞬时标志, 裁剪早于末轮漏报(现场 event 的 truncated 仍按 11.3 每轮语义不变);
#   ②C1: finalize 新增输出 trim_count/trim_tokens, 原 on_trim 采集数据不进 finalize 成死链路。
# 2026-08-21 - 小欧 - 11.6.3: _artifacts内存态收集+on_tool_call扩展artifacts参数+_merge_artifacts去重上限+build_final_stats_step真值
"""任务级遥测采集（独立模块，收敛全部监控状态/计算/产出）—— 小欧 2026-08-20

设计定位（北京老陈 2026-08-20 指示：监控代码独立放 app/monitoring/）：
- 本模块不依赖 agent 内部实现细节，仅读取 agent 的公开属性与 message_builder 既有能力；
- 全部"新增状态 + stats/context_overview 计算 + 落库聚合"都在本文件，核心 agent 文件仅薄钩子调用。
"""
from typing import Dict, Any, Optional, List
import time
from datetime import datetime

from app.logger import logger
from app.monitoring import storage  # 落库层（独立，storage 内部惰性导入 database 防环）


# 统计 step_count 时剔除的全部非业务 MetaStep type（与 11.2-B / 12.17 完全一致，单一来源）
_M_SKIP = {
    "usage", "paused", "resumed", "retrying", "cancelled",
    "authorization_required", "start", "stats", "context_overview", "final_stats",
}


class TaskTelemetry:
    """单任务遥测采集器：状态 + 计算 + 产出（独立，不污染核心 agent）"""

    def __init__(self, task_id: str, session_id: str, agent):
        self.task_id = task_id
        self.session_id = session_id
        self.agent = agent
        self._run_start_ts: Optional[float] = None          # 任务真实起点（同源 stream_orchestrator:198）
        self._first_token_ts: Optional[float] = None        # 首 chunk 时延基准
        self._llm_calls: List[Dict[str, Any]] = []          # 逐次 LLM 调用明细（落 llm_calls）
        self._tool_stats: Dict[str, Dict[str, float]] = {}  # 工具聚合（落 task_tool_metrics）
        self._injected_context: Optional[Dict[str, int]] = None  # 跨任务注入基线（固定快照）
        self._trim_count = 0
        self._trim_tokens = 0
        self._artifacts: List[Dict[str, str]] = []   # 任务产出物收集（内存态，终态随 final_stats / update_task 下发）— 小欧 2026-08-21

    # ── 生命周期钩子（由核心薄钩子调用）─────────────────────
    def on_start(self, start_time: Optional[float]) -> None:
        self._run_start_ts = start_time if start_time else time.time()

    def set_injected_context(self, snapshot: Dict[str, int]) -> None:
        """跨任务注入上下文基线快照（start_step 注入后一次性写入，固定不随裁剪变）"""
        self._injected_context = {
            "message_count": int(snapshot.get("message_count", 0) or 0),
            "estimated_tokens": int(snapshot.get("estimated_tokens", 0) or 0),
        }

    def mark_first_token(self) -> None:
        if self._first_token_ts is None:
            self._first_token_ts = time.time()

    def on_llm_call(self, usage: Optional[Dict[str, Any]], duration: float = 0.0,
                    model: Optional[str] = None, provider: Optional[str] = None,
                    error_type: Optional[str] = None, finish_reason: Optional[str] = None) -> None:
        _idx = len(self._llm_calls) + 1
        _u = usage or {}
        self._llm_calls.append({
            "task_id": self.task_id,
            "session_id": self.session_id,
            "call_index": _idx,
            "model": model,
            "provider": provider,
            "duration_seconds": round(duration, 3),
            "prompt_tokens": int(_u.get("prompt_tokens") or 0),
            "completion_tokens": int(_u.get("completion_tokens") or 0),
            "total_tokens": int(_u.get("total_tokens") or 0),
            "error_type": error_type,
            "finish_reason": finish_reason,
            "timestamp": datetime.now().isoformat(sep=" "),
        })

    def on_trim(self, trimmed: bool, trimmed_tokens: int = 0) -> None:
        if trimmed:
            self._trim_count += 1
            self._trim_tokens += int(trimmed_tokens or 0)

    def on_tool_call(self, tool_name: str, success: bool, duration_seconds: float = 0.0,
                     artifacts: Optional[List[Dict[str, str]]] = None) -> None:
        """action 工具执行后聚合（权威数据源 = execution_result.llm_data.duration_ms/1000）"""
        _t = self._tool_stats.setdefault(tool_name, {"call_count": 0, "error_count": 0, "latency": 0.0})
        _t["call_count"] += 1
        if not success:
            _t["error_count"] += 1
        _t["latency"] += float(duration_seconds or 0)
        if artifacts and isinstance(artifacts, list):
            self._merge_artifacts(artifacts)

    def _merge_artifacts(self, new_items: list) -> None:
        """合并新产出物到内存态（去重+上限50）— 小欧 2026-08-21 SRP: 独立方法便于单测"""
        for _a in new_items:
            if not isinstance(_a, dict):
                continue
            _p = _a.get("path")
            if _p and _p not in {x.get("path") for x in self._artifacts}:
                self._artifacts.append(_a)
        if len(self._artifacts) > 50:
            self._artifacts = self._artifacts[:50]

    # ── 产出（SSE 事件，独立计算）─────────────────────────
    def build_stats_step(self):
        """产出 MetaStep(type="stats") —— 与 11.2-B 字段口径一致"""
        from app.services.agent.steps.base import MetaStep  # 局部导入防环
        _agent = self.agent
        _step_count = len([s for s in _agent.steps if getattr(s, "TYPE", "") not in _M_SKIP])
        _duration = round(time.time() - self._run_start_ts, 1) if self._run_start_ts else 0.0
        return MetaStep(
            step=getattr(_agent, "llm_call_count", 0),
            type="stats",
            content="",
            step_count=_step_count,
            llm_call_count=getattr(_agent, "llm_call_count", 0),
            retry_count=getattr(_agent, "_retry_count", 0),
            duration=_duration,
            severity="info",
        )

    def build_final_stats_step(self):
        """产出 MetaStep(type="final_stats") —— 终态统计单独事件（final 后单发；duration 与流式 stats 同 _run_start_ts 同源）— 小欧 2026-08-20"""
        from app.services.agent.steps.base import MetaStep  # 局部导入防环
        _agent = self.agent
        _duration = round(time.time() - self._run_start_ts, 1) if self._run_start_ts else 0.0
        return MetaStep(
            step=getattr(_agent, "llm_call_count", 0),
            type="final_stats",
            content="",
            duration=_duration,
            artifacts=list(self._artifacts),   # 任务产出物：action_handler 经 on_tool_call 收集（内存态，单一来源）— 小欧 2026-08-21
            severity="info",
        )

    def build_context_overview(self) -> Dict[str, Any]:
        """产出 context_overview 字典 —— 复用 message_builder 既有能力（11.3-A）"""
        from app.services.agent.message_builder import MessageBuilder
        _mb = self.agent.message_builder
        _history = _mb.conversation_history
        _message_count = len(_history)
        _estimated = MessageBuilder._estimate_tokens(_history)
        _truncated = bool(getattr(_mb, "_trimmed_this_round", False))
        _inj = self._injected_context or {"message_count": 0, "estimated_tokens": 0}
        _inj_tokens = _inj["estimated_tokens"]
        _ratio = round(min(_inj_tokens, _estimated) / max(_estimated, 1), 3)   # P1-2 clamp 到 0~1
        _summary = ""
        for _m in reversed(_history):
            _c = _m.get("content") or ""
            if _c and _m.get("role") in ("user", "assistant"):
                _summary = _c[:120]
                break
        return {
            "message_count": _message_count,
            "estimated_tokens": _estimated,
            "truncated": _truncated,
            "injected_message_count": _inj["message_count"],
            "injected_estimated_tokens": _inj_tokens,
            "injected_ratio": _ratio,
            "summary": _summary,
        }

    # ── 终态聚合 + 落库 ─────────────────────────────────
    def finalize(self) -> Dict[str, Any]:
        """聚合 task_metrics 一行（字段名与 11.2-C task_metrics 列一致）"""
        _agent = self.agent
        _status = getattr(_agent, "status", None)
        _outcome = "completed"
        if _status is not None:
            _n = str(getattr(_status, "name", _status)).upper()
            if _n == "FAILED":
                _outcome = "failed"
            elif _n in ("CANCELLED", "CANCELED"):
                _outcome = "cancelled"
        # error_type 聚合：取首个非 None 的 llm_calls.error_type；否则按 outcome 推导
        _app_err = next((r["error_type"] for r in self._llm_calls if r.get("error_type")), None)
        if _app_err:
            _error_type = _app_err
        elif _outcome == "cancelled":
            _error_type = "user_cancel"
        elif _outcome == "failed":
            _error_type = "unknown"
        else:
            _error_type = None
        _duration = round(time.time() - self._run_start_ts, 1) if self._run_start_ts else 0.0
        _first_token_latency = (
            round(self._first_token_ts - self._run_start_ts, 3)
            if self._first_token_ts and self._run_start_ts else None
        )
        _llm_latency = round(sum(r["duration_seconds"] for r in self._llm_calls), 3)
        _tool_exec = round(sum(t["latency"] for t in self._tool_stats.values()), 3)
        _tokens = getattr(_agent, "task_accumulated_tokens", {}) or {}
        _overview = self.build_context_overview()
        _llm_client = getattr(_agent, "llm_client", None)
        _meta = getattr(_agent, "_start_meta", None)
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "context_root_task_id": (_meta or {}).get("context_root_task_id"),
            "context_link_mode": (_meta or {}).get("context_link_mode"),
            "outcome": _outcome,
            "error_type": _error_type,
            "model": getattr(_llm_client, "model", None),
            "provider": getattr(_llm_client, "provider", None),
            "total_steps": len([s for s in _agent.steps if getattr(s, "TYPE", "") not in _M_SKIP]),
            "llm_call_count": getattr(_agent, "llm_call_count", 0),
            "retry_count": getattr(_agent, "_retry_count", 0),
            "tool_call_count": int(sum(t["call_count"] for t in self._tool_stats.values())),
            "tool_error_count": int(sum(t["error_count"] for t in self._tool_stats.values())),
            "duration_seconds": _duration,
            "llm_latency_seconds": _llm_latency,
            "tool_execution_seconds": _tool_exec,
            "first_token_latency_seconds": _first_token_latency,
            "prompt_tokens": int(_tokens.get("prompt_tokens", 0) or 0),
            "completion_tokens": int(_tokens.get("completion_tokens", 0) or 0),
            "total_tokens": int(_tokens.get("total_tokens", 0) or 0),
            "context_message_count": _overview["message_count"],
            "context_estimated_tokens": _overview["estimated_tokens"],
            "context_truncated": 1 if self._trim_count > 0 else 0,   # B1修复(复核确认): 任务级裁剪判定, 原读末轮瞬时标志致"裁剪早于末轮则漏报" — 小欧 2026-08-20
            "context_injected_message_count": _overview["injected_message_count"],
            "context_injected_estimated_tokens": _overview["injected_estimated_tokens"],
            "context_injected_ratio": _overview["injected_ratio"],
            "trim_count": self._trim_count,     # C1修复(复核确认): 原 on_trim 采集数据不进 finalize, 裁剪遥测死链路 — 小欧 2026-08-20
            "trim_tokens": self._trim_tokens,
            "created_at": datetime.now().isoformat(sep=" "),
        }

    def finalize_and_persist(self) -> None:
        """任务结束：task_metrics / task_tool_metrics / llm_calls 落 monitoring.db（非阻塞降级）"""
        try:
            _summary = self.finalize()
            storage.persist_task_metrics(_summary)
            storage.persist_tool_metrics(self.task_id, [
                {"task_id": self.task_id, "tool_name": _name,
                 "call_count": int(_v["call_count"]), "error_count": int(_v["error_count"]),
                 "total_latency_seconds": round(_v["latency"], 3)}
                for _name, _v in self._tool_stats.items()
            ])
            storage.persist_llm_calls(self._llm_calls)
        except Exception as _e:
            logger.warning(f"[TaskTelemetry] 落库 monitoring.db 失败(降级不阻塞主链路): {_e!r}")