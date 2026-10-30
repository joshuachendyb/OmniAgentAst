# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-30 小欧 新建: 引用回执 DTO + reason→level 唯一裁决 + SSE 组帧 — 小欧-2026-10-30
# 2026-10-30 小欧 批3: ①_LEVEL_RANK 序号表由 _LEVEL_ORDER 元组派生(单一真源, 原手写 dict 与元组易分叉);
#   ②新增 describe_items(去重后的 label/path 点名文案, 首发与插话阻断提示共用, 原两条路径各写一遍拼串) — 小欧-2026-10-30

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
"""
from typing import Any, Dict, List, Optional

from app.utils.sse_formatter import format_sse_event

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
