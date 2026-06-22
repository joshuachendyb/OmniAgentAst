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

from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List, Literal


class HttpRequestInput(BaseModel):
    url: str = Field(
        ..., description="请求的目标URL,如 https://api.example.com/data"
    )
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"] = Field(
        default="GET", description="HTTP方法,默认GET"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="请求头字典,如 {\"Authorization\": \"Bearer token\", \"Content-Type\": \"application/json\"}"
    )
    params: Optional[Dict[str, str]] = Field(
        default=None, description="URL查询参数,如 {\"page\": \"1\", \"limit\": \"20\"}"
    )
    json_body: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON请求体(POST/PUT/PATCH时使用),自动设Content-Type为application/json"
    )


class DownloadFileInput(BaseModel):
    url: str = Field(
        ..., description="要下载文件的URL,如 https://example.com/file.zip"
    )
    destination_path: str = Field(
        ..., description="文件保存的完整路径,如 D:/Downloads/file.zip"
    )


class FetchWebpageInput(BaseModel):
    url: str = Field(
        ..., description="网页URL,如 https://example.com/page"
    )
    prompt: Optional[str] = Field(
        default=None, description="提取指令。未指定时返回完整页面内容,指定时精准提取"
    )
    extract_format: Literal["markdown", "html", "text"] = Field(
        default="markdown", description="提取格式:markdown(默认)/html/text"
    )


class SearchWebInput(BaseModel):
    query: str = Field(
        ..., description="搜索查询字符串,支持中英文"
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
        ..., description="目标主机地址(必填),可以是域名或IP地址,例如 8.8.8.8 或 baidu.com"
    )
    mode: Literal["ping", "port"] = Field(
        default="ping",
        description="诊断模式。ping=ICMP可达性检测(主机级), port=TCP端口检测(服务级)"
    )
    port: Optional[int] = Field(
        default=None,
        ge=1, le=65535,
        description="目标端口号(mode=port时【必填】,范围1-65535;mode=ping时忽略)"
    )


__all__ = [
    "HttpRequestInput",
    "DownloadFileInput",
    "FetchWebpageInput",
    "SearchWebInput",
    "NetworkDiagnoseInput",
]
