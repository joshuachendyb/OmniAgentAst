# -*- coding: utf-8 -*-
# 模块说明: provider 适配基类 — 默认行为==现状(仅 Authorization, 无动态头, body 原样, chat 端点)
#   新 provider 特殊 HTTP 握手 = 继承本基类覆写对应钩子; 未覆写即完全默认(现状语义)。
#   归属依据(北京老陈核查): 承载 provider 的请求适配与调用约定差异 ——
#   前者指 HTTP 接缝差异与门禁 body/端点路由(7 个纯变换钩子), 后者指纯文本任务的
#   调用约定(callTextForTask, 带 I/O)。两者同源于"provider 约定变化", 故同处一基类。
#   schema/reasoning/工具别名(#3/4/5)为全局层, 绝不 provider 化。
# 编辑历史: 2026-09-23 小欧 新建
# 编辑历史: 2026-10-09 小欧 加 callTextForTask 钩子(纯文本任务定制调用, 默认不接管) — 小欧-2026-10-09

from typing import Dict, Optional


class ProviderAdapter:
    """provider 适配基类 — 小欧 2026-09-23"""

    @staticmethod
    def static_headers(api_key: str) -> Dict[str, str]:
        """客户端创建时的静态头 — 默认仅 Authorization(现状行为)"""
        return {"Authorization": f"Bearer {api_key}"}

    @staticmethod
    def per_request_headers() -> Dict[str, str]:
        """每请求动态头 — 默认无(现状行为)"""
        return {}

    @staticmethod
    def ensure_gate_body(body: Dict) -> Dict:
        """发送前门禁 body 保障 — 默认原样返回(现状行为)"""
        return body

    @staticmethod
    def endpoint_for(model: str) -> str:
        """按模型选端点 — 默认 chat 端点(现状行为)"""
        return "/chat/completions"

    @staticmethod
    def force_stream() -> bool:
        """非流式是否改走流式收集 — 默认 False(现状行为)"""
        return False

    @staticmethod
    def to_responses_body(chat_body: Dict, model: str) -> Dict:
        """responses 端点 body 转换 — 默认原样(现状行为, 仅 endpoint_for 返回 /responses 的适配器会覆写)"""
        return chat_body

    @staticmethod
    def error_message_map() -> Dict[int, str]:
        """provider 特有错误码 → 用户友好消息 — 默认空(走全局 error_classifier)"""
        return {}

    @staticmethod
    async def callTextForTask(client, messages) -> Optional[str]:
        """纯文本任务的定制化调用钩子 — 默认不接管, 返回 None 由调用方走通用路径

        用途: 压缩摘要这类"不要工具、只要一段文本"的任务, 若某 provider 的调用约定与
        通用路径不同, 由其适配器覆写本钩子接管。默认不接管故对既有链路零影响。
        返回 None = 未接管, 调用方自行走通用路径; 本钩子绝不抛异常, 以免波及既有链路。
        """
        return None