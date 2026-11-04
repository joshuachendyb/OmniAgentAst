# -*- coding: utf-8 -*-
"""日志级别定义 — 小欧 2026-10-06

编辑历史:
2026-10-06 - 小欧 - ② 新增 RECOVERED 档(25, 介于 INFO20 与 WARNING30 之间)
2026-11-03 - 小欧 - 新增 to_level_int(): 级别名→logging 整数级别的唯一换算点(DRY),
  收口 LogConfig.get_console_level_int / log_and_print / shared_handler._get_file_level 三处 ——
  原三处各写一遍 getLevelName+isinstance, 其中 _get_file_level 用裸 getattr 遇坏配置直接 AttributeError
  让服务起不来(控制台侧却安全回落, 两边不一致) — 小欧-2026-11-03
"""
import logging

# 语义: 检测到异常, 但补偿动作已完成(资源已回收/状态已修复), 无需人工介入。
# 与既有事件层语义同源(react_inference._RECOVERABLE_ERRORS = {rejected, blocked, timeout}
# 的"可恢复≠失败"), 本档把同一区分下沉到日志层。
# 客观判据(两条同时成立才算 RECOVERED):
#   ①补偿动作已执行完毕且成功(不是"待兜底"/"重试仍失败"/"已放行但未完成");
#   ②失败后果已被消除, 无资源泄漏、无状态损坏。
# 取 25 的理由: 文件日志 level=INFO(20) 照常落盘留存证据; 控制台镜像 level=WARNING(30)
#   故不上控制台, 避免"已自愈"刷屏淹没真 ERROR。
RECOVERED = 25
logging.addLevelName(RECOVERED, "RECOVERED")


def log_recovered(logger, msg: str) -> None:
    """记一条已自愈事件(判据见 RECOVERED 定义); 唯一出口, 调用点不硬编码 25 — 小欧 2026-10-06"""
    logger.log(RECOVERED, msg)


def to_level_int(name: str, default: int = logging.INFO) -> int:
    """级别名→logging 整数级别(唯一换算点) — 小欧-2026-11-03

    非法/未知名回落 default, 两种口径的分歧只体现在传参上, 不再各写一套换算:
    - 配置值取 WARNING(坏配置不放大控制台噪音);
    - 行档位取 INFO(坏档位名不吞行, 照常落文件)。
    """
    lv = logging.getLevelName(str(name).upper())
    return lv if isinstance(lv, int) else default


__all__ = ["RECOVERED", "log_recovered", "to_level_int"]
