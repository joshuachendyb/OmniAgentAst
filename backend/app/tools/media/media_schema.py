# -*- coding: utf-8 -*-
"""媒体生成工具输入模型(generate_image / generate_video) — 小欧 2026-11-20

扁平简单类型(prompt/model/mode 等 str), 无嵌套 BaseModel, 严格 provider 兼容(同 agent_schema 契约)。
"""
from typing import Optional

from pydantic import BaseModel, Field

# 模型名提示从工具层常量引入(三堂会审归位); 写进描述不强制 enum, 用户可配新模型 — 小欧-2026-11-20
from app.tools.tool_constants import MEDIA_MODEL_HINT


class GenerateImageInput(BaseModel):
    prompt: str = Field(..., min_length=1, description="图片内容描述(文本生图提示词), 尽量具体")
    model: Optional[str] = Field(default=None, description=MEDIA_MODEL_HINT)
    image: Optional[str] = Field(default=None, description="图生图(i2i)的参考图。可传:用户上传图片的本地路径(如 E:\\...\\attachments\\xxx.png)、attachment_id(32位hex)、公网URL、data URI——均支持, 后端自动转为厂商可解析格式; 留空=纯文本生图(t2i)")


class GenerateVideoInput(BaseModel):
    prompt: str = Field(..., min_length=1, description="视频内容描述(文本生视频提示词), 尽量具体")
    model: Optional[str] = Field(default=None, description=MEDIA_MODEL_HINT)
    mode: str = Field(default="t2v", description="生成方式: t2v=纯文本生视频, i2v=带参考图生视频(需给 image)")
    image: Optional[str] = Field(default=None, description="i2v 的参考图。可传本地路径/attachment_id/公网URL/data URI——本地图/附件/ data URI 后端会自动上传到临时图床转成公网 URL(生视频 i2v 厂商只认公网 URL); mode=t2v 时留空")
    timeout: int = Field(default=660, ge=120, le=1200,
                         description="视频生成等待上限(秒); 异步任务含排队+出片, 默认660, 别调太小")
