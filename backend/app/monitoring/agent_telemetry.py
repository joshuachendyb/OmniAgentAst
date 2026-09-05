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
# 2026-08-21 - 小欧 - 12.2-Q5/Q2(按文档[1]12.2 diff设计落地): ①Q5-D3 新增 checkpoint_llm_calls() 运行中每轮
#   增量持久化 llm_calls(整表重写+唯一索引幂等去重), 中途崩溃监控数据最多丢最后一轮不再全丢;
#   ②Q2-D5 finalize_and_persist 落库失败 warning→error 提级留痕(保持降级不阻塞主链路)。
# 2026-08-22 - 小欧 - _merge_artifacts去重改为 tool_name+path 组合去重（设计补充：同路径不同工具应分别收集）
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.7: on_llm_call 形参 (model, provider) → tele_model: ModelRef
#   结构(dict 内保留 model/provider 单值派生键, 落库由 persist 层序列化); finalize 的 model/provider 两键 →
#   task_model=llm_model.model_dump_json()(F1 补 task_metrics 写入源); import 补 ModelRef
# 2026-08-23 - 小欧 - 三轮三堂会审修复(P1): finalize 的 task_model 改任务快照优先(_agent._task_llm_model,
#   回退 llm_client.llm_model)——防共享单例被并发任务还原后记录到他人模型(既有竞态一并根治)
# 2026-09-04 - 小健 - 新增 collect_and_report(第2阶段拆分): 工具执行批后批量聚合从 action_handler.execute_tools 下沉,
#   收敛到 telemetry 模块, action_handler 不再持有 duration/artifacts 收集细节; 函数体完整复制不改逻辑
# 2026-09-04 - 小健 - SLAP修复: build_final_stats_step 加 outcome 参数(默认空串), 优先用传入的 outcome,
#   为空时 fallback 到 agent.status.value; 消除监控层隐式依赖核心状态 — 小健-2026-09-04
# 2026-09-05 - 小健 - [7]8.6 一拆三: _log_task_end 自 stream_reader.py 整份搬入(任务收尾日志+统计属遥测同类,
#   仅改 import 归属零逻辑改动, 禁backward无垫片); 追加 log_and_print import(TASK_END console 打印)
# 2026-09-05 - 小欧 - 防御加固(三堂会审): finalize 的 task_model 改走 _model_to_json 单向容错——原直呼
#   _tm.model_dump_json(), 非Pydantic模型(SimpleNamespace等) AttributeError 致整表遥测落库失败(一行序列化拖垮
#   全部指标, 与"降级不阻塞"声明相悖)。生产链路恒 ModelRef(Pydantic) 行为不变; 未来插件/轻量client出非Pydantic
#   模型时该字段保全降级, 不再拖垮整表。来源线索: 回归测试以 SimpleNamespace 伪装模型触发 ERROR 日志 4 次。
"""任务级遥测采集（独立模块，收敛全部监控状态/计算/产出）—— 小欧 2026-08-20

设计定位（北京老陈 2026-08-20 指示：监控代码独立放 app/monitoring/）：
- 本模块不依赖 agent 内部实现细节，仅读取 agent 的公开属性与 message_builder 既有能力；
- 全部"新增状态 + stats/context_overview 计算 + 落库聚合"都在本文件，核心 agent 文件仅薄钩子调用。
"""
from typing import Dict, Any, Optional, List
import time
import json  # _model_to_json 单向容错序列化(vars 兜底) — 小欧 2026-09-05
from datetime import datetime

from app.logger import logger, log_and_print  # log_and_print: TASK_END console 打印 — 小健 2026-09-05
from app.db.models.chat_models import ModelRef   # 归一: 模型身份唯一结构 — 小欧 2026-08-22
from app.monitoring import storage  # 落库层（独立，storage 内部惰性导入 database 防环）


# 统计 step_count 时剔除的全部非业务 MetaStep type（与 11.2-B / 12.17 完全一致，单一来源）
_M_SKIP = {
    "usage", "paused", "resumed", "retrying", "cancelled",
    "authorization_required", "start", "stats", "context_overview", "final_stats",
}


