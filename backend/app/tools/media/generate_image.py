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
编辑历史: 2026-11-21 小欧 三堂会审整改: 公网产物的 artifacts 名改由 artifact_from_url 按 URL 真实后缀定名(原硬编码 .png);
  本地附件摘要按是否真拿到 attachment_id 拼接, 登记失败兜底时不再出现空 attachment_id= — 小欧-2026-11-21
编辑历史: 2026-11-21 小欧 厂商响应不再只留产物地址: 规格(size/output_format)与出图耗时拼进 summary 一句,
  厂商回显 model 覆盖 metrics.model, 其余字段(created/task_id/revised_prompt/usage/失败 request id)原样进
  other_data.provider(落库落档, 不进 LLM) — 小欧-2026-11-21
编辑历史: 2026-11-21 小欧 规格改走 vendor_spec 标准键映射(尺寸/格式/耗时, 未映射不显示); 成功 summary 去掉产物段
  (附件路径已在 data, 重复即噪音), 公网形态本地形态话术一致 — 小欧-2026-11-21
编辑历史: 2026-11-21 小欧 未交付不再报 warning: b64 落盘失败(厂商已生成、本地产物丢失)与厂商无产物一律
  exec_code=error(分别 ERR_GENERATE_PERSIST_FAILED / ERR_GENERATE_REJECTED), LLM 须明确知道没拿到图 — 小欧-2026-11-21
编辑历史: 2026-11-21 小欧 落点收窄 + DRY: 原 _vendor_fields 与 generate_video 逐字重复, 合并为
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

# 默认生成图像模型与错误码从工具层常量引入 — 小欧-2026-11-20
from app.tools.tool_constants import (
    ERR_GENERATE_INCOMPLETE,
    ERR_GENERATE_NO_CHANNEL,
    ERR_GENERATE_PERSIST_FAILED,
    ERR_GENERATE_REJECTED,
    MEDIA_DEFAULT_IMAGE_MODEL,
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


def _build_image_llm_data(
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
    """生图 llm_data 单一构造出口 — 与 question/schedule 的 builder 同构。
    action.params 带本次入参(prompt/model/档位), status 五字段齐全, metrics 由厂商回显派生
    (model/size/format/usage tokens, 键值统一 {value,text} 形, 前端工具行标签与 LLM 统计行共用)。
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
        "metrics": metrics or {},
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
                metrics={"model": {"value": effective_model, "text": effective_model}},
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
    metrics, spec, other, model_echo = build_vendor_fields("image", result, effective_model)
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
                    hint="换模型或检查模型配置", metrics=metrics,
                ),
                other_data=other,
            )
        return build_warning(
            data={},
            llm_data=_build_image_llm_data(
                "warning", dur, f"生成图像，警告：{reason}", in_params, "完成但有警告",
                code=ERR_GENERATE_INCOMPLETE, detail=reason, hint="可稍后重试", metrics=metrics,
            ),
            other_data=other,
        )
    url = str(result.get("url") or "")
    file_path = str(result.get("file_path") or "")
    attachment_id = str(result.get("attachment_id") or "")
    # 只有拿到可用产物(url 或落盘 file_path)才算成功; 引擎 ok=True 但只有 b64 未落盘 = 没交付产物
    if not url and not file_path:
        # 没交付就是失败: 落盘失败是大模型已生成、本地产物丢了, 报 error 而非 warning(LLM 须知道没拿到图)
        if result.get("b64"):
            detail = "厂商返回图片但保存为附件失败, 无可用产物"
            return build_error(
                data={},
                llm_data=_build_image_llm_data(
                    "error", dur, "生成图像，失败：本地产物保存失败", in_params, "失败",
                    code=ERR_GENERATE_PERSIST_FAILED, detail=detail,
                    hint="稍后重试; 持续失败请检查附件目录写入权限与磁盘空间", metrics=metrics,
                ),
                other_data=other,
            )
        return build_error(
            data={},
            llm_data=_build_image_llm_data(
                "error", dur, "生成图像，失败：厂商未返回可用产物", in_params, "失败",
                code=ERR_GENERATE_REJECTED, detail="厂商未返回可用图片产物",
                hint="换模型或检查模型配置", metrics=metrics,
            ),
            other_data=other,
        )
    # summary 只报结论与规格, 产物指针在 data(不重复); 两种形态话术一致 — 小欧-2026-11-21
    # 2026-11-22 小欧 - data 带 session_id: 前端产物卡片据此取本地附件 raw 接口, 不依赖全局前台会话
    _sid = str(result.get("session_id") or "")
    summary = f"生成图像，成功：模型 {model_echo}{spec}"
    if url:
        # 公网产物: form=url, name 取 URL 末段文件名, 签名查询串不进名字
        other = declare_artifacts(other, [artifact_from_url(url, "image")])
        result_data: Dict[str, Any] = {"url": url, "type": "image", "session_id": _sid}
    else:
        # 本地落盘产物: 与其余写工具同一入口, form/type 由契约判定(不再手搓条目)
        other = declare_artifact_file(other, file_path)
        result_data = {"file_path": file_path, "attachment_id": attachment_id, "type": "image", "session_id": _sid}
    llm_data = _build_image_llm_data("success", dur, summary, in_params, "成功", metrics=metrics)
    return build_success(data=result_data, llm_data=llm_data, other_data=other)
