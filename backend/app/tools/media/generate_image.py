# -*- coding: utf-8 -*-
"""生成图像工具(generate_image) — 对话中生成图片, 产物公网 URL 交给 LLM 回复呈现。

编辑历史: 2026-11-20 小欧 新建: 经 get_current_generate_callback 调 generation 端点(工具层零越层),
  产物 URL 写进 data/llm_data, LLM 据此在回复里输出 ![](url) 由前端 MarkdownText 渲染; 产物声明 artifacts。
编辑历史: 2026-11-20 小欧 b64 产物分流: 公网URL走markdown内联; 无URL但已落盘(SenseNova b64→attachment)在 llm_data.action.artifacts 声明本地产物, 明确禁止 ![](本地路径)(会401); 不把4MB data URI 塞进回复。
编辑历史: 2026-11-20 小欧 三堂会审命名整改: cb→generate_callback(生成回调)、use_model→effective_model(实际采用模型)、
  md→markdown_text(markdown字符串); 纯改名零行为变更。
编辑历史: 2026-11-20 小欧 话术审查整改: url 分支 summary 强调"原样输出 markdown、勿改写 URL、勿用普通链接", 防 LLM 改写签名 URL; 纯话术改动零行为变更。
编辑历史: 2026-11-20 小欧 data/llm_data 分配整改: 按项目约定 llm_data 为答案真值唯一出口、data 只留输入回显 —— ①删 data 里与 summary 重复的
  url/file_path/attachment_id/markdown 及空值键, data 仅 {prompt,model}; ②失败分支(error/warning)补 action 供首行显示工具名;
  ③失败原因只留 summary 不重复进 data.reason; ④message 按项目约定用状态词(成功/失败/完成但有警告), summary 用 {tool_zh}，{成功/失败/警告}：{结果} 统一口径 — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 三堂会审整改: ①失败归因不再硬编码"队列拥堵", 按 result.settled 区分未定(可重试)/确定拒绝(换模型),
  消跨层语义断裂; ②错误码提 tool_constants 常量; ③成功 summary 用"成功：结果"冒号口径; ④删 markdown_text 死变量(内联);
  ⑤订正 b64 编辑历史里 with_artifact_file 的说法(实际手工声明 artifacts) — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 复用整改: 产物声明由手工内联 action.artifacts 改用公共 helper with_artifacts(llm_data, artifacts),
  与全项目十余个写工具同模式(复用优先); 编辑历史此前"with_artifact_file"说法不准(with_artifact_file 靠扩展名猜 type, 不适用 URL 产物) — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 按厂商文档补全生图全能力: 工具加 images(多图合成)/size(档位)/ratio(宽高比)参数并透传回调; 纯能力扩展旧调用零影响 — 小欧-2026-11-20
"""
import os
import time
from typing import Any, Dict, List, Optional

from app.tools.context import get_current_generate_callback

# 默认生成图像模型与错误码从工具层常量引入(三堂会审归位) — 小欧-2026-11-20
from app.tools.tool_constants import (
    ERR_GENERATE_INCOMPLETE,
    ERR_GENERATE_NO_CHANNEL,
    MEDIA_DEFAULT_IMAGE_MODEL,
)
from app.tools.tool_response import build_error, build_success, build_warning, with_artifacts


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
    if generate_callback is None:
        return build_error(
            data={"prompt": prompt},
            llm_data={
                # summary 统一口径: {tool_zh}，失败：{原因} — 小欧-2026-11-20
                "summary": "生成图像，失败：生成图像通道未就绪",
                # message 用约定状态词(失败); 具体原因归 detail, observation 显示"✖ 错误: ..."
                "status": {"exec_code": "error", "message": "失败", "code": ERR_GENERATE_NO_CHANNEL, "detail": "生成图像回调未注入, 无法生成图片"},
                "duration_ms": int((time.monotonic() - t0) * 1000),
                # 失败也必须带 action, 否则 observation 首行工具名为空("调用工具-") — 小欧-2026-11-20
                "action": {"tool": "generate_image", "tool_zh": "生成图像"},
            },
        )
    effective_model = model or MEDIA_DEFAULT_IMAGE_MODEL
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
        # 错误归因按 settled 区分(三堂会审): settled=False=未定(队列/网络/超时)→可稍后重试;
        #   settled=True=确定拒绝(模型不存在/参数非法)→换模型或查配置。不硬编码"队列拥堵"免误导 — 小欧-2026-11-20
        reason = str(result.get("reason", ""))[:120]
        advice = ("可稍后重试" if result.get("settled") is False
                  else "换模型或检查模型配置")
        # data 只留输入回显; 失败原因只在 llm_data.summary 出现一次(避免 data.reason 与 summary 重复)
        return build_warning(
            data={"prompt": prompt, "model": effective_model},
            llm_data={
                "summary": f"生成图像，警告：{reason}, {advice}",
                "status": {"exec_code": "warning", "message": "完成但有警告", "code": ERR_GENERATE_INCOMPLETE},
                "duration_ms": dur,
                "action": {"tool": "generate_image", "tool_zh": "生成图像"},
            },
        )
    url = str(result.get("url") or "")
    file_path = str(result.get("file_path") or "")
    attachment_id = str(result.get("attachment_id") or "")
    b64 = str(result.get("b64") or "")
    # 产物两条路: 公网 URL → markdown 内联展示; 无 URL 但 b64 已落盘(如 SenseNova) → 产物声明, 前端产物抽屉查看
    if url:
        summary = (f"生成图像，成功：模型 {effective_model}。请在回复里原样输出这段 markdown(勿改写 URL、勿用普通链接): "
                   f"![生成的图片]({url})")
        artifacts = [{"name": "generated_image.png", "path": url, "type": "image"}]
    elif file_path:
        summary = (f"生成图像，成功：模型 {effective_model}, 已存为会话附件(attachment_id={attachment_id}), "
                   f"产物路径 {file_path}。请告知用户图片已生成并可在产物/附件中查看。"
                   "注意: 该模型产物是本地文件(非公网URL), 不要用 markdown ![](file_path) 展示(会 401)。")
        artifacts = [{"name": os.path.basename(file_path), "path": file_path, "type": "image"}]
    elif b64:
        # 落盘失败的兜底: 不把大 b64 塞进回复, 只文字说明
        summary = f"生成图像，成功：模型 {effective_model}但产物落盘失败, 请重试或换模型。"
        artifacts = []
    else:
        summary = "生成图像，成功"
        artifacts = []
    # data 只留输入回显; 产物(url/file_path/attachment_id/markdown)是答案真值, 只在 llm_data.summary+artifacts 出现, 不重复塞 data
    llm_data: Dict[str, Any] = {
        "summary": summary,
        "status": {"exec_code": "success", "message": "成功"},
        "duration_ms": dur,
        "action": {"tool": "generate_image", "tool_zh": "生成图像"},
    }
    # 复用公共 helper 挂产物清单(与全项目写工具同模式) — 小欧-2026-11-20
    return build_success(data={"prompt": prompt, "model": effective_model},
                         llm_data=with_artifacts(llm_data, artifacts))
