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
    """http_request 工具的输入参数 - 小沈 2026-05-03 补齐文档参数+timeout改毫秒"""
    url: str = Field(
        ..., description="请求的目标 URL，必须是完全有效的 URL（如 https://api.example.com/data）"
    )
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"] = Field(
        default="GET", description="HTTP方法。由 Agent 根据用户意图智能推演：默认 GET，若有 body 或意图为提交/更新则自动设为 POST/PUT/DELETE/PATCH"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="业务请求头（可选）。Agent 优先从安全上下文自动注入 Authorization，LLM 传入的 headers 仅作补充，严禁覆盖安全头"
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
        default=30000, ge=1000, le=600000, description="超时毫秒数，默认30000（30秒），最大600000（10分钟）。由 Agent 根据请求类型智能调整 - 小沈 2026-05-03"
    )
    verify_ssl: bool = Field(
        default=True, description="是否验证 SSL 证书。由 Agent 根据环境智能判断，仅内网测试环境可设为 false"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理服务器地址。Agent 执行三步走策略：1.优先直连尝试；2.失败则读取环境变量代理重试；3.均失败则报错"
    )
    retry: int = Field(
        default=3, ge=0, le=10, description="重试次数。Agent 执行指数退避重试（针对 429/5xx），重试耗尽后抛出明确错误"
    )
    follow_redirects: bool = Field(
        default=True, description="是否跟随重定向。若 Agent 检测到认证死循环，自动设为 false 并报错"
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
        default=30000, ge=1000, le=120000, description="超时毫秒数，默认30000（30秒），最大120000（2分钟）。Agent根据域名响应历史动态调整 - 小沈 2026-05-03"
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


class PingInput(BaseModel):
    """ping 工具的输入参数 - 小沈 2026-05-02"""
    host: str = Field(
        ..., description="目标主机地址（必填），可以是域名或IP地址，例如 8.8.8.8 或 www.baidu.com"
    )
    count: int = Field(
        default=4, ge=1, le=10, description="发送ping包数量，默认4次，最多10次"
    )
    timeout: int = Field(
        default=5, ge=1, le=30, description="每次ping的超时时间（秒），默认5秒，最大30秒"
    )


class PortCheckInput(BaseModel):
    """port_check 工具的输入参数 - 小沈 2026-05-02"""
    host: str = Field(
        ..., description="目标主机地址（必填），可以是域名或IP地址，例如 127.0.0.1 或 localhost"
    )
    port: int = Field(
        ..., ge=1, le=65535, description="要检查的端口号（必填），范围 1-65535，例如 80、443、8080"
    )
    timeout: int = Field(
        default=3, ge=1, le=10, description="连接超时时间（秒），默认3秒，最大10秒"
    )


__all__ = [
    "HttpRequestInput",
    "DownloadFileInput",
    "FetchWebpageInput",
    "SearchWebInput",
    "PingInput",
    "PortCheckInput",
]
