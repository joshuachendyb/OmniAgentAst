# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-20 - 小欧 - 复核schema docstring规范,NetworkDiagnoseInput保留既有docstring,其余工具默认行为均已在Field中体现,无需新增
# 2026-07-21 - 小欧 - 入参即信任: SearchWebInput.num_results le=50→1000, 支撑LLM指定最多1000条搜索结果
# 2026-07-25 - 小欧 - headers描述精简: 去废词, 名称仅ASCII约束一句话说清
# 2026-07-25 - 小欧 - description去冗余: 10处默认/范围/必填重复移除
# 2026-07-25 - 小欧 - description去冗余: url/body/method/headers/extract_format 参数名自明前缀精简, body去内部细节
# 2026-07-25 - 小欧 - DownloadFileInput.dest 补充路径限制说明(不支持绝对路径/../)
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
        ..., min_length=1, description="请求的目标URL"
    )
    method: Literal["GET", "POST", "PUT", "DELETE", "PATCH"] = Field(
        default="GET", description="HTTP方法,默认GET。支持GET/POST/PUT/DELETE/PATCH"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="请求头,名称仅ASCII,如 {\"Authorization\": \"Bearer token\", \"Content-Type\": \"application/json\"}"
    )
    body: Optional[Dict[str, Any]] = Field(
        default=None, description="JSON请求体(POST/PUT/PATCH/DELETE时使用)"
    )
    timeout: int = Field(
        default=30, ge=1, le=300, description="超时时间(秒)"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理地址"
    )


class DownloadFileInput(BaseModel):
    url: str = Field(
        ..., min_length=1, description="要下载文件的URL"
    )
    dest: Optional[str] = Field(
        default=None, description="文件保存的相对路径(相对于下载目录),仅文件名或子路径(如 file.zip 或 subdir/file.zip),不支持绝对路径或../; 不填则自动从URL提取文件名"
    )
    headers: Optional[Dict[str, str]] = Field(
        default=None, description="请求头,名称仅ASCII,如 {\"Authorization\": \"Bearer token\"}"
    )
    timeout: int = Field(
        default=60, ge=5, le=3600, description="超时时间(秒)"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理地址"
    )


class FetchWebpageInput(BaseModel):
    """获取网页文本内容(默认markdown格式)。当URL指向图片/PDF时自动检测并返回Base64编码数据(不走extract_format设置)"""
    url: str = Field(
        ..., min_length=1, description="网页URL"
    )
    prompt: Optional[str] = Field(
        default=None, description="提取指令。未指定时返回完整页面内容,指定时精准提取"
    )
    extract_format: Literal["markdown", "html", "text"] = Field(
        default="markdown", description="提取格式:推荐用markdown(保留结构)/html(原始)/text(纯文本)。仅对网页文本生效,URL指向图片/PDF时自动返回Base64编码"
    )
    js_render: bool = Field(
        default=False, description="是否启用JS渲染(处理动态页面)"
    )
    timeout: int = Field(
        default=30, ge=1, le=120, description="超时时间(秒)"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理地址,如 http://127.0.0.1:8080"
    )


class SearchWebInput(BaseModel):
    query: str = Field(
        ..., description="搜索查询字符串"
    )
    num_results: int = Field(
        default=10, ge=1, le=1000, description="返回结果数量"
    )
    allowed_domains: Optional[str] = Field(
        default=None, description="允许搜索的域名列表(逗号分隔)"
    )
    blocked_domains: Optional[str] = Field(
        default=None, description="禁止搜索的域名列表(逗号分隔)"
    )
    proxy: Optional[str] = Field(
        default=None, description="代理地址"
    )


class NetworkDiagnoseInput(BaseModel):
    """网络连通性诊断工具
    
    【mode参数】决定诊断类型：
    - ping: ICMP可达性检测(主机级)
    - port: TCP端口检测(服务级)
    
    【使用示例】
    - ping测试 → ping_port(host="8.8.8.8")
    - 端口检测 → ping_port(host="8.8.8.8", mode="port", port=53)
    """
    host: str = Field(
        ..., min_length=1, description="目标主机地址,可以是域名或IP地址,例如 8.8.8.8 或 baidu.com。注意:出于安全考虑,禁止访问内网地址(127.x.x.x/10.x.x.x/172.16-31.x.x/192.168.x.x等)"
    )
    mode: Literal["ping", "port"] = Field(
        default="ping",
        description="诊断模式。ping=ICMP可达性检测, port=TCP端口检测"
    )
    port: Optional[int] = Field(
        default=None,
        ge=1, le=65535,
        description="目标端口号(mode=port时必填;mode=ping时严禁传入)"
    )
    count: int = Field(
        default=4, ge=1, le=20, description="ping请求次数"
    )
    timeout: int = Field(
        default=5, ge=1, le=30, description="超时时间(秒)"
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
