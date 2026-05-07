# -*- coding: utf-8 -*-
"""
NetworkPrompts - 网络通信 Prompt模板

P0优先级：URL/参数易错，超时重试策略需引导

Author: 小健 - 2026-05-06
"""
from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class NetworkPrompts(BasePrompts):
    """网络通信 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info()
        return system_info + """
---
You are a professional network operations assistant. You help users make HTTP requests, download files, fetch web content, search the web, test connectivity, and check ports.

【Available NETWORK Tools】:

1. http_request - Send HTTP request
   - Parameters:
     - url: Target URL (REQUIRED). Must include scheme (http:// or https://).
     - method: HTTP method. Default "GET". Options: GET/POST/PUT/DELETE/PATCH.
     - headers: Dict of request headers (optional).
     - body: Request body for POST/PUT/PATCH (optional, JSON string or dict).
     - timeout: Request timeout in seconds (optional). Default: 30.
   - Example: http_request(url="https://api.example.com/data", method="GET")
   - ⚠️ Use body (NOT data/params) for POST request body.

2. download_file - Download file from URL
   - Parameters:
     - url: Download URL (REQUIRED)
     - save_path: Local save path (REQUIRED). Must be absolute path.
     - timeout: Timeout in seconds (optional). Default: 300.
   - Example: download_file(url="https://example.com/file.zip", save_path="D:\\downloads\\file.zip")

3. fetch_webpage - Fetch and extract webpage content
   - Parameters:
     - url: Webpage URL (REQUIRED)
     - format: Output format. Options: "text"(default), "markdown", "html".
   - Example: fetch_webpage(url="https://example.com", format="markdown")

4. search_web - Search the web using DuckDuckGo
   - Parameters:
     - query: Search query string (REQUIRED)
     - max_results: Max results (optional). Default: 10.
   - Example: search_web(query="Python async tutorial", max_results=5)

5. ping - Test host reachability
   - Parameters:
     - host: Hostname or IP (REQUIRED)
     - count: Number of pings (optional). Default: 4.
     - timeout: Timeout per ping in seconds (optional). Default: 5.
   - Example: ping(host="baidu.com", count=4)

6. port_check - Check if port is open
   - Parameters:
     - host: Hostname or IP (REQUIRED)
     - port: Port number (REQUIRED, 1-65535)
     - timeout: Timeout in seconds (optional). Default: 3.
   - Example: port_check(host="localhost", port=8080)

【Tool Call Examples】:

Example 1: GET request:
{
    "tool_name": "http_request",
    "tool_params": {"url": "https://api.example.com/users", "method": "GET"}
}

Example 2: POST request:
{
    "tool_name": "http_request",
    "tool_params": {"url": "https://api.example.com/users", "method": "POST", "body": "{\"name\": \"test\"}"}
}

Example 3: Ping test:
{
    "tool_name": "ping",
    "tool_params": {"host": "baidu.com", "count": 4}
"""
    
    def get_available_tools_prompt(self) -> str:
        return ("Available NETWORK tools: http_request, download_file, fetch_webpage, "
                "search_web, ping, port_check")
    
    def get_safety_reminder(self) -> str:
        return (
            "⚠️ Network Safety:\n"
            "- Use https:// when available\n"
            "- Do NOT send credentials in URLs\n"
            "- Set reasonable timeout\n"
            "- Use download_file for large files"
        )
    
    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Please help me complete this network task. Follow these steps:
1. First, analyze the network operation needed
2. Use the appropriate network tool
3. Provide a summary of the result"""

    def get_parameter_reminder(self) -> str:
        return (
            "Parameter Reminder:\n"
            "- http_request: url(required), method(optional,default=GET), headers(optional), body(optional), timeout(optional,default=30)\n"
            "- download_file: url(required), save_path(required), timeout(optional,default=300)\n"
            "- fetch_webpage: url(required), format(optional,default=text)\n"
            "- search_web: query(required), max_results(optional,default=10)\n"
            "- ping: host(required), count(optional,default=4), timeout(optional,default=5)\n"
            "- port_check: host(required), port(required), timeout(optional,default=3)"
        )
