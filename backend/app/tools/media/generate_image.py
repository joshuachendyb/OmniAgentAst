# -*- coding: utf-8 -*-
"""生成图像工具(generate_image) — 对话中生成图片, 产物公网 URL 交给 LLM 回复呈现。

编辑历史: 2026-11-20 小欧 新建: 经 get_current_generate_callback 调 generation 端点(工具层零越层),
  产物 URL 写进 data/llm_data, LLM 据此在回复里输出 ![](url) 由前端 MarkdownText 渲染; 产物声明 artifacts。
编辑历史: 2026-11-20 小欧 b64 产物分流: 公网URL走markdown内联; 无URL但已落盘(SenseNova b64→attachment)在 llm_data.action.artifacts 声明本地产物, 明确禁止 ![](本地路径)(会401); 不把4MB data URI 塞进回复。
编辑历史: 2026-11-20 小欧 命名整改: cb→generate_callback(生成回调)、use_model→effective_model(实际采用模型)、
  md→markdown_text(markdown字符串); 纯改名零行为变更。
编辑历史: 2026-11-20 小欧 话术审查整改: url 分支 summary 强调"原样输出 markdown、勿改写 URL、勿用普通链接", 防 LLM 改写签名 URL; 纯话术改动零行为变更。
编辑历史: 2026-11-20 小欧 按厂商文档补全生图全能力: 工具加 images(多图合成)/size(档位)/ratio(宽高比)参数并透传回调; 纯能力扩展旧调用零影响 — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 返回值对齐全项目规范(参照 question/search_web/schedule): 抽 _build_image_llm_data 统一构造 llm_data
  (summary + action{tool,tool_zh,params入参} + status 五字段 exec_code/message/code/detail/hint + duration_ms + metrics);
  data = 执行产出(产物 url/file_path/attachment_id/type), 不再是入参回显(入参归 action.params); 失败归因按 settled 区分;
  产物清单仍走 with_artifacts(llm_data.action.artifacts) → final_stats/产物抽屉 — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 按 Tool 编写规范整改: effective_model/in_params 构造提到无通道 error 检查之前, 保证 error 态 action.params 也带全(prompt/model/档位), 与 generate_video 同构 — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 三态语义校正: settled=True(厂商确定拒绝)→error+ERR_GENERATE_REJECTED、settled=False(未定)→warning; 修 b64 落盘失败/成功无产物两处"成功但失败"矛盾文案; status.message 由 builder 查表改为三态调用处写死(避免非法 exec_code 崩溃) — 小欧-2026-11-20
"""
import os
import time
from typing import Any, Dict, List, Optional

from app.tools.context import get_current_generate_callback

# 默认生成图像模型与错误码从工具层常量引入 — 小欧-2026-11-20
from app.tools.tool_constants import (
    ERR_GENERATE_INCOMPLETE,
    ERR_GENERATE_NO_CHANNEL,
    ERR_GENERATE_REJECTED,
    MEDIA_DEFAULT_IMAGE_MODEL,
)
from app.tools.tool_response import build_error, build_success, build_warning, with_artifacts


