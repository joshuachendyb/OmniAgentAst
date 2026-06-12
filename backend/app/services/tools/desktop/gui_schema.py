# -*- coding: utf-8 -*-
"""
GUI 工具参数 Schema 定义

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional, Literal


class ScreenRecordInput(BaseModel):
    duration: int = Field(..., ge=1, le=300, description="录制时长,单位为秒,最大300秒(5分钟)")
    output_path: Optional[str] = Field(default=None, description="输出文件路径(可选)。不传则保存到系统临时目录如<temp>/screen_record_<时间戳>.mp4")
    fps: int = Field(default=15, ge=1, le=60, description="录制帧率(每秒采集的画面帧数)。帧率越高视频越流畅但文件体积越大。默认15帧/秒,范围1-60")


class OcrInput(BaseModel):
    image_path: str = Field(..., description="图片文件路径。如 D:/images/screenshot.png")
    language: Literal["eng", "chi_sim", "eng+chi_sim"] = Field(default="eng", description="识别语言。eng=英文,chi_sim=简体中文,eng+chi_sim=中英混合。默认eng")


class SendNotificationInput(BaseModel):
    title: str = Field(..., description="通知标题。如 \"任务完成\"、\"提醒\"")
    message: str = Field(..., description="通知内容。通知的详细信息")
    duration: int = Field(default=5, ge=1, le=60, description="显示时长(可选),单位为秒,最大60秒。默认5秒")


__all__ = [
    "ScreenRecordInput",
    "OcrInput",
    "SendNotificationInput",
]
