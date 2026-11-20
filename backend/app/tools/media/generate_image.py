# -*- coding: utf-8 -*-
"""生图工具(generate_image) — 对话中生成图片, 产物公网 URL 交给 LLM 回复呈现。

编辑历史: 2026-11-20 小欧 新建: 经 get_current_generate_callback 调 generation 端点(工具层零越层),
  产物 URL 写进 data/llm_data, LLM 据此在回复里输出 ![](url) 由前端 MarkdownText 渲染; 产物声明 artifacts。
"""
import time
from typing import Any, Dict, Optional

from app.tools.context import get_current_generate_callback
from app.tools.tool_response import build_error, build_success, build_warning

# 默认生图模型(回调侧会校验是否在配置中)
_DEFAULT_MODEL = "agnes-image-2.1-flash"


async def generate_image(prompt: str, model: Optional[str] = None,
                         image: Optional[str] = None) -> Dict[str, Any]:
    """生成一张图片。返回 {data, llm_data, other_data}。"""
    t0 = time.monotonic()
    cb = get_current_generate_callback()
    if cb is None:
        return build_error(
            data={"prompt": prompt},
            llm_data={
                "summary": "生图通道未就绪",
                "status": {"exec_code": "error", "message": "生图回调未注入, 无法生成图片", "code": "ERR_GENERATE_NO_CHANNEL"},
                "duration_ms": int((time.monotonic() - t0) * 1000),
            },
        )
    use_model = model or _DEFAULT_MODEL
    result = await cb("image", use_model, prompt, image=image)
    dur = int((time.monotonic() - t0) * 1000)
    if not result.get("ok"):
        return build_warning(
            data={"prompt": prompt, "model": use_model, "reason": result.get("reason", "")},
            llm_data={
                "summary": f"生图未完成: {result.get('reason', '')[:120]}",
                "status": {"exec_code": "warning", "message": "生图未完成(队列/环境原因), 可稍后重试或换模型", "code": "ERR_GENERATE_INCOMPLETE"},
                "duration_ms": dur,
            },
        )
    url = str(result.get("url") or "")
    b64 = str(result.get("b64") or "")
    # 产物 markdown: 有公网 URL 直接引用; 只有 b64 则内联 data URI
    md_url = url or (f"data:image/png;base64,{b64}" if b64 else "")
    artifacts = [{"name": "generated_image.png", "path": url or "inline://b64", "type": "image"}] if md_url else []
    return build_success(
        data={"prompt": prompt, "model": use_model, "url": url, "markdown": f"![生成的图片]({md_url})" if md_url else ""},
        llm_data={
            "summary": f"图片已生成(模型 {use_model})。请在回复中用 markdown 展示图片: ![生成的图片]({md_url})" if md_url else "图片已生成",
            "status": {"exec_code": "success", "message": "图片生成成功"},
            "duration_ms": dur,
            "action": {"tool": "generate_image", "tool_zh": "生图", "artifacts": artifacts},
        },
    )
