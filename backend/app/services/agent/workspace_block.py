# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-31 小欧 - 新建: 事项目录注入块唯一渲染实现(原 stream_orchestrator._append_ws_suffix 迁入);
#   截断按「默认工作区 > 带 memo/非 read_write 属性 > 其余」排序 + 默认工作区保留位;
#   标签与块内用语统一为「事项目录」 — 小欧-2026-10-31
# 2026-10-31 小欧 - 渲染与观测补全: 渲染结果改 WsBlock(text/kept/skipped), 渲染一次即得
#   观测数字; 新增 report_ws_block(注入汇总日志) 与 build_ws_notice(超限轻提示, 复用 notice 信封) — 小欧-2026-10-31
# 2026-11-15 小欧 - 标签字面量收归 app.wire_prefix(ENV_WS_OPEN/CLOSE), 消除 4.4.3 纪律1 残留 — 小欧-2026-11-15
"""services.agent.workspace_block — 事项目录注入块(渲染 + 观测)

为何独立: 目录块原先在编排层拼字符串, 只有首发路径调用, 插话必然漏注;
  现集中到本模块, 首发/插话共用一份格式与截断规则。

职责边界: 本模块只负责渲染与观测(日志/回执载荷), 不装配消息;
  渲染点在编排层(首发与插话各调一次), 装配点在 message_builder(接收已渲染文本)。

格式(与引用块同款包裹标签, 标签词与块内用语统一):
  <事项目录>
  以下是你可用的事项目录：
    - <路径>
  要求生成临时/中间文件，请写入事项目录。
  </事项目录>

截断纪律: MAX_WORKSPACES=64 × 路径长度最坏约 16KB/轮, 超 WS_INJECT_MAX_CHARS
  只保留优先级高的若干条 + 末尾省略提示; 默认工作区恒保留, 超限则截路径不截整条。

观测纪律: 渲染一次即得 kept/skipped 数字, 日志(report_ws_block)与 SSE 提示
  (build_ws_notice)都取自同一份, 两通道可逐项对账; 提示只报省略条数, 不阻断本轮。
"""
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

from app.logger import logger
from app.wire_prefix import ENV_WS_OPEN, ENV_WS_CLOSE

WS_INJECT_MAX_CHARS = 4096     # 注入块总字符上限(与目录数上限共同约束最坏体积)

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


def select_ws_lines(snapshot) -> Tuple[List[str], int, int]:
    """按优先级选行并截断。返回 (块行(含省略提示行), 保留条数, 跳过条数)。

    默认工作区(排序后第一条)恒保留: 即使单条超上限也截路径保留,
    否则"最该被模型知道的目录"会在清单过长时被整体跳过。
    """
    entries = getattr(snapshot, "entries", None)
    if not entries:
        return [], 0, 0
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
    return kept, len(kept) - (1 if skipped else 0), skipped


@dataclass(frozen=True)
class WsBlock:
    """目录块渲染结果(纯数据)。text 无目录时为空串; kept/skipped 供日志与回执取数。"""
    text: str
    kept: int
    skipped: int


def render_workspace_block(snapshot) -> WsBlock:
    """渲染事项目录块。无快照/无目录返回 WsBlock("", 0, 0)。

    纯渲染: 不做安全判定(越界过滤归 workspace_service), 不读 ContextVar(调用方传快照)。
    """
    lines, kept, skipped = select_ws_lines(snapshot)
    if not lines:
        return WsBlock("", 0, 0)
    body = "\n".join(lines)
    block = (
        f"{ENV_WS_OPEN}\n"
        "以下是你可用的事项目录：\n"
        f"{body}\n"
        "要求生成临时/中间文件，请写入事项目录。\n"
        f"{ENV_WS_CLOSE}\n\n"
    )
    return WsBlock(block, kept, skipped)


def ws_source(snapshot) -> str:
    """快照来源文案(日志用): session=会话目录快照可用; none=无快照或空目录。"""
    return "session" if getattr(snapshot, "entries", None) else "none"


def report_ws_block(scope: str, block: WsBlock, snapshot, action: str) -> None:
    """目录块处置汇总日志(唯一实现, 首发/插话共用): 动作/条数/跳过数/来源。

    action: inject=注入本轮 / invalidate=内容已变, 注入新块并作废旧块 /
            skip_dup=内容未变, 不重复注入 / skip_none=无目录快照, 本轮无块。
    正常注入汇总日志的落点, 与 build_ws_notice 取同一份数字。
    """
    logger.info(f"[ws] scope={scope} action={action} kept={block.kept} "
                f"skipped={block.skipped} source={ws_source(snapshot)}")


def build_ws_notice(scope: str, block: WsBlock) -> Dict[str, Any]:
    """目录块超限回执载荷(复用 notice 信封, 不阻断): 只报省略条数。

    phase 取 done: 信封契约只有 start/done/failed, 此处语义是"本轮目录已装配完成、有省略",
    非失败; 前端按 ws_inject_done 查表渲染警示图标, 不新增前端组件。
    """
    return {
        "type": "notice",
        "kind": "ws_inject",
        "phase": "done",
        "content": f"事项目录过长，已省略 {block.skipped} 条（默认目录始终保留）",
        "step": 0,
    }


__all__ = [
    "WS_INJECT_MAX_CHARS",
    "ENV_WS_OPEN",
    "ENV_WS_CLOSE",
    "WS_INVALIDATED",
    "WsBlock",
    "select_ws_lines",
    "render_workspace_block",
    "ws_source",
    "report_ws_block",
    "build_ws_notice",
]
