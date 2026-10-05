# -*- coding: utf-8 -*-
"""日志级别定义 — 小欧 2026-10-06

编辑历史:
2026-10-06 - 小欧 - ② 新增 RECOVERED 档(25, 介于 INFO20 与 WARNING30 之间)
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


__all__ = ["RECOVERED", "log_recovered"]
