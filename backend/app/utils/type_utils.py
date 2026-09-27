# -*- coding: utf-8 -*-
"""
type_utils — 无依赖的类型转换工具

⚠️ 本模块**刻意不 import 任何项目内模块**。原因: `app.utils.text_utils` 在模块级
`from app.logger import logger`，而 `app.logger.config` 又 `from app.config import get_config`
—— 若把纯函数放进 text_utils，`app.config` 就无法复用它（循环导入）。
放在无依赖的叶子模块里，app.config 与各 service 才能共用同一份实现（DRY）。

编辑历史:
  2026-09-27 小欧 - 新建。抽出 to_int_or，消除配置出口各写一套 int 兜底的重复实现。
    起因：本轮把 config_service 的 timeout/max_retries 改成 `or 60/3`，把 0 吞成默认值
    （`max_retries: 0` = 不重试 属合法配置，且 2026-09-21 已明文修过一次此坑）。
    ⚠️ 本模块必须保持零项目内 import —— 一旦 import app.logger/app.config，
    app.config 就无法复用 to_int_or（config → utils → app.logger → config 成环）。
    已有守护测试 tests/test_to_int_or_guard.py（含反向注入验证）。
"""
from typing import Any


def to_int_or(value: Any, default: int) -> int:
    """配置值转 int：None / 非数字字符串 / 无法转换的类型一律回落 default。

    三条语义边界，缺一不可:
      ① `value is None` 才回落 —— **0 是合法值**（如 `max_retries: 0` = 不重试），
         写成 `value or default` 会把 0 吞成默认值（2026-09-21 已修过这个坑，勿改回）；
      ② 数字字符串("60")正常转换 —— yaml 手写成带引号不应导致接口 500
         （Pydantic v2 lax 模式其实也会强转，但脏值不该依赖 DTO 兜底）；
      ③ 非法字符串("abc")回落默认值而非抛 ValueError —— 出口归一，不让脏配置穿透成 500。
    """
    if value is None:
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default
