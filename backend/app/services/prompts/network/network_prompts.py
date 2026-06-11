# -*- coding: utf-8 -*-
"""
NetworkPrompts - 网络通信 Prompt模板

P0优先级:URL/参数易错,超时重试策略需引导

Author: 小健 - 2026-05-06
P1修复 — 小欧 2026-06-11: 硬编码工具描述改为build_tool_descriptions()动态生成(DRY+OCP)
"""
from app.services.prompts.base_prompt_template import BasePrompts


class NetworkPrompts(BasePrompts):
    """网络通信 Prompt模板类"""
    
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt - 小沈 2026-06-11 系统信息提到Base公共层"""
        return "你是一个网络操作助手,负责HTTP请求、文件下载、网页内容获取、网络搜索、连通性测试和端口检查。"

    def get_tool_details(self) -> str:
        """获取工具描述和示例(FC模式下可选跳过) - 小沈 2026-06-11"""
        tools = ["http_request", "download_file", "fetch_webpage", "search_web", "network_diagnose"]
        tool_descriptions = self.build_tool_descriptions(tools, category_label="NETWORK")
        return f"""【Available NETWORK Tools】:
{tool_descriptions}

【Tool Call Examples】:
Example 1: GET请求
{{"thought": "用户要获取接口数据", "reasoning": "使用http_request执行GET请求", "tool_name": "http_request", "tool_params": {{"url": "https://api.example.com/users", "method": "GET"}}}}

Example 2: POST请求
{{"thought": "用户要创建资源", "reasoning": "使用http_request执行POST请求,json_body传数据", "tool_name": "http_request", "tool_params": {{"url": "https://api.example.com/users", "method": "POST", "json_body": {{"name": "test"}}}}}}

Example 3: 网络诊断
{{"thought": "用户要测试网络连通性", "reasoning": "使用network_diagnose测试ping", "tool_name": "network_diagnose", "tool_params": {{"host": "baidu.com", "count": 4}}}}"""
    

    def _get_domain_name(self) -> str:
        return "网络"

    def _get_domain_steps(self) -> str:
        return "1. 分析需要的网络操作(HTTP请求、下载、搜索、连通性测试)\n2. 使用正确参数的合适网络工具\n3. 用中文报告网络诊断结果"

    def _get_domain_extra_notes(self) -> str:
        return "- URL必须包含scheme(http://或https://)\n- POST/PUT用json_body参数(NOT data/params)\n- 使用timeout避免挂起\n- 失败两次后换不同方法"

    def get_safety_reminder(self) -> str:
        return "网络操作安全:URL参数需验证防注入,敏感数据使用HTTPS"
