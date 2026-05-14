"""
LLM 能力探测器实现

【创建时间】2026-03-20 11:23:15 小强
【参考】Structured-Outputs-自适应兼容方案-小沈-2026-03-20.md 3.2节

功能：
1. CapabilityDetector 类 - 通过实际请求探测 LLM 支持的功能
2. _probe_tools() - 探测 tools 支持
3. _probe_response_format() - 探测 response_format 支持
4. _probe_reasoning() - 探测 reasoning 特征
"""

import json
import httpx
from typing import Optional

from app.services.agent.capability import LLMFeature, LLMProbeResult, LLMCapability
from app.utils.logger import logger


class CapabilityDetector:
    """
    API 能力探测器
    
    通过实际请求探测 LLM 支持的功能
    不依赖模型名称，硬编码
    """
    
    def __init__(self, api_base: str, api_key: str, model: str):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        self._capability_cache: Optional[LLMFeature] = None
    
    @property
    def capability(self) -> Optional[LLMFeature]:
        """获取缓存的能力"""
        return self._capability_cache
    
    def is_cached(self) -> bool:
        """是否已探测过"""
        return self._capability_cache is not None
    
    async def detect(self) -> LLMProbeResult:
        """
        自动探测 LLM 支持的功能
        
        Returns:
            LLMProbeResult: 探测结果
        """
        # 如果已缓存，直接返回
        if self._capability_cache:
            return LLMProbeResult(
                success=True,
                feature=self._capability_cache
            )
        
        result = LLMProbeResult(success=False, feature=LLMFeature())
        
        try:
            # 【2026-05-14 小沈】共用client，避免3次独立创建
            async with httpx.AsyncClient(timeout=30) as client:
                logger.info(f"[探测] 模型: {self.model}")
                
                # Step 1: 探测 tools（优先级最高）
                tools_result = await self._probe_tools(client)
                result.tools_tested = True
                result.tools_works = tools_result["works"]
                tools_icon = "✅" if tools_result["works"] else "❌"
                tools_detail = tools_result.get('reason', 'OK') if tools_result["works"] else tools_result.get('reason', 'N/A')
                
                # Step 2: 探测 response_format
                rf_result = await self._probe_response_format(client)
                result.response_format_tested = True
                result.response_format_works = rf_result["works"]
                rf_icon = "✅" if rf_result["works"] else "❌"
                rf_detail = rf_result.get('reason', 'OK') if rf_result["works"] else rf_result.get('reason', '不支持')
                
                # Step 3: 探测 reasoning 特征
                reasoning_result = await self._probe_reasoning(client)
                reasoning_icon = "✅" if reasoning_result["has_reasoning"] else "❌"
                reasoning_detail = "有reasoning_content" if reasoning_result["has_reasoning"] else "无"
                
                # Step 4: 构建能力特征
                capability = LLMCapability.NONE
                if result.response_format_works:
                    capability |= LLMCapability.RESPONSE_FORMAT
                if result.tools_works:
                    capability |= LLMCapability.TOOLS
                if reasoning_result["has_reasoning"]:
                    capability |= LLMCapability.REASONING
                
                feature = LLMFeature(
                    capability=capability,
                    supports_response_format=result.response_format_works,
                    supports_tools=result.tools_works,
                    supports_reasoning=reasoning_result["has_reasoning"],
                    uses_reasoning_content=reasoning_result["uses_reasoning_content"],
                    uses_outer_content=reasoning_result["uses_outer_content"],
                    detection_method="auto"
                )
                
                result.success = True
                result.feature = feature
                
                # 缓存结果
                self._capability_cache = feature
                
                # 【优化 2026-05-11 小健】紧凑格式：探测结果汇总
                logger.info(
                    f"[探测] 结果:\n"
                    f"  ├─ tools: {tools_icon} {'支持' if tools_result['works'] else '不支持'} ({tools_detail})\n"
                    f"  ├─ response_format: {rf_icon} {'支持' if rf_result['works'] else '不支持'} ({rf_detail})\n"
                    f"  └─ reasoning: {reasoning_icon} {'支持' if reasoning_result['has_reasoning'] else '不支持'} ({reasoning_detail})"
                )
                
                return result
            
        except Exception as e:
            logger.error(f"[CapabilityDetector] 探测异常: {e}")
            result.error = str(e)
            return result
    
    async def _probe_response_format(self, client: httpx.AsyncClient) -> dict:
        """
        探测 response_format 支持
        
        检测逻辑：
        - HTTP非200 → 不支持
        - 空响应 → 不支持（LongCat特征）
        - 空content → 不支持
        - 非JSON → 不支持
        - 有效JSON → 支持
        """
        schema = {
            "type": "json_object",
            "json_schema": {
                "type": "object",
                "properties": {"response": {"type": "string"}}
            }
        }
        try:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Say hello and respond with JSON"}],
                    "response_format": schema,
                    "stream": False
                }
            )
            if response.status_code != 200:
                return {"works": False, "reason": f"HTTP {response.status_code}"}
            content_length = response.headers.get("content-length", "0")
            if content_length == "0":
                return {"works": False, "reason": "Empty response - model does not support response_format"}
            data = response.json()
            message = data.get("choices", [{}])[0].get("message", {})
            content = message.get("content", "")
            if not content or len(content.strip()) == 0:
                return {"works": False, "reason": "Empty content - model does not support response_format"}
            try:
                parsed = json.loads(content)
                return {"works": True, "parsed": parsed}
            except json.JSONDecodeError:
                return {"works": False, "reason": "Invalid JSON - model does not support response_format"}
        except Exception as e:
            return {"works": False, "reason": str(e)}
    
    async def _probe_tools(self, client: httpx.AsyncClient) -> dict:
        """
        探测 tools（Function Calling）支持
        
        发送带tools的请求，检查是否返回tool_calls
        """
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "test_tool",
                    "description": "A test tool",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "param": {"type": "string", "description": "A test parameter"}
                        },
                        "required": ["param"]
                    }
                }
            }
        ]
        logger.info(f"[CapabilityDetector] _probe_tools: model={self.model}, api_base={self.api_base}")
        try:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "Please call the test_tool function with any parameter"}],
                    "tools": tools,
                    "tool_choice": "auto",
                    "stream": False
                }
            )
            logger.info(f"[CapabilityDetector] _probe_tools: HTTP {response.status_code}")
            if response.status_code != 200:
                return {"works": False, "reason": f"HTTP {response.status_code}"}
            content_type = response.headers.get("content-type", "")
            if "application/json" not in content_type:
                preview = response.text[:200] if response.text else "empty"
                logger.warning(f"[CapabilityDetector] _probe_tools: Non-JSON response, content_type={content_type}, preview={preview}")
                return {"works": False, "reason": f"Non-JSON response: {content_type}"}
            data = response.json()
            logger.info(f"[CapabilityDetector] _probe_tools: response data keys = {list(data.keys())}")
            message = data.get("choices", [{}])[0].get("message", {})
            logger.info(f"[CapabilityDetector] _probe_tools: message keys = {list(message.keys())}")
            tool_calls = message.get("tool_calls", [])
            if tool_calls:
                logger.info(f"[CapabilityDetector] _probe_tools: tool_calls found = {len(tool_calls)}")
                return {"works": True, "tool_calls": tool_calls}
            logger.info(f"[CapabilityDetector] _probe_tools: No tool_calls in response, content preview = {str(message.get('content', ''))[:200]}")
            return {"works": False, "reason": "No tool_calls returned"}
        except Exception as e:
            logger.error(f"[CapabilityDetector] _probe_tools: exception = {e}", exc_info=True)
            return {"works": False, "reason": str(e)}
    
    async def _probe_reasoning(self, client: httpx.AsyncClient) -> dict:
        """
        探测 reasoning 特征
        
        检查响应中是否使用reasoning_content字段
        """
        try:
            response = await client.post(
                f"{self.api_base}/chat/completions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": self.model,
                    "messages": [{"role": "user", "content": "What is 2+2?"}],
                    "stream": False
                }
            )
            if response.status_code != 200:
                return {"has_reasoning": False, "uses_reasoning_content": False, "uses_outer_content": False}
            data = response.json()
            message = data.get("choices", [{}])[0].get("message", {})
            has_reasoning = "reasoning_content" in message
            has_outer_content = "content" in message and message.get("content")
            return {
                "has_reasoning": has_reasoning,
                "uses_reasoning_content": has_reasoning,
                "uses_outer_content": has_outer_content
            }
        except Exception:
            return {"has_reasoning": False, "uses_reasoning_content": False, "uses_outer_content": False}


# 导出
__all__ = ["CapabilityDetector"]
