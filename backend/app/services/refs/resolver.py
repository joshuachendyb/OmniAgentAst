# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-29 小欧 新建: 输入框引用解析(按标识读正文, 唯一读盘点) — 小欧-2026-10-29

# 2026-10-29 小欧 修正: 摘录比例常量 REF_* 改从 app.constants 导入——compaction_constants 为
#   压缩/裁剪专属域, 引用摘录比例非其职责; 单一真源迁至系统层常量第4节 — 小欧-2026-10-29

# 2026-10-30 小欧 三堂会审整改: ①A2 捕获 browse.fail() 的 HTTPException 并按 code 映射
#   unsupported/missing; 区间读中途文件消失由 isfile 复核判 missing, 不再误判 range_out;
#   ②A3 读后按实际字符复核(read_max_bytes), 补行数门槛挡不住的"行少单行极长"与 2MB 截断线;
#   ③A13 同 path 去重提前到读取前, 整份+区间并存时区间不再白读; ④A14 删区间分支无效 size 回写 — 小欧-2026-10-30
# 2026-10-30 小欧 批3收尾: 字符级头尾摘录迁 services/refs/clip.clip_text(与预算压缩共用,
#   杜绝两处口径分叉) — 小欧-2026-10-30
# 2026-10-30 小欧 批3: resolve_refs 放行条目统一追加(原实现 elif/else 两条分支各写一次 resolved.append,
#   同一语句两处, 收口为循环尾单点) — 小欧-2026-10-30
# 2026-10-30 小欧 B1: 区间分支出口补 clip_text + truncated 回执 —— 原实现直接返回, 长区间
#   绕过单条上限(4.6.2)且回执为空 — 小欧-2026-10-30

"""services.refs.resolver — 按引用标识读正文(唯一 IO 点)

为何独立: 读取分流在 quote.ts:34-36(有外部/根内分流)与 refresh.ts:35(没有)的历史
  实测分叉(D1/D2 直接成因); 本模块成为后端唯一读盘点, 前端不再读正文。
复用既有实现(DRY): read_text_file / read_external_file / _read_range, 不新写读盘逻辑。
"""
import asyncio
import os
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from fastapi import HTTPException

from app.file_browse import browse_service as browse
from app.file_browse.errors import UNDECODABLE, UNSUPPORTED_TYPE
from app.constants import REF_AVG_LINE_CHARS, REF_HEAD_RATIO, REF_TAIL_RATIO  # 摘录比例单一真源(5.2.11)
from app.services.refs.clip import clip_text   # 2026-10-30 小欧: 字符级头尾摘录公共实现(与 budget 共用)
from app.services.refs.limits import RefLimits

# 单条读取超时(外部盘/网络盘慢时不拖死编排)
REF_READ_TIMEOUT = 5
# 并发读上限(防一次引用多个大文件打满磁盘)
REF_READ_CONCURRENCY = 4
# 区间分块行数: 与 browse_service._read_range 单次钳制同口径(:946)
REF_READ_BLOCK_LINES = 5000


@dataclass
class ResolvedRef:
    ref: Dict[str, Any]   # 原始 ref(已填好 content/size; 失败时为原始引用)
    truncated: bool       # 是否因读取上限被截断(直读截断或头尾摘录)
    note: str             # 失败标记或回执 detail("err:missing:FileNotFoundError"/"已省略 N 行"/"range_clipped"); 文件更新提示由前端本地 mtime 比对, 不出后端回执(R2)


async def _read_blocks(path: str, is_ext: bool, offset: int, limit: int,
                       *, count_total: bool = False) -> Tuple[str, bool]:
    """分块读一个行区间(每块 ≤REF_READ_BLOCK_LINES, 对齐 _read_range 单次钳制)。

    为何要分块: _read_range 单次最多返回 5000 行(browse_service.py:946),
      请求 6000 行区间不切块会静默丢 1000 行(4.6.1 "分块 ≤5000 行")。
    返回 (content, clipped): clipped=块内实读行数小于请求行数, 即请求区间越过文件尾
      (部分区间超尾, 4.6.4 → 回执 range_clipped); 完全越界由空 content 判定。
    """
    reader = browse.read_external_file if is_ext else browse.read_text_file
    parts: List[str] = []
    cur, left, clipped = offset, limit, False
    while left > 0:
        n = min(left, REF_READ_BLOCK_LINES)
        r = await asyncio.to_thread(reader, path, cur, n, count_total=count_total)
        content = r.get("content") or ""
        if not content:
            # 2026-10-30 小欧 A2: _read_lines_range 吞 OSError 返回空串, 若文件在区间读中途
            #   被删/被移走, 原地 break 会被上层误判为 range_out。此处按盘面复核区分:
            #   已不存在 → 抛 FileNotFoundError 走 missing; 仍存在(区间起点在文件尾后) → 正常 break。
            if not await asyncio.to_thread(os.path.isfile, path):
                raise FileNotFoundError(path)
            break
        parts.append(content)
        got = int(r.get("loaded_lines") or 0)
        if got < n:
            clipped = True          # 已到文件尾且请求未被满足
            break
        cur += got
        left -= got
        count_total = False         # total_lines 只在首个块取
    return "".join(parts), clipped


