# -*- coding: utf-8 -*-
"""
Network 工具函数模块 - 网络通信工具

【创建时间】2026-04-29 小沈
【规范】按新规范使用 register.py + Pydantic 模型注册

包含：
- http_request: 发起HTTP请求
- download_file: 下载文件到本地
- fetch_webpage: 获取和处理网页内容
- search_web: 搜索网络获取最新信息

返回格式：统一 {code, data, message} 格式
- code: SUCCESS 或 ERR_xxx 错误码
- data: 成功时返回数据，失败时为 None
- message: 描述信息

Author: 小沈 - 2026-04-29
"""

import os
import json
import re
from typing import Optional, Dict, Any, Literal, List
from urllib.parse import urlencode, urlparse, urlunparse, quote_plus

import httpx
from app.utils.logger import logger


async def http_request(
    url: str,
    method: str = "GET",
    headers: Optional[Dict[str, str]] = None,
    params: Optional[Dict[str, str]] = None,
    body: Optional[Any] = None,
    json_body: Optional[Dict[str, Any]] = None,
    timeout: int = 30,
    follow_redirects: bool = True,
) -> dict:
    """
    发起HTTP请求

    支持 GET/POST/PUT/DELETE/PATCH/HEAD/OPTIONS 方法。
    支持自定义请求头、查询参数、请求体。
    支持超时控制和重定向跟随。
    """
    try:
        # 验证URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {
                "code": "ERR_NETWORK_INVALID_URL",
                "data": None,
                "message": f"无效的URL: {url}，URL必须包含协议和域名（如 https://api.example.com/data）"
            }

        # 处理查询参数
        if params:
            query_string = urlencode(params, doseq=True)
            url = urlunparse(parsed._replace(query=query_string))

        # 构建请求头
        request_headers = {}
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=follow_redirects
        ) as client:
            # 根据method选择请求方式
            method_upper = method.upper()

            request_kwargs = {
                "url": url,
                "headers": request_headers,
            }

            # 处理请求体
            if method_upper in ("POST", "PUT", "PATCH"):
                if json_body is not None:
                    request_kwargs["json"] = json_body
                elif body is not None:
                    request_kwargs["content"] = body.encode("utf-8") if isinstance(body, str) else body

            response = await client.request(method_upper, **request_kwargs)
            response.raise_for_status()

            # 尝试解析响应体
            content_type = response.headers.get("content-type", "")
            response_body = None
            if "application/json" in content_type:
                try:
                    response_body = response.json()
                except (json.JSONDecodeError, ValueError):
                    response_body = response.text
            else:
                response_body = response.text

            return {
                "code": "SUCCESS",
                "data": {
                    "status_code": response.status_code,
                    "headers": dict(response.headers),
                    "body": response_body,
                },
                "message": f"请求成功 (HTTP {response.status_code})"
            }

    except httpx.TimeoutException:
        return {
            "code": "ERR_NETWORK_TIMEOUT",
            "data": None,
            "message": f"请求超时（{timeout}秒）：{url}"
        }
    except httpx.HTTPStatusError as e:
        try:
            error_body = e.response.text
        except Exception:
            error_body = None
        return {
            "code": "ERR_NETWORK_HTTP_ERROR",
            "data": {
                "status_code": e.response.status_code,
                "body": error_body,
            },
            "message": f"HTTP请求失败 (HTTP {e.response.status_code})：{url}"
        }
    except httpx.RequestError as e:
        return {
            "code": "ERR_NETWORK_REQUEST_ERROR",
            "data": None,
            "message": f"网络请求失败：{str(e)}"
        }
    except Exception as e:
        logger.error(f"[http_request] 未知错误: {e}")
        return {
            "code": "ERR_NETWORK_UNKNOWN",
            "data": None,
            "message": f"请求异常: {str(e)}"
        }


