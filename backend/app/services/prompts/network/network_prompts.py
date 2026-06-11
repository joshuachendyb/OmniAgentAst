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

【调用决策示例】:
用户: "获取https://api.example.com/users的数据"
→ 判断: GET请求 → 调用http_request(url="https://api.example.com/users", method="GET")

用户: "创建一个用户"
→ 判断: POST+JSON → 调用http_request(url="...", method="POST", json_body={{"name":"test"}})

用户: "测试到baidu.com的连通性"
→ 判断: 网络诊断 → 调用network_diagnose(host="baidu.com", count=4)"""
    

    def _get_domain_name(self) -> str:
        return "网络"

    def _get_domain_steps(self) -> str:
        return ("1. 判断操作类型(HTTP请求/下载/搜索/诊断)\n"
                "2. 确保URL包含scheme(http/https),选择合适工具\n"
                "3. 用中文报告结果,失败时说明原因")

    def _get_domain_extra_notes(self) -> str:
        return "- URL必须包含scheme(http://或https://)\n- POST/PUT用json_body参数(NOT data/params)\n- 使用timeout避免挂起\n- 失败两次后换不同方法"

    def get_safety_reminder(self) -> str:
        return ("网络操作安全:\n"
                "- URL必须包含scheme(http://或https://)\n"
                "- POST/PUT用json_body参数\n"
                "- 敏感数据使用HTTPS")