def _fail(ref: Dict[str, Any], reason: str, exc: Exception) -> ResolvedRef:
    """失败落点: note 标记 "err:<reason>:<异常名>", resolve_refs 据此入 dropped(4.6.4)。

    归类映射: FileNotFoundError/PermissionError → missing(不存在/不可读);
      IsADirectoryError/UnicodeDecodeError → unsupported(非文本/不可解码);
      其余异常 → missing 从严(detail 携带异常名, 定位用)。
    """
    return ResolvedRef(ref=ref, truncated=False,
                       note=f"err:{reason}:{type(exc).__name__}")


async def _read_one(ref: Dict[str, Any], limits: RefLimits) -> ResolvedRef:
    """按标识读单条正文。同步读盘经 asyncio.to_thread 卸载出事件循环(仓库既有范式)。

    读法矩阵(4.6.1):
      根内 + 无 lineRange + 字符数≤上限 → read_text_file(整份直读)
      根内 + 无 lineRange + 超上限     → 头尾摘录(4.6.3: 全扫一次取 total_lines,
                                         头 REF_HEAD_RATIO 段 + 尾 REF_TAIL_RATIO 段, 各分块)
      根内 + 有 lineRange              → _read_blocks 分块读区间(≤5000 行/块)
      外部 + 无/有 lineRange           → read_external_file(同上口径)
      无 path                          → dropped(no_path)
    """
    path = (ref.get("path") or "").strip()
    if not path:
        return ResolvedRef(ref=ref, truncated=False, note="no_path")
    lr = ref.get("lineRange") or {}
    offset = lr.get("start")
    limit = (lr.get("end", lr.get("start")) - lr.get("start") + 1) if lr.get("start") else None
    is_ext = browse._is_abs_drive_path(path)
    try:
        if offset is not None:
            # 有区间: 分块读, 不触发全扫(count_total=False 见 5.2.10)
            content, clipped = await _read_blocks(path, is_ext, int(offset), int(limit or 1))
            if not content:
                # 区间完全越界(起点在文件尾之后): dropped(range_out, 4.6.4), 不静默放行空块
                return ResolvedRef(ref=ref, truncated=False, note="err:range_out:_read_blocks")
            # 2026-10-29 小欧 - range_clipped 回执(F2): 请求区间超出文件尾时如实告知,
            #   不再静默(4.6.1 注); 未越尾则 note 空 → resolve_refs 走放行分支。
            #   2026-10-30 小欧 A14: 删 `"size": ref.get("size")` —— 与 {**ref} 重复, 空操作。
            # 2026-10-30 小欧 B1: 区间分支原样返回, 完全绕过单条上限(4.6.2) —— 一条长区间
            #   (实测 56,000 tok > 单条 42,428) 直入 prompt 且回执为空。与整份分支同走
            #   clip_text 复核: 超限则头尾摘录 + truncated 回执; 区间越尾同时给出说明。
            content, _omitted_chars = clip_text(content, limits.read_max_bytes)
            truncated = bool(_omitted_chars)
            if truncated:
                note = f"已省略 {_omitted_chars} 字符" + ("；区间超出文件尾" if clipped else "")
            else:
                note = "range_clipped" if clipped else ""
            return ResolvedRef(ref={**ref, "content": content},
                               truncated=truncated,
                               note=note)
        # 无区间: 先整份直读(_read_truncated, ≤2MB, 零全扫)
        reader = browse.read_external_file if is_ext else browse.read_text_file
        r = await asyncio.to_thread(reader, path)
        content = r.get("content") or ""
        truncated = bool(r.get("truncated"))
        note = "仅读取前 N 行" if truncated else ""
        if truncated or int(r.get("size") or 0) > limits.read_max_bytes:
            # 超单条上限 → 头尾摘录(4.6.3): 全扫一次取 total_lines(仅此一次), 头/尾各分块读
            probe = await asyncio.to_thread(reader, path, 1, 1, count_total=True)
            total = int(probe.get("total_lines") or 0)
            head_lines = max(1, int(REF_HEAD_RATIO * limits.read_max_bytes / REF_AVG_LINE_CHARS))
            tail_lines = max(1, int(REF_TAIL_RATIO * limits.read_max_bytes / REF_AVG_LINE_CHARS))
            if total > head_lines + tail_lines:
                head, _ = await _read_blocks(path, is_ext, 1, head_lines)
                tail, _ = await _read_blocks(path, is_ext, total - tail_lines + 1, tail_lines)
                _omitted = total - head_lines - tail_lines
                content = f"{head}\n…[引用超长, 已省略 {_omitted} 行]\n{tail}"
                truncated = True
                note = f"已省略 {_omitted} 行"
        # 2026-10-30 小欧 A3: 行数门槛之后再按实际字符复核。行少但单行极长(160KB/800 行)
        #   与 2MB 单行截断文件都从原实现的 `total <= head+tail` 缺口直出全文, 现统一收口。
        content, _omitted_chars = clip_text(content, limits.read_max_bytes)
        if _omitted_chars:
            truncated = True
            note = f"已省略 {_omitted_chars} 字符"
        return ResolvedRef(ref={**ref, "content": content, "size": r.get("size")},
                           truncated=truncated,
                           note=note)
    except asyncio.TimeoutError:
        raise   # 外层 _guarded 统一超时落点(dropped reason=timeout)
    except HTTPException as e:
        # 2026-10-30 小欧 A2: browse 的唯一抛错出口是 fail()(HTTPException, detail={code,message})。
        #   原实现被下方 Exception 兜成 missing, 415(UNSUPPORTED_TYPE/UNDECODABLE) 永远到不了
        #   unsupported。此处按 code 精确映射, 其余(404/400/403/413)归 missing。
        _code = e.detail.get("code") if isinstance(e.detail, dict) else None
        _reason = "unsupported" if _code in (UNSUPPORTED_TYPE, UNDECODABLE) else "missing"
        return ResolvedRef(ref=ref, truncated=False,
                           note=f"err:{_reason}:{_code or 'HTTPException'}")
    except FileNotFoundError as e:
        return _fail(ref, "missing", e)
    except PermissionError as e:
        return _fail(ref, "missing", e)
    except (IsADirectoryError, UnicodeDecodeError) as e:
        return _fail(ref, "unsupported", e)
    except Exception as e:  # noqa: BLE001 — fail() 抛业务错误, 一律归类回执(4.6.4)
        return _fail(ref, "missing", e)


