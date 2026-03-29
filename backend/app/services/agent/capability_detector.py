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
import logging
from typing import Optional

from app.services.agent.capability import LLMFeature, LLMProbeResult, LLMCapability

logger = logging.getLogger(__name__)


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
            logger.info(f"[CapabilityDetector] 开始探测模型: {self.model}")
            
            # 【修复P1-004】Step 1: 探测 tools（优先级最高）
            tools_result = await self._probe_tools()
            result.tools_tested = True
            result.tools_works = tools_result["works"]
            logger.info(f"[CapabilityDetector] tools探测结果: works={tools_result['works']}, reason={tools_result.get('reason', 'N/A')}")
            
            # 【修复P1-004】Step 2: 探测 response_format（记录能力，策略选择由StrategySelector决定）
            rf_result = await self._probe_response_format()
            result.response_format_tested = True
            result.response_format_works = rf_result["works"]
            logger.info(f"[CapabilityDetector] response_format探测结果: works={rf_result['works']}, reason={rf_result.get('reason', 'N/A')}")
            
            # Step 3: 探测 reasoning 特征
            reasoning_result = await self._probe_reasoning()
            logger.info(f"[CapabilityDetector] reasoning探测结果: has_reasoning={reasoning_result['has_reasoning']}")
            
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
            
            logger.info(f"[CapabilityDetector] 探测完成: supports_tools={feature.supports_tools}, supports_response_format={feature.supports_response_format}")
            
            return result
            
        except Exception as e:
            logger.error(f"[CapabilityDetector] 探测异常: {e}")
            result.error = str(e)
            return result
    
    async def _probe_response_format(self) -> dict:
        """
        探测 response_format 支持
        
        【修复P0-003】根据 LongCat 特征检测：response_format 会返回空响应
        - 如果 content 为空或 content-length 为 0 → 不支持 response_format
        - 如果返回有效 JSON → 支持 response_format
        """
        schema = {
            "type": "json_object",
            "json_schema": {
                "type": "object",
                "properties": {
                    "response": {"type": "string"}
                }
            }
        }
        
        try:
            async with httpx.AsyncClient(timeout=30) as client:
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
                
                # 【修复P0-003】检查 HTTP 状态码
                if response.status_code != 200:
                    return {"works": False, "reason": f"HTTP {response.status_code}"}
                
                # 【修复P0-003】检测空响应（LongCat 特征：response_format 返回空）
                content_length = response.headers.get("content-length", "0")
                if content_length == "0":
                    return {"works": False, "reason": "Empty response - model does not support response_format"}
                
                data = response.json()
                message = data.get("choices", [{}])[0].get("message", {})
                content = message.get("content", "")
                
                # 【修复P0-003】检测空 content
                if not content or len(content.strip()) == 0:
                    return {"works": False, "reason": "Empty content - model does not support response_format"}
                
                # 【修复P0-003】验证是否返回有效 JSON
                try:
                    parsed = json.loads(content)
                    # 有效 JSON → 支持 response_format
                    return {"works": True, "parsed": parsed}
                except json.JSONDecodeError:
                    # 返回非 JSON → 不支持 response_format
                    return {"works": False, "reason": "Invalid JSON - model does not support response_format"}
                    
        except Exception as e:
            return {"works": False, "reason": str(e)}
    
    async def _probe_tools(self) -> dict:
        """
        探测 tools 支持
        
        发送一个带 tools 的请求，检查是否返回 tool_calls
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
            async with httpx.AsyncClient(timeout=30) as client:
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
                
                data = response.json()
                logger.info(f"[CapabilityDetector] _probe_tools: response data keys = {list(data.keys())}")
                
                message = data.get("choices", [{}])[0].get("message", {})
                logger.info(f"[CapabilityDetector] _probe_tools: message keys = {list(message.keys())}")
                
                # 检查是否有 tool_calls
                tool_calls = message.get("tool_calls", [])
                if tool_calls:
                    logger.info(f"[CapabilityDetector] _probe_tools: tool_calls found = {len(tool_calls)}")
                    return {"works": True, "tool_calls": tool_calls}
                logger.info(f"[CapabilityDetector] _probe_tools: No tool_calls in response, content preview = {str(message.get('content', ''))[:200]}")
                return {"works": False, "reason": "No tool_calls returned"}
                
        except Exception as e:
            logger.error(f"[CapabilityDetector] _probe_tools: exception = {e}")
            return {"works": False, "reason": str(e)}
    
    async def _probe_reasoning(self) -> dict:
        """
        探测 reasoning 特征
        
        检查响应中是否使用 reasoning_content 字段
        """
        try:
            async with httpx.AsyncClient(timeout=30) as client:
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
                
                # 检查 reasoning_content 字段
                has_reasoning = "reasoning_content" in message
                
                # 检查外层 content 字段
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
