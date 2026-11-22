# -*- coding: utf-8 -*-
"""生图/生视频通用生成引擎（generation 通道唯一 HTTP 出口 = general 入口）。

【新厂商接入契约】
  generate_image / generate_video 是协议无关的通用引擎, 默认走通用方言。
  新厂商协议通用 → 零定制: 只需在 config 登记 model, 直接调本模块函数。
  厂商有差异 → 只加一个 provider adapter 覆写对应钩子, 本引擎零改动(OCP):
    · 请求方言: prepare_image_body / prepare_video_body(size 档位/字段名/输出格式位置)
    · 响应方言: parse_image_result / parse_video_status / parse_video_reason / parse_video_url(产物/状态提取)
  覆写钩子返回 None 即回退引擎通用启发式, 故新厂商只覆写有差异的钩子。
  现有范例: agnes(生图档位+ratio)、sensenova(生图 WIDTHxHEIGHT), 均只改 adapter。

【通用能力边界(诚实说明)】
  生图 = 同步单请求(POST 直接返产物); 生视频 = 异步任务(提交→轮询)。
  若某厂商生图也走异步(如通义万相), 需扩展引擎的任务分支, 非仅覆写钩子可涵盖 —
  当前未接入此类厂商, 不预先抽象(YAGNI); 接入时再加通用 submit/poll 分支。
  探测腿(model_service)与业务腿(media_generate)共用本引擎; 生成端点禁直连 httpx。

2026-11-09 订正: 素材不可达判定收窄为短语集常量(原含"下载"二字即归此类过宽); _video_url 取证串标注勿回放 - 小欧-2026-11-09
2026-11-20 小欧 产物出参: generate_image/generate_video 加可选 out 字典, 成功时写入未截断原始产物(url/b64/mp4), 探测腿不传则三元组不变(OCP); _video_url 加 preserve_case 供业务下载签名 URL
2026-11-20 小欧 按厂商文档补全视频全能力: generate_video 支持 mode(text/keyframe/reference)及 first_frame/last_frame/images/
  audios/videos/seconds/size/aspect_ratio/seed, 全部可选(OCP, 探测腿与旧调用零影响); 加 VIDEO_MODES/SIZES/ASPECT_RATIOS 白名单常量 — 小欧-2026-11-20
2026-11-20 小欧 按厂商文档补全生图全能力: generate_image 加 size/ratio/多图 images 及 provider 方言翻译
  (agnes 档位+ratio / sensenova 档位换算 WIDTHxHEIGHT, 实测两家参数协议不同); image 归一为数组(sensenova 只认数组);
  全部可选(OCP); 加 IMAGE_SIZES/RATIOS/档位像素表常量 — 小欧-2026-11-20
2026-11-21 小欧 订正 generate_video docstring 的 settled 口径: 原写「任务 failed = 确定拒绝」与实现不符,
  实为 settled=False(厂商侧资源/素材问题, 不判模型无能); 与 FUNCTIONS.md §10.4 对齐 — 小欧-2026-11-21
2026-11-22 小欧 生图端点按适配器选: generate_image 改用 adapter.image_endpoint(has_refs) 代替固定 IMAGE_PATH,
  默认仍 generations(探测腿/文生图/其他厂商零影响), sensenova 有参考图切 /images/edits — 小欧-2026-11-22
"""
import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.llm.adapters.base import ProviderAdapter

# 通用默认生图端点: 实际端点由 adapter.image_endpoint(has_refs) 按厂商+有无参考图选定,
#   默认(基类/探测腿/文生图)=本值, sensenova 有参考图走 /images/edits; 常量保留供文档登记 — 小欧-2026-11-22
IMAGE_PATH = "/images/generations"
VIDEO_PATH = "/videos"

# 厂商明确拒绝的状态: 只有这三个算"确定不收", 其余错误码是环境问题。
# 单源常量: 输入腿(_probe_once)也从这里取, 两腿判定口径物理同源 - 小欧-2026-11-09
REJECT_STATUS = frozenset({400, 415, 422})

