# -*- coding: utf-8 -*-
"""
GUI 工具参数 Schema 定义

【创建时间】2026-05-02 小沈
【2026-05-19 小沈】删除10个旧Schema(已合入desktop_schema.py统一入口)，仅保留3个GUI工具Schema

保留的工具Schema：
- ScreenRecordInput — screen_record
- OcrInput — ocr
- SendNotificationInput — send_notification

Author: 小沈 - 2026-05-02
"""

from pydantic import BaseModel, Field
from typing import Optional


class ScreenRecordInput(BaseModel):
    """screen_record 工具的输入参数"""
    duration: int = Field(..., description="录制时长，单位为秒")
    output_path: Optional[str] = Field(default=None, description="输出文件路径（可选）")
    fps: Optional[int] = Field(default=15, description="帧率。默认为15")


class OcrInput(BaseModel):
    """ocr 工具的输入参数"""
    image_path: str = Field(..., description="图片文件路径。如 D:/images/screenshot.png")
    language: Optional[str] = Field(default="eng", description="识别语言。可选值：eng/chi_sim/eng+chi_sim。默认为eng")


class SendNotificationInput(BaseModel):
    """send_notification 工具的输入参数"""
    title: str = Field(..., description="通知标题。如 \"任务完成\"、\"提醒\"")
    message: str = Field(..., description="通知内容。通知的详细信息")
    duration: Optional[int] = Field(default=5, description="显示时长（可选），单位为秒。默认5秒")


__all__ = [
    "ScreenRecordInput",
    "OcrInput",
    "SendNotificationInput",
]
