# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-29 小欧 新建: 输入框引用解析(按标识读正文, 唯一读盘点) — 小欧-2026-10-29

# 2026-10-29 小欧 修正: 摘录比例常量 REF_* 改从 app.constants 导入——compaction_constants 为
#   压缩/裁剪专属域, 引用摘录比例非其职责; 单一真源迁至系统层常量第4节 — 小欧-2026-10-29

# 2026-10-30 小欧 整改: 异常捕获按 browse.fail code 精确映射(unsupported/missing), 区间读中途文件消失 isfile 复核判 missing;
#   读后按实际字符复核, 同 path 去重提前到读取前, 删区间分支无效 size 回写 — 小欧-2026-10-30
# 2026-10-30 小欧 收口: 字符级头尾摘录迁 services/refs/clip.clip_text(与预算压缩共用, 杜绝两处口径分叉);
#   resolve_refs 放行条目统一循环尾单点追加; 区间分支出口补 clip_text + truncated 回执 — 小欧-2026-10-30
# 2026-11-06 小欧 重建附件分支(配套误还原后恢复): 增 _read_attachment(按 attachment_id 查表 +
#   extract.build_inject_text 生成注入文本), _read_one 先分流 kind=attachment;
#   失败 reason 用 attachment_missing/attachment_failed — 小欧-2026-11-06
# 2026-11-06 小欧 收口: _read_one 附件分支补 await asyncio.to_thread(_read_attachment) ——
#   DB 查表为同步阻塞 IO, 原同步直调在事件循环上裸跑, 违背"同步读盘 to_thread 卸载"纪律 — 小欧-2026-11-06
# 2026-11-07 小欧 越权收紧: resolve_refs/_read_one/_read_attachment 增加 session_id 必填参数,
#   附件注入前校验会话归属(经 get_attachment_scoped, 与 API 端点同一口径) ——
#   跨会话按 id 注入属越权, 不匹配折算 attachment_missing(视同失效, 不阻断其余引用)
# 2026-11-07 小欧 单条预算闸门: text 附件不再豁免 clip_text, 所有 kind 统一走 read_max_bytes
#   (clip_text 未超限原样返回, 小文本仍全文注入) —— 修复 ≤256KB 文本直入绕过
#   预算、大文本整批被拒的问题 — 小欧-2026-11-07
# 2026-11-07 小欧 跨会话放行: 跨会话附件改为 auto_promote(自动升级为全局, 不再折算 missing),
#   注入成功即 touch_usage 记账 —— 「最近用过」的唯一真源 — 小欧-2026-11-07
# 2026-11-07 小欧 注释清理: 去除文档号/修复序号/评审引用等过期标识, 注释语义不变 — 小欧-2026-11-07
# 2026-11-09 小欧 S3: 真抽取成功/失败回填抽取态(mark_extract_result, 在 clip_text 之前取 len) — 小欧-2026-11-09
# 2026-11-11 小欧 附件能力域: 增 url 分支(链接文本+准入, 不下载); 抽取态回填改读契约
#   fallback_quality, 删除档案卡前缀字符串匹配; 同 path 去重键兼容 url — 小欧-2026-11-11
# 2026-11-11 小欧 P5 指标埋点: 真抽取成功/失败补 [cap-metric] extract_ok/extract_fail
#   (kind 来自附件记录, 失败可定位到 kind) — 小欧-2026-11-11



# 2026-11-14 小欧 非文本引用文本出口: file/selection 的 image/video/audio/richdoc 原落 read_text_file
#   被 415 丢弃(首发正文整条消失)。改在 path 校验后按契约文本出口产卡/抽取正文, 复用唯一实现,
#   产物过 clip_text 预算闸门; 单条解析失败折 unsupported 不阻断整批。binary/unknown 仍走原读取
#   语义(避免未知后缀文本被误判)。附件真抽取态判据随契约 fallback_quality 改名 text_full — 小欧-2026-11-14

