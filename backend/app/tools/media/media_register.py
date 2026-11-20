# -*- coding: utf-8 -*-
"""媒体生成工具注册点(generate_image / generate_video) — 小欧 2026-11-20

模板参照 agent_register.py: 分类 MEDIA, 扁平 input_model, 一句路由描述。
编辑历史: 2026-11-20 小欧 工具描述同步 image 参数支持本地路径/attachment_id(后端转data URI), 明确引导 LLM 从会话 attachments 目录取上传图的路径做 i2i 编辑。
编辑历史: 2026-11-20 小欧 话术审查整改: 两工具描述消除含糊与矛盾 —— 明确 mode/image 如何决定 t2i/i2i、t2v/i2v; image 四种来源与 schema 对齐;
  model 只列本模态模型避免传错; 产物展示区分公网URL(markdown)与本地附件(不用markdown, 会401), 消除与 llm_data.summary 的冲突; 纯话术改动零行为变更。
"""
from app.logger import logger
from app.tools.media.generate_image import generate_image
from app.tools.media.generate_video import generate_video
from app.tools.media.media_schema import GenerateImageInput, GenerateVideoInput
from app.tools.registry import tool_registry
from app.tools.tool_types import ToolCategory

MEDIA_TOOL_DESCRIPTIONS = {
    "generate_image": (
        "适用: 用户要求生成/画一张图片, 或基于已有图片编辑(改色/换风格等)时。"
        "prompt 写想要的内容或改动; model 为生成图像模型名(只传生成图像模型如 agnes-image-2.1-flash, 不填用默认; 切勿传生成视频模型)。"
        "image 决定模式: 留空=文生图(t2i), 传参考图=图生图(i2i); 参考图可传用户上传图的本地路径(在会话 attachments 目录下)、"
        "attachment_id、公网图片URL 或 data URI 四者之一, 后端自动归一, 本地图无需公网图床。"
        "产物为公网URL时, 在回复里原样输出工具返回的 markdown ![](url) 展示; 若产物是本地附件(工具会说明), 则只告知用户去产物/附件查看, 不要用 markdown 展示本地路径。"
    ),
    "generate_video": (
        "适用: 用户要求生成/制作一段视频, 或让一张图动起来时。异步任务, 常需数分钟, 请勿中途重复提交(会重复扣费)。"
        "prompt 写想要的画面或如何动; model 为生成视频模型名(只传生成视频模型如 agnes-video-2.5-flash, 不填用默认; 切勿传生成图像模型)。"
        "mode 决定模式: t2v=文生视频(默认, image 留空), i2v=图生视频(必须同时给 image 作首帧参考图; 若 mode=i2v 却没给 image, 会按无参考图的 t2v 处理)。"
        "image 四种都支持: 本地路径(会话 attachments 目录下)、attachment_id、公网图片URL、data URI; 本地图/附件/data URI 后端会自动公网化, 本地图也能做。"
        "timeout 为等待上限秒(默认660, 范围120~1200, 别调太小)。产物为公网URL, 在回复里原样输出工具返回的 markdown ![生成的视频](url) 展示, 别输出普通链接。"
    ),
}

MEDIA_INPUT_MODELS = {
    "generate_image": GenerateImageInput,
    "generate_video": GenerateVideoInput,
}

MEDIA_TOOL_EXAMPLES = {
    "generate_image": [
        {"prompt": "一只戴墨镜的猫坐在沙滩上, 夕阳西下, 写实风格", "model": "agnes-image-2.1-flash"},
        {"prompt": "把图片主色调改成蓝色", "image": "会话 attachments 目录下用户上传图的本地路径", "model": "agnes-image-2.1-flash"},
    ],
    "generate_video": [
        {"prompt": "一个红色圆点在白色背景上缓慢移动", "model": "agnes-video-2.5-flash", "mode": "t2v"},
        {"prompt": "让镜头缓慢推近", "image": "会话 attachments 目录下用户上传图的本地路径", "model": "agnes-video-2.5-flash", "mode": "i2v"},
    ],
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