async def resolve_refs(
    refs: List[Dict[str, Any]],
    *,
    limits: RefLimits,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], List[Dict[str, str]]]:
    """并发读全部引用(信号量限流 + 超时), 返回 (resolved, dropped, notices)。

    resolved 元素 = 原始 ref + content/size(供 render 消费);
    dropped 元素 = {label, path, reason, detail}(供回执点名; reason 按 4.6.4 分类);
    notices 元素 = {label, path, reason, detail}(非阻断提示); 条目 level 由
    notice.build_notice 统一查 REASON_LEVELS 补齐(单一裁决点, resolver/budget 不碰 level)。
    """
    sem = asyncio.Semaphore(REF_READ_CONCURRENCY)

    # 2026-10-30 小欧 A13: 同 path 去重提前到**读取前**(整份优先, 同 path 的区间条目直接丢弃)。
    #   原实现在全部读完后再合并 → 整份+区间并存时区间白读一次(磁盘 IO 与超时预算都浪费)。
    refs = _merge_same_path(list(refs))

    async def _guarded(ref: Dict[str, Any]) -> ResolvedRef:
        async with sem:
            try:
                return await asyncio.wait_for(_read_one(ref, limits), timeout=REF_READ_TIMEOUT)
            except asyncio.TimeoutError:
                return ResolvedRef(ref=ref, truncated=False, note="timeout")

    results = await asyncio.gather(*[_guarded(r) for r in refs])
    resolved: List[Dict[str, Any]] = []
    dropped: List[Dict[str, str]] = []
    notices: List[Dict[str, str]] = []
    for rr in results:
        if rr.note.startswith("err:"):
            _tag, _reason, _exc = rr.note.split(":", 2)     # "err:<reason>:<异常名>"
            dropped.append({
                "label": (rr.ref.get("label") or rr.ref.get("path") or ""),
                "path": rr.ref.get("path") or "",
                "reason": _reason,          # 4.6.4 分类: missing/unsupported/range_out
                "detail": _exc,             # 异常名, 定位用
            })
            continue
        if rr.note in ("timeout", "no_path"):
            dropped.append({
                "label": (rr.ref.get("label") or rr.ref.get("path") or ""),
                "path": rr.ref.get("path") or "",
                "reason": rr.note,
            })
            continue
        if rr.truncated or rr.note == "range_clipped":
            # 2026-10-29 小欧 - range_clipped 与 truncated 同类: 非阻断, 放行 + 回执点名
            notices.append({
                "label": (rr.ref.get("label") or rr.ref.get("path") or ""),
                "path": rr.ref.get("path") or "",
                "reason": "truncated" if rr.truncated else "range_clipped",
                "detail": rr.note,
            })
        # 放行条目统一在此追加(原实现 elif/else 两条分支各写一次, 同一语句两处 — 2026-10-30 小欧)
        resolved.append(rr.ref)
    # 同 path 已在读取前去重(A13), 此处不再二次合并
    return resolved, dropped, notices


def _merge_same_path(refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """同 path 去重(读取前调用): 同一请求内同一文件整份只读一次; 不同区间各读一次。

    整份(lineRange 空)优先: 若已有整份, 丢弃所有该 path 的区间条目; 否则按 lineRange 保序。
    """
    by_path: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for r in refs:
        p = r.get("path") or ""
        if p not in by_path:
            by_path[p] = []
            order.append(p)
        by_path[p].append(r)
    out: List[Dict[str, Any]] = []
    for p in order:
        items = by_path[p]
        whole = [i for i in items if not i.get("lineRange")]
        if whole:
            out.append(whole[0])   # 整份优先, 丢弃区间条目
        else:
            out.extend(items)
    return out
