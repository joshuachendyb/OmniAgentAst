# -*- coding: utf-8 -*-
# 模块说明: muse /responses 端点 SSE 流式归一(events → chat 形 choices[0].delta 行) — 小欧 2026-09-24
#   v3.7.1 模块化搬迁: 由 client_sdk.py v3.7.1 整体迁出, 与 OpenAI 兼容 chat 直通通道物理隔离。
#   归属: responses 协议专属处理(事件归一/折叠状态机/工具帧/completed 终帧), 非通用层;
#   client_sdk 主循环仅在 _is_responses 时逐帧落地本模块产物。第三种异构协议(如 Anthropic
#   /v1/messages)届时新增同级兄弟模块并按 protocol 能力位分派, 禁止 provider 化([66]归属边界)。
# 编辑历史: 2026-09-24 小欧 新建(client_sdk v3.7.1 八个成员整体搬迁, 依赖仅 json/typing, 零行为变更)

import json
from typing import Dict, Optional, Set


def _first_output_text(content) -> Optional[str]:
    """message.content 兼容 str(整体文本)/list(output_text 块), 取首段文本 — 小欧 2026-09-24 v3.7(修复 str 快照识别失效)
    v3.7.1(小欧 2026-09-24) 已查 FUNCTIONS.md 无同能公用函数(text_utils 仅 XML 提取), 复用优先合规。"""
    if isinstance(content, str):
        return content or None
    for cp in content or []:
        if isinstance(cp, dict) and cp.get("type") == "output_text" and cp.get("text"):
            return cp["text"]
    return None


def _tool_meta(name, call_id, item_id, arguments, *, full=False, is_new=False) -> Dict:
    """工具归一元数据 dict 统一构造 — 小欧 2026-09-24 v3.7.1 函数化(DRY: _norm 三处 tool dict 重复)
    id 恒取 call_id(仅 added/item.done 帧携带, 权威); item_id 供折叠层做稳定 index 分配, 不作 id 兜底
    (v3.7.1 已回滚 item_id 兜底: 会让 done 帧覆盖建档帧的权威 call_id, C15/C17/C20 回归实证)。"""
    m = {"name": name or "", "id": call_id, "item_id": item_id,
         "arguments": arguments or "", "full": full}
    if is_new:
        m["is_new"] = True
    return m


def _chat_frame(delta: Dict, *, finish_reason: Optional[str] = None,
                usage: Optional[Dict] = None) -> str:
    """chat 形 SSE 行(choices[0].delta + 可选 finish_reason/usage) — 小欧 2026-09-24 v3.7.1
    函数化(DRY+SLAP: 主循环所有落地统一, 4 处 json.dumps 收敛为单点)。"""
    frame = {"choices": [{"index": 0, "delta": delta}]}
    if finish_reason is not None:
        frame["choices"][0]["finish_reason"] = finish_reason
    if usage:
        frame["usage"] = usage
    return json.dumps(frame, ensure_ascii=False)


class _DeltaFoldState:
    """responses 流 chat delta 折叠状态(文本增量标记/工具建档表/参数增量去重集) — 小欧 2026-09-24 v3.7.1
    函数化(主循环瘦身): 集中承载逐帧 emit 的去重状态, 供 _fold_emit_delta 单点读写。"""

    __slots__ = ("saw_text_delta", "tool_idx", "saw_tool_args_idx")

    def __init__(self):
        self.saw_text_delta = False             # 已 emit 过文本增量(delta): 其后整段文本快照丢弃防重复
        self.tool_idx: Dict[str, int] = {}      # 工具 item_id→稳定 index(并行工具不串槽)
        self.saw_tool_args_idx: Set[int] = set()  # 已 emit 参数增量的 index 集(按工具分开, 防误弃其余工具快照)


def _norm_responses_delta(data: Dict) -> Dict:
    """responses 端点事件 → 归一片段(实测事件形态收敛) — 小欧 2026-09-24 v3.5 取证修正; v3.6 补快照保底; v3.7 补信令/并行/推理
    实测(2026-09-24 muse-spark-1.3 真实 SSE): 文本增量事件 output_text.delta;
    done/content_part.done/output_item.done 为整段快照, 若也提取
    同一文本会拼 4 次(重复 bug)——故快照标记为 content_full(保底源, 由消费侧
    仅在"全程无增量"时当唯一来源, 支持只发整段快照的 provider；有增量则丢弃防重复)。
    v3.7 新增: ①推理增量 reasoning_summary_text.delta(唯一实证事件名) → {"reasoning"};
    ②tool 片段带 item_id(流唯一标识)与 is_new(建档标记), 供消费侧按工具分配稳定 index(并行不串槽);
    ③message 快照兼容 content 为 str(整体文本)与 list(output_text 块)两种形态。
    工具链: output_item.added{function_call} 建档 + function_call_arguments.delta 增量 +
    function_call_arguments.done/output_item.done 整段覆盖(full=True)。completed 事件(终帧信令:
    文本快照+finish_reason 推断+usage)由消费侧 _responses_completed_eval 单遍处理, 不经本函数。"""
    et = data.get("type")
    if et == "response.output_text.delta":
        d = data.get("delta")
        return {"content": d} if d else {}
    if et == "response.reasoning_summary_text.delta":   # 唯一实证推理增量事件名 — 小欧 2026-09-24 v3.7.1 删猜测别名
        d = data.get("delta")
        return {"reasoning": d} if d else {}
    # v3.6 文本整段快照保底识别(仅流全程无 delta 增量时由消费侧作唯一来源) — 小欧 2026-09-24
    if et == "response.output_text.done":
        t = data.get("text")
        return {"content_full": t} if t else {}
    if et == "response.content_part.done":
        part = data.get("part") or {}
        if part.get("type") == "output_text":
            t = part.get("text")
            return {"content_full": t} if t else {}
    if et == "response.output_item.added":
        item = data.get("item") or {}
        if item.get("type") == "function_call":
            return {"tool": _tool_meta(item.get("name") or "", item.get("call_id"),
                                       item.get("id") or item.get("call_id"), "", is_new=True)}
    if et == "response.function_call_arguments.delta":
        d = data.get("delta")
        return {"tool": {"arguments": d, "item_id": data.get("item_id"),
                         "full": False}} if d else {}
    if et == "response.function_call_arguments.done":
        return {"tool": _tool_meta(data.get("name") or "", None, data.get("item_id"),
                                   data.get("arguments") or "", full=True)} \
            if data.get("arguments") else {}
    if et == "response.output_item.done":
        item = data.get("item") or {}
        if item.get("type") == "function_call":
            return {"tool": _tool_meta(item.get("name") or "", item.get("call_id"),
                                       item.get("id") or item.get("call_id"),
                                       item.get("arguments") or "", full=True)}
        if item.get("type") == "message":   # v3.6 文本快照保底; v3.7 兼容 str/list content — 小欧 2026-09-24
            t = _first_output_text(item.get("content"))
            return {"content_full": t} if t else {}
    return {}


