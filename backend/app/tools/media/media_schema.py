# -*- coding: utf-8 -*-
"""媒体生成工具输入模型(generate_image / generate_video) — 小欧 2026-11-20

扁平简单类型(prompt/model/mode 等 str), 无嵌套 BaseModel, 严格 provider 兼容(同 agent_schema 契约)。
编辑历史: 2026-11-20 小欧 话术审查整改: model 字段改用按模态拆分的 hint(防传错模型); prompt 去"尽量具体"改列具体要素;
  mode/image 讲清 t2i/i2i/t2v/i2v 触发条件(留空 vs 传值); image 四种来源完整列出; timeout 补范围120~1200与"别调太小"原因; 纯话术改动零行为变更。
"""
from typing import Optional

from pydantic import BaseModel, Field

# 模型名话术从工具层常量引入(按工具拆开, 避免传错模态模型); 写进描述不强制 enum, 用户可配新模型 — 小欧-2026-11-20
from app.tools.tool_constants import MEDIA_IMAGE_MODEL_HINT, MEDIA_VIDEO_MODEL_HINT


class GenerateImageInput(BaseModel):
    prompt: str = Field(..., min_length=1, description="图片内容描述(文本生成图像提示词)。写清主体、风格、场景、光线等要素, 越具体出图越贴合; 图生图(i2i)时用来描述想要的改动(如'改成蓝色')")
    model: Optional[str] = Field(default=None, description=MEDIA_IMAGE_MODEL_HINT)
    image: Optional[str] = Field(default=None, description="图生图(i2i)参考图, 四种都支持: ①用户上传图的本地路径(如会话 attachments 目录下的 xxx.png) ②attachment_id(32位十六进制) ③公网图片URL ④data URI(data:image/...;base64,...)。留空=纯文本生成图像(t2i); 传值=基于这张图编辑(i2i)。后端自动归一为厂商可解析格式, 本地图无需公网图床")


class GenerateVideoInput(BaseModel):
    prompt: str = Field(..., min_length=1, description="视频内容描述(文本生成视频提示词)。写清主体、动作、镜头、风格等要素, 越具体出片越贴合; 图生视频(i2v)时用来描述画面如何动起来(如'镜头缓慢推近')")
    model: Optional[str] = Field(default=None, description=MEDIA_VIDEO_MODEL_HINT)
    mode: str = Field(default="t2v", description="生成方式二选一: t2v=纯文本生成视频(此时 image 留空); i2v=图生视频(必须给 image 作为首帧参考图)。默认 t2v")
    image: Optional[str] = Field(default=None, description="图生视频(i2v)的参考图(首帧), 四种都支持: ①本地路径(如会话 attachments 目录下的 xxx.png) ②attachment_id(32位十六进制) ③公网图片URL ④data URI(data:image/...;base64,...)。本地路径/attachment_id/data URI 后端会自动上传到临时图床换成公网URL(生成视频厂商只认公网URL), 本地图也能做; mode=t2v 时必须留空")
    timeout: int = Field(default=660, ge=120, le=1200,
                         description="视频生成等待上限(秒), 有效范围 120~1200, 默认 660。异步任务含厂商排队+出片, 常需数分钟, 不要调太小否则任务未完成就超时")
