# -*- coding: utf-8 -*-
"""生图工具(generate_image) — 对话中生成图片, 产物公网 URL 交给 LLM 回复呈现。

编辑历史: 2026-11-20 小欧 新建: 经 get_current_generate_callback 调 generation 端点(工具层零越层),
  产物 URL 写进 data/llm_data, LLM 据此在回复里输出 ![](url) 由前端 MarkdownText 渲染; 产物声明 artifacts。
编辑历史: 2026-11-20 小欧 b64 产物分流: 公网URL走markdown内联; 无URL但已落盘(SenseNova b64→attachment)走 with_artifact_file 声明本地产物, 明确禁止 ![](本地路径)(会401); 不把4MB data URI 塞进回复。
"""
import os
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
    file_path = str(result.get("file_path") or "")
    attachment_id = str(result.get("attachment_id") or "")
    b64 = str(result.get("b64") or "")
    # 产物两条路: 公网 URL → markdown 内联展示; 无 URL 但 b64 已落盘(如 SenseNova) → 产物声明, 前端产物抽屉查看
    if url:
        md = f"![生成的图片]({url})"
        summary = f"图片已生成(模型 {use_model})。请在回复中用 markdown 展示: {md}"
        artifacts = [{"name": "generated_image.png", "path": url, "type": "image"}]
    elif file_path:
        md = ""
        summary = (f"图片已生成(模型 {use_model}), 已存为会话附件(attachment_id={attachment_id}), "
                   f"产物路径 {file_path}。请告知用户图片已生成并可在产物/附件中查看。"
                   "注意: 该模型产物是本地文件(非公网URL), 不要用 markdown ![](file_path) 展示(会 401)。")
        artifacts = [{"name": os.path.basename(file_path), "path": file_path, "type": "image"}]
    elif b64:
        # 落盘失败的兜底: 不把大 b64 塞进回复, 只文字说明
        md = ""
        summary = f"图片已生成(模型 {use_model})但产物落盘失败, 请重试或换模型。"
        artifacts = []
    else:
        md = ""
        summary = "图片已生成"
        artifacts = []
    return build_success(
        data={"prompt": prompt, "model": use_model, "url": url,
              "file_path": file_path, "attachment_id": attachment_id, "markdown": md},
        llm_data={
            "summary": summary,
            "status": {"exec_code": "success", "message": "图片生成成功"},
            "duration_ms": dur,
            "action": {"tool": "generate_image", "tool_zh": "生图", "artifacts": artifacts},
        },
    )
