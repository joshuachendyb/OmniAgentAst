# -*- coding: utf-8 -*-
"""
NetworkPrompts - 网络通信 Prompt模板

P0优先级:URL/参数易错,超时重试策略需引导

Author: 小健 - 2026-05-06
P1修复 — 小欧 2026-06-11: 硬编码工具描述改为build_tool_descriptions()动态生成(DRY+OCP)
"""
from datetime import datetime

from app.services.prompts.base_prompt_template import BasePrompts
from app.services.prompts.middle import get_system_prompt as get_system_prompt_string
from app.utils.logger import logger


class NetworkPrompts(BasePrompts):
    """网络通信 Prompt模板类"""
    
    def get_core_system_prompt(self) -> str:
        """获取核心系统Prompt - 小沈 2026-06-11 系统信息提到Base公共层"""
        return "You are a professional network operations assistant. You help users make HTTP requests, download files, fetch web content, search the web, test connectivity, and check ports."

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
        return "Remember:\n- URL必须包含scheme(http://或https://)\n- POST/PUT用json_body参数(NOT data/params)\n- 使用timeout避免挂起\n- 失败两次后换不同方法"

    def get_safety_reminder(self) -> str:
        return "⚠️ Network Safety: Validate URL parameters to avoid injection risks. Use HTTPS for sensitive data."