# 2026-11-14 小欧 三堂会审整改: 删 _read_attachment 内 KIND_CONTRACT 重复延迟导入(模块头已有
#   同名导入); url 分支改用 extract.link_body 公名(消私有名跨模块消费) — 小欧-2026-11-14
#
# 2026-11-14 小欧 第7章7.4 阶段B 物化: resolve_refs/_read_one 增 llm_model 透传; 本地 image/audio
#   在模型声明原生 + 大小≤内联上限 + 音频容器 wav/mp3 时, _materialize_media 经 save_bytes 入附件库
#   (继承单文件/会话总量/sha 去重/会话归属), ref 补 attachment_id 后由计划器判 native; 失败回落文本出口 — 小欧-2026-11-14
#   (根内相对路径经 browse._resolve_within_root 解析, 与读取同口径, 不按进程 CWD 误读) — 小欧-2026-11-14
#
# 2026-11-14 小欧 阶段B 物化失败回执: _materialize_media 改返回 (attachment_id, reason, detail),
#   无会话/超内联上限/落库异常分别回 materialize_no_session/materialize_too_large/materialize_failed;
#   回落文本出口成功时随 ResolvedRef.notices 下发 warn 级回执, 文本出口自身失败仍只报 dropped — 小欧-2026-11-14
# 2026-11-15 小欧 7.4.2 selection 入口类型保护: selection 语义为文本行区间, 指向 image/video/audio/richdoc
#   时显式 dropped(selection_not_text), 不物化、不产元信息卡 — 小欧-2026-11-15


"""services.refs.resolver — 按引用标识读正文(唯一 IO 点)

为何独立: 读取分流在 quote.ts:34-36(有外部/根内分流)与 refresh.ts:35(没有)的历史
  实测分叉直接成因; 本模块成为后端唯一读盘点, 前端不再读正文。
复用既有实现(DRY): read_text_file / read_external_file / _read_range, 不新写读盘逻辑。
"""
import asyncio
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Tuple

from fastapi import HTTPException

# 附件注入文本唯一产生点(extract 纯函数 + service 查表), 读盘在 extract 内走 browse
from app.attachments import extract
from app.attachments.contract import KIND_CONTRACT
from app.attachments.attachment_service import (
    get_attachment_scoped,
    mark_extract_result,
    save_bytes,
    touch_usage,
)
from app.attachments.observability import metric
from app.constants import REF_AVG_LINE_CHARS, REF_HEAD_RATIO, REF_TAIL_RATIO  # 摘录比例单一真源
from app.file_browse import browse_service as browse
from app.file_browse.errors import UNDECODABLE, UNSUPPORTED_TYPE
from app.logger import logger
from app.services.refs.clip import (
    clip_text,  # 2026-10-30 小欧: 字符级头尾摘录公共实现(与 budget 共用)
)
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
    note: str             # 失败标记或回执 detail("err:missing:FileNotFoundError"/"已省略 N 行"/"range_clipped"); 文件更新提示由前端本地 mtime 比对, 不出后端回执
    notices: List[Dict[str, str]] = field(default_factory=list)  # 非阻断回执(物化失败等), 随放行条目一并下发


async def _read_blocks(path: str, is_ext: bool, offset: int, limit: int,
                       *, count_total: bool = False) -> Tuple[str, bool]:
    """分块读一个行区间(每块 ≤REF_READ_BLOCK_LINES, 对齐 _read_range 单次钳制)。

    为何要分块: _read_range 单次最多返回 5000 行(browse_service.py:946),
      请求 6000 行区间不切块会静默丢 1000 行(分块 ≤5000 行)。
    返回 (content, clipped): clipped=块内实读行数小于请求行数, 即请求区间越过文件尾
      (部分区间超尾 → 回执 range_clipped); 完全越界由空 content 判定。
    """
    reader = browse.read_external_file if is_ext else browse.read_text_file
    parts: List[str] = []
    cur, left, clipped = offset, limit, False
    while left > 0:
        n = min(left, REF_READ_BLOCK_LINES)
        r = await asyncio.to_thread(reader, path, cur, n, count_total=count_total)
        content = r.get("content") or ""
        if not content:
            # 2026-10-30 小欧: _read_lines_range 吞 OSError 返回空串, 若文件在区间读中途
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
    """失败落点: note 标记 "err:<reason>:<异常名>", resolve_refs 据此入 dropped。

    归类映射: FileNotFoundError/PermissionError → missing(不存在/不可读);
      IsADirectoryError/UnicodeDecodeError → unsupported(非文本/不可解码);
      其余异常 → missing 从严(detail 携带异常名, 定位用)。
    """
    return ResolvedRef(ref=ref, truncated=False,
                       note=f"err:{reason}:{type(exc).__name__}")


