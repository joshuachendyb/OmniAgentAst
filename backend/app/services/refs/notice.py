# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-30 小欧 新建: 引用回执 DTO + reason→level 唯一裁决 + SSE 组帧 — 小欧-2026-10-30
# 2026-10-30 小欧 批3: ①_LEVEL_RANK 序号表由 _LEVEL_ORDER 元组派生(单一真源, 原手写 dict 与元组易分叉);
#   ②新增 describe_items(去重后的 label/path 点名文案, 首发与插话阻断提示共用, 原两条路径各写一遍拼串) — 小欧-2026-10-30
# 2026-10-30 小欧 引用进 loop 前可观测(北京老陈令): 新增 summarize_refs/refs_counts_text/report_refs/
#   build_refs_ready_notice/create_refs_ready_event —— 每请求 1 行汇总(log_and_print, 控制台+文件)
#   + ≤5 行明细(仅文件) + SSE notice(kind=refs_ready), 两通道共用 summarize_refs 同一份数字可对账;
#   token 走公共 estimate_tokens(不新造第 4 份实现) — 小欧-2026-10-30
# 2026-10-30 小欧 北京老陈令「路径不许截断」: 删 _paths_text 的 60 字符右截断(连同
#   REF_LOG_PATH_MAX_CHARS) —— 右截断会连 `:start-end` 与文件名一起切掉, 同文件整份与片段
#   在汇总行变成同一字符串; 现给完整路径, 行长度只由 5 条上限 + "另N条" 控制 — 小欧-2026-10-30

"""services.refs.notice — 引用回执(SSE refs_notice)的 DTO 与组帧

为何独立: 回执原先没有落点, 前端 chip 只能内联 pending/invalid 两态。
  本模块定义 DTO + reason 枚举, 把 resolver/budget 产出的 dropped/notices 统一打包,
  并把"条目级别"收口到 build_notice(单一裁决点)。

登记纪律(4.9): 事件类型在 steps/__init__.py 的 ALL_STEP_TYPES 汇集点登记,
  转发表由它推导(_SSE_FORWARD_TYPES = ALL_STEP_TYPES − {"thought"}), 不存在双登记。
  本模块不提供登记函数(YAGNI: 登记是汇集点的静态一行, 无需运行期入口)。

载体纪律: 回执有两类承载, 随路径而定 —
  首发路径的流是新建任务流, 前端 pump 直接消费, `yield` 即可见;
  插话路径的帧发在新 POST 流上而前端 postInterject 只 readToEnd 不解析,
  `yield` 前端收不到 —— 必须经目标任务 buffer(get_stream_buffer().publish)载体下发。
  本模块只负责组帧, 载体选择归编排层。

观测纪律(refs_ready): 引用正文不进日志(可能含隐私/大段内容), 可追溯信息只有"几条/多少 token/
  哪些路径"。日志与 SSE notice 都从 summarize_refs 取数(同一份数字), 查错时两通道互为对照。
"""
from typing import Any, Dict, List, Optional

from app.logger import logger, log_and_print
from app.services.agent.agent_utils import estimate_tokens   # 2026-10-31 小欧: 自 token_estimate 迁入 agent_utils
from app.utils.sse_formatter import format_sse_event

# 日志体量上限(引用正文永不落日志, 只留可追溯的路径/行区间/计数) — 小欧-2026-10-30
REF_LOG_PATHS_MAX = 5        # 汇总行 paths= 列出条数上限
REF_LOG_DETAIL_MAX = 5       # 明细行条数上限(仅写文件, 不上控制台)

# reason → level 映射(单一裁决点, 落地 4.8 判定表; resolver/budget 只产 reason 不碰 level):
#   info  = 非阻断省略类(内容已入 prompt, 仅提示)
#   warn  = 部分不可用点名类
#   error = 拒绝类(空内容/整批阻断)
REASON_LEVELS: Dict[str, str] = {
    "truncated": "info", "range_clipped": "info",
    "missing": "warn", "out_of_root": "warn", "unsupported": "warn",
    "timeout": "warn", "range_out": "warn", "no_path": "warn",
    "compressed": "warn", "rejected": "error",
}

# 级别序(越靠后越严重), worst_level 取最高; 序号表由元组派生(单一真源) — 小欧 2026-10-30
_LEVEL_ORDER = ("info", "warn", "error")
_LEVEL_RANK = {level: rank for rank, level in enumerate(_LEVEL_ORDER)}