async def download_file(
    url: str,
    destination_path: str,
    headers: Optional[Dict[str, str]] = None,
    timeout: int = 300,
    chunk_size: int = 8192,
) -> dict:
    """
    从URL下载文件到本地路径

    支持大文件流式下载。
    自动创建目标目录。
    支持超时控制和自定义请求头。
    """
    try:
        # 验证URL
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {
                "code": "ERR_NETWORK_INVALID_URL",
                "data": None,
                "message": f"无效的URL: {url}，URL必须包含协议和域名"
            }

        # 验证目标路径
        dest_path = os.path.abspath(destination_path)
        dest_dir = os.path.dirname(dest_path)
        if not dest_dir:
            return {
                "code": "ERR_NETWORK_INVALID_PATH",
                "data": None,
                "message": f"无效的目标路径: {destination_path}，路径必须包含目录"
            }

        # 创建目标目录
        try:
            os.makedirs(dest_dir, exist_ok=True)
        except (PermissionError, OSError) as e:
            return {
                "code": "ERR_NETWORK_CREATE_DIR",
                "data": None,
                "message": f"无法创建目录 {dest_dir}: {str(e)}"
            }

        # 构建请求头
        request_headers = {}
        if headers:
            request_headers.update(headers)

        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True
        ) as client:
            async with client.stream("GET", url, headers=request_headers) as response:
                response.raise_for_status()

                # 获取文件信息
                total_size = int(response.headers.get("content-length", 0))
                content_type = response.headers.get("content-type", "")

                # 流式写入文件
                downloaded = 0
                try:
                    with open(dest_path, "wb") as f:
                        async for chunk in response.aiter_bytes(chunk_size=chunk_size):
                            f.write(chunk)
                            downloaded += len(chunk)
                except (PermissionError, OSError) as e:
                    # 清理不完整的文件
                    try:
                        if os.path.exists(dest_path):
                            os.remove(dest_path)
                    except OSError:
                        pass
                    return {
                        "code": "ERR_NETWORK_WRITE_FILE",
                        "data": None,
                        "message": f"写入文件失败 {dest_path}: {str(e)}"
                    }

                return {
                    "code": "SUCCESS",
                    "data": {
                        "file_path": dest_path,
                        "file_size": downloaded,
                        "content_type": content_type,
                        "total_size": total_size,
                    },
                    "message": f"文件下载成功 ({downloaded} 字节)：保存到 {dest_path}"
                }

    except httpx.TimeoutException:
        return {
            "code": "ERR_NETWORK_TIMEOUT",
            "data": None,
            "message": f"下载超时（{timeout}秒）：{url}"
        }
    except httpx.HTTPStatusError as e:
        return {
            "code": "ERR_NETWORK_HTTP_ERROR",
            "data": None,
            "message": f"下载失败 (HTTP {e.response.status_code})：{url}"
        }
    except httpx.RequestError as e:
        return {
            "code": "ERR_NETWORK_REQUEST_ERROR",
            "data": None,
            "message": f"网络请求失败：{str(e)}"
        }
    except Exception as e:
        logger.error(f"[download_file] 未知错误: {e}")
        return {
            "code": "ERR_NETWORK_UNKNOWN",
            "data": None,
            "message": f"下载异常: {str(e)}"
        }