def _read_attachment(ref: Dict[str, Any], limits: RefLimits,
                     session_id: str | None) -> ResolvedRef:
    """附件注入文本生成(唯一产生点)。

    kind=attachment: 按 attachment_id 查表(get_attachment_scoped, 含访问权校验),
    生成注入文本。失败 reason:
      attachment_missing  记录不存在(引用已失效)
      attachment_failed   build_inject_text 内部异常(读盘/解析失败)
    附件不参与行级读取/预算压缩 —— 注入按 id 查表, 不受 path 越界影响。
    2026-11-07 小欧: 跨会话 session 级附件 auto_promote(自动收藏, 不 404);
      生成成功后 touch_usage 记账(use_count/last_used_at 唯一写入点, 「最近用过」真源) — 小欧-2026-11-07
    """
    att = get_attachment_scoped(ref.get("attachment_id") or "", session_id,
                                auto_promote=True)
    if not att:
        return ResolvedRef(ref=ref, truncated=False,
                           note="err:attachment_missing:AttachmentNotFound")
    try:
        text = extract.build_inject_text(att)
    except Exception as e:  # noqa: BLE001 — 呈现失败折算 attachment_failed, 不阻断其余引用
        # 首次失败也回填抽取态(详情页可见), 然后照旧给回执
        mark_extract_result(att["id"], 0, False)
        metric("extract_fail", "attachment", att.get("kind") or "binary", reason=type(e).__name__)
        return ResolvedRef(ref=ref, truncated=False,
                           note=f"err:attachment_failed:{type(e).__name__}")
    # 仅"真抽取正文"(契约 fallback_quality=text_full)成功才回填 ok —— 档案卡/元数据不改变抽取态,
    #   避免占住 extract_status='none' 导致真抽取永久无法回填。前缀属实现细节, 不得作判据。
    _route = KIND_CONTRACT[("attachment", att.get("kind") or "binary")]
    if _route.fallback_quality == "text_full":
        mark_extract_result(att["id"], len(text), True)
        metric("extract_ok", "attachment", att.get("kind") or "binary")
    touch_usage(att["id"])
    # 2026-11-07 小欧 单条预算统一: text 也走 clip_text —— 未超限(len≤cap)原样返回, 故
    #   ≤read_max_bytes 的小文本仍全文注入; 超限则头尾摘录, 守住单条预算。原"text 跳过 clip"
    #   让 ≤256KB 全文直入, 默认预算下(read_max_bytes≈30k~79k字符, 见 limits)50KB 文本即超
    #   单条上限, 百 KB 文本整批被拒; 附件 budget 语义(整份不压缩)与读取期单条预算(read_max)
    #   是两道闸门, 后者必须对所有 kind 生效。
    text, omitted = clip_text(text, limits.read_max_bytes)
    return ResolvedRef(ref={**ref, "content": text, "size": att.get("size")},
                       truncated=bool(omitted),
                       note=f"已省略 {omitted} 字符" if omitted else "")


_AUDIO_NATIVE_EXTS = {".wav", ".mp3"}


def _native_modality(llm_model: Any, modality: str) -> bool:
    """模型画像是否声明该模态原生(能力判定归 capability, 本层只问结果)。"""
    if not modality:
        return False
    from app.services.agent import capability  # 延迟导入防循环
    cap = capability.profile(llm_model).get(modality)
    return bool(cap and cap.native)


def _materialize_media(ref: Dict[str, Any], path: str, content_kind: str,
                       session_id: str | None) -> Tuple[str | None, str | None, str]:
    """本地媒体物化入附件库(第7章7.4 阶段B): 复用 save_bytes 自动继承单文件/会话总量/同 sha 去重。
    返回 (attachment_id, reason, detail); 成功时 reason/detail 为 None/""。无会话/超内联上限/
    落库异常均回落文本出口, 由调用方按 reason 补一条非阻断回执, 不阻断本轮。
    session_id 即附件会话归属, 展开期 get_attachment_scoped 按同一归属收权。"""
    if not session_id:
        return None, "materialize_no_session", ""
    from app.services.agent.media_payload import inline_limit_bytes  # 延迟导入防循环
    try:
        # 根内相对路径经 browse 根解析(与读取同口径), 外部盘符路径直接用; 不可达抛错回落文本
        src = Path(path) if browse._is_abs_drive_path(path) \
            else browse._resolve_within_root(path)[0]
        if os.path.getsize(src) > inline_limit_bytes():
            return None, "materialize_too_large", ""
        raw = src.read_bytes()
        att = save_bytes(session_id, src.name, raw,
                         mime=ref.get("mime") or None, source_path=path)
        return att.get("id"), None, ""
    except Exception as e:  # noqa: BLE001 — 物化失败回落文本出口, 不阻断本轮
        logger.warning("[refs] 媒体物化失败 path=%s kind=%s err=%s", path, content_kind, e)
        return None, "materialize_failed", type(e).__name__



