# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-08 小欧 新建: D 态模型冷却注册表(429 限速记忆) — 设计 [15] 三堂会审落码
#   记载某模型走完 L1+L2 重试仍 429 后的限速态, 后续访问主动延迟, 防并发白打 429。
#   key 用 provider+model(§4.2 粒度决策, 同模型名走不同网关限速互相独立), 纯内存不落库。

"""
模型冷却注册表 — 429 限速记忆(D 态) — 小欧 2026-11-08

职责: 记录某模型 L1+L2 重试耗尽后的限速状态, 后续访问主动延迟, 防并发白打 429。
边界: 纯内存、不落库、不跨进程；成功调用后清零；档位升档自 constants 读取。
"""

import time
from typing import Dict, Optional

from app.constants import MODEL_COOLDOWN_STEPS, MODEL_QUOTA_COOLDOWN  # 2026-11-08 小欧: 从全局 constants 导入, 不重复定义(DRY)
from app.logger import logger


class ModelCooldownRegistry:
    """模型冷却注册表(单例) — SRP: 只管理"某模型限速后该冷却多久"的记忆与读取"""

    _instance: Optional["ModelCooldownRegistry"] = None

    def __init__(self):
        # key: model_id (provider+model)
        # value: {"cooldown_until": epoch, "hits": int, "is_quota": bool}
        self._table: Dict[str, Dict] = {}

    @classmethod
    def get(cls) -> "ModelCooldownRegistry":
        """单例入口 — 内存态共享, 冷启动/重启自动清零"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def mark(self, model_id: str, is_quota: bool = False) -> None:
        """L1+L2 重试耗尽后标记冷却 — 限速沿档位升档, 限额(配额)固定 100s 独立冷却(用户裁定)"""
        entry = self._table.get(model_id, {"hits": 0})
        entry["hits"] += 1
        if is_quota:
            cooldown = MODEL_QUOTA_COOLDOWN
        else:
            idx = min(entry["hits"] - 1, len(MODEL_COOLDOWN_STEPS) - 1)
            cooldown = MODEL_COOLDOWN_STEPS[idx]
        entry["cooldown_until"] = time.time() + cooldown
        entry["is_quota"] = is_quota
        self._table[model_id] = entry
        logger.info(f"[ModelCooldown] {model_id} 标记冷却 {cooldown}s (hits={entry['hits']}, quota={is_quota})")

    def delay_for(self, model_id: str) -> float:
        """剩余冷却秒数；0 = 无冷却"""
        return self.delay_info(model_id)[0]

    def delay_info(self, model_id: str) -> tuple:
        """剩余冷却秒数 + 是否限额(配额)冷却: (remaining, is_quota)；无冷却时 (0.0, False)
        供 llm_call 区分冷却类型以给准确文案(限额 vs 限速) — 小欧-2026-11-08"""
        entry = self._table.get(model_id)
        if not entry:
            return (0.0, False)
        remaining = entry["cooldown_until"] - time.time()
        return (max(0.0, remaining), bool(entry.get("is_quota", False)))

    def clear(self, model_id: str) -> None:
        """成功调用后清零 — 冷却只挡"紧跟的重复请求", 成功后该模型恢复正常"""
        if model_id in self._table:
            logger.info(f"[ModelCooldown] {model_id} 成功调用，清除冷却")
            del self._table[model_id]


__all__ = ["ModelCooldownRegistry"]