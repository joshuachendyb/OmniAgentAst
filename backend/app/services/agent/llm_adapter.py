"""
LLM 适配器统一入口实现

功能：
1. LLMAdapter 类 - 统一管理 LLM 能力探测和策略选择
"""

from typing import Optional

from app.services.agent.capability import LLMFeature, LLMCapability
from app.services.agent.capability_detector import CapabilityDetector
from app.services.agent.strategy_selector import StrategySelector, SelectedStrategy
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
        auto_detect: bool = True
    ):
        self.api_base = api_base
        self.api_key = api_key
        self.model = model
        
        # 能力探测器
        self._detector = CapabilityDetector(api_base, api_key, model)
        
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
            # 【优化 2026-05-11 小健】紧凑格式：开始探测
            logger.info(f"[适配器] 开始探测: model={self.model}")
            
            # 探测能力
            try:
                result = await self._detector.detect()
            except Exception as e:
                # 【重构 2026-05-14 小健】统一走StrategySelector.fallback()
                logger.error(f"[适配器] 探测异常: {e}", exc_info=True)
                self._strategy = StrategySelector.fallback(f"探测异常: {e}")
                return self._strategy
            
            if result.success:
                self._feature = result.feature
                self._strategy = StrategySelector.select(self._feature)
                # 【优化 2026-05-11 小健】紧凑格式：策略选择结果
                logger.info(
                    f"[适配器] 策略选择:\n"
                    f"  └─ 最终策略: {self._strategy.method} ({self._strategy.description})"
                )
            else:
                # 【重构 2026-05-14 小健】统一走StrategySelector.fallback()
                logger.warning(f"[适配器] 探测失败: error={result.error}")
                self._strategy = StrategySelector.fallback(f"探测失败: {result.error}")
        
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


# 导出
__all__ = ["LLMAdapter"]
