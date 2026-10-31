# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-31 小欧 - 新建: 事项目录注入块唯一渲染实现(原 stream_orchestrator._append_ws_suffix 迁入);
#   截断按「默认工作区 > 带 memo/非 read_write 属性 > 其余」排序 + 默认工作区保留位;
#   标签与块内用语统一为「事项目录」 — 小欧-2026-10-31
"""services.agent.workspace_block — 事项目录注入块(纯渲染, 零 IO)

为何独立: 目录块原先在编排层拼字符串, 只有首发路径调用, 插话必然漏注;
  迁到 agent 层后与引用块同址装配(单一装配点), 两条路径共用一份格式与截断规则。

格式(与引用块同款包裹标签, 标签词与块内用语统一):
  <事项目录>
  以下是你可用的事项目录：
    - <路径>
  要求生成临时/中间文件，请写入事项目录。
  </事项目录>

截断纪律: MAX_WORKSPACES=64 × 路径长度最坏约 16KB/轮, 超 WS_INJECT_MAX_CHARS
  只保留优先级高的若干条 + 末尾省略提示; 默认工作区恒保留, 超限则截路径不截整条。
"""
from typing import List, Tuple

WS_INJECT_MAX_CHARS = 4096     # 注入块总字符上限(与目录数上限共同约束最坏体积)

WS_TAG_OPEN = "<事项目录>"
WS_TAG_CLOSE = "</事项目录>"

# 旧块作废文案: 插话更新目录后, 历史里的旧块保留标签但清空正文 —
#   多份同类清单并存时模型没有可靠的版本比较能力, 只留一份有效清单是确定性做法。
WS_INVALIDATED = "（已被后续更新覆盖，以最新一条为准）"

# 目录优先级: 默认工作区最该被模型知道, 其次是有备注/特殊属性的目录, 其余按路径序。
_RANK_DEFAULT = 0
_RANK_ANNOTATED = 1
_RANK_PLAIN = 2


def _rank(entry) -> int:
    """条目优先级: 默认工作区 > 带 memo 或非默认读写属性 > 其余。"""
    if getattr(entry, "is_default", False):
        return _RANK_DEFAULT
    if getattr(entry, "memo", None):
        return _RANK_ANNOTATED
    if getattr(entry, "workspace_property", "read_write") != "read_write":
        return _RANK_ANNOTATED
    return _RANK_PLAIN


def _clip(line: str, cap: int) -> str:
    """单行超上限时截路径保首(默认工作区不可整条丢)。"""
    return line if len(line) <= cap else line[:max(cap - 1, 0)] + "…"


def select_ws_lines(snapshot) -> Tuple[List[str], int]:
    """按优先级选行并截断。返回 (保留行, 跳过条数); 跳过行计入末尾省略提示。

    默认工作区(排序后第一条)恒保留: 即使单条超上限也截路径保留,
    否则"最该被模型知道的目录"会在清单过长时被整体跳过。
    """
    entries = getattr(snapshot, "entries", None)
    if not entries:
        return [], 0
    lines = [f"  - {e.path}" for e in sorted(entries, key=lambda e: (_rank(e), e.path))]
    kept: List[str] = [_clip(lines[0], WS_INJECT_MAX_CHARS)]
    total, skipped = len(kept[0]), 0
    for line in lines[1:]:
        if total + len(line) > WS_INJECT_MAX_CHARS:
            skipped += 1
            continue
        kept.append(line)
        total += len(line)
    if skipped:
        kept.append(f"  ...(其余 {skipped} 条省略)")
    return kept, skipped


def render_workspace_block(snapshot) -> Tuple[str, int]:
    """渲染事项目录块。返回 (块文本, 跳过条数); 无快照/无目录返回 ("", 0)。

    纯渲染: 不做安全判定(越界过滤归 workspace_service), 不读 ContextVar(调用方传快照)。
    """
    lines, skipped = select_ws_lines(snapshot)
    if not lines:
        return "", 0
    body = "\n".join(lines)
    block = (
        f"{WS_TAG_OPEN}\n"
        "以下是你可用的事项目录：\n"
        f"{body}\n"
        "要求生成临时/中间文件，请写入事项目录。\n"
        f"{WS_TAG_CLOSE}\n\n"
    )
    return block, skipped


__all__ = [
    "WS_INJECT_MAX_CHARS",
    "WS_TAG_OPEN",
    "WS_TAG_CLOSE",
    "WS_INVALIDATED",
    "select_ws_lines",
    "render_workspace_block",
]
