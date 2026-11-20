# -*- coding: utf-8 -*-
"""生成视频工具(generate_video) — 对话中生成视频(异步任务 submit→poll), 产物公网 URL 交前端呈现。

编辑历史: 2026-11-20 小欧 新建: 经 get_current_generate_callback 调 generation 端点(工具层零越层);
  timeout 默认660秒(覆盖排队+出片), TOOL_RETRY_CONFIG max_retries=0 防重复提交扣费。
编辑历史: 2026-11-20 小欧 三堂会审命名整改: cb→generate_callback(生成回调)、use_model→effective_model(实际采用模型); 纯改名零行为变更。
编辑历史: 2026-11-20 小欧 话术审查整改: summary 强调"原样输出 markdown、勿改写 URL、勿用普通链接"; 纯话术改动零行为变更。
编辑历史: 2026-11-20 小欧 data/llm_data 分配整改: data 只留 {prompt,model,mode} 输入回显, 删与 summary 重复的 url 及空值; 失败分支补 action;
  失败原因只留 summary 不重复进 data.reason; message 按项目约定用状态词(成功/失败/完成但有警告), summary 用 {tool_zh}，{成功/失败/警告}：{结果} 统一口径 — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 三堂会审整改: ①失败归因按 settled 区分; ②错误码提常量; ③mode 回显实际生效值; ④成功 summary 冒号口径;
  ⑤duration_ms 实时计算; ⑥产物声明改用 with_artifacts 公共 helper(与全项目写工具同模式) — 小欧-2026-11-20
"""
import time
from typing import Any, Dict, List, Optional

from app.tools.context import get_current_generate_callback

# 默认生成视频模型与错误码从工具层常量引入(三堂会审归位) — 小欧-2026-11-20
from app.tools.tool_constants import (
    ERR_GENERATE_INCOMPLETE,
    ERR_GENERATE_NO_CHANNEL,
    MEDIA_DEFAULT_VIDEO_MODEL,
)
from app.tools.tool_response import build_error, build_success, build_warning, with_artifacts


async def generate_video(prompt: str, model: Optional[str] = None,
                         mode: str = "t2v", image: Optional[str] = None,
                         images: Optional[List[str]] = None,
                         first_frame: Optional[str] = None,
                         last_frame: Optional[str] = None,
                         audios: Optional[List[str]] = None,
                         videos: Optional[List[Dict[str, Any]]] = None,
                         seconds: Optional[str] = None,
                         size: Optional[str] = None,
                         aspect_ratio: Optional[str] = None,
                         seed: Optional[int] = None,
                         timeout: int = 660) -> Dict[str, Any]:
    """生成一段视频(text/keyframe/reference 全模式)。返回 {data, llm_data, other_data}。"""
    t0 = time.monotonic()
    generate_callback = get_current_generate_callback()
    if generate_callback is None:
        return build_error(
            data={"prompt": prompt},
            llm_data={
                # summary 统一口径: {tool_zh}，失败：{原因} — 小欧-2026-11-20
                "summary": "生成视频，失败：生成视频通道未就绪",
                # message 用约定状态词(失败); 具体原因归 detail
                "status": {"exec_code": "error", "message": "失败", "code": ERR_GENERATE_NO_CHANNEL, "detail": "生成视频回调未注入, 无法生成视频"},
                "duration_ms": int((time.monotonic() - t0) * 1000),
                # 失败也必须带 action, 否则 observation 首行工具名为空 — 小欧-2026-11-20
                "action": {"tool": "generate_video", "tool_zh": "生成视频"},
            },
        )
    effective_model = model or MEDIA_DEFAULT_VIDEO_MODEL
    kwargs: Dict[str, Any] = {"timeout": float(timeout), "mode": mode}
    # image(单图兼容旧 i2v)合并进 images, 与显式 images 一起送编排层公网化
    merged_images: list = list(images) if images else []
    if image and image not in merged_images:
        merged_images.insert(0, image)
    # 只透传非空可选参数, 未给的走厂商默认(探测腿/旧调用零影响)
    if merged_images:
        kwargs["images"] = merged_images
    for key, val in (("first_frame", first_frame), ("last_frame", last_frame),
                     ("audios", audios), ("videos", videos), ("seconds", seconds),
                     ("size", size), ("aspect_ratio", aspect_ratio), ("seed", seed)):
        if val is not None:
            kwargs[key] = val
    result = await generate_callback("video", effective_model, prompt, **kwargs)
    dur = int((time.monotonic() - t0) * 1000)
    if not result.get("ok"):
        # 错误归因按 settled 区分(三堂会审): 未定→可稍后重试; 确定拒绝→换模型或查配置; 不硬编码归因
        reason = str(result.get("reason", ""))[:120]
        advice = ("可稍后重试" if result.get("settled") is False
                  else "换模型或检查模型配置")
        # data 只留输入回显; 失败原因只在 llm_data.summary 出现一次
        return build_warning(
            data={"prompt": prompt, "model": effective_model},
            llm_data={
                "summary": f"生成视频，警告：{reason}, {advice}",
                "status": {"exec_code": "warning", "message": "完成但有警告", "code": ERR_GENERATE_INCOMPLETE},
                "duration_ms": dur,
                "action": {"tool": "generate_video", "tool_zh": "生成视频"},
            },
        )
    url = str(result.get("url") or "")
    artifacts = [{"name": "generated_video.mp4", "path": url, "type": "video"}] if url else []
    # 明确要求 markdown 图片语法(前端 img 组件按 .mp4 后缀渲染 <video>), 别输出普通链接; 强调原样输出防改写签名 URL — 小欧-2026-11-20
    if url:
        summary = (f"生成视频，成功：模型 {effective_model}。请在回复里原样输出这段 markdown(勿改写 URL、勿用普通链接): "
                   f"![生成的视频]({url})")
    else:
        summary = "生成视频，成功"
    # data 只留输入回显; mode 原样回显(text/keyframe/reference 或别名 t2v/i2v), 由编排层映射厂商三态 — 小欧-2026-11-20
    llm_data: Dict[str, Any] = {
        "summary": summary,
        "status": {"exec_code": "success", "message": "成功"},
        "duration_ms": dur,
        "action": {"tool": "generate_video", "tool_zh": "生成视频"},
    }
    # 复用公共 helper 挂产物清单(与全项目写工具同模式) — 小欧-2026-11-20
    return build_success(data={"prompt": prompt, "model": effective_model, "mode": kwargs["mode"]},
                         llm_data=with_artifacts(llm_data, artifacts))
