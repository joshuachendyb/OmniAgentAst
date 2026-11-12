# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-11 小欧 新建: 附件能力域运行指标(P5) — 单行结构化埋点 + 只读日志聚合,
#   不加新表(§10 P5 口径), 聚合源=logs/app_*.log 的 [cap-metric] 行

"""attachments.observability — 附件能力域运行指标（P5 运营与观测）。

埋点: metric() 产出单行可解析日志, 识别标记 [cap-metric], 仅进文件通道(logger.info),
  不上控制台(高频逐项行, 控制台只留 WARNING+)。
聚合: metrics_summary() 按文件名日期扫 logs/app_*.log, 纯只读, 不写任何存储。

事件口径(与 §10 P5 三指标对应):
  native        wire 展开走原生 part 成功
  degraded      无原生通道降级(注入文本/档案卡/链接文本)
  native_fail   原生 part 构造/载荷失败(build_logical_part/ensure_payload/to_wire_part)
  extract_ok / extract_fail   真抽取结果(fallback_quality=content 的 kind)
  fetch_fail    远端下载失败(remote_fetch 四闸门/HTTP/超限)

比率: 降级占比 = degraded/(native+degraded); 原生失败率 = native_fail/(native+native_fail);
  抽取失败率 = extract_fail/(extract_ok+extract_fail)。失败可定位到 (source, kind)。
"""
import re
from collections import Counter
from pathlib import Path
from typing import Dict, Optional

from app.logger import logger
from app.logger.config import LOG_DIR

_TAG = "[cap-metric]"
_LINE_RE = re.compile(r"\[cap-metric\] event=(\S+) source=(\S+) kind=(\S+)")
_FILE_DATE_RE = re.compile(r"app_(\d{4}-\d{2}-\d{2})\.log")


def metric(event: str, source: str, kind: str,
           model: str = "", reason: str = "") -> None:
    """单行指标埋点(仅文件通道): [cap-metric] event=.. source=.. kind=.. model=.. reason=.."""
    logger.info("%s event=%s source=%s kind=%s model=%s reason=%s",
                _TAG, event, source, kind, model.replace(" ", "_"), reason.strip())


def metrics_summary(days: int = 1, log_dir: Optional[str] = None) -> Dict[str, Dict[str, float]]:
    """按天聚合近 N 天的 [cap-metric] 行(只读日志, 不加新表)。

    返回 {event: {"source/kind": 次数}} + rates(三比率, 按 source/kind)。
    无日志文件/无指标行返回空结构, 不抛异常。
    """
    root = Path(log_dir) if log_dir else LOG_DIR
    dates = sorted({m.group(1) for f in root.glob("app_*.log")
                    if (m := _FILE_DATE_RE.search(f.name))})
    keep = set(dates[-max(1, int(days)):])
    counts: Counter = Counter()
    for f in root.glob("app_*.log"):
        m = _FILE_DATE_RE.search(f.name)
        if not m or m.group(1) not in keep:
            continue
        try:
            for line in f.read_text(encoding="utf-8", errors="replace").splitlines():
                hit = _LINE_RE.search(line)
                if hit:
                    counts[(hit.group(1), hit.group(2), hit.group(3))] += 1
        except OSError:
            continue
    events: Dict[str, Dict[str, int]] = {}
    for (ev, src, kind), n in counts.items():
        events.setdefault(ev, {})[f"{src}/{kind}"] = n

    def _rate(num_ev: str, den_evs: tuple) -> Dict[str, float]:
        out: Dict[str, float] = {}
        for key in set().union(*(events.get(e, {}) for e in den_evs)):
            den = sum(events.get(e, {}).get(key, 0) for e in den_evs)
            if den:
                out[key] = round(events.get(num_ev, {}).get(key, 0) / den, 4)
        return out

    return {
        "days": max(1, int(days)),
        "counts": events,
        "rates": {
            "degrade": _rate("degraded", ("native", "degraded")),
            "native_fail": _rate("native_fail", ("native", "native_fail")),
            "extract_fail": _rate("extract_fail", ("extract_ok", "extract_fail")),
        },
    }
