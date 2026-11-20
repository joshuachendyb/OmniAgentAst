# -*- coding: utf-8 -*-
"""媒体生成工具输入模型(generate_image / generate_video) — 小欧 2026-11-20

扁平简单类型(prompt/model/mode 等 str), 无嵌套 BaseModel, 严格 provider 兼容(同 agent_schema 契约)。
"""
from typing import Optional

from pydantic import BaseModel, Field

# 生成模型名提示(写进描述, 不强制 enum——用户可配新模型, 强制 enum 会挡住 OCP)
_MODEL_HINT = "生成模型名(须为已配置且声明对应输出模态的模型, 如 agnes-image-2.1-flash / agnes-video-2.5-flash); 不填则用系统默认生成模型"


class GenerateImageInput(BaseModel):
    prompt: str = Field(..., min_length=1, description="图片内容描述(文本生图提示词), 尽量具体")
    model: Optional[str] = Field(default=None, description=_MODEL_HINT)
    image: Optional[str] = Field(default=None, description="图生图(i2i)的参考图。可传:用户上传图片的本地路径(如 E:\\...\\attachments\\xxx.png)、attachment_id(32位hex)、公网URL、data URI——均支持, 后端自动转为厂商可解析格式; 留空=纯文本生图(t2i)")


class GenerateVideoInput(BaseModel):
    prompt: str = Field(..., min_length=1, description="视频内容描述(文本生视频提示词), 尽量具体")
    model: Optional[str] = Field(default=None, description=_MODEL_HINT)
    mode: str = Field(default="t2v", description="生成方式: t2v=纯文本生视频, i2v=带参考图生视频(需给 image)")
    image: Optional[str] = Field(default=None, description="i2v 的参考图。可传本地路径/attachment_id/公网URL/data URI(后端自动转换); mode=t2v 时留空")
    timeout: int = Field(default=660, ge=120, le=1200,
                         description="视频生成等待上限(秒); 异步任务含排队+出片, 默认660, 别调太小")