def _model_to_json(_m):
    """模型身份结构→JSON串(单向容错): Pydantic 直调 model_dump_json; 其余取 vars 兜底;
    不可序列化降 None——绝不因一行序列化拖垮整表遥测落库 — 小欧 2026-09-05
    生产链路恒 ModelRef(Pydantic) 行为与原 `_tm.model_dump_json() if _tm else None` 逐字节等价。"""
    if _m is None:
        return None
    _mjd = getattr(_m, "model_dump_json", None)
    if callable(_mjd):
        try:
            return _mjd()
        except Exception:
            pass
    _d = vars(_m) if hasattr(_m, "__dict__") else None
    if _d:
        return json.dumps({k: v for k, v in _d.items() if not k.startswith("_")},
                          ensure_ascii=False, default=str)
    return None


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
                    tele_model: Optional[ModelRef] = None,
                    error_type: Optional[str] = None, finish_reason: Optional[str] = None) -> None:
        """2026-08-22 小欧 归一报告v1.25 6.7: (model, provider) 分离形参 → tele_model: ModelRef 结构;
        dict 内保留 model/provider 单值派生键(设计 diff 明示), 落库由 persist 层序列化 tele_model"""
        _idx = len(self._llm_calls) + 1
        _u = usage or {}
        self._llm_calls.append({
            "task_id": self.task_id,
            "session_id": self.session_id,
            "call_index": _idx,
            "tele_model": tele_model,
            "model": tele_model.model if tele_model else None,
            "provider": tele_model.provider if tele_model else None,
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
        """合并新产出物到内存态（去重按 tool_name+path 组合+上限50）— 小欧 2026-08-21"""
        for _a in new_items:
            if not isinstance(_a, dict):
                continue
            _key = (_a.get("tool_name", ""), _a.get("path", ""))
            if _key[1] and _key not in {(x.get("tool_name", ""), x.get("path", "")) for x in self._artifacts}:
                self._artifacts.append(_a)
        if len(self._artifacts) > 50:
            self._artifacts = self._artifacts[:50]

    def collect_and_report(self, all_calls: List[Any], results: List[Any]) -> None:
        """工具执行批后批量聚合遥测（从 action_handler.execute_tools 下沉）— 小健 2026-09-04

        遍历 all_calls+results 配对, 逐条调用 on_tool_call(tool_name, success, duration, artifacts)。
        逻辑与下沉前完全一致(完整复制), 收敛到 telemetry 模块, action_handler 不再持有收集细节。
        """
        for _call, _res in zip(all_calls, results):
            _tname = _call.get("tool_name", "") if isinstance(_call, dict) else ""
            _ok = not isinstance(_res, Exception)
            _dur = 0.0
            _arts = None
            if _ok and isinstance(_res, dict):
                _llm_d = (_res.get("llm_data") or {})
                _dur = float(_llm_d.get("duration_ms", 0) or 0) / 1000.0
                _act = _llm_d.get("action")
                if isinstance(_act, dict):
                    # 仅认写工具 with_artifacts 自声明；兜底派生已删(三堂会审F1: 读工具也构造action.target, 派生会把读取对象误落为伪产出物) — 小欧 2026-08-22 北京老陈定案
                    _arts = _act.get("artifacts")
                    # 注入 tool_name 到每个 artifact — 小欧 2026-08-22 设计补充（4字段: tool_name/name/path/type）
                    if _arts and isinstance(_arts, list):
                        for _a in _arts:
                            if isinstance(_a, dict) and "tool_name" not in _a:
                                _a["tool_name"] = _tname
            self.on_tool_call(_tname, _ok, _dur, artifacts=_arts)


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

    def build_final_stats_step(self, outcome: str = ""):
        """产出 MetaStep(type="final_stats") —— 终态统计单独事件（final 后单发；duration 与流式 stats 同 _run_start_ts 同源）— 小欧 2026-08-20
        outcome参数: 调用方显式传入终态(completed/failed/cancelled), 优先使用; 为空时fallback到agent.status — 小健 2026-09-04
        """
        from app.services.agent.steps.base import MetaStep  # 局部导入防环
        _agent = self.agent
        _duration = round(time.time() - self._run_start_ts, 1) if self._run_start_ts else 0.0
        # 2026-09-03 小沈 修复: 增发final_status字段, 从agent.status.value派生,
        #   前端frames.finalStats.final_status据此兜底badge=failed, 防executionSteps中final step丢失时badge卡running — 小沈-2026-09-03
        # 2026-09-04 小健 SLAP修复: outcome显式传入优先, fallback到agent.status — 消除监控层隐式依赖核心状态
        _final_status = outcome if outcome else getattr(getattr(_agent, "status", None), "value", None)
        return MetaStep(
            step=getattr(_agent, "llm_call_count", 0),
            type="final_stats",
            content="",
            duration=_duration,
            artifacts=list(self._artifacts),   # 任务产出物：action_handler 经 on_tool_call 收集（内存态，单一来源）— 小欧 2026-08-21
            severity="info",
            final_status=_final_status,
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
        # 三堂会审修复(P1): 任务快照优先——防单例被并发还原后 finalize 记录到他人模型 — 小欧 2026-08-22
        _tm = getattr(_agent, "_task_llm_model", None) or getattr(_llm_client, "llm_model", None)
        return {
            "task_id": self.task_id,
            "session_id": self.session_id,
            "context_root_task_id": (_meta or {}).get("context_root_task_id"),
            "context_link_mode": (_meta or {}).get("context_link_mode"),
            "outcome": _outcome,
            "error_type": _error_type,
            # 归一(小欧 2026-08-22 报告v1.25 6.7): model/provider 两键 → task_model JSON 串(F1 补写入源)
            "task_model": _model_to_json(_tm),
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

    def checkpoint_llm_calls(self) -> None:
        """运行中每轮增量持久化 llm_calls(整表重写+唯一索引幂等去重;中途崩溃最多丢最后一轮,不再全丢) — 12.2-Q5 小欧 2026-08-21"""
        try:
            storage.persist_llm_calls(self._llm_calls)
        except Exception as _e:
            logger.warning(f"[TaskTelemetry] llm_calls checkpoint 失败(降级): {_e!r}")

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
            logger.error(f"[TaskTelemetry] 落库 monitoring.db 失败(降级不阻塞主链路, 监控数据缺失可凭此日志追溯): {_e!r}")  # 12.2-Q2: warning→error提级留痕 — 小欧 2026-08-21


def _log_task_end(task_id: str, end_type: str, start_time: Optional[float] = None,
                  steps: Optional[list] = None, agent: Any = None) -> None:
    """输出 TASK_END 日志（结束方式+耗时+步骤统计+LLM调用次数+累计token消耗）— 一行完整
    小健 2026-09-05 自 stream_reader.py 整份搬入(8.6 一拆三, 统计杂务归遥测同类), 逐字复制零改动"""
    parts = [f"task_id={task_id}", f"end_type={end_type}"]
    if start_time is not None:
        elapsed = time.time() - start_time
        parts.append(f"duration={elapsed:.2f}s")
    if agent is not None:
        parts.append(f"llm_calls={getattr(agent, 'llm_call_count', 0)}")
        # 累计 token 消耗(真实用量) — 小欧 2026-08-09: 修正 steps 中 usage=N 仅为 step 计数而非 token
        _au = getattr(agent, "accumulated_usage", None)
        if _au and isinstance(_au, dict):
            parts.append("usage_tokens=" + ",".join(
                f"{k}={_au.get(k, 0)}" for k in ("prompt_tokens", "completion_tokens", "total_tokens")))
        # 11.1 token 四层同构：追加任务级/会话级/链级累计输出 — 小欧 2026-08-20
        _tau = getattr(agent, "task_accumulated_tokens", None)
        if _tau and isinstance(_tau, dict):
            parts.append("task_acc=" + ",".join(
                f"{k}={_tau.get(k, 0)}" for k in ("prompt_tokens", "completion_tokens", "total_tokens")))
        _sau = getattr(agent, "session_accumulated_tokens", None)
        if _sau and isinstance(_sau, dict):
            parts.append("session_acc=" + ",".join(
                f"{k}={_sau.get(k, 0)}" for k in ("prompt_tokens", "completion_tokens", "total_tokens")))
        _cau = getattr(agent, "chain_accumulated_tokens", None)
        if _cau and isinstance(_cau, dict):
            parts.append("chain_acc=" + ",".join(
                f"{k}={_cau.get(k, 0)}" for k in ("prompt_tokens", "completion_tokens", "total_tokens")))
    if steps:
        counter: Dict[str, int] = {}
        for s in steps:
            t = s.get("type", "?") if isinstance(s, dict) else "?"
            counter[t] = counter.get(t, 0) + 1
        # 2026-08-09 - 小欧 - 三审收尾: usage 为非业务 Meta 步骤, 真实消耗由 usage_tokens 承担, 不混入业务统计;
        #   同性质非业务 MetaStep(paused/resumed/retrying/cancelled/authorization_required/start) 一并剔除, 与
        #   "Meta 步骤非业务步骤"注释自洽; 业务步骤(action/thought/observation/final/error)不计入排除,
        #   不误伤。total 必须在 pop 之后计算, 否则 total_steps 含排除项与注释声明矛盾。
        # 2026-08-18 小欧 P1/P3/P5/P6: chunk/error/usage/paused/resumed/retrying/cancelled 均仅SSE不落库,
        #   不入 current_execution_steps, total_steps 自然剔除; cancelled 经 task_runtime.task_cancel_check_and_yield(:90) append 进内存 steps 须显式剔除,
        #   收敛剔除集={cancelled,authorization_required,start}与 agent_runner:388 口径一致(10.4.4 第0步) — 小欧 2026-08-18(修正)
        for _t in ("cancelled", "authorization_required", "start"):
            counter.pop(_t, None)
        total = sum(counter.values())
        step_summary = ",".join(f"{k}={v}" for k, v in sorted(counter.items()))
        if step_summary:
            parts.append(f"steps=[{step_summary}]")
        parts.append(f"total_steps={total}")
    _msg = f"[TASK_END] {time.strftime('%H:%M:%S')} {' | '.join(parts)}"
    log_and_print(_msg)