def _tool_delta_frame(idx: int, tool: Dict, with_args: bool) -> Dict:
    """chat 形 tool_calls delta 帧(携带稳定 index) — 小欧 2026-09-24 v3.7
    with_args=False 用于建档帧: 只带 id/name, 参数一律由增量/快照帧供(防 provider added 携全参数 → 与增量重复拼接)。
    分析结论(小欧 2026-09-24 v3.7.1): id 恒取 call_id(仅 added/item.done 帧携带), 不用 item_id 兜底——
    一旦"满 id 兜底"会让 done 帧携带 item_id, 累加器用后帧覆盖已建档的权威 call_id(C15/C17/C20 回归实证);
    真实 responses 协议恒先 output_item.added(从建档帧), 纯 args.delta/done 无 call_id 属假想边界不作处理。"""
    fn = {}
    if tool.get("name"):
        fn["name"] = tool["name"]
    if with_args and tool.get("arguments"):
        fn["arguments"] = tool["arguments"]
    tc = {"index": idx}
    if tool.get("id"):
        tc["id"] = tool["id"]
    tc["function"] = fn
    return tc


def _responses_completed_eval(ev: Dict) -> tuple:
    """response.completed → (文本快照, meta(finish_reason/usage)) 单遍扫描 output — 小欧 2026-09-24 v3.7.1
    函数化(DRY: 原 _norm completed 分支与 _responses_completed_meta 对同一 output 遍历两遍 → 收敛单遍):
    responses 无 stop_reason 字段(实测): 出现 function_call → tool_calls, incomplete_details 非空 → length,
    否则 stop; 同时顺路提取 message 文本快照(content_full, 兼容 str/list); usage 取 response.usage(实证位置)。"""
    resp = ev.get("response") or {}
    content_full = None
    fr = "stop"
    if resp.get("incomplete_details"):
        fr = "length"
    else:
        for oi in resp.get("output") or []:
            if not isinstance(oi, dict):
                continue
            if oi.get("type") == "function_call":
                fr = "tool_calls"
            elif oi.get("type") == "message" and content_full is None:
                content_full = _first_output_text(oi.get("content"))
    usage = resp.get("usage")
    meta: Dict = {"finish_reason": fr}
    if usage:
        meta["usage"] = usage
    return content_full, meta


def _fold_emit_delta(norm: Dict, st: _DeltaFoldState) -> Optional[Dict]:
    """归一片段 → 待 emit 的 chat delta(None=本帧丢弃) — 小欧 2026-09-24 v3.7.1
    函数化(主循环瘦身): 文本增量→快照保底→推理增量→工具(建档/增量/整段按 index 去重)的
    emit 决策与状态读写收敛为单点, 主循环只剩"解析+落底 _chat_frame"两行。"""
    if norm.get("content"):
        st.saw_text_delta = True
        return {"content": norm["content"]}
    if norm.get("content_full"):
        # 整段文本快照保底: 全程无文本增量才作唯一来源(有增量→丢弃防重复)
        return {"content": norm["content_full"]} if not st.saw_text_delta else None
    if norm.get("reasoning"):
        # v3.7 reasoning 增量: 独立通道, 与正文 content 互不干扰, 消费侧走 is_reasoning
        return {"reasoning_content": norm["reasoning"]}
    tool = norm.get("tool")
    if not tool:
        return None
    _tid = tool.get("item_id") or tool.get("id") or ""
    if tool.get("is_new"):
        # 建档帧: 按 item_id 分配稳定 index, 仅带 id/name; 无 item_id → 落 0 不占槽不登记(状态一致) — 小欧 2026-09-24 v3.7.1
        idx = len(st.tool_idx) if _tid else 0
        if _tid:
            st.tool_idx[_tid] = idx
        return {"tool_calls": [_tool_delta_frame(idx, tool, with_args=False)]}
    idx = st.tool_idx.get(_tid, 0) if _tid else 0
    if tool.get("full"):
        # 整段参数快照: 该 index 未 emit 过参数增量→保底 emit 完整参数; 已单向过→丢弃防重复
        if idx in st.saw_tool_args_idx:
            return None
        st.saw_tool_args_idx.add(idx)
        return {"tool_calls": [_tool_delta_frame(idx, tool, with_args=True)]}
    _has_args = bool(tool.get("arguments"))   # 单取防双判 — 小欧 2026-09-24 v3.7.1
    if _has_args:
        st.saw_tool_args_idx.add(idx)
    return {"tool_calls": [_tool_delta_frame(idx, tool, with_args=_has_args)]}