def _level_of(item: Dict[str, Any]) -> str:
    """条目级别: 显式 level 优先; 缺失按 REASON_LEVELS 查表(未知 reason 从严 warn)。"""
    level = item.get("level")
    if level in _LEVEL_RANK:
        return level
    return REASON_LEVELS.get(str(item.get("reason") or ""), "warn")


def worst_level(items: List[Dict[str, Any]]) -> str:
    """从回执条目聚合整体级别(单一裁决, 无硬编码)。入参空 → "info"。

    保留为公开实现/测试口: build_notice 内部聚合走本函数。
    """
    rank = 0
    for it in items or []:
        rank = max(rank, _LEVEL_RANK[_level_of(it)])
    return _LEVEL_ORDER[rank]


def describe_items(items: List[Dict[str, Any]]) -> str:
    """回执点名文案: 去重后的 label/path, 空则"未命名"; 全空返回"未知"。

    首发与插话的阻断提示共用本函数(原两条路径各写一遍 dict.fromkeys 拼串) — 小欧 2026-10-30
    """
    names = dict.fromkeys(
        (it.get("label") or it.get("path") or "未命名") for it in items or []
    )
    return "、".join(names) or "未知"


def build_notice(level: Optional[str], scope: str,
                 items: List[Dict[str, Any]]) -> Dict[str, Any]:
    """组 refs_notice 事件载荷。scope: first | interject。

    条目 level 在此统一补齐(resolver/budget 产出只带 reason/detail);
    帧级 level: 入参 None 时按条目聚合 worst_level。
    """
    _items = [{**it, "level": _level_of(it)} for it in items]
    return {
        "type": "refs_notice",
        "level": level or worst_level(_items),
        "scope": scope,
        "items": _items,
    }


def create_refs_notice_event(scope: str, items: List[Dict[str, Any]]) -> str:
    """组 refs_notice 的 SSE 帧(首发路径供编排层 `yield`; 插话路径经 publish 载体下发)。

    帧级 level 由条目聚合(4.8 判定表唯一裁决), 编排层不硬编码也不碰 level。
    """
    return format_sse_event("refs_notice", 0, build_notice(None, scope, items))


# ---- 引用进入 loop 前的观测: 汇总 / 日志 / notice ———————————————— 小欧-2026-10-30


def summarize_refs(final_refs: List[Dict[str, Any]],
                   notices: List[Dict[str, Any]]) -> Dict[str, int]:
    """引用处置汇总 — 日志与 SSE notice 共用的**唯一数字源**(两通道可逐项对账)。

    files  = 去重后的文件数(整份与区间同 path 只算一个文件);
    fragments = 带 lineRange 的条目数(行片段);
    items  = 实际进入本轮 prompt 的条目数(= files 条目 + 行片段条目, 不含被丢弃/拒绝);
    tokens = 进入本轮正文的估算 token(公共 estimate_tokens, 与预算裁决同口径);
    rejected = 回执条目数(读取失败/越界/压缩/整批拒绝, 即"没能完整进入"的项)。
    """
    paths = {str(r.get("path") or "") for r in final_refs}
    paths.discard("")
    return {
        "files": len(paths),
        "fragments": sum(1 for r in final_refs if r.get("lineRange")),
        "items": len(final_refs),
        "tokens": sum(estimate_tokens(r.get("content")) for r in final_refs),
        "rejected": len(notices or []),
    }


def _tokens_text(tokens: int) -> str:
    """token 文案: <1000 显原值, ≥1000 折 k 保留一位(如 约 640 tokens / 约 1.2k tokens)。"""
    if tokens < 1000:
        return f"约 {tokens} tokens"
    return f"约 {tokens / 1000:.1f}k tokens"


def refs_counts_text(summary: Dict[str, int]) -> str:
    """条目计数文案: 无行片段时只报文件数; 有则"文件、片段（共 N 项）"。

    共 N 项 = 实际进入 prompt 的条目数(片段多来自同文件多区间, 与文件数不可相加),
    故有片段时必须显式给出总项数, 避免"2 个文件、3 个片段"被误读成 5 项。
    """
    if not summary["fragments"]:
        return f"{summary['files']} 个文件"
    return (f"{summary['files']} 个文件、{summary['fragments']} 个行片段"
            f"（共 {summary['items']} 项）")


def _span_text(ref: Dict[str, Any]) -> str:
    """条目行区间文案: 有 lineRange 给 "起-止", 整份给 "整份"。"""
    lr = ref.get("lineRange") or {}
    start, end = lr.get("start"), lr.get("end")
    return f"{start}-{end}" if start else "整份"


