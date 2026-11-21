# -*- coding: utf-8 -*-
"""媒体生成工具注册点(generate_image / generate_video) — 小欧 2026-11-20

模板参照 agent_register.py: 分类 MEDIA, 扁平 input_model, 一句路由描述。
编辑历史: 2026-11-20 小欧 工具描述同步 image 参数支持本地路径/attachment_id(后端转data URI), 明确引导 LLM 从会话 attachments 目录取上传图的路径做 i2i 编辑。
编辑历史: 2026-11-20 小欧 话术审查整改: 两工具描述消除含糊与矛盾 —— 明确 mode/image 如何决定 t2i/i2i、t2v/i2v; image 四种来源与 schema 对齐;
  model 只列本模态模型避免传错; 产物展示区分公网URL(markdown)与本地附件(不用markdown, 会401), 消除与 llm_data.summary 的冲突; 纯话术改动零行为变更。
编辑历史: 2026-11-20 小欧 按厂商文档补全生图全能力: generate_image 描述加 images 多图合成、size 档位、ratio 宽高比, examples 补多图合成示例 — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 生成工具回归通用 tool 行: 移除 hide_from_steps 隐藏, 让 action/observation 按其他 tool 同款通道下发(工具名/浮层参数/状态/耗时/结果), 前端产出物另由 artifacts 专用卡片呈现; 多轮多张每次调用各自成行 — 小欧-2026-11-20
编辑历史: 2026-11-21 小欧 三堂会审整改: 两工具描述的产物展示口径与实现对齐 —— 产物由前端卡片呈现(data 的 url/file_path),
  原"在回复里原样输出 markdown ![](url)"已无实现依据且与 llm_data.summary(只报结果)冲突, 改为禁止粘贴 URL/markdown — 小欧-2026-11-21
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
        "prompt 写想要的内容或改动; model 为生成图像模型名(只传生成图像模型如 agnes-image-2.5-flash/agnes-image-2.1-flash 或 sensenova-u1.5-lite, 不填用默认; 切勿传生成视频模型)。"
        "image 决定模式: 留空=文生图(t2i), 传单张参考图=图生图(i2i), 传 images 多张=多图合成(prompt 里说明每张图角色与组合方式); "
        "参考图可传本地路径(会话 attachments 目录下)、attachment_id、公网图片URL 或 data URI, 后端自动归一, 本地图无需公网图床。"
        "size 尺寸档位 1K/2K/3K/4K 与 ratio 宽高比(1:1/3:4/4:3/16:9/9:16/2:3/3:2/21:9)可选, 不填用厂商默认; "
        "return_base64=true 可要求以 Base64 返回(产物落盘为会话附件, 不塞进回复), 一般无需设置。"
        "产物由界面卡片自动呈现(公网URL出缩略图, 本地附件出文件卡), 回复里只需一句话说明已生成, 不要粘贴 URL、不要写 markdown 图片或链接。"
    ),
    "generate_video": (
        "适用: 用户要求生成/制作视频、让图动起来、按首/尾帧控制、或多模态参考生成时。异步任务, 常需数分钟, 请勿中途重复提交(会重复扣费)。"
        "prompt 写画面/动作/镜头/声音; reference 模式用 <Picture N>/<Audio N>/<Video N> 按序指代素材。model 为生成视频模型名(只传生成视频模型如 agnes-video-2.5-flash, 不填用默认; 切勿传生成图像模型)。"
        "mode 取以下之一(三组语义): t2v/text=纯文本生成视频(媒体全留空, 默认); keyframe=首尾帧控制(给 first_frame 和/或 last_frame, 成片以此为真实首/尾帧); "
        "i2v/reference=多模态参考(给 images 多图 / audios 音频 / videos 视频至少一类; 单图可用 image, 与 images 合并)。"
        "图片类素材(image/images/first_frame/last_frame)支持本地路径(会话 attachments 目录下)、attachment_id、公网URL、data URI, 本地的后端自动公网化; "
        "audios 为公网音频URL列表; videos 为对象列表, 每项 {url:公网视频URL, start_seconds?:起始秒, require_audio?:是否要求音轨}, prompt 用 <Video N> 指代(flash 不支持视频参考)。"
        "可选: seconds('4'~'12')、size(720P/1080P/1K/2K, flash仅720P)、aspect_ratio(21:9/16:9/4:3/1:1/3:4/9:16)、seed(可复现)。timeout 等待上限秒(默认660, 范围120~1200)。"
        "产物由界面卡片自动呈现(公网URL出播放器, 本地附件出文件卡), 回复里只需一句话说明已生成, 不要粘贴 URL、不要写 markdown 图片或链接。"
    ),
}

MEDIA_INPUT_MODELS = {
    "generate_image": GenerateImageInput,
    "generate_video": GenerateVideoInput,
}

MEDIA_TOOL_EXAMPLES = {
    "generate_image": [
        {
            "prompt": "一只戴墨镜的猫坐在沙滩上, 夕阳西下, 写实风格",
            "model": "agnes-image-2.1-flash",
        },
        {
            "prompt": "把图片主色调改成蓝色",
            "image": "会话 attachments 目录下用户上传图的本地路径",
            "model": "agnes-image-2.1-flash",
        },
        {
            "prompt": "以第一张图为主角、第二张图为产品参考, 生成电影级海报, 保留角色身份与产品外形",
            "images": ["会话 attachments 目录下角色图的本地路径", "会话 attachments 目录下产品图的本地路径"],
            "size": "2K",
            "ratio": "16:9",
            "model": "agnes-image-2.1-flash",
        },
    ],
    "generate_video": [
        {
            "prompt": "一个红色圆点在白色背景上缓慢移动",
            "model": "agnes-video-2.5-flash",
            "mode": "t2v",
        },
        {
            "prompt": "以 <Picture 1> 的角色和画风为参考, 在花田中自然奔跑",
            "image": "会话 attachments 目录下用户上传图的本地路径",
            "model": "agnes-video-2.5-flash",
            "mode": "reference",
        },
        {
            "prompt": "从首帧姿态自然转身走向窗边, 平滑过渡到尾帧构图",
            "first_frame": "会话 attachments 目录下首帧图的本地路径",
            "last_frame": "会话 attachments 目录下尾帧图的本地路径",
            "model": "agnes-video-2.5",
            "mode": "keyframe",
        },
    ],
}


def _register_media_tools():
    """注册 generate_image/generate_video 两个媒体生成工具 — 小欧 2026-11-20"""
    tool_methods = {"generate_image": generate_image, "generate_video": generate_video}
    # 走注册表默认可见: action/observation 与其他 tool 同款下发(工具名/浮层参数/状态/耗时/结果),
    #   产物另由前端 artifacts 专用卡片呈现; 多轮多张每次调用各自成行 — 小欧-2026-11-20
    for name, method in tool_methods.items():
        tool_registry.register(
            name=name,
            description=MEDIA_TOOL_DESCRIPTIONS.get(name, ""),
            category=ToolCategory.MEDIA,
            implementation=method,
            version="1.0.0",
            input_model=MEDIA_INPUT_MODELS.get(name),
            examples=MEDIA_TOOL_EXAMPLES.get(name, []),
        )
        logger.debug(f"[media_register] 已注册工具: {name}")


__all__ = ["_register_media_tools"]
