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
    2026-10-31 小欧 - 新增 to_dict_or / safe_sub_dict(三堂会审同源修复): 工具返回结构逐层下钻的
      类型防御原先在 observation_formatter(_safe_llm_sub) 与 toolhelper.tool_utils 各写一份,
      且 tool_utils 用的 `.get(k, {})` 只防缺键、不防 None/str。收敛为公用函数, 两处改调;
      本模块仍保持零项目内 import。— 小欧-2026-10-31
"""
from typing import Any


def to_dict_or(value: Any) -> dict:
    """把任意值归一为 dict: dict 原样返回, None/str/list 等一律返回 {}。

    适用场景: 工具返回的 llm_data 及其子结构(status/action/params)由各工具自行拼装,
      类型不受约束(实测存在 str、None);取值前必须先归一, 否则 `.get` 触发 AttributeError。
    使用方法: 直接调用; 需要取子结构用 safe_sub_dict, 单层取键后归一用它。
    输入: value —— 任意对象。
    输出: 原 dict 或空 dict(永不抛异常, 永不返回 None)。
    前置条件: 无。
    设计边界: 与 `(value or {})` 的区别 —— 后者只防 None/空值, 真值 str 仍会崩(2026-08-18 已踩过);
      本函数用 isinstance 判定, 覆盖 None/str/list/int 全部畸形输入。
    """
    return value if isinstance(value, dict) else {}


def safe_sub_dict(data: Any, key: str) -> dict:
    """安全取子字典: data[key] 是 dict 则返回它, 否则返回 {} —— 小欧 2026-10-31

    适用场景: 嵌套结构逐层下钻(llm_data → status / action → params), 每层类型都不可信。
    使用方法: safe_sub_dict(safe_sub_dict(llm_data, "action"), "params").get("path", 默认) 。
    输入: data —— 任意对象(非 dict 视作空); key —— 要取的键。
    输出: 子 dict 或空 dict(永不抛异常)。
    前置条件: 无; 若确实需要区分"键不存在"与"值为 None", 本函数不适用, 请显式判断。
    关联逻辑: toolhelper.tool_utils.save_text_to_file 与 observation_formatter 的
      status/action 取值共用本函数(同一防御真源), 不再各写 isinstance 判定或 `.get(k, {})`。
    """
    return to_dict_or(to_dict_or(data).get(key))


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
