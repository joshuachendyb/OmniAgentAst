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
        system_info = get_system_info(include_commands=False)  # 【修复 2026-05-14 小沈】NetworkAgent不注入命令格式，避免LLM幻觉调execute_shell_command
        return system_info + """
You are a professional network operations assistant. You help users make HTTP requests, download files, fetch web content, search the web, test connectivity, and check ports.

【Available NETWORK Tools】:

1. http_request - Send HTTP request
   - Example: http_request(url="https://api.example.com/data", method="GET")
   - ⚠️ Use body (NOT data/params) for POST request body.

2. download_file - Download file from URL
   - Example: download_file(url="https://example.com/file.zip", save_path="D:\\downloads\\file.zip")

3. fetch_webpage - Fetch and extract webpage content
   - Example: fetch_webpage(url="https://example.com", format="markdown")

4. search_web - Search the web using DuckDuckGo
   - Example: search_web(query="Python async tutorial", max_results=5)

5. ping - Test host reachability
   - Example: ping(host="baidu.com", count=4)

6. port_check - Check if port is open
   - Example: port_check(host="localhost", port=8080)

【Tool Call Examples】:

Example 1: GET request
{
    "thought": "用户要获取用户列表数据",
    "reasoning": "使用http_request执行GET请求",
    "tool_name": "http_request",
    "tool_params": {"url": "https://api.example.com/users", "method": "GET"}
}

Example 2: POST request
{
    "thought": "用户要创建新用户",
    "reasoning": "使用http_request执行POST请求，body传JSON数据",
    "tool_name": "http_request",
    "tool_params": {"url": "https://api.example.com/users", "method": "POST", "body": "{\"name\": \"test\"}"}
}

Example 3: Ping test
{
    "thought": "用户要测试网络连通性",
    "reasoning": "使用ping测试到baidu.com的连接",
    "tool_name": "ping",
    "tool_params": {"host": "baidu.com", "count": 4}
}

Example 4: Task completed
{
    "thought": "网络请求任务已完成",
    "reasoning": "请求成功，数据已返回",
    "tool_name": "finish",
    "tool_params": {"result": "获取到100条用户数据"}
}
"""
    

    def get_parameter_reminder(self) -> str:
        from app.services.tools.registry import tool_registry, ToolCategory
        auto_reminder = tool_registry.generate_param_reminder(category=ToolCategory.NETWORK)
        forbidden = (
            "\n\nFORBIDDEN parameter names - DO NOT use:\n"
            "- ❌ data / params (correct: body)\n"
            "- ❌ address / host_url (correct: url)\n"
            "- ❌ path / file_path (correct: save_path)\n"
            "- ❌ q / keyword (correct: query)"
        )
        return auto_reminder + forbidden

    def get_task_prompt(self, task: str) -> str:
        return f"""Task: {task}

Please help me complete this network task. Follow these steps:
1. First, identify the network operation needed (HTTP request, download, search, connectivity test)
2. Use the appropriate network tool with correct URL/parameters
3. Handle errors gracefully (timeout, connection refused, DNS failure) and suggest alternatives

Remember:
- URL must include scheme (http:// or https://)
- For POST/PUT, use body parameter (NOT data/params)
- Use timeout for operations that may hang
- If DuckDuckGo search fails, try alternative keywords or simpler queries

【NETWORK避免重复规则】:
- 获取公网IP的推荐方法优先级：http_request(httpbin.org/ip) > nslookup > curl
- 如果http_request到国外URL超时，换用国内URL(如 httpbin.org/ip, myip.ipip.net)
- ipconfig /all 只需执行1次，结果包含所有内网信息
- ping测试只需1次，不需要重复ping同一地址
- Do NOT repeat successful operations - reuse the results
- If an operation fails twice, try a DIFFERENT approach"""