def _build_image_llm_data(
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
    """生图 llm_data 单一构造出口 — 与 question/schedule 的 builder 同构。
    action.params 带本次入参(prompt/model/档位), status 五字段齐全, metrics 记实际采用模型。
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
        "action": {"tool": "generate_image", "tool_zh": "生成图像", "params": params},
        "status": status,
        "duration_ms": duration_ms,
        "metrics": {"model": model} if model else {},
    }


async def generate_image(prompt: str, model: Optional[str] = None,
                         image: Optional[str] = None,
                         images: Optional[List[str]] = None,
                         size: Optional[str] = None,
                         ratio: Optional[str] = None,
                         return_base64: bool = False,
                         response_format: Optional[str] = None) -> Dict[str, Any]:
    """生成一张图片(t2i/i2i/多图合成)。返回 {data, llm_data, other_data}。"""
    t0 = time.monotonic()
    generate_callback = get_current_generate_callback()
    effective_model = model or MEDIA_DEFAULT_IMAGE_MODEL
    # 入参快照: action.params 承载(与 question/search_web 同款), data 不再重复。
    #   在 error 检查前构造, 保证三态(含无通道 error)params 都完整 — 与 generate_video 同构
    in_params: Dict[str, Any] = {"prompt": prompt, "model": effective_model}
    if image:
        in_params["image"] = image
    if images:
        in_params["images"] = images
    if size:
        in_params["size"] = size
    if ratio:
        in_params["ratio"] = ratio
    if generate_callback is None:
        return build_error(
            data={},
            llm_data=_build_image_llm_data(
                "error", int((time.monotonic() - t0) * 1000),
                "生成图像，失败：生成图像通道未就绪", in_params, "失败",
                code=ERR_GENERATE_NO_CHANNEL, detail="生成图像回调未注入, 无法生成图片",
                hint="请在设置页配置生图 provider/model 后重试或换模型",
                model=effective_model,
            ),
        )
    # 只透传非空可选参数; 新参数(images/size/ratio)不传则编排层走默认, 旧调用零影响
    cb_kwargs: Dict[str, Any] = {}
    if images:
        cb_kwargs["images"] = images
    if size:
        cb_kwargs["size"] = size
    if ratio:
        cb_kwargs["ratio"] = ratio
    if return_base64:
        cb_kwargs["return_base64"] = True
    if response_format:
        cb_kwargs["response_format"] = response_format
    result = await generate_callback("image", effective_model, prompt, image=image, **cb_kwargs)
    dur = int((time.monotonic() - t0) * 1000)
    if not result.get("ok"):
        # 三态语义(按 settled 分, 不硬编码): settled=True=厂商确定拒绝(模型/参数/鉴权/no_output)→error, 换模型或查配置;
        #   settled=False=未定(队列/网络/超时)→warning, 可稍后重试
        reason = str(result.get("reason", ""))[:120]
        if result.get("settled") is True:
            return build_error(
                data={},
                llm_data=_build_image_llm_data(
                    "error", dur, f"生成图像，失败：{reason}", in_params, "失败",
                    code=ERR_GENERATE_REJECTED, detail=reason,
                    hint="换模型或检查模型配置", model=effective_model,
                ),
            )
        return build_warning(
            data={},
            llm_data=_build_image_llm_data(
                "warning", dur, f"生成图像，警告：{reason}, 可稍后重试", in_params, "完成但有警告",
                code=ERR_GENERATE_INCOMPLETE, detail=reason, hint="可稍后重试", model=effective_model,
            ),
        )
    url = str(result.get("url") or "")
    file_path = str(result.get("file_path") or "")
    attachment_id = str(result.get("attachment_id") or "")
    b64 = str(result.get("b64") or "")
    # data = 执行产出(产物), 与 read_text_file/query_sql 口径一致; 清单另走 with_artifacts
    if url:
        summary = (f"生成图像，成功：模型 {effective_model}。请在回复里原样输出这段 markdown(勿改写 URL、勿用普通链接): "
                   f"![生成的图片]({url})")
        artifacts = [{"name": "generated_image.png", "path": url, "type": "image"}]
        result_data: Dict[str, Any] = {"url": url, "type": "image"}
    elif file_path:
        summary = (f"生成图像，成功：模型 {effective_model}, 已存为会话附件(attachment_id={attachment_id}), "
                   f"产物路径 {file_path}。请告知用户图片已生成并可在产物/附件中查看。"
                   "注意: 该模型产物是本地文件(非公网URL), 不要用 markdown ![](file_path) 展示(会 401)。")
        artifacts = [{"name": os.path.basename(file_path), "path": file_path, "type": "image"}]
        result_data = {"file_path": file_path, "attachment_id": attachment_id, "type": "image"}
    elif b64:
        # 落盘失败兜底: 大 b64 不塞进 data/回复, 只文字说明。措辞避免"成功但失败"自相矛盾 — 小欧-2026-11-20
        summary = (f"生成图像：模型 {effective_model} 已产出图片, 但保存为会话附件失败, 暂时无法在回复中展示图片。"
                   "请重试生成; 若反复失败请换模型。")
        artifacts = []
        result_data = {}
    else:
        summary = "生成图像，成功"
        artifacts = []
        result_data = {}
    llm_data = _build_image_llm_data("success", dur, summary, in_params, "成功", model=effective_model)
    return build_success(data=result_data, llm_data=with_artifacts(llm_data, artifacts))
