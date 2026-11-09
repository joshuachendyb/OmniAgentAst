# -*- coding: utf-8 -*-
"""生图/生视频端点调用单点（generation 通道唯一 HTTP 出口）。

探测腿（settings2 生成验证 probe-output）与未来真业务（会话生图工具等）
共用本函数；生成端点禁直连 httpx。视频是异步任务：提交 → 轮询 → 取产物
- 小欧-2026-11-09
"""
import asyncio
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

# OpenAI Images 兼容协议常量（厂家漂移时改 provider adapter generation_paths() 钩子）
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
# 视频腿: 异步任务(提交→轮询), mode 必填且是生成方式枚举。真机枚举实证合法值仅 {text, reference}:
#   text=纯文本生视频(带素材字段直接 400), reference=带参考图生视频(素材走 images, 传 first_frame/image 被 400 拒)
PROBE_VIDEO_PROMPT = "一个红色圆点在白色背景上缓慢移动"
PROBE_VIDEO_I2V_PROMPT = "让画面缓慢推近"
VIDEO_MODE_T2V = "text"
VIDEO_MODE_I2V = "reference"
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


def _source_unreachable(text: str) -> bool:
    """厂商抓不到探测素材的报错(图/视频两条腿同一判定): 属素材不可达, 不判模型能力 - 小欧-2026-11-09

    真机样例: images 腿 "media URL could not be downloaded"; videos 腿中文"下载失败"。
    """
    return "could not be downloaded" in text or "下载" in text


async def generate_image(
    api_base: str,
    headers: Dict[str, str],
    model: str,
    prompt: str,
    *,
    image: Optional[str] = None,
    timeout: float = 120.0,
) -> Tuple[bool, str, bool]:
    """生成一张图 → (产物成功?, evidence, 是否确定结论)。

    settled 口径与 model_service._probe_once 对齐：200 且产物 url/b64 非空
    = 确定 OK；400/415/422 = 确定拒绝；401/403/429/5xx/网络错 = 未定，
    调用方不得写结论。image 传 URL 时走图生图（i2i），与 t2i 同端点同函数
    - 小欧-2026-11-09
    """
    body: Dict[str, Any] = {"model": model, "prompt": prompt}
    if image:
        body["image"] = image
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                f"{api_base.rstrip('/')}{IMAGE_PATH}", headers=headers, json=body
            )
    except Exception as e:
        return False, f"network_error: {type(e).__name__}: {e}"[:_EV_LIMIT], False
    if resp.status_code != 200:
        text = resp.text
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
        return False, "bad_json", False
    rec = (
        data.get("data")[0]
        if isinstance(data, dict)
        and isinstance(data.get("data"), list)
        and data.get("data")
        else {}
    )
    url = str(rec.get("url") or "")
    b64 = str(rec.get("b64_json") or "")
    if url:
        return True, f"url={url}"[:_EV_LIMIT], True
    if b64:
        return True, f"b64_len={len(b64)}", True
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


def _video_url(data: Any) -> str:
    """递归找产物地址: 先认键名含 video 的 http 串, 再退任意 .mp4 直链。

    视频任务响应常同时带封面图/尾帧图, 只按 "url" 取值会拿错, 故按键名优先级收敛
    - 小欧-2026-11-09
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
            return raw
    for _, low, raw in found:
        if ".mp4" in low:
            return raw
    return ""


async def generate_video(
    api_base: str,
    headers: Dict[str, str],
    model: str,
    prompt: str,
    mode: str,
    *,
    images: Optional[List[str]] = None,
    timeout: float = 120.0,
    poll_timeout: float = VIDEO_POLL_TIMEOUT,
) -> Tuple[bool, str, bool]:
    """生成一段视频（提交+轮询）→ (产物成功?, evidence, 是否确定结论)。

    settled 口径与 generate_image 对齐：任务终态且有视频地址 = 确定 OK；
    400/415/422 或任务 failed = 确定拒绝；401/429/5xx/队列已满/轮询超时/网络错
    = 未定（厂商侧环境或排队问题，不得据此判模型无生视频能力）
    - 小欧-2026-11-09
    """
    body: Dict[str, Any] = {"model": model, "prompt": prompt, "mode": mode}
    if images:
        body["images"] = images
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
            # 图源不可达 / 队列已满 / mode 校验: 都属探测环境或协议漂移, 不判模型能力 - 小欧-2026-11-09
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
            return False, "bad_json", False
        task_id = ""
        if isinstance(data, dict):
            for key in ("task_id", "id", "video_id"):
                val = data.get(key)
                if isinstance(val, str) and val:
                    task_id = val
                    break
        if not task_id:
            return False, f"no_task_id: {resp.text}"[:_EV_LIMIT], False
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
                return False, f"poll_http_{poll.status_code}: {poll.text}"[:_EV_LIMIT], False
            try:
                detail = poll.json()
            except Exception:
                return False, "bad_json", False
            status = _video_status(detail) or "unknown"
            if status in VIDEO_DONE:
                url = _video_url(detail)
                if url:
                    return True, f"url={url}"[:_EV_LIMIT], True
                # 终态却取不到视频地址: 多半是响应结构变化, 不能据此判"无生成能力"
                return False, f"no_output_field: {poll.text}"[:_EV_LIMIT], False
            if status in VIDEO_FAILED:
                # 任务失败多为厂商侧资源/素材抓取问题, 不据此判"模型无生视频能力"; 原因串原文留证 - 小欧-2026-11-09
                reason = _video_reason(detail)
                prefix = "source_unreachable" if _source_unreachable(reason) else "task_failed"
                return False, f"{prefix}: {status} {reason}".strip()[:_EV_LIMIT], False
        return False, f"poll_timeout: {status or 'unknown'}"[:_EV_LIMIT], False
