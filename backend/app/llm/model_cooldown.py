# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-11-08 小欧 新建: D 态模型冷却注册表(429 限速记忆) — 设计 [15] 三堂会审落码
#   记载某模型走完 L1+L2 重试仍 429 后的限速态, 后续访问主动延迟, 防并发白打 429。
#   key 用 provider+model(§4.2 粒度决策, 同模型名走不同网关限速互相独立), 纯内存不落库。
# 2026-11-08 小欧: mark/clear 补 log_and_print 调用点(console 观测冷却生效/清零) — 小欧-2026-11-08
#   两处 log_and_print 显式传 level="WARNING" — 小欧-2026-11-08
#   【log_and_print 上屏机制速查】(用户提示, 后续排查直接看这里):
#     ① 签名: log_and_print(msg, level="DEBUG"), level 是"该行属于哪一档"的声明, 不是过滤阈值;
#     ② 控制台上屏判定 = 精确匹配(==): _lv == LogConfig.get_console_level_int() 才 console_put,
#        NOT >= 阈值 —— 档位不相等那行永远不上屏(2026-11-03 老陈令: 是哪个级别就只打哪个级别);
#     ③ 当前 logging.level=WARNING → console_int=30; 默认 DEBUG 换算 _lv=10, 10 != 30 → 只落文件不上屏;
#     ④ 冷却属异常/业务路径观测, 必须声明 level="WARNING" 才在 WARNING 档上屏(文件通道仍 >= 阈值完整落盘);
#     ⑤ 唯一换算点 to_level_int(name, default) 内部 .upper(), "warning"/"WARNING"/logging.WARNING(30) 皆可,
#        非法档位名回落 default=INFO 不吞行(该行照常落文件, 只是不上屏)。
# 2026-11-08 小欧 三堂会审修复: mark/clear 删并存 logger.info(只用 log_and_print 收口双输出为单点) —
#   logger 与 _file_logger 共享同一文件 handler, 并存会同一行写文件两次; 删死导入 logger(仅剩 log_and_print) — 小欧-2026-11-08

"""
模型冷却注册表 — 429 限速记忆(D 态) — 小欧 2026-11-08

职责: 记录某模型 L1+L2 重试耗尽后的限速状态, 后续访问主动延迟, 防并发白打 429。
边界: 纯内存、不落库、不跨进程；成功调用后清零；档位升档自 constants 读取。
"""

import time
from typing import Dict, Optional

from app.constants import (  # 2026-11-08 小欧: 从全局 constants 导入, 不重复定义(DRY)
    MODEL_COOLDOWN_STEPS,
    MODEL_QUOTA_COOLDOWN,
)
from app.logger import (
    log_and_print,  # 2026-11-08 小欧: log_and_print 供 console 观测冷却是否生效(收口 logger.info+print 为单点, 不并存 logger)
)


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
        # 2026-11-08 小欧 三堂会审: 只用 log_and_print(收口 logger.info+print 为单点), 不并存 logger.info——
        #   logger 与 _file_logger 共享同一文件 handler, 并存会同一行写文件两次 — 小欧-2026-11-08
        log_and_print(f"[ModelCooldown] {model_id} 标记冷却 {cooldown}s (hits={entry['hits']}, quota={is_quota})", level="WARNING")  # 2026-11-08 小欧: console 观测冷却生效(显式 WARNING: 默认 DEBUG 在 WARNING 档不上屏)

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
            # 2026-11-08 小欧 三堂会审: 只用 log_and_print(收口 logger.info+print 为单点), 不并存 logger.info(防同一行写文件两次) — 小欧-2026-11-08
            log_and_print(f"[ModelCooldown] {model_id} 成功调用，清除冷却", level="WARNING")  # 2026-11-08 小欧: console 观测冷却清零(显式 WARNING)
            del self._table[model_id]


__all__ = ["ModelCooldownRegistry"]