def _paths_text(final_refs: List[Dict[str, Any]]) -> str:
    """汇总行 paths=: ≤5 条进入引用的**完整路径**(带行区间), 超出另计条数。

    2026-10-30 小欧 北京老陈令「不许截断」: 原按 60 字符右截断, 会把 `:start-end` 与文件名
      一起切掉 —— 同一文件的整份与片段在日志里变成同一个字符串, 定位信息全丢。现一律给全文;
      行长度由条数上限(5 条 + "另N条")控制, 不靠切路径。
    """
    segs: List[str] = []
    seen = set()
    for r in final_refs:
        path = str(r.get("path") or "")
        if not path:
            continue
        span = _span_text(r)
        key = (path, span)
        if key in seen:
            continue
        seen.add(key)
        segs.append(path if span == "整份" else f"{path}:{span}")
    if not segs:
        return "-"
    more = len(segs) - REF_LOG_PATHS_MAX
    head = ", ".join(segs[:REF_LOG_PATHS_MAX])
    return f"{head} …(另{more}条)" if more > 0 else head


def _detail_lines(final_refs: List[Dict[str, Any]],
                  notices: List[Dict[str, Any]]) -> List[str]:
    """逐条目明细行: 进入的给 行区间/字符/token/路径, 未进入的给 reason/detail/label。"""
    lines: List[str] = []
    for r in final_refs:
        lines.append(
            f"[refs] in span={_span_text(r)} chars={len(str(r.get('content') or ''))} "
            f"tokens={estimate_tokens(r.get('content'))} path={r.get('path') or ''}"
        )
    for n in notices or []:
        lines.append(
            f"[refs] out reason={n.get('reason') or ''} detail={n.get('detail') or '-'} "
            f"label={n.get('label') or ''} path={n.get('path') or ''}"
        )
    return lines


def report_refs(scope: str, summary: Dict[str, int],
                final_refs: List[Dict[str, Any]],
                notices: List[Dict[str, Any]]) -> None:
    """引用处置落日志(查错第一现场): 1 行汇总上控制台+文件, ≤5 行明细仅进文件。

    scope: first | interject。汇总行行首 OK / BLOCKED 区分"全部进入"与"全被阻断"。
    引用正文永不落日志 —— 只留路径/行区间/字符数/token/reason, 正文仍在 _start_meta["refs"]。
    """
    head = "OK" if summary["items"] else "BLOCKED"
    log_and_print(
        f"[refs] {head} scope={scope} files={summary['files']} "
        f"fragments={summary['fragments']} items={summary['items']} "
        f"tokens={summary['tokens']} rejected={summary['rejected']} "
        f"paths={_paths_text(final_refs)}"
    )
    lines = _detail_lines(final_refs, notices)
    for line in lines[:REF_LOG_DETAIL_MAX]:
        logger.info(line)
    if len(lines) > REF_LOG_DETAIL_MAX:
        logger.info(f"[refs] 明细另 {len(lines) - REF_LOG_DETAIL_MAX} 条已省略")


def build_refs_ready_notice(scope: str, summary: Dict[str, int]) -> Dict[str, Any]:
    """组 refs_ready 通知载荷(前端事件列表可见): 进入即 done, 全部不可用即 failed。

    无结构化 refs 字段(北京老陈定: 只给用户看, 前端无消费者, 先建后用是过度设计);
    数字取自 summary, 与日志汇总行同一份, 文案必须与之逐项对得上。
    """
    _interject = scope == "interject"
    if summary["items"]:
        content = (f"{'插话引用进入' if _interject else '引用进入本轮'}："
                   f"{refs_counts_text(summary)}，{_tokens_text(summary['tokens'])}")
        phase = "done"
    else:
        content = (f"{'插话引用全部不可用' if _interject else '引用全部不可用'}："
                   f"{summary['rejected']} 项未能进入本轮，请求已阻断")
        phase = "failed"
    return {"type": "notice", "kind": "refs_ready", "phase": phase,
            "content": content, "step": 0}


def create_refs_ready_event(scope: str, summary: Dict[str, int]) -> str:
    """组 refs_ready 的 SSE 帧(首发路径 `yield`; 插话路径取 build_refs_ready_notice 载荷经
    目标任务 buffer 下发)。"""
    return format_sse_event("notice", 0, build_refs_ready_notice(scope, summary))