# 生成验证探测 prompt（真机实证：一次一图、语句极短、确定性图形，成本最低）
PROBE_PROMPT = "一个红色圆点，白色背景"
# 生成腿探测图源（i2i 图片输入 / i2v 参考图）: 厂商侧须能直连 GET 的公网位图,
#   禁 ico/短链/鉴权地址; 实测厂商抓图 200（央视CDN同类被拒 source_unreachable）— 小欧-2026-11-09
PROBE_IMAGE_URL = "https://www.people.com.cn/img/2020peopleindex/img/2024tp/rmwj.jpg"
# 图生图探测 prompt（对任意图源通用: 只改主色调, 不假设图内容）
PROBE_I2I_PROMPT = "把图片主色调改为蓝色"
# 视频腿: 异步任务(提交→轮询), mode 必填且是生成方式枚举, 厂商文档合法值 {text, keyframe, reference}:
#   text=纯文本; keyframe=首/尾帧(first_frame/last_frame); reference=图/音/视频参考(images/audios/videos)
PROBE_VIDEO_PROMPT = "一个红色圆点在白色背景上缓慢移动"
PROBE_VIDEO_I2V_PROMPT = "让画面缓慢推近"
# 视频生成的三种模式(厂商文档 agnes-video-2.5/flash): text=纯文本, keyframe=首/尾帧, reference=图/音/视频参考
VIDEO_MODE_T2V = "text"       # 纯文本生视频(保留别名兼容既有 t2v 工具语义)
VIDEO_MODE_I2V = "reference"  # 图片参考生视频(保留别名兼容既有 i2v 工具语义)
VIDEO_MODE_KEYFRAME = "keyframe"  # 首帧/尾帧控制(工具层经 tool_constants 引用, 见 MEDIA_VIDEO_MODE_KEYFRAME)
# 轮询节奏与上限: 单腿最多等 600s。真机实测整个任务 402s(排队≈250s 后 in_progress,
#   出片≈150s), 队列时长不可控; 超时只记未完成, 不下能力结论
VIDEO_POLL_INTERVAL = 5.0
VIDEO_POLL_TIMEOUT = 600.0
# 队列满(503 video_queue_full)是账号级拥堵: 提交重试 3 次、间隔 30s, 仍满才记未完成
VIDEO_QUEUE_RETRIES = 3
VIDEO_QUEUE_GAP = 30.0
VIDEO_DONE = frozenset({"completed", "succeeded", "success"})
VIDEO_FAILED = frozenset({"failed", "error"})

# evidence 只作人读取证: 成功腿的 COS 地址带签名可达数百字符, 一律截短 - 小欧-2026-11-09
_EV_LIMIT = 160

# 厂商抓不到探测素材的报错短语集(图/视频两腿同一判定): 原来含"下载"二字即归此类过宽,
#   厂商任何文案提到"下载"(如违规提示)都会被误判成素材不可达, 收窄为实测短语 — 小欧-2026-11-09
_SOURCE_UNREACHABLE_MARKS = (
    "could not be downloaded",  # images 腿: media URL could not be downloaded
    "下载失败", "无法下载", "下载超时",  # videos 腿: 中文报错(真机样例"下载失败")
)


def _source_unreachable(text: str) -> bool:
    """厂商抓不到探测素材的报错(图/视频两条腿同一判定): 属素材不可达, 不判模型能力 - 小欧-2026-11-09

    真机样例: images 腿 "media URL could not be downloaded"; videos 腿中文"下载失败"。
    短语见 _SOURCE_UNREACHABLE_MARKS, 勿放宽回子串"下载"。
    """
    return any(m in text for m in _SOURCE_UNREACHABLE_MARKS)


# 厂商响应里"产物本体"的键: 已单独进 out(url/b64), 元数据再存一份等于把 MB 级串翻倍
_META_DROP_KEYS = frozenset({"b64_json", "url", "image_url", "video_url", "image", "mask"})
# 键名含 b64/base64 的字符串一律当产物本体剔: 厂商自造键名(b64、base64、image_base64…)同样不能落库
_META_DROP_KEY_PARTS = ("b64", "base64")
# 单值护栏: 其余未知键承载 base64 时不把 MB 级串带进 other_data 落库
_META_STR_MAX = 8192
_META_EMPTY = object()


