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


class FetchWebpageInput(BaseModel):
    """fetch_webpage 工具的输入参数"""
    url: str = Field(
        ..., description="完全有效的URL（如 https://example.com/page）。必须是可访问的网页地址"
    )
    prompt: Optional[str] = Field(
        default=None, description="提取指令（可选）。默认提取页面核心内容、关键数据和摘要。LLM仅在需精准提取时传参"
    )
    extract_format: Literal["markdown", "html", "text"] = Field(
        default="markdown", description="提取格式。可选值：markdown（默认，LLM处理效率高）、html（保留完整DOM结构）、text（纯文本）"
    )
    js_render: bool = Field(
        default=False, description="是否启用JS渲染（Headless浏览器）。默认false（静态抓取）。若返回内容为空或检测到SPA特征，Agent自动重试true"
    )
    timeout: int = Field(
        default=30, ge=5, le=120, description="超时秒数。默认30秒。Agent根据域名响应历史动态调整：慢站自动延长至60秒"
    )
    max_tokens: int = Field(
        default=8000, ge=500, le=32000, description="最大返回Token数。默认8000。Agent按语义块边界智能截断，确保返回完整结构化文本"
    )
    user_agent: Optional[str] = Field(
        default=None, description="自定义User-Agent。默认null，由Agent自动注入随机化标准浏览器UA"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理服务器地址。Agent执行三步走策略：1.优先直连尝试；2.失败则读取环境变量代理重试；3.均失败则报错"
    )


class SearchWebInput(BaseModel):
    """search_web 工具的输入参数"""
    query: str = Field(
        ..., description="搜索查询字符串，至少2个字符。支持中英文搜索关键词"
    )
    allowed_domains: Optional[List[str]] = Field(
        default=None, description="包含的域名数组（可选）。若LLM未传且用户意图明确，Agent自动解析并填入"
    )
    blocked_domains: Optional[List[str]] = Field(
        default=None, description="排除的域名数组（可选）。Agent维护全局黑名单（广告站、内容农场），默认自动注入"
    )
    num_results: int = Field(
        default=10, ge=1, le=50, description="返回结果数量。默认10。概览类意图设5，深度调研类意图设20"
    )
    time_range: Literal["any", "d", "w", "m", "y"] = Field(
        default="any", description="时间范围。可选值：any（不限）、d（一天内）、w（一周内）、m（一月内）、y（一年内）"
    )
    language: Optional[str] = Field(
        default=None, description="搜索语言。默认匹配当前会话语言。Agent根据query语种自动切换"
    )
    safe_search: Literal["strict", "moderate", "off"] = Field(
        default="moderate", description="安全搜索级别。可选值：strict（严格）、moderate（中等）、off（关闭）"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理服务器地址。Agent执行三步走策略：1.优先直连尝试；2.失败则读取环境变量代理重试；3.均失败则报错"
    )


__all__ = [
    "HttpRequestInput",
    "DownloadFileInput",
    "FetchWebpageInput",
    "SearchWebInput",
]
