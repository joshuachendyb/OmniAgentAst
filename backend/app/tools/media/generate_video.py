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
编辑历史: 2026-11-21 小欧 三堂会审整改: 公网产物的 artifacts 名改由 artifact_from_url 按 URL 真实后缀定名(原硬编码 .mp4);
  本地附件摘要按是否真拿到 attachment_id 拼接, 登记失败兜底时不再出现空 attachment_id= — 小欧-2026-11-21
编辑历史: 2026-11-21 小欧 厂商响应不再只留产物地址: 规格(seconds/size/quality)与出片耗时拼进 summary 一句,
  厂商回显 model 覆盖 metrics.model, 其余字段(task_id/video_id/created_at/completed_at/progress/input_*/
  失败 request id)原样进 other_data.provider(落库落档, 不进 LLM) — 小欧-2026-11-21
编辑历史: 2026-11-21 小欧 规格改走 vendor_spec 标准键映射(时长+清晰度/质量档/耗时, 未映射不显示); 成功 summary
  去掉产物段(附件路径已在 data, 重复即噪音), 公网形态本地形态话术一致 — 小欧-2026-11-21
编辑历史: 2026-11-21 小欧 未交付不再报 warning: b64 落盘失败与厂商无产物一律 exec_code=error
  (分别 ERR_GENERATE_PERSIST_FAILED / ERR_GENERATE_REJECTED), LLM 须明确知道没拿到视频 — 小欧-2026-11-21
编辑历史: 2026-11-21 小欧 落点收窄 + DRY: 原 _vendor_fields 与 generate_image 逐字重复, 合并为
  vendor_spec.build_vendor_fields(kind, result, effective_model) 单源; other_data 只装厂商 usage 数字
  (原 other_data.provider 与其余标量改走 metrics), 无 usage 时为空 dict — 小欧-2026-11-21
编辑历史: 2026-11-21 小欧 产物声明迁出 tool_response 并补形态: 公网 URL 走 declare_artifacts+artifact_from_url
  (form=url, type 取 URL 后缀), 本地落盘走 declare_artifact_file(form=file), 两者都挂 other_data["artifacts"]
  (不再挂 llm_data.action.artifacts, 也不再手搓条目 dict) — 小欧-2026-11-21
"""
import time
from typing import Any, Dict, List, Optional

from app.services.generation.vendor_spec import build_vendor_fields
from app.tools.context import get_current_generate_callback

# 默认生成视频模型与错误码从工具层常量引入 — 小欧-2026-11-20
from app.tools.tool_constants import (
    ERR_GENERATE_INCOMPLETE,
    ERR_GENERATE_NO_CHANNEL,
    ERR_GENERATE_PERSIST_FAILED,
    ERR_GENERATE_REJECTED,
    MEDIA_DEFAULT_VIDEO_MODEL,
)
from app.tools.tool_response import (
    build_error,
    build_success,
    build_warning,
)
from app.utils.artifacts import (  # 产物契约唯一实现 — 小欧 2026-11-21
    artifact_from_url,
    declare_artifact_file,
    declare_artifacts,
)


def _build_video_llm_data(
    exec_code: str,
    duration_ms: int,
    summary: str,
    params: Dict[str, Any],
    message: str,
    code: str = "",
    detail: str = "",
    hint: str = "",
    metrics: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """生视频 llm_data 单一构造出口 — 与 question/schedule 的 builder 同构。
    action.params 带本次入参(prompt/model/mode/档位), status 五字段齐全, metrics 由厂商回显派生
    (model/seconds/size/quality, 键值统一 {value,text} 形, 前端工具行标签与 LLM 统计行共用)。
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
        "metrics": metrics or {},
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
                metrics={"model": {"value": effective_model, "text": effective_model}},
            ),
        )
    result = await generate_callback("video", effective_model, prompt, **kwargs)
    dur = int((time.monotonic() - t0) * 1000)
    metrics, spec, other, model_echo = build_vendor_fields("video", result, effective_model)
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
                    hint="换模型或检查模型配置", metrics=metrics,
                ),
                other_data=other,
            )
        return build_warning(
            data={},
            llm_data=_build_video_llm_data(
                "warning", dur, f"生成视频，警告：{reason}", in_params, "完成但有警告",
                code=ERR_GENERATE_INCOMPLETE, detail=reason, hint="可稍后重试", metrics=metrics,
            ),
            other_data=other,
        )
    url = str(result.get("url") or "")
    file_path = str(result.get("file_path") or "")
    attachment_id = str(result.get("attachment_id") or "")
    # 可用产物 = 公网 url 或 b64 落盘的本地附件路径; 两者皆无才算没交付
    if not url and not file_path:
        # 没交付就是失败: 落盘失败是大模型已生成、本地产物丢了, 报 error 而非 warning(LLM 须知道没拿到视频)
        if result.get("b64"):
            detail = "厂商返回视频但保存为附件失败, 无可用产物"
            return build_error(
                data={},
                llm_data=_build_video_llm_data(
                    "error", dur, "生成视频，失败：本地产物保存失败", in_params, "失败",
                    code=ERR_GENERATE_PERSIST_FAILED, detail=detail,
                    hint="稍后重试; 持续失败请检查附件目录写入权限与磁盘空间", metrics=metrics,
                ),
                other_data=other,
            )
        return build_error(
            data={},
            llm_data=_build_video_llm_data(
                "error", dur, "生成视频，失败：厂商未返回可用产物", in_params, "失败",
                code=ERR_GENERATE_REJECTED, detail="厂商未返回可用视频产物",
                hint="换模型或检查模型配置", metrics=metrics,
            ),
            other_data=other,
        )
    # summary 只报结论与规格, 产物指针在 data(不重复); 两种形态话术一致 — 小欧-2026-11-21
    summary = f"生成视频，成功：模型 {model_echo}{spec}"
    if url:
        # 公网产物: form=url, name 取 URL 末段文件名, 签名查询串不进名字
        other = declare_artifacts(other, [artifact_from_url(url, "video")])
        result_data: Dict[str, Any] = {"url": url, "type": "video"}
    else:
        # 本地落盘产物: 与其余写工具同一入口, form/type 由契约判定(不再手搓条目)
        other = declare_artifact_file(other, file_path)
        result_data = {"file_path": file_path, "attachment_id": attachment_id, "type": "video"}
    llm_data = _build_video_llm_data("success", dur, summary, in_params, "成功", metrics=metrics)
    return build_success(data=result_data, llm_data=llm_data, other_data=other)