def _prune_meta(node: Any) -> Any:
    """递归剔产物本体、空容器与超长串; 返回 _META_EMPTY 表示该分支整体丢弃 — 小欧-2026-11-21

    产物本体只按"键名命中且值为字符串"剔: 厂商把 image/mask 用作结构化元数据时照常保留(其内部 url 再被剔)。
    """
    if isinstance(node, dict):
        kept = {}
        for k, v in node.items():
            name = str(k).lower()
            if isinstance(v, str) and (
                name in _META_DROP_KEYS or any(part in name for part in _META_DROP_KEY_PARTS)
            ):
                continue
            child = _prune_meta(v)
            if child is not _META_EMPTY:
                kept[k] = child
        return kept or _META_EMPTY
    if isinstance(node, list):
        items = [c for c in (_prune_meta(v) for v in node) if c is not _META_EMPTY]
        return items or _META_EMPTY
    if isinstance(node, str) and len(node) > _META_STR_MAX:
        return _META_EMPTY
    return node


def _put_meta(out: Optional[Dict[str, Any]], data: Any) -> None:
    """厂商响应原文 → out["meta"]: 只剔产物本体与空壳, 其余字段原样留给工具落 other_data — 小欧-2026-11-21

    meta 承载 created/task_id/revised_prompt/usage/size/quality/seconds/progress/时间戳/失败原因,
    由调用方决定进 summary/llm_data/other_data; 多次调用累积合并(后者覆盖同名键), 提交阶段拿到的
    task_id 不因后续轮询响应缺项而丢; 探测腿不传 out 时零影响。
    """
    if out is None:
        return
    meta = _prune_meta(data) if isinstance(data, dict) else _META_EMPTY
    merged = out.get("meta") if isinstance(out.get("meta"), dict) else {}
    if isinstance(meta, dict):
        merged.update(meta)
    out["meta"] = merged


def _resp_meta(resp: httpx.Response) -> Dict[str, Any]:
    """非 200 响应 → meta: JSON 体原样, 解析不出则 {status_code, body(截断)} — 小欧-2026-11-21

    失败态的 code/message/request id 是排查最有用的一手信息, 不能只留 160 字 evidence。
    """
    try:
        data = resp.json()
        if isinstance(data, dict):
            return data
    except Exception:  # noqa: BLE001 — 非 JSON 错误页(网关/反代)走 body 兜底
        pass
    return {"status_code": resp.status_code, "body": resp.text[:2000]}