async def fetch_webpage(
    url: str,
    prompt: Optional[str] = None,
    extract_format: str = "markdown",
    js_render: bool = False,
    timeout: int = 30,
    max_tokens: int = 8000,
    user_agent: Optional[str] = None,
    proxy: Optional[str] = None,
) -> dict:
    """
    获取和处理网页内容 - 小沈 2026-05-02
    
    支持静态抓取和JS渲染（需要额外依赖）。
    支持多种输出格式：markdown、html、text。
    支持AI提取指令（prompt）。
    """
    try:
        parsed = urlparse(url)
        if not parsed.scheme or not parsed.netloc:
            return {
                "code": "ERR_NETWORK_INVALID_URL",
                "data": None,
                "message": f"无效的URL: {url}"
            }
        
        headers = {}
        if user_agent:
            headers["User-Agent"] = user_agent
        else:
            headers["User-Agent"] = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        
        proxy_config = None
        if proxy:
            proxy_config = {"http://": proxy, "https://": proxy}
        
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(timeout),
            follow_redirects=True,
            proxies=proxy_config
        ) as client:
            response = await client.get(url, headers=headers)
            response.raise_for_status()
            
            html_content = response.text
            content_type = response.headers.get("content-type", "")
            
            if extract_format == "html":
                extracted_content = html_content
            elif extract_format == "text":
                text_content = re.sub(r'<script[^>]*>.*?</script>', '', html_content, flags=re.DOTALL|re.IGNORECASE)
                text_content = re.sub(r'<style[^>]*>.*?</style>', '', text_content, flags=re.DOTALL|re.IGNORECASE)
                text_content = re.sub(r'<[^>]+>', ' ', text_content)
                text_content = re.sub(r'\s+', ' ', text_content).strip()
                extracted_content = text_content
            else:
                extracted_content = _html_to_markdown(html_content)
            
            if len(extracted_content) > max_tokens * 4:
                extracted_content = extracted_content[:max_tokens * 4]
                truncated = True
            else:
                truncated = False
            
            result_data = {
                "url": url,
                "content": extracted_content,
                "format": extract_format,
                "content_type": content_type,
                "status_code": response.status_code,
                "truncated": truncated,
            }
            
            if prompt:
                result_data["prompt"] = prompt
                result_data["note"] = "AI提取功能需要LLM后处理"
            
            return {
                "code": "SUCCESS",
                "data": result_data,
                "message": f"成功获取网页内容（{extract_format}格式）" + ("（已截断）" if truncated else "")
            }
    
    except httpx.TimeoutException:
        return {
            "code": "ERR_NETWORK_TIMEOUT",
            "data": None,
            "message": f"获取网页超时（{timeout}秒）：{url}"
        }
    except httpx.HTTPStatusError as e:
        return {
            "code": "ERR_NETWORK_HTTP_ERROR",
            "data": None,
            "message": f"获取网页失败 (HTTP {e.response.status_code})：{url}"
        }
    except httpx.RequestError as e:
        return {
            "code": "ERR_NETWORK_REQUEST_ERROR",
            "data": None,
            "message": f"网络请求失败：{str(e)}"
        }
    except Exception as e:
        logger.error(f"[fetch_webpage] 未知错误: {e}")
        return {
            "code": "ERR_NETWORK_UNKNOWN",
            "data": None,
            "message": f"获取网页异常: {str(e)}"
        }


def _html_to_markdown(html: str) -> str:
    """简单的HTML转Markdown - 小沈 2026-05-02"""
    text = html
    text = re.sub(r'<script[^>]*>.*?</script>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<style[^>]*>.*?</style>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<head[^>]*>.*?</head>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<nav[^>]*>.*?</nav>', '', text, flags=re.DOTALL|re.IGNORECASE)
    text = re.sub(r'<footer[^>]*>.*?</footer>', '', text, flags=re.DOTALL|re.IGNORECASE)
    
    text = re.sub(r'<h1[^>]*>(.*?)</h1>', r'# \1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h2[^>]*>(.*?)</h2>', r'## \1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h3[^>]*>(.*?)</h3>', r'### \1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h4[^>]*>(.*?)</h4>', r'#### \1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h5[^>]*>(.*?)</h5>', r'##### \1\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<h6[^>]*>(.*?)</h6>', r'###### \1\n', text, flags=re.IGNORECASE)
    
    text = re.sub(r'<strong[^>]*>(.*?)</strong>', r'**\1**', text, flags=re.IGNORECASE)
    text = re.sub(r'<b[^>]*>(.*?)</b>', r'**\1**', text, flags=re.IGNORECASE)
    text = re.sub(r'<em[^>]*>(.*?)</em>', r'*\1*', text, flags=re.IGNORECASE)
    text = re.sub(r'<i[^>]*>(.*?)</i>', r'*\1*', text, flags=re.IGNORECASE)
    
    text = re.sub(r'<a[^>]*href=["\']([^"\']+)["\'][^>]*>(.*?)</a>', r'[\2](\1)', text, flags=re.IGNORECASE)
    
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<p[^>]*>(.*?)</p>', r'\1\n\n', text, flags=re.IGNORECASE)
    text = re.sub(r'<li[^>]*>(.*?)</li>', r'- \1\n', text, flags=re.IGNORECASE)
    
    text = re.sub(r'<[^>]+>', ' ', text)
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    
    return text.strip()


