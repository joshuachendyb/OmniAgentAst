# Network HTTP 客户端 SDK 设计方案

**创建时间**: 2026-05-29 13:24:47
**版本**: v1.0
**设计人**: 小沈
**设计性质**: 全新设计（不参考当前代码，从零设计 SDK）

---

## 版本历史

| 版本 | 时间 | 签名 | 更新内容 |
|------|------|------|---------|
| v1.0 | 2026-05-29 13:24:47 | 小沈 | 初始版本：完整需求说明 + 详细设计 |

---

## 一、需求说明

### 1.1 业务背景

Agent 系统中，network tools 模块需要调用用户指定的任意 HTTP 端点（下载文件、抓取网页、搜索等）。当前存在以下问题：

**问题一：5 个函数各自创建 httpx.AsyncClient，无连接池复用。** 每次请求创建/销毁客户端，TCP 握手开销白白浪费。

**问题二：代理配置 4 处重复解析，行为不一致。** 有的用 `_resolve_proxy()`，有的自己内联写 env-var 兜底，有的直接传 proxy 参数不做兜底。

**问题三：超时配置混乱。** 5 个函数各自硬编码超时值，没有集中管理。

**根本原因**：没有一个统一的 HTTP 客户端 SDK。每个函数各自创建客户端，各自处理代理和超时。

### 1.2 SDK 定位

**Network HTTP 客户端 SDK**，是一个**基础模块**，被 network tools 调用：

```
调用方                          SDK
─────────────                ─────────
http_request        ──────→   HTTPClientSDK
download_file       ──────→   HTTPClientSDK
fetch_webpage       ──────→   HTTPClientSDK
_search_mcp_engine  ──────→   HTTPClientSDK
_search_bing        ──────→   HTTPClientSDK
```

**核心职责**：

1. **创建 HTTP 客户端** — 统一入口，连接池、代理、超时集中管理
2. **发送请求** — GET / POST / DELETE，支持流式下载
3. **代理统一** — 一处解析，全局生效
4. **生命周期管理** — 调用方用 `async with` 管理，自动关闭

**明确不包括**：

**一、不处理 LLM 调用。** LLM 调用有独立的 SDK（LLM Client SDK）。

**二、不做请求缓存。** 不缓存 HTTP 响应。

**三、不做请求限流。** 不限制调用频率。

**四、不做重试。** 重试由调用方自己处理（或走统一 RetryEngine）。

**五、不改变 API 接口。** 不对外暴露新的 REST 端点。

### 1.3 使用场景

| 场景 | 调用方 | 触发条件 | 涉及 API |
|------|--------|---------|---------|
| **SC-01 HTTP 请求** | network_tools | Agent 执行网络操作 | `request()` |
| **SC-02 文件下载** | network_tools | Agent 下载文件 | `download()` |
| **SC-03 网页抓取** | network_tools | Agent 抓取网页内容 | `get()` |
| **SC-04 搜索引擎** | network_tools | Agent 搜索 MCP/Bing | `get()` / `post()` |

### 1.4 功能需求

#### FR-01 创建 HTTP 客户端

| 项目 | 规格 |
|------|------|
| **标识** | FR-01 |
| **名称** | 创建 HTTP 客户端 |
| **输入** | timeout（超时秒数）、proxy（代理地址，可选）、verify_ssl（SSL 验证）、follow_redirects（跟随重定向） |
| **输出** | `HTTPClient` 上下文管理器 |
| **行为** | 统一解析代理（proxy > HTTPS_PROXY > HTTP_PROXY > None），统一连接池（max=100, keepalive=20），返回 async with 上下文管理器 |
| **异常** | 无（纯创建函数） |
| **使用场景** | SC-01 ~ SC-04 |

#### FR-02 发送请求

| 项目 | 规格 |
|------|------|
| **标识** | FR-02 |
| **名称** | 发送 HTTP 请求 |
| **输入** | method（GET/POST/DELETE 等）、url、headers（可选）、data（可选）、json（可选） |
| **输出** | httpx.Response |
| **行为** | 发送指定方法的 HTTP 请求，返回响应对象 |
| **异常** | 网络错误 → 抛出异常；HTTP 错误 → 抛出异常 |
| **使用场景** | SC-01, SC-03, SC-04 |

#### FR-03 文件下载

| 项目 | 规格 |
|------|------|
| **标识** | FR-03 |
| **名称** | 下载文件 |
| **输入** | url、save_path（保存路径）、chunk_size（分块大小，可选） |
| **输出** | 下载的字节数 |
| **行为** | 流式下载文件到指定路径，支持进度回调 |
| **异常** | 网络错误 → 抛出异常；磁盘错误 → 抛出异常 |
| **使用场景** | SC-02 |

