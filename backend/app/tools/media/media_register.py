# -*- coding: utf-8 -*-
"""媒体生成工具注册点(generate_image / generate_video) — 小欧 2026-11-20

模板参照 agent_register.py: 分类 MEDIA, 扁平 input_model, 一句路由描述。
编辑历史: 2026-11-20 小欧 工具描述同步 image 参数支持本地路径/attachment_id(后端转data URI), 明确引导 LLM 从会话 attachments 目录取上传图的路径做 i2i 编辑。
"""
from app.logger import logger
from app.tools.media.generate_image import generate_image
from app.tools.media.generate_video import generate_video
from app.tools.media.media_schema import GenerateImageInput, GenerateVideoInput
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory

MEDIA_TOOL_DESCRIPTIONS = {
    "generate_image": (
        "适用: 用户要求生成/画一张图片时。文字描述想要的内容, 调用本工具生成图片。"
        "prompt 为图片内容描述; model 为生图模型名(不填用默认 agnes-image-2.1-flash); "
        "image 为图生图(i2i)参考图, 可传用户上传图片的本地路径/attachment_id/公网URL(后端自动转换), 留空=纯文本生图(t2i)。"
        "用户上传的图片可从会话的 attachments 目录找到本地路径直接传 image。生成后在回复里用 ![](产物URL) 展示图片。"
    ),
    "generate_video": (
        "适用: 用户要求生成/制作一段视频时。文字描述想要的画面, 调用本工具生成视频(异步, 约几分钟)。"
        "prompt 为视频内容描述; model 为生视频模型名(不填用默认 agnes-video-2.5-flash); "
        "mode=t2v(纯文本)或 i2v(带参考图, 需给 image); timeout 等待上限秒(默认660)。"
        "生成后在回复里用 markdown 展示视频: ![生成的视频](产物URL)。"
    ),
}

MEDIA_INPUT_MODELS = {
    "generate_image": GenerateImageInput,
    "generate_video": GenerateVideoInput,
}

MEDIA_TOOL_EXAMPLES = {
    "generate_image": [{
        "prompt": "一只戴墨镜的猫坐在沙滩上, 夕阳西下, 写实风格",
        "model": "agnes-image-2.1-flash",
    }],
    "generate_video": [{
        "prompt": "一个红色圆点在白色背景上缓慢移动",
        "model": "agnes-video-2.5-flash",
        "mode": "t2v",
    }],
}


def _register_media_tools():
    """注册 generate_image/generate_video 两个媒体生成工具 — 小欧 2026-11-20"""
    tool_methods = {"generate_image": generate_image, "generate_video": generate_video}
    # 产物走专属呈现(图片 markdown / 视频产物卡), 不画通用工具行
    hide_from_steps = {"generate_image", "generate_video"}
    for name, method in tool_methods.items():
        tool_registry.register(
            name=name,
            description=MEDIA_TOOL_DESCRIPTIONS.get(name, ""),
            category=ToolCategory.MEDIA,
            implementation=method,
            version="1.0.0",
            input_model=MEDIA_INPUT_MODELS.get(name),
            examples=MEDIA_TOOL_EXAMPLES.get(name, []),
            hide_from_steps=name in hide_from_steps,
        )
        logger.debug(f"[media_register] 已注册工具: {name}")


__all__ = ["_register_media_tools"]