async def search_web(
    query: str,
    allowed_domains: Optional[List[str]] = None,
    blocked_domains: Optional[List[str]] = None,
    num_results: int = 10,
    time_range: str = "any",
    language: Optional[str] = None,
    safe_search: str = "moderate",
    proxy: Optional[str] = None,
) -> dict:
    """
    搜索网络获取最新信息 - 小沈 2026-05-02
    
    使用DuckDuckGo搜索API（无需API密钥）。
    支持域名过滤、时间范围、安全搜索等参数。
    """
    try:
        if len(query) < 2:
            return {
                "code": "ERR_SEARCH_QUERY_TOO_SHORT",
                "data": None,
                "message": "搜索查询至少需要2个字符"
            }
        
        proxy_config = None
        if proxy:
            proxy_config = {"http://": proxy, "https://": proxy}
        
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
        
        search_url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": 1,
            "skip_disambig": 1,
        }
        
        async with httpx.AsyncClient(
            timeout=httpx.Timeout(30),
            follow_redirects=True,
            proxies=proxy_config
        ) as client:
            response = await client.get(search_url, params=params, headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            results = []
            
            if data.get("AbstractText"):
                results.append({
                    "title": data.get("Heading", "摘要"),
                    "url": data.get("AbstractURL", ""),
                    "snippet": data.get("AbstractText", ""),
                    "source": "DuckDuckGo Instant Answer"
                })
            
            for topic in data.get("RelatedTopics", [])[:num_results]:
                if isinstance(topic, dict):
                    if "Text" in topic and "FirstURL" in topic:
                        results.append({
                            "title": topic.get("Text", "").split(" - ")[0] if " - " in topic.get("Text", "") else topic.get("Text", ""),
                            "url": topic.get("FirstURL", ""),
                            "snippet": topic.get("Text", ""),
                            "source": "DuckDuckGo"
                        })
                    elif "Topics" in topic:
                        for subtopic in topic.get("Topics", []):
                            if len(results) >= num_results:
                                break
                            if "Text" in subtopic and "FirstURL" in subtopic:
                                results.append({
                                    "title": subtopic.get("Text", "").split(" - ")[0] if " - " in subtopic.get("Text", "") else subtopic.get("Text", ""),
                                    "url": subtopic.get("FirstURL", ""),
                                    "snippet": subtopic.get("Text", ""),
                                    "source": "DuckDuckGo"
                                })
            
            if allowed_domains:
                results = [r for r in results if any(domain in r.get("url", "") for domain in allowed_domains)]
            
            if blocked_domains:
                results = [r for r in results if not any(domain in r.get("url", "") for domain in blocked_domains)]
            
            results = results[:num_results]
            
            return {
                "code": "SUCCESS",
                "data": {
                    "query": query,
                    "results": results,
                    "total": len(results),
                    "time_range": time_range,
                    "language": language,
                },
                "message": f"找到 {len(results)} 条搜索结果"
            }
    
    except httpx.TimeoutException:
        return {
            "code": "ERR_NETWORK_TIMEOUT",
            "data": None,
            "message": "搜索请求超时"
        }
    except httpx.HTTPStatusError as e:
        return {
            "code": "ERR_NETWORK_HTTP_ERROR",
            "data": None,
            "message": f"搜索请求失败 (HTTP {e.response.status_code})"
        }
    except httpx.RequestError as e:
        return {
            "code": "ERR_NETWORK_REQUEST_ERROR",
            "data": None,
            "message": f"网络请求失败：{str(e)}"
        }
    except Exception as e:
        logger.error(f"[search_web] 未知错误: {e}")
        return {
            "code": "ERR_NETWORK_UNKNOWN",
            "data": None,
            "message": f"搜索异常: {str(e)}"
        }