#### FR-04 代理统一解析

| 项目 | 规格 |
|------|------|
| **标识** | FR-04 |
| **名称** | 代理统一解析 |
| **输入** | proxy 参数（可选） |
| **输出** | 代理 URL 或 None |
| **行为** | 优先级：proxy 参数 > HTTPS_PROXY 环境变量 > HTTP_PROXY 环境变量 > None |
| **异常** | 无 |
| **使用场景** | SC-01 ~ SC-04 |

### 1.5 非功能需求

| 需求 | 说明 | 指标 |
|------|------|------|
| **连接池复用** | 客户端使用连接池，避免每次请求重建 TCP 连接 | max_connections=100, max_keepalive=20 |
| **代理统一** | 所有 HTTP 调用走统一代理解析 | 一处修改全局生效 |
| **超时可控** | 每类调用有独立超时配置，集中管理 | 默认 30s |
| **零破坏性** | 现有网络工具功能不变 | 零破坏性变更 |

### 1.6 命名约定

| 项目 | 命名 | 说明 |
|------|------|------|
| SDK 模块 | `app/services/tools/network/http_client_sdk.py` | Network HTTP 客户端 SDK |
| 客户端类 | `HTTPClient` | HTTP 客户端实例（上下文管理器） |
| 工厂函数 | `create_http_client()` | 创建客户端的唯一入口 |

---

## 二、SDK API 设计

### 2.1 创建客户端

```python
from app.services.tools.network.http_client_sdk import create_http_client

# 作为上下文管理器使用
async with create_http_client(timeout_sec=30, proxy="http://127.0.0.1:7890") as client:
    response = await client.get("https://example.com")
    print(response.text)
```

### 2.2 发送请求

```python
async with create_http_client() as client:
    # GET
    response = await client.get("https://api.example.com/data")

    # POST JSON
    response = await client.post("https://api.example.com/data", json={"key": "value"})

    # POST form
    response = await client.post("https://api.example.com/upload", data=b"binary data")

    # DELETE
    response = await client.delete("https://api.example.com/resource/123")
```

### 2.3 文件下载

```python
async with create_http_client() as client:
    bytes_downloaded = await client.download(
        url="https://example.com/large-file.zip",
        save_path="/tmp/file.zip",
        chunk_size=8192,
    )
    print(f"下载了 {bytes_downloaded} 字节")
```

### 2.4 指定代理

```python
# 方式1：参数指定
async with create_http_client(proxy="http://127.0.0.1:7890") as client:
    response = await client.get("https://example.com")

# 方式2：环境变量自动读取（HTTPS_PROXY / HTTP_PROXY）
async with create_http_client() as client:
    response = await client.get("https://example.com")
```

---

## 三、详细设计

### 3.1 模块结构

```
app/services/tools/network/
├── http_client_sdk.py   # Network HTTP 客户端 SDK（新建）
├── network_tools.py     # 网络工具（改造，使用 SDK）
└── network_helper.py    # 辅助函数（删除 _create_http_client 死代码）
```

### 3.2 http_client_sdk.py 设计