async def generate_image(
    api_base: str,
    headers: Dict[str, str],
    model: str,
    prompt: str,
    *,
    image: Optional[str] = None,
    size: Optional[str] = None,
    ratio: Optional[str] = None,
    images: Optional[List[str]] = None,
    return_base64: bool = False,
    response_format: Optional[str] = None,
    adapter: Optional[ProviderAdapter] = None,
    timeout: float = 120.0,
    out: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, bool]:
    """生成一张图 → (产物成功?, evidence, 是否确定结论)。

    settled 口径与 model_service._probe_once 对齐：200 且产物 url/b64 非空
    = 确定 OK；400/415/422 = 确定拒绝；401/403/429/5xx/网络错 = 未定，
    调用方不得写结论。image 传 URL 时走图生图（i2i），与 t2i 同端点同函数
    - 小欧-2026-11-09
    size/ratio/images(多图合成)/return_base64/response_format 经 provider adapter 的 prepare_image_body 钩子
      做方言翻译(默认 agnes 档位+ratio, sensenova 覆写为 WIDTHxHEIGHT), generation_client 协议无关(OCP);
      端点经 adapter.image_endpoint(has_refs) 按厂商+有无参考图选定(默认 generations, sensenova 有参考图走 /images/edits);
      全可选不传则请求体只含既有字段; 探测腿不传 adapter 走默认(agnes 风格) — 小欧-2026-11-20 / 2026-11-22
    out: 可选产物出口(对话生图工具)——成功时写入未截断的原始 url/b64_json 及 meta(厂商其余字段);
      探测腿不传则三元组行为不变(OCP) — 小欧-2026-11-20
    """
    body: Dict[str, Any] = {"model": model, "prompt": prompt}
    # 参考图: 单图(image)与多图(images)保序合并为数组(厂商普遍接受数组, sensenova 只认数组)
    refs = list(images) if images else []
    if image and image not in refs:
        refs.insert(0, image)
    # 方言翻译下沉到 provider adapter(基类通用, agnes/sensenova 覆写请求与响应钩子);
    #   gen_adapter 全函数复用(端点方言 + 请求方言 + 响应方言), generation_client 无 provider 硬编码(OCP) — 小欧-2026-11-20
    gen_adapter = adapter or ProviderAdapter()
    gen_adapter.prepare_image_body(body, size=size, ratio=ratio, image_refs=refs or None,
                                   return_base64=return_base64, response_format=response_format)
    # 端点方言: 按适配器 + 有无参考图选端点(基类恒 generations; sensenova 有参考图走 /images/edits);
    #   探测腿不传 adapter=基类无参考图 → generations, 行为不变 — 小欧-2026-11-22
    endpoint = gen_adapter.image_endpoint(has_refs=bool(refs))
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{api_base.rstrip('/')}{endpoint}", headers=headers, json=body
            )
    except Exception as e:
        return False, f"network_error: {type(e).__name__}: {e}"[:_EV_LIMIT], False
    if resp.status_code != 200:
        text = resp.text
        _put_meta(out, _resp_meta(resp))  # 失败响应体同样落档: 错误码/request id 是排查一手信息
        # 厂商抓不到图源: 属探测素材不可达, 不判模型能力 — 小欧-2026-11-09
        if image and _source_unreachable(text):
            return False, f"source_unreachable: {text}"[:_EV_LIMIT], False
        return (
            False,
            f"http_{resp.status_code}: {text}"[:_EV_LIMIT],
            resp.status_code in REJECT_STATUS,
        )
    try:
        data = resp.json()
    except Exception:
        _put_meta(out, _resp_meta(resp))
        return False, "bad_json", False
    # 响应方言: 厂商覆写 parse_image_result 优先; 否则用通用 data[0].url/b64_json(OCP)
    parsed = gen_adapter.parse_image_result(data) if isinstance(data, dict) else None
    if parsed is not None:
        url, b64 = str(parsed[0] or ""), str(parsed[1] or "")
    else:
        rec = (
            data.get("data")[0]
            if isinstance(data, dict)
            and isinstance(data.get("data"), list)
            and data.get("data")
            else {}
        )
        url = str(rec.get("url") or "")
        b64 = str(rec.get("b64_json") or "")
    if url or b64:
        # 产物原始值写入 out(未截断), 供对话生图工具下载/展示; 探测腿不传 out 零影响 — 小欧-2026-11-20
        if out is not None:
            out.update(url=url, b64=b64)
            _put_meta(out, data)
        if url:
            return True, f"url={url}"[:_EV_LIMIT], True
        return True, f"b64_len={len(b64)}", True
    _put_meta(out, data)
    return False, "no_output", True


def _video_status(data: Any) -> str:
    """任务状态串: 厂商可能平铺(status)或包了一层(data.status) - 小欧-2026-11-09"""
    if isinstance(data, dict):
        for key in ("status", "state", "task_status"):
            val = data.get(key)
            if isinstance(val, str) and val:
                return val.lower()
        inner = data.get("data")
        if inner is not None:
            return _video_status(inner)
    return ""


def _video_reason(data: Any) -> str:
    """任务失败原因串: 厂商字段名不统一(error/message/fail_reason/data.*), 取首个非空文本 - 小欧-2026-11-09"""
    if isinstance(data, dict):
        for key in ("error", "message", "fail_reason", "failure_reason", "reason", "error_message"):
            val = data.get(key)
            if isinstance(val, str) and val:
                return val
            if isinstance(val, dict):
                inner = val.get("message") or val.get("msg") or val.get("code")
                if isinstance(inner, str) and inner:
                    return inner
        inner = data.get("data")
        if inner is not None:
            return _video_reason(inner)
    return ""


