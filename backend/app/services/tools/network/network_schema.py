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
    """http_request 工具的输入参数 — 小沈 2026-05-19 精简11→8"""
    url: str = Field(
        ..., description="请求的目标URL，如 https://api.example.com/data"
    )
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"] = Field(
        default="GET", description="HTTP方法，默认GET。Agent根据用户意图智能推演"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="请求头。Agent优先自动注入Authorization，LLM传入仅作补充"
    )
    params: Optional[Dict[str, str]] = Field(
        default=None, description="URL查询参数，如 {\"page\": 1, \"limit\": 20}"
    )
    json_body: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON请求体(POST/PUT/PATCH时使用)，自动设Content-Type为application/json"
    )
    timeout: int = Field(
        default=30000, ge=1000, le=600000, description="超时毫秒数，默认30000(30秒)"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理服务器地址。Agent三步走：1.直连 2.环境变量代理 3.报错"
    )
    retry: int = Field(
        default=3, ge=0, le=10, description="重试次数，默认3。Agent执行指数退避重试(针对429/5xx)"
    )


class DownloadFileInput(BaseModel):
    """download_file 工具的输入参数 — 小沈 2026-05-19 精简7→5"""
    url: str = Field(
        ..., description="要下载文件的URL，如 https://example.com/file.zip"
    )
    destination_path: str = Field(
        ..., description="文件保存的完整路径，如 D:/Downloads/file.zip"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="请求头，如 {\"Authorization\": \"Bearer token\"}"
    )
    timeout: int = Field(
        default=300000, ge=1000, le=3600000, description="下载超时毫秒数，默认300000(5分钟)"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理服务器地址。Agent三步走：1.直连 2.环境变量代理 3.报错"
    )


class FetchWebpageInput(BaseModel):
    """fetch_webpage 工具的输入参数 — 小沈 2026-05-19 精简8→7"""
    url: str = Field(
        ..., description="网页URL，如 https://example.com/page"
    )
    prompt: Optional[str] = Field(
        default=None, description="提取指令。未指定时返回完整页面内容，指定时精准提取"
    )
    extract_format: Literal["markdown", "html", "text"] = Field(
        default="markdown", description="提取格式：markdown(默认)/html/text"
    )
    js_render: bool = Field(
        default=False, description="是否启用JS渲染(Playwright)。SPA动态页面需设为true"
    )
    timeout: int = Field(
        default=30000, ge=1000, le=120000, description="超时毫秒数，默认30000(30秒)"
    )
    max_tokens: int = Field(
        default=8000, ge=500, le=32000, description="最大返回Token数，默认8000"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理服务器地址。Agent三步走：1.直连 2.环境变量代理 3.报错"
    )


class SearchWebInput(BaseModel):
    """search_web 工具的输入参数 — 小沈 2026-05-19 精简7→5"""
    query: str = Field(
        ..., description="搜索查询字符串，支持中英文"
    )
    allowed_domains: Optional[List[str]] = Field(
        default=None, description="仅搜索这些域名，如 [\"docs.python.org\"]"
    )
    blocked_domains: Optional[List[str]] = Field(
        default=None, description="排除这些域名。Agent维护全局黑名单默认自动注入"
    )
    num_results: int = Field(
        default=10, ge=1, le=50, description="返回结果数量，默认10"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理服务器地址。Agent三步走：1.直连 2.环境变量代理 3.报错"
    )


class NetworkDiagnoseInput(BaseModel):
    """network_diagnose 工具的输入参数 - 小沈 2026-05-17
    合并 ping + port_check
    """
    host: str = Field(
        ..., description="目标主机地址（必填），可以是域名或IP地址，例如 8.8.8.8 或 baidu.com"
    )
    mode: Literal["ping", "port"] = Field(
        default="ping",
        description="诊断模式。ping=ICMP可达性检测(主机级), port=TCP端口检测(服务级)"
    )
    port: Optional[int] = Field(
        default=None,
        ge=1, le=65535,
        description="目标端口号。mode='port'时必填(范围1-65535)，mode='ping'时忽略"
    )
    count: int = Field(
        default=4, ge=1, le=20, description="ping次数。mode='ping'时生效，默认4次，最大20次"
    )
    timeout: int = Field(
        default=5, ge=1, le=30, description="超时秒数，默认5秒"
    )


__all__ = [
    "HttpRequestInput",
    "DownloadFileInput",
    "FetchWebpageInput",
    "SearchWebInput",
    "NetworkDiagnoseInput",
]