```python
"""
Network HTTP 客户端 SDK
Author: 小沈 - 2026-05-29

基础模块，被 network tools 调用。
只处理任意 HTTP 端点，不处理 LLM 调用。
"""

import os
from typing import Any, AsyncGenerator, Dict, Optional, Union

import httpx


# 集中配置
DEFAULT_TIMEOUT_SEC = 30.0
DEFAULT_MAX_CONNECTIONS = 100
DEFAULT_MAX_KEEPALIVE = 20


def resolve_proxy(proxy: Optional[str] = None) -> Optional[str]:
    """
    统一代理解析

    优先级：proxy参数 > HTTPS_PROXY环境变量 > HTTP_PROXY环境变量
    """
    return proxy or os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")


class HTTPClient:
    """HTTP 客户端实例（上下文管理器）"""

    def __init__(
        self,
        timeout_sec: float = DEFAULT_TIMEOUT_SEC,
        proxy: Optional[str] = None,
        verify_ssl: bool = True,
        follow_redirects: bool = True,
    ):
        proxy_url = resolve_proxy(proxy)
        limits = httpx.Limits(
            max_connections=DEFAULT_MAX_CONNECTIONS,
            max_keepalive_connections=DEFAULT_MAX_KEEPALIVE,
        )
        timeout = httpx.Timeout(timeout_sec, connect=min(timeout_sec, 10.0))
        self._client = httpx.AsyncClient(
            verify=verify_ssl,
            timeout=timeout,
            limits=limits,
            follow_redirects=follow_redirects,
            proxy=proxy_url if proxy_url else None,
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    async def get(self, url: str, **kwargs) -> httpx.Response:
        """发送 GET 请求"""
        return await self._client.get(url, **kwargs)

    async def post(self, url: str, **kwargs) -> httpx.Response:
        """发送 POST 请求"""
        return await self._client.post(url, **kwargs)

    async def delete(self, url: str, **kwargs) -> httpx.Response:
        """发送 DELETE 请求"""
        return await self._client.delete(url, **kwargs)

    async def request(self, method: str, url: str, **kwargs) -> httpx.Response:
        """发送任意方法的 HTTP 请求"""
        return await self._client.request(method, url, **kwargs)

    async def download(
        self,
        url: str,
        save_path: str,
        chunk_size: int = 8192,
    ) -> int:
        """
        流式下载文件

        Args:
            url: 下载地址
            save_path: 保存路径
            chunk_size: 分块大小

        Returns:
            下载的字节数
        """
        bytes_downloaded = 0
        async with self._client.stream("GET", url) as response:
            response.raise_for_status()
            with open(save_path, "wb") as f:
                async for chunk in response.aiter_bytes(chunk_size):
                    f.write(chunk)
                    bytes_downloaded += len(chunk)
        return bytes_downloaded


def create_http_client(
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
    proxy: Optional[str] = None,
    verify_ssl: bool = True,
    follow_redirects: bool = True,
) -> HTTPClient:
    """
    创建 HTTP 客户端 — 唯一入口

    Args:
        timeout_sec: 超时秒数，默认 30
        proxy: 代理地址（可选）。None 时从环境变量读取
        verify_ssl: 是否验证 SSL 证书，默认 True
        follow_redirects: 是否跟随重定向，默认 True

    Returns:
        HTTPClient 上下文管理器

    使用方式：
        async with create_http_client(timeout_sec=30) as client:
            response = await client.get("https://example.com")
    """
    return HTTPClient(
        timeout_sec=timeout_sec,
        proxy=proxy,
        verify_ssl=verify_ssl,
        follow_redirects=follow_redirects,
    )
```

### 3.3 调用方改造要点

| 函数 | 改造前 | 改造后 |
|------|--------|--------|
| `http_request` | `async with httpx.AsyncClient(timeout=..., proxy=_resolve_proxy(proxy))` | `async with create_http_client(timeout_sec, proxy) as client:` |
| `download_file` | `async with httpx.AsyncClient(...)` + 内联代理解析 | `async with create_http_client(timeout, proxy) as client:` + `client.download()` |
| `fetch_webpage` | `async with httpx.AsyncClient(...)` + 直接传 proxy | `async with create_http_client(timeout, proxy) as client:` |
| `_search_mcp_engine` | `async with httpx.AsyncClient(...)` + 直接传 proxy | `async with create_http_client(25.0, proxy) as client:` |
| `_search_bing` | `async with httpx.AsyncClient(...)` + 直接传 proxy | `async with create_http_client(15.0, proxy_config) as client:` |

### 3.4 删除内容

| 删除项 | 文件 | 原因 |
|--------|------|------|
| `_create_http_client()` | network_helper.py:200-233 | 死代码，被新 SDK 替代 |
| `_resolve_proxy()` | network_tools.py:128-135 | 被 `http_client_sdk.resolve_proxy` 替代 |
| `download_file` 内联代理解析 | network_tools.py:329-331 | DRY 违反，用 SDK 替代 |

---

## 四、改动文件清单

### 4.1 新建文件

| 文件 | 职责 | 行数估算 |
|------|------|---------|
| `app/services/tools/network/http_client_sdk.py` | Network HTTP 客户端 SDK | ~80 行 |

### 4.2 修改文件

| 文件 | 改动内容 |
|------|---------|
| `app/services/tools/network/network_tools.py` | 5 处 httpx.AsyncClient → create_http_client；删除内联代理 |
| `app/services/tools/toolhelper/network_helper.py` | 删除 _create_http_client 死代码 |

### 4.3 删除内容

| 删除项 | 文件 | 原因 |
|--------|------|------|
| `_create_http_client()` | network_helper.py | 死代码 |
| `_resolve_proxy()` | network_tools.py | 被 SDK 替代 |
| 内联代理解析 | network_tools.py download_file | DRY 违反 |

### 4.4 改动统计

| 类型 | 数量 |
|------|------|
| 新建 | 1 个文件 |
| 修改 | 2 个文件 |
| 删除 | 1 个函数 + 1 段代码 |
| **合计** | **3 个文件** |

---

## 五、依赖关系

```
http_client_sdk.py ◄──── network_tools.py（5 处调用）
                  ◄──── （不依赖 LLM SDK）
```

**依赖方向**：单向，无循环依赖。与 LLM SDK 完全独立。

---

**文档完成时间**: 2026-05-29 13:24:47
**设计人**: 小沈