def _read_nontext(ref: Dict[str, Any], path: str, content_kind: str,
                  limits: RefLimits) -> ResolvedRef:
    """非文本引用按契约文本出口产出(元信息卡/抽取正文), 复用唯一抽取实现(DRY)。
    失败折算 unsupported, 该条 dropped 但不影响其余引用。同步读盘由调用方 to_thread 卸载。
    (第7章7.4 阶段B 起, image/audio 原生可达时由 _read_media 物化, 本函数只留文本出口。)"""
    route = KIND_CONTRACT[("file", content_kind)]
    att = {
        "stored_path": path,
        "path": path,
        "original_name": Path(path).name,
        "mime": ref.get("mime") or "",
        "size": int(ref.get("size") or 0),
        "kind": content_kind,
    }
    try:
        body = route.extractor(att)
    except Exception as e:  # noqa: BLE001 — 单条解析失败不阻断整批
        return ResolvedRef(ref=ref, truncated=False,
                           note=f"err:unsupported:{type(e).__name__}")
    body, omitted = clip_text(body, limits.read_max_bytes)
    return ResolvedRef(ref={**ref, "content": body},
                       truncated=bool(omitted),
                       note=f"已省略 {omitted} 字符" if omitted else "")



async def _read_one(ref: Dict[str, Any], limits: RefLimits,
                    session_id: str | None, llm_model: Any = None) -> ResolvedRef:
    """按标识读单条正文。同步读盘经 asyncio.to_thread 卸载出事件循环(仓库既有范式)。

    读法矩阵:
      附件(kind=attachment)       → _read_attachment(to_thread 卸载 DB 查表, 按 id 查表不落文件读分支)
      根内 + 无 lineRange + 字符数≤上限 → read_text_file(整份直读)
      根内 + 无 lineRange + 超上限     → 头尾摘录(全扫一次取 total_lines,
                                         头 REF_HEAD_RATIO 段 + 尾 REF_TAIL_RATIO 段, 各分块)
      根内 + 有 lineRange              → _read_blocks 分块读区间(≤5000 行/块)
      外部 + 无/有 lineRange           → read_external_file(同上口径)
      无 path                          → dropped(no_path)
    """
    if ref.get("kind") == "url":
        # 扩展点 0: 链接文本 + 准入(url_reject_reason), 不下载不读盘(P4 下载归 remote_fetch)
        from app.services.agent.media_payload import url_reject_reason  # 延迟导入: 仅 url 引用需要
        url = str(ref.get("url") or "")
        reason = url_reject_reason(url)
        if reason:
            return ResolvedRef(ref=ref, truncated=False,
                               note=f"err:url_rejected:{reason}")
        return ResolvedRef(ref={**ref, "content": extract.link_body(url)},
                           truncated=False, note="")
    if ref.get("kind") == "attachment":
        # 2026-11-06 小欧: DB 查表(get_attachment)为同步阻塞 IO, 须 to_thread 卸载出事件循环,
        #   否则违背本文件"同步读盘经 asyncio.to_thread 卸载(仓库既有范式)"纪律 — 小欧-2026-11-06
        return await asyncio.to_thread(_read_attachment, ref, limits, session_id)
    path = (ref.get("path") or "").strip()
    if not path:
        return ResolvedRef(ref=ref, truncated=False, note="no_path")
    # 媒体/富文档引用先按契约文本出口产卡, 不再落入 read_text_file 的 415 门;
    #   binary/unknown 不在此拦截(保留既有文本读取语义, 避免未知后缀文本被误判为二进制卡)。
    _ck = extract.classify(Path(path), str(ref.get("mime") or ""), int(ref.get("size") or 0))
    if _ck in ("image", "video", "audio", "richdoc"):
        # 7.4.2: selection 语义是文本行区间, 非文本 selection 无生产入口; 显式拒绝并回执,
        #   不物化、不产元信息卡, 防止异常构造的跨类型引用被当成可投递媒体。
        if ref.get("kind") == "selection":
            return ResolvedRef(ref=ref, truncated=False,
                               note="err:selection_not_text:NonTextSelection")
        # 第7章7.4 阶段B: 本地 image/audio 且模型声明原生、大小在上限内、音频容器为 wav/mp3 时,
        #   物化入附件库并补 attachment_id, 由计划器判 native 走原生槽; 其余回落契约文本出口。
        if (_ck in ("image", "audio")
                and _native_modality(llm_model, KIND_CONTRACT[("file", _ck)].native_modality)
                and (_ck != "audio" or Path(path).suffix.lower() in _AUDIO_NATIVE_EXTS)):
            _aid, _mreason, _mdetail = await asyncio.to_thread(
                _materialize_media, ref, path, _ck, session_id)
            if _aid:
                return ResolvedRef(ref={**ref, "attachment_id": _aid, "content": ""},
                                   truncated=False, note="")
            _rr = await asyncio.to_thread(_read_nontext, ref, path, _ck, limits)
            # 文本出口成功才补物化失败回执; 文本出口自身失败已入 dropped, 不再叠一条噪声
            if _mreason and not _rr.note.startswith("err:"):
                _rr.notices = [{
                    "label": ref.get("label") or path,
                    "path": path,
                    "reason": _mreason,
                    "detail": _mdetail,
                }]
            return _rr
        return await asyncio.to_thread(_read_nontext, ref, path, _ck, limits)
    lr = ref.get("lineRange") or {}
    offset = lr.get("start")
    limit = (lr.get("end", lr.get("start")) - lr.get("start") + 1) if lr.get("start") else None
    is_ext = browse._is_abs_drive_path(path)
    try:
        if offset is not None:
            # 有区间: 分块读, 不触发行数全扫(count_total=False)
            content, clipped = await _read_blocks(path, is_ext, int(offset), int(limit or 1))
            if not content:
                # 区间完全越界(起点在文件尾之后): dropped(range_out), 不静默放行空块
                return ResolvedRef(ref=ref, truncated=False, note="err:range_out:_read_blocks")
            # 2026-10-29 小欧 - range_clipped 回执: 请求区间超出文件尾时如实告知,
            #   不再静默; 未越尾则 note 空 → resolve_refs 走放行分支。
            #   2026-10-30 小欧: 删 `"size": ref.get("size")` —— 与 {**ref} 重复, 空操作。
            #   2026-10-30 小欧: 区间分支原样返回, 完全绕过单条上限 —— 一条长区间
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
            # 超单条上限 → 头尾摘录: 全扫一次取 total_lines(仅此一次), 头/尾各分块读
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
        # 2026-10-30 小欧: 行数门槛之后再按实际字符复核。行少但单行极长(160KB/800 行)
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
        # 2026-10-30 小欧: browse 的唯一抛错出口是 fail()(HTTPException, detail={code,message})。
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
    except Exception as e:  # noqa: BLE001 — fail() 抛业务错误, 一律归类回执
        return _fail(ref, "missing", e)


