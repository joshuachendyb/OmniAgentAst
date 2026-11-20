# -*- coding: utf-8 -*-
"""生成视频工具(generate_video) — 对话中生成视频(异步任务 submit→poll), 产物公网 URL 交前端呈现。

编辑历史: 2026-11-20 小欧 新建: 经 get_current_generate_callback 调 generation 端点(工具层零越层);
  timeout 默认660秒(覆盖排队+出片), TOOL_RETRY_CONFIG max_retries=0 防重复提交扣费。
编辑历史: 2026-11-20 小欧 话术审查整改: summary 强调"原样输出 markdown、勿改写 URL、勿用普通链接"; 纯话术改动零行为变更。
编辑历史: 2026-11-20 小欧 按厂商文档补全生视频全能力: text/keyframe/reference 三模式 + 媒体/通用参数透传 — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 返回值对齐全项目规范(参照 question/search_web/schedule): 抽 _build_video_llm_data 统一构造 llm_data
  (summary + action{tool,tool_zh,params入参} + status 五字段 exec_code/message/code/detail/hint + duration_ms + metrics);
  data = 执行产出(产物 url/type), 不再是入参回显(入参归 action.params); 失败归因按 settled 区分;
  产物清单走 with_artifacts(llm_data.action.artifacts) → final_stats/产物抽屉 — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 三态语义校正: settled=True(厂商确定拒绝)→error+ERR_GENERATE_REJECTED、settled=False(未定)→warning; 修成功无产物处"成功但失败"矛盾文案; status.message 由 builder 查表改为三态调用处写死(避免非法 exec_code 崩溃) — 小欧-2026-11-20
"""
import time
from typing import Any, Dict, List, Optional

from app.tools.context import get_current_generate_callback

# 默认生成视频模型与错误码从工具层常量引入 — 小欧-2026-11-20
from app.tools.tool_constants import (
    ERR_GENERATE_INCOMPLETE,
    ERR_GENERATE_NO_CHANNEL,
    ERR_GENERATE_REJECTED,
    MEDIA_DEFAULT_VIDEO_MODEL,
)
from app.tools.tool_response import build_error, build_success, build_warning, with_artifacts


def _build_video_llm_data(
    exec_code: str,
    duration_ms: int,
    summary: str,
    params: Dict[str, Any],
    message: str,
    code: str = "",
    detail: str = "",
    hint: str = "",
    model: str = "",
) -> Dict[str, Any]:
    """生视频 llm_data 单一构造出口 — 与 question/schedule 的 builder 同构。
    action.params 带本次入参(prompt/model/mode/档位), status 五字段齐全, metrics 记实际采用模型。
    message 由三态调用处写死(成功/完成但有警告/失败), 不在 builder 查表(避免非法 exec_code 崩溃)。
    """
    status = {
        "exec_code": exec_code,
        "message": message,
        "code": code,
        "detail": detail,
        "hint": hint,
    }
    return {
        "summary": summary,
        "action": {"tool": "generate_video", "tool_zh": "生成视频", "params": params},
        "status": status,
        "duration_ms": duration_ms,
        "metrics": {"model": model} if model else {},
    }


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
    # 入参快照: action.params 承载(与 question/search_web 同款), data 不再重复
    in_params: Dict[str, Any] = {"prompt": prompt, "model": effective_model, "mode": mode}
    for key in ("images", "first_frame", "last_frame", "audios", "videos",
                "seconds", "size", "aspect_ratio", "seed"):
        if kwargs.get(key) is not None:
            in_params[key] = kwargs[key]
    if generate_callback is None:
        return build_error(
            data={},
            llm_data=_build_video_llm_data(
                "error", int((time.monotonic() - t0) * 1000),
                "生成视频，失败：生成视频通道未就绪", in_params, "失败",
                code=ERR_GENERATE_NO_CHANNEL, detail="生成视频回调未注入, 无法生成视频",
                hint="请在设置页配置生视频 provider/model 后重试或换模型",
                model=effective_model,
            ),
        )
    result = await generate_callback("video", effective_model, prompt, **kwargs)
    dur = int((time.monotonic() - t0) * 1000)
    if not result.get("ok"):
        # 三态语义(按 settled 分, 不硬编码): settled=True=厂商确定拒绝→error 换模型/查配置;
        #   settled=False=未定(队列/网络/超时)→warning 可稍后重试
        reason = str(result.get("reason", ""))[:120]
        if result.get("settled") is True:
            return build_error(
                data={},
                llm_data=_build_video_llm_data(
                    "error", dur, f"生成视频，失败：{reason}", in_params, "失败",
                    code=ERR_GENERATE_REJECTED, detail=reason,
                    hint="换模型或检查模型配置", model=effective_model,
                ),
            )
        return build_warning(
            data={},
            llm_data=_build_video_llm_data(
                "warning", dur, f"生成视频，警告：{reason}, 可稍后重试", in_params, "完成但有警告",
                code=ERR_GENERATE_INCOMPLETE, detail=reason, hint="可稍后重试", model=effective_model,
            ),
        )
    url = str(result.get("url") or "")
    artifacts = [{"name": "generated_video.mp4", "path": url, "type": "video"}] if url else []
    # data = 执行产出(产物), 与 read_text_file/query_sql 口径一致
    result_data: Dict[str, Any] = {"url": url, "type": "video"} if url else {}
    if url:
        # 明确要求 markdown 图片语法(前端 img 组件按 .mp4 后缀渲染 <video>), 别输出普通链接; 强调原样输出防改写签名 URL
        summary = (f"生成视频，成功：模型 {effective_model}。请在回复里原样输出这段 markdown(勿改写 URL、勿用普通链接): "
                   f"![生成的视频]({url})")
    else:
        # ok=True 但引擎未给出 mp4 地址: 不能标"成功"却无产物, 措辞如实说明 — 小欧-2026-11-20
        summary = (f"生成视频：模型 {effective_model} 任务已提交, 但未取得视频产物地址, 暂时无法展示。"
                   "请重试; 若反复失败请换模型。")
    llm_data = _build_video_llm_data("success", dur, summary, in_params, "成功", model=effective_model)
    return build_success(data=result_data, llm_data=with_artifacts(llm_data, artifacts))
