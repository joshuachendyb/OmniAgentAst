# -*- coding: utf-8 -*-
"""媒体生成工具输入模型(generate_image / generate_video) — 小欧 2026-11-20

扁平简单类型(prompt/model/mode 等 str), 无嵌套 BaseModel, 严格 provider 兼容(同 agent_schema 契约)。
编辑历史: 2026-11-20 小欧 话术审查整改: model 字段改用按模态拆分的 hint(防传错模型); prompt 去"尽量具体"改列具体要素;
  mode/image 讲清 t2i/i2i/t2v/i2v 触发条件(留空 vs 传值); image 四种来源完整列出; timeout 补范围120~1200与"别调太小"原因; 纯话术改动零行为变更。
编辑历史: 2026-11-20 小欧 按厂商文档(agnes-video-2.5/flash)补全视频全能力: mode 扩 text/keyframe/reference;
  加 first_frame/last_frame(首尾帧)、images(多图)/audios/videos(多模态参考)、seconds/size/aspect_ratio/seed 通用参数;
  prompt 引导用 <Picture N>/<Audio N>/<Video N> 指代素材 — 小欧-2026-11-20
编辑历史: 2026-11-20 小欧 按厂商文档(agnes-image-2.1/2.5-flash)补全生图全能力: GenerateImageInput 加 images(多图合成)/
  size(1K~4K档位)/ratio(8种宽高比); 实测 agnes 档位+ratio、sensenova WIDTHxHEIGHT 由后端按 provider 翻译 — 小欧-2026-11-20
"""
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

# 模型名话术从工具层常量引入(按工具拆开, 避免传错模态模型); 写进描述不强制 enum, 用户可配新模型 — 小欧-2026-11-20
from app.tools.tool_constants import MEDIA_IMAGE_MODEL_HINT, MEDIA_VIDEO_MODEL_HINT


class GenerateImageInput(BaseModel):
    prompt: str = Field(..., min_length=1, description="图片内容描述(文本生成图像提示词)。写清主体、风格、场景、光线等要素, 越具体出图越贴合; 图生图(i2i)时用来描述想要的改动(如'改成蓝色')")
    model: Optional[str] = Field(default=None, description=MEDIA_IMAGE_MODEL_HINT)
    image: Optional[str] = Field(default=None, description="单张参考图(i2i), 四种都支持: ①本地路径(会话 attachments 目录) ②attachment_id(32位hex) ③公网图片URL ④data URI。留空=文生图(t2i); 传值=图生图(i2i)。后端自动归一, 本地图无需图床。多图合成请用 images")
    images: Optional[List[str]] = Field(default=None, description="多图合成参考图列表(2张及以上)。每项来源同 image(本地路径/attachment_id/公网URL/data URI), 后端自动公网化。与 image 同时给时合并。prompt 里说明每张图的角色与组合方式")
    size: Optional[str] = Field(default=None, description="输出尺寸档位: 1K/2K/3K/4K(agnes), sensenova 会自动换算成对应像素尺寸并钳制到4096上限。不填用厂商默认")
    ratio: Optional[str] = Field(default=None, description="宽高比: 1:1/3:4/4:3/16:9/9:16/2:3/3:2/21:9, 与 size 档位配合; 不填时 agnes 用厂商默认(通常1:1), sensenova 比例隐含在换算尺寸里")
    return_base64: bool = Field(default=False, description="是否要求以 Base64 返回产物(文生图)。默认 False=返回公网URL; 设为 True 时产物落盘为会话附件, 不会把大 b64 塞进回复")
    response_format: Optional[str] = Field(default=None, description="输出格式: url 或 b64_json。不填用厂商默认(url)。一般无需显式设置, return_base64 已覆盖常用场景")


class GenerateVideoInput(BaseModel):
    prompt: str = Field(..., min_length=1,
                        description="视频内容描述。写清主体、动作、镜头、风格、声音。参考模式(reference)里用 <Picture N>/<Audio N>/<Video N> 指代素材(从1编号), 如'以 <Picture 1> 的角色风格, 跟随 <Audio 1> 的节奏'")
    model: Optional[str] = Field(default=None, description=MEDIA_VIDEO_MODEL_HINT)
    mode: str = Field(default="t2v",
                      description="生成方式: t2v/text=纯文本生成视频(媒体字段全留空); keyframe=首尾帧控制(给 first_frame 和/或 last_frame); i2v/reference=多模态参考(给 images/audios/videos 至少一类)。默认 t2v")
    image: Optional[str] = Field(default=None,
                                 description="单张参考图(兼容旧 i2v 用法), 等价于 images 只填一张。支持本地路径/attachment_id/公网URL/data URI, 本地图后端自动公网化。与 images 同时给时两者合并")
    images: Optional[List[str]] = Field(default=None,
                                        description="参考图片公网URL列表(reference模式)。多张时 prompt 用 <Picture 1>/<Picture 2> 按序指代。最多8张(flash最多5张), 本地文件路径/attachment_id 会自动公网化")
    first_frame: Optional[str] = Field(default=None,
                                       description="首帧图片(keyframe模式), 成片会以此为真实首帧。支持本地路径/attachment_id/公网URL/data URI, 后端自动公网化; 与 last_frame 至少给一个")
    last_frame: Optional[str] = Field(default=None,
                                      description="尾帧图片(keyframe模式), 成片会以此为真实尾帧。来源同 first_frame; 与 first_frame 至少给一个")
    audios: Optional[List[str]] = Field(default=None,
                                        description="参考音频公网URL列表(reference模式), 最多3段, prompt 用 <Audio N> 指代。需厂商可直连GET的公网地址")
    videos: Optional[List[Dict[str, Any]]] = Field(default=None,
                                                   description="参考视频对象列表(reference模式), 最多1个。每项是一个对象: {url: 公网视频URL(必填), start_seconds: 起始秒(可选, 默认0), require_audio: 是否要求含音轨(可选, 默认false)}。prompt 用 <Video N> 指代; 注意 flash 模型不支持视频参考")
    seconds: Optional[str] = Field(default=None, description="视频时长, 字符串 '4'~'12', 默认 '5'")
    size: Optional[str] = Field(default=None, description="输出分辨率档位: 720P/1080P/1K/2K(flash 仅支持 720P)。不填用厂商默认")
    aspect_ratio: Optional[str] = Field(default=None, description="画幅比例: 21:9/16:9/4:3/1:1/3:4/9:16, 默认 16:9")
    seed: Optional[int] = Field(default=None, description="随机种子, 相同种子提高结果可复现性")
    timeout: int = Field(default=660, ge=120, le=1200,
                         description="视频生成等待上限(秒), 有效范围 120~1200, 默认 660。异步任务含厂商排队+出片, 常需数分钟, 不要调太小否则任务未完成就超时")
