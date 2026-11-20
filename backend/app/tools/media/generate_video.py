# -*- coding: utf-8 -*-
"""生视频工具(generate_video) — 对话中生成视频(异步任务 submit→poll), 产物公网 URL 交前端呈现。

编辑历史: 2026-11-20 小欧 新建: 经 get_current_generate_callback 调 generation 端点(工具层零越层);
  timeout 默认660秒(覆盖排队+出片), TOOL_RETRY_CONFIG max_retries=0 防重复提交扣费。
"""
import time
from typing import Any, Dict, Optional

from app.tools.context import get_current_generate_callback

# 默认生视频模型从工具层常量引入(三堂会审归位) — 小欧-2026-11-20
from app.tools.tool_constants import MEDIA_DEFAULT_VIDEO_MODEL
from app.tools.tool_response import build_error, build_success, build_warning


async def generate_video(prompt: str, model: Optional[str] = None,
                         mode: str = "t2v", image: Optional[str] = None,
                         timeout: int = 660) -> Dict[str, Any]:
    """生成一段视频。返回 {data, llm_data, other_data}。"""
    t0 = time.monotonic()
    cb = get_current_generate_callback()
    if cb is None:
        return build_error(
            data={"prompt": prompt},
            llm_data={
                "summary": "生视频通道未就绪",
                "status": {"exec_code": "error", "message": "生视频回调未注入, 无法生成视频", "code": "ERR_GENERATE_NO_CHANNEL"},
                "duration_ms": 0,
            },
        )
    use_model = model or MEDIA_DEFAULT_VIDEO_MODEL
    kwargs: Dict[str, Any] = {"timeout": float(timeout)}
    if mode == "i2v" and image:
        kwargs["mode"] = "i2v"
        kwargs["images"] = [image]
    else:
        kwargs["mode"] = "t2v"
    result = await cb("video", use_model, prompt, **kwargs)
    dur = int((time.monotonic() - t0) * 1000)
    if not result.get("ok"):
        return build_warning(
            data={"prompt": prompt, "model": use_model, "reason": result.get("reason", "")},
            llm_data={
                "summary": f"生视频未完成: {result.get('reason', '')[:120]}",
                "status": {"exec_code": "warning", "message": "生视频未完成(队列拥堵/环境原因), 可稍后重试", "code": "ERR_GENERATE_INCOMPLETE"},
                "duration_ms": dur,
            },
        )
    url = str(result.get("url") or "")
    artifacts = [{"name": "generated_video.mp4", "path": url, "type": "video"}] if url else []
    return build_success(
        data={"prompt": prompt, "model": use_model, "url": url, "mode": mode},
        llm_data={
            # 明确要求 markdown 图片语法(前端 img 组件按 .mp4 后缀渲染 <video>), 别输出普通链接 — 小欧-2026-11-20
            "summary": f"视频已生成(模型 {use_model})。请在回复里用 markdown 展示视频: ![生成的视频]({url})" if url else "视频已生成",
            "status": {"exec_code": "success", "message": "视频生成成功"},
            "duration_ms": dur,
            "action": {"tool": "generate_video", "tool_zh": "生视频", "artifacts": artifacts},
        },
    )
