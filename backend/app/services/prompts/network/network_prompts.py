# -*- coding: utf-8 -*-
"""
NetworkPrompts - 网络通信 Prompt模板

P0优先级：URL/参数易错，超时重试策略需引导

Author: 小健 - 2026-05-06
"""
from datetime import datetime

from app.services.prompts.BasePromptTemplate import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_info
from app.utils.logger import logger


class NetworkPrompts(BasePrompts):
    """网络通信 Prompt模板类"""
    
    def get_system_prompt(self) -> str:
        system_info = get_system_info(include_commands=False)  # 【修复 2026-05-14 小沈】NetworkAgent不注入命令格式，避免LLM幻觉调execute_shell_command
        return system_info + """
You are a professional network operations assistant. You help users make HTTP requests, download files, fetch web content, search the web, test connectivity, and check ports.

【Available NETWORK Tools — 共5个】:

1. http_request - Send HTTP request
   - When to use: GET/POST/PUT/DELETE requests, API calls
   - Returns: status_code, headers, body, elapsed_time
   - Examples:
     * http_request(url="https://api.example.com/data", method="GET")
     * http_request(url="https://api.example.com/users", method="POST", json_body={"name": "test"})

2. download_file - Download file from URL
   - When to use: download files, save remote content to disk
   - Returns: file_path, file_size, content_type
   - Examples:
     * download_file(url="https://example.com/file.zip", destination_path="D:\\downloads\\file.zip")

3. fetch_webpage - Fetch and extract webpage content
   - When to use: read webpage text, extract content from URL
   - Returns: title, content, links, metadata
   - Examples:
     * fetch_webpage(url="https://example.com", extract_format="markdown")

4. search_web - Search the web
   - When to use: search for information, find URLs, get current data
   - Returns: results with title, url, snippet
   - Examples:
     * search_web(query="Python async tutorial", num_results=5)

5. network_diagnose - Network connectivity diagnostics
   - When to use: ping test, port check
   - Returns: reachable, latency, packet_loss, port_status
   - Examples:
     * network_diagnose(host="8.8.8.8")
     * network_diagnose(host="localhost", mode="port", port=8080)

【Tool Call Examples】:
Example 1: GET请求
{"thought": "用户要获取接口数据", "reasoning": "使用http_request执行GET请求", "tool_name": "http_request", "tool_params": {"url": "https://api.example.com/users", "method": "GET"}}

Example 2: POST请求
{"thought": "用户要创建资源", "reasoning": "使用http_request执行POST请求，json_body传数据", "tool_name": "http_request", "tool_params": {"url": "https://api.example.com/users", "method": "POST", "json_body": {"name": "test"}}}

Example 3: 网络诊断
{"thought": "用户要测试网络连通性", "reasoning": "使用network_diagnose测试ping", "tool_name": "network_diagnose", "tool_params": {"host": "baidu.com", "count": 4}}

Example 4: 任务完成
{"thought": "网络请求已完成", "reasoning": "请求成功，数据已返回", "tool_name": "finish", "tool_params": {"result": "获取到100条数据"}}
"""
    

    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.NETWORK)
        forbidden = (
            "\n\nFORBIDDEN parameter names - DO NOT use:\n"
            "- ❌ data / params (correct: json_body)\n"
            "- ❌ address / host_url (correct: url)\n"
            "- ❌ path / file_path / save_path (correct: destination_path)\n"
            "- ❌ q / keyword (correct: query)"
        )
        return auto_reminder + forbidden

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Current time: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}

请完成此网络任务，按以下步骤：
1. 分析需要的网络操作（HTTP请求、下载、搜索、连通性测试）
2. 使用正确参数的合适网络工具
3. 用中文报告网络诊断结果

Remember:
- URL必须包含scheme（http://或https://）
- POST/PUT用json_body参数（NOT data/params）
- 使用timeout避免挂起
- 失败两次后换不同方法"""

    def get_safety_reminder(self) -> str:
        return "⚠️ Network Safety: Validate URL parameters to avoid injection risks. Use HTTPS for sensitive data."
