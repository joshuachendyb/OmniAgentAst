# -*- coding: utf-8 -*-
"""
Network 工具参数 Schema 定义

【创建时间】2026-04-29 小沈
【设计依据】按2026-04-29新增工具规范流程

职责：
定义 network 工具的 Pydantic 模型。

Author: 小沈 - 2026-04-29
"""

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal


class HttpRequestInput(BaseModel):
    """http_request 工具的输入参数"""
    url: str = Field(
        ..., description="请求URL（必填），例如 https://api.example.com/data"
    )
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"] = Field(
        default="GET", description="HTTP请求方法，默认为GET"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="请求头字典，例如 {\"Authorization\": \"Bearer token\"}"
    )
    params: Optional[Dict[str, str]] = Field(
        default=None, description="URL查询参数（Query String），例如 {\"page\": 1, \"limit\": 20}"
    )
    body: Optional[Any] = Field(
        default=None, description="请求体内容，支持字符串、字典或列表。当method为POST/PUT/PATCH时使用"
    )
    json_body: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON请求体（自动设置Content-Type为application/json）。当method为POST/PUT/PATCH时使用，优先于body"
    )
    timeout: int = Field(
        default=30, ge=1, le=300, description="超时时间（秒），默认为30秒，最大300秒"
    )
    follow_redirects: bool = Field(
        default=True, description="是否跟随重定向，默认为True"
    )


class DownloadFileInput(BaseModel):
    """download_file 工具的输入参数"""
    url: str = Field(
        ..., description="要下载文件的URL（必填），例如 https://example.com/file.zip"
    )
    destination_path: str = Field(
        ..., description="文件保存的完整路径（必填），例如 D:/Downloads/file.zip"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="请求头字典，例如 {\"Authorization\": \"Bearer token\"}"
    )
    timeout: int = Field(
        default=300, ge=1, le=3600, description="下载超时时间（秒），默认为300秒，最大3600秒"
    )
    chunk_size: int = Field(
        default=8192, ge=1024, le=1048576, description="下载分块大小（字节），默认8192字节"
    )


__all__ = [
    "HttpRequestInput",
    "DownloadFileInput",
]
