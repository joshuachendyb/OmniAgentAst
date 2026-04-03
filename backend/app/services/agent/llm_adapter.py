"""
LLM 适配器统一入口实现

【创建时间】2026-03-20 11:23:15 小强
【参考】Structured-Outputs-自适应兼容方案-小沈-2026-03-20.md 3.4节、3.2.7节

功能：
1. LLMAdapter 类 - 统一管理 LLM 能力探测和策略选择
2. build_messages() - 构建发送给 LLM 的消息列表
3. build_tools() - 构建工具定义（添加系统适配说明）
"""

import copy
from typing import Optional

from app.services.agent.capability import LLMFeature, LLMCapability
from app.services.agent.capability_detector import CapabilityDetector
from app.services.agent.strategy_selector import StrategySelector, SelectedStrategy
from app.services.agent.os_adapter import OSAdapter
from app.utils.logger import logger


class LLMAdapter:
    """
    LLM 适配器
    
    统一管理 LLM 能力探测和策略选择
    """
    
    def __init__(
        self,
        api_base: str,
        api_key: str,
        model: str,
        auto_detect: bool = True,
        os_adapter: Optional[OSAdapter] = None
    ):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        
        # 能力探测器
        self._detector = CapabilityDetector(api_base, api_key, model)
        
        # 系统适配器
        self.os_adapter = os_adapter or OSAdapter()
        
        # 自动探测
        if auto_detect:
            # 延迟探测，在首次调用时触发
            self._feature: Optional[LLMFeature] = None
            self._strategy: Optional[SelectedStrategy] = None
        else:
            self._feature = None
            self._strategy = None
    
    async def ensure_capability(self) -> SelectedStrategy:
        """
        确保能力已探测，返回选中的策略
        
        Returns:
            SelectedStrategy: 选中的策略
        """
        if self._strategy is None:
            logger.info(f"[LLMAdapter] 开始探测模型能力: model={self.model}")
            
            # 探测能力
            result = await self._detector.detect()
            
            if result.success:
                self._feature = result.feature
                self._strategy = StrategySelector.select(self._feature)
                logger.info(f"[LLMAdapter] 探测成功: method={self._strategy.method}, description={self._strategy.description}")
            else:
                # 探测失败，默认降级
                logger.warning(f"[LLMAdapter] 探测失败: {result.error}")
                self._strategy = SelectedStrategy(
                    method="prompt",
                    capability=LLMCapability.NONE,
                    description=f"探测失败: {result.error}"
                )
        
        return self._strategy
    
    @property
    def feature(self) -> Optional[LLMFeature]:
        """获取能力特征"""
        return self._feature
    
    @property
    def strategy(self) -> Optional[SelectedStrategy]:
        """获取选中策略"""
        return self._strategy
    
    @property
    def method(self) -> str:
        """获取当前使用的方法"""
        return self._strategy.method if self._strategy else "unknown"
    
    def build_messages(self, messages: Optional[list] = None, system_override: Optional[str] = None) -> list:
        """
        构建发送给 LLM 的消息列表
        
        Args:
            messages: 历史消息列表（可选，默认为空列表）
            system_override: 系统提示覆盖（可选）
        
        Returns:
            构建好的消息列表
        """
        result = []
        
        # 添加系统提示（包含系统适配信息）
        system_content = system_override or self.os_adapter.get_system_prompt()
        result.append({"role": "system", "content": system_content})
        
        # 添加历史消息（处理 None 或空列表）
        if messages:
            result.extend(messages)
        
        return result
    
    def build_tools(self, tools: list) -> list:
        """
        构建工具定义（添加系统适配说明）
        
        Args:
            tools: 原始工具定义列表
        
        Returns:
            添加了系统适配说明的工具列表
        """
        if not tools:
            return tools
        
        tool_hints = self.os_adapter.get_tool_descriptions()
        enriched_tools = []
        
        for tool in tools:
            enriched_tool = copy.deepcopy(tool)
            if "function" in enriched_tool:
                func = enriched_tool["function"]
                if "parameters" in func:
                    params = func["parameters"]
                    if "properties" in params:
                        if "path" in params["properties"]:
                            params["properties"]["path"]["description"] = tool_hints["path"]
            enriched_tools.append(enriched_tool)
        
        return enriched_tools


# 导出
__all__ = ["LLMAdapter"]
