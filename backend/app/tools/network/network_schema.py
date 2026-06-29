# -*- coding: utf-8 -*-
"""
Network Schema - 网络工具参数模型

【Schema Docstring 规范】小健 2026-06-18
一般情况下，严禁给Schema类加docstring。
仅在以下情况可以添加：
1. 函数使用过于复杂，需要详细说明
2. 多action的tool，需要说明不同action的用法
3. 添加的是tool描述的增强信息，不是冗余信息

禁止：
- 重复register.py中的描述
- 添加过于冗长的说明
- 添加与参数无关的内容

Author: 小沈 - 2026-04-29
"""

from pydantic import BaseModel, Field, model_validator
from typing import Optional, Dict, Any, List, Literal


class HttpRequestInput(BaseModel):
    url: str = Field(
        ..., min_length=1, description="请求的目标URL,如 https://api.example.com/data"
    )
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field(
        default="GET", description="HTTP方法,默认GET。支持GET/POST/PUT/DELETE/PATCH"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="请求头字典,如 {\"Authorization\": \"Bearer token\", \"Content-Type\": \"application/json\"}"
    )
    body: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON请求体(POST/PUT/PATCH/DELETE时使用),自动设Content-Type为application/json"
    )
    timeout: int = Field(
        default=30, ge=1, le=300, description="超时时间(秒),默认30,范围1-300"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理地址,如 http://127.0.0.1:8080"
    )


class DownloadFileInput(BaseModel):
    url: str = Field(
        ..., min_length=1, description="要下载文件的URL,如 https://example.com/file.zip"
    )
    destination_path: str = Field(
        ..., min_length=1, description="文件保存的相对路径(相对于下载目录),如 file.zip 或 subdir/file.zip"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="请求头字典,如 {\"Authorization\": \"Bearer token\"}"
    )
    timeout: int = Field(
        default=60, ge=5, le=3600, description="超时时间(秒),默认60,范围5-3600"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理地址,如 http://127.0.0.1:8080"
    )


class FetchWebpageInput(BaseModel):
    url: str = Field(
        ..., min_length=1, description="网页URL,如 https://example.com/page"
    )
    prompt: Optional[str] = Field(
        default=None, description="提取指令。未指定时返回完整页面内容,指定时精准提取"
    )
    extract_format: Literal["markdown", "html", "text"] = Field(
        default="markdown", description="提取格式:推荐用markdown(保留结构)/html(原始)/text(纯文本)"
    )
    js_render: bool = Field(
        default=False, description="是否启用JS渲染(处理动态页面),默认false"
    )
    timeout: int = Field(
        default=30, ge=1, le=120, description="超时时间(秒),默认30,范围1-120"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理地址,如 http://127.0.0.1:8080"
    )


class SearchWebInput(BaseModel):
    query: str = Field(
        ..., description="搜索查询字符串,支持中英文"
    )
    num_results: int = Field(
        default=10, ge=1, le=50, description="返回结果数量,默认10,范围1-50"
    )
    allowed_domains: Optional[str] = Field(
        default=None, description="允许搜索的域名列表(逗号分隔),如 'example.com,github.com'"
    )
    blocked_domains: Optional[str] = Field(
        default=None, description="禁止搜索的域名列表(逗号分隔),如 'pornhub.com'"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理地址,如 http://127.0.0.1:8080"
    )


class NetworkDiagnoseInput(BaseModel):
    """网络连通性诊断工具
    
    【mode参数】决定诊断类型：
    - ping: ICMP可达性检测(主机级)
    - port: TCP端口检测(服务级)
    
    【使用示例】
    - ping测试 → network_diagnose(host="8.8.8.8")
    - 端口检测 → network_diagnose(host="8.8.8.8", mode="port", port=53)
    """
    host: str = Field(
        ..., min_length=1, description="目标主机地址(必填),可以是域名或IP地址,例如 8.8.8.8 或 baidu.com"
    )
    mode: Literal["ping", "port"] = Field(
        default="ping",
        description="诊断模式。ping=ICMP可达性检测(主机级), port=TCP端口检测(服务级)"
    )
    port: Optional[int] = Field(
        default=None,
        ge=1, le=65535,
        description="目标端口号(mode=port时必填,范围1-65535;mode=ping时严禁传入)"
    )
    count: int = Field(
        default=4, ge=1, le=20, description="ping请求次数,默认4,范围1-20"
    )
    timeout: int = Field(
        default=5, ge=1, le=30, description="超时时间(秒),默认5,范围1-30"
    )

    @model_validator(mode="after")
    def _check_port_for_mode(self):
        if self.mode == "port" and self.port is None:
            raise ValueError("mode=port时port必填")
        if self.mode == "ping" and self.port is not None:
            raise ValueError("mode=ping时严禁传入port")
        return self


__all__ = [
    "HttpRequestInput",
    "DownloadFileInput",
    "FetchWebpageInput",
    "SearchWebInput",
    "NetworkDiagnoseInput",
]