async def resolve_refs(
    refs: List[Dict[str, Any]],
    *,
    limits: RefLimits,
    session_id: str | None = None,
    llm_model: Any = None,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, str]], List[Dict[str, str]]]:
    """并发读全部引用(信号量限流 + 超时), 返回 (resolved, dropped, notices)。

    resolved 元素 = 原始 ref + content/size(供 render 消费);
    dropped 元素 = {label, path, reason, detail}(供回执点名; reason 见 _fail 分类映射);
    notices 元素 = {label, path, reason, detail}(非阻断提示); 条目 level 由
    notice.build_notice 统一查 REASON_LEVELS 补齐(单一裁决点, resolver/budget 不碰 level)。
    session_id: 会话归属(附件注入按此校验; None 时附件一律折算 missing, fail-closed)。
    llm_model: 目标模型身份快照(第7章7.4 阶段B: 本地 image/audio 原生可达时物化入附件库;
      缺省 None 视为无原生能力, 全部回落文本出口)。
    """
    sem = asyncio.Semaphore(REF_READ_CONCURRENCY)

    # 2026-10-30 小欧: 同 path 去重提前到**读取前**(整份优先, 同 path 的区间条目直接丢弃)。
    #   原实现在全部读完后再合并 → 整份+区间并存时区间白读一次(磁盘 IO 与超时预算都浪费)。
    refs = _merge_same_path(list(refs))

    async def _guarded(ref: Dict[str, Any]) -> ResolvedRef:
        async with sem:
            try:
                return await asyncio.wait_for(
                    _read_one(ref, limits, session_id, llm_model), timeout=REF_READ_TIMEOUT)
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
                "reason": _reason,          # 分类: missing/unsupported/range_out
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
        # 条目自带的非阻断回执(如物化失败), 与截断/压缩同级点名, 不影响放行
        notices.extend(rr.notices)
        # 放行条目统一在此追加(原实现 elif/else 两条分支各写一次, 同一语句两处 — 2026-10-30 小欧)
        resolved.append(rr.ref)
    # 同 path 已在读取前去重, 此处不再二次合并
    return resolved, dropped, notices


def _merge_same_path(refs: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """同 path 去重(读取前调用): 同一请求内同一文件整份只读一次; 不同区间各读一次。

    整份(lineRange 空)优先: 若已有整份, 丢弃所有该 path 的区间条目; 否则按 lineRange 保序。
    """
    by_path: Dict[str, List[Dict[str, Any]]] = {}
    order: List[str] = []
    for r in refs:
        p = r.get("path") or r.get("url") or ""
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