def _video_url(data: Any, preserve_case: bool = False) -> str:
    """递归找产物地址: 先认键名含 video 的 http 串, 再退任意 .mp4 直链。

    视频任务响应常同时带封面图/尾帧图, 只按 "url" 取值会拿错, 故按键名优先级收敛。
    默认返回 lower 串仅供人读取证(签名参数大小写敏感, 严禁回放);
    preserve_case=True 返回原始大小写串, 供对话生视频工具下载产物 — 小欧-2026-11-20
    """
    found: List[Tuple[str, str, str]] = []

    def _walk(node: Any, key: str) -> None:
        if isinstance(node, dict):
            for k, v in node.items():
                _walk(v, str(k))
        elif isinstance(node, list):
            for v in node:
                _walk(v, key)
        elif isinstance(node, str) and node.startswith("http"):
            found.append((key.lower(), node.lower(), node))

    _walk(data, "")
    for key, low, raw in found:
        if "video" in key and (".mp4" in low or "video" in low):
            return raw if preserve_case else low
    for _, low, raw in found:
        if ".mp4" in low:
            return raw if preserve_case else low
    return ""


async def generate_video(
    api_base: str,
    headers: Dict[str, str],
    model: str,
    prompt: str,
    mode: str,
    *,
    images: Optional[List[str]] = None,
    first_frame: Optional[str] = None,
    last_frame: Optional[str] = None,
    audios: Optional[List[str]] = None,
    videos: Optional[List[Dict[str, Any]]] = None,
    seconds: Optional[str] = None,
    size: Optional[str] = None,
    aspect_ratio: Optional[str] = None,
    seed: Optional[int] = None,
    adapter: Optional[ProviderAdapter] = None,
    timeout: float = 120.0,
    poll_timeout: float = VIDEO_POLL_TIMEOUT,
    out: Optional[Dict[str, Any]] = None,
) -> Tuple[bool, str, bool]:
    """生成一段视频（提交+轮询）→ (产物成功?, evidence, 是否确定结论)。

    settled 口径与 generate_image 对齐：任务终态且有视频地址 = 确定 OK；400/415/422 = 确定拒绝。
    任务 failed 记未定——多为厂商侧资源/素材抓取问题, 不据此判模型无生视频能力; 401/429/5xx/
    队列已满/轮询超时/网络错/终态无地址/协议漂移同为未定 - 小欧-2026-11-09
    模式(text/keyframe/reference)与媒体/通用参数按厂商文档 agnes-video-2.5/flash 全量支持,
      所有新参数可选、不传则请求体只含既有字段(探测腿与旧调用零影响, OCP) — 小欧-2026-11-20
    out: 可选产物出口(对话生视频工具)——成功时写入未截断的原始 mp4 url 及 meta(厂商其余字段);
      探测腿不传则三元组行为不变(OCP) — 小欧-2026-11-20
    """
    body: Dict[str, Any] = {"model": model, "prompt": prompt, "mode": mode}
    # 方言翻译下沉到 provider adapter(视频字段各家当前一致, 默认 agnes 风格直传;
    #   新厂商有差异时只覆写 prepare_video_body, generation_client 零改动 — OCP) — 小欧-2026-11-20
    gen_adapter = adapter or ProviderAdapter()
    gen_adapter.prepare_video_body(body, first_frame=first_frame, last_frame=last_frame,
                                   images=images, audios=audios, videos=videos,
                                   seconds=seconds, size=size, aspect_ratio=aspect_ratio, seed=seed)
    base = api_base.rstrip("/")
    async with httpx.AsyncClient(timeout=timeout) as client:
        resp = None
        for attempt in range(VIDEO_QUEUE_RETRIES):
            try:
                resp = await client.post(f"{base}{VIDEO_PATH}", headers=headers, json=body)
            except Exception as e:
                return False, f"network_error: {type(e).__name__}: {e}"[:_EV_LIMIT], False
            if "video_queue_full" not in resp.text or attempt == VIDEO_QUEUE_RETRIES - 1:
                break
            await asyncio.sleep(VIDEO_QUEUE_GAP)
        if resp.status_code != 200:
            text = resp.text
            _put_meta(out, _resp_meta(resp))  # 失败响应体同样落档: 错误码/request id 是排查一手信息
            # 图源不可达 / 队列已满 / mode 校验: 都属探测环境或协议漂移, 不判模型能力 — 小欧-2026-11-09
            if images and _source_unreachable(text):
                return False, f"source_unreachable: {text}"[:_EV_LIMIT], False
            if "video_queue_full" in text:
                return False, f"queue_full: {text}"[:_EV_LIMIT], False
            if ("mode" in text and ("无效" in text or "不能为空" in text)) or "不能包含" in text:
                return False, f"protocol_drift: {text}"[:_EV_LIMIT], False
            return (
                False,
                f"http_{resp.status_code}: {text}"[:_EV_LIMIT],
                resp.status_code in REJECT_STATUS,
            )
        try:
            data = resp.json()
        except Exception:
            _put_meta(out, _resp_meta(resp))
            return False, "bad_json", False
        task_id = ""
        if isinstance(data, dict):
            for key in ("task_id", "id", "video_id"):
                val = data.get(key)
                if isinstance(val, str) and val:
                    task_id = val
                    break
        if not task_id:
            _put_meta(out, data)
            return False, f"no_task_id: {resp.text}"[:_EV_LIMIT], False
        # 提交即落档 task_id/created_at: 轮询超时或轮询失败时仍能追到任务, 不因后续未完成而丢
        _put_meta(out, data)
        deadline = time.monotonic() + poll_timeout
        status = ""
        while time.monotonic() < deadline:
            await asyncio.sleep(VIDEO_POLL_INTERVAL)
            try:
                poll = await client.get(f"{base}{VIDEO_PATH}/{task_id}", headers=headers)
            except Exception as e:
                return False, f"network_error: {type(e).__name__}: {e}"[:_EV_LIMIT], False
            if poll.status_code != 200:
                # 轮询失败(task_not_exist/鉴权/限流)不构成"模型不能生成"的证据 → 一律未定
                _put_meta(out, _resp_meta(poll))
                return False, f"poll_http_{poll.status_code}: {poll.text}"[:_EV_LIMIT], False
            try:
                detail = poll.json()
            except Exception:
                _put_meta(out, _resp_meta(poll))
                return False, "bad_json", False
            # 响应方言: 厂商覆写钩子优先, 否则用通用启发式(_video_* 递归) — OCP
            status = (gen_adapter.parse_video_status(detail) or _video_status(detail)) or "unknown"
            if status in VIDEO_DONE:
                # 一次递归取原始大小写 URL: evidence 用其 lower 取证(与 _video_url 默认口径等价), out 用原串下载;
                #   避免同一 detail 两次全量遍历(DRY)
                raw_url = gen_adapter.parse_video_url(detail, preserve_case=True) or _video_url(detail, preserve_case=True)
                evidence_url = raw_url.lower()
                if evidence_url:
                    # 产物原始大小写 URL 写入 out 供下载(签名参数大小写敏感); 探测腿零影响 — 小欧-2026-11-20
                    if out is not None:
                        out["url"] = raw_url
                        _put_meta(out, detail)
                    return True, f"url={evidence_url}"[:_EV_LIMIT], True
                # 终态却取不到视频地址: 多半是响应结构变化, 不能据此判"无生成能力"
                _put_meta(out, detail)
                return False, f"no_output_field: {poll.text}"[:_EV_LIMIT], False
            if status in VIDEO_FAILED:
                # 任务失败多为厂商侧资源/素材抓取问题, 不据此判"模型无生视频能力"; 原因串原文留证 — 小欧-2026-11-09
                reason = gen_adapter.parse_video_reason(detail) or _video_reason(detail)
                _put_meta(out, detail)
                prefix = "source_unreachable" if _source_unreachable(reason) else "task_failed"
                return False, f"{prefix}: {status} {reason}".strip()[:_EV_LIMIT], False
        return False, f"poll_timeout: {status or 'unknown'}"[:_EV_LIMIT], False


# 新厂商零定制接入: 直接调用本模块的 generate_image/generate_video(协议无关通用引擎),
#   有差异则传 adapter 覆写钩子 — 无需另设 general_gen_* 别名(已删, 零调用方) — 小欧 2026-11-20
