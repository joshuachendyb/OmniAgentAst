
"""
日志工具模块 — 统一入口
整合 log_config(通用日志)

创建时间: 2026-07-10
迁移更新: 2026-07-10 小欧 — 从 utils/log_config/ 迁入合并
"""
# 编辑历史:
# 2026-07-23 小欧 - 新增公共函数 log_and_print(): 将 logger.info(msg)+print(msg) 双输出模式收口到统一函数, 解决 console handler 仅 WARNING 以上级别时 info 日志无法上控制台的问题; 导出至 __all__
# 2026-08-30 小欧 - 控制台镜像离线化(根治 case09 挂起): log_and_print 的 print(msg)→console_put(msg), 事件循环线程零同步 stdout 写; stdout 阻塞时只丢控制台镜像, logger.info 文件日志始终完整
# 2026-10-06 小欧 - ② 导出 RECOVERED/log_recovered(已自愈档 25) 并入 __all__
# 2026-11-03 小欧 - log_and_print 新增 level 参数(默认 DEBUG=进度类): 控制台通道改由 logging.console_level 判定
#   (level >= 阈值才上屏), 文件通道固定 INFO 不随档位丢失; 18 处安全/异常/取消/任务起止调用点显式传 WARNING — 小欧-2026-11-03
# 2026-11-03 小欧 - 修控制台重复行: 文件通道改用无控制台 handler 的 _file_logger, 控制台只留 console_put 一条;
#   原实现阈值≤INFO 时 ConsoleMirrorHandler 与 console_put 各打一行且 level 形同失效 — 小欧-2026-11-03
# 2026-11-03 小欧 - 口径调整(北京老陈令): 业务步骤行([Thought]/[Action]/[Final]/[Loop]/[action_handler]/[start_summary]/
#   [start_step]/[StepEmit]/[SSE]心跳/任务启动时间戳/[Runner]锚点)统一显式传 level="WARNING", 默认档即可见 — 小欧-2026-11-03
# 2026-11-03 小欧 - 控制台判定由 >= 改 ==(北京老陈令: 是哪个级别就只打哪个级别, 不连带其他级别; 早先 >= 语义作废):
#   log_and_print 与 ConsoleMirrorHandler 同口径, 文件通道仍为 >= 阈值 — 小欧-2026-11-03
# 2026-11-03 小欧 - 文件通道改按声明档位落盘(北京老陈令: 控制台只是"看", 其余必须完整进日志文件):
#   原 _file_logger.info() 固定 INFO, file_level=WARNING 时 WARNING 档步骤行整行丢失 → 改 _file_logger.log(_lv, msg);
#   非法档位名回落 INFO 不吞行 — 小欧-2026-11-03
# 2026-11-03 小欧 - 两档位彻底解耦(北京老陈令: 各自设置各自的, 不能有关系): 删 shared_handler 的
#   _get_gate_level()=min(文件, 控制台), 总闸恒定 DEBUG; 文件 handler 只认 file_level, 控制台 handler 只认
#   console_level — 改一项对另一条通道零影响 — 小欧-2026-11-03
# 2026-11-03 小欧 - 换算收口 DRY: 行档位换算改走 levels.to_level_int(与 LogConfig.get_console_level_int 同源),
#   原本文件内联 getLevelName+isinstance — 小欧-2026-11-03
# 2026-11-03 小欧 - 撤销双键(北京老陈令: 一个值即可, 拆两个是画蛇添足): 控制台与文件共用 logging.level,
#   用法不同 —— 控制台只显示 == 该值的行, 文件按原逻辑 >= 该值(常规阈值, 调试模式开时强制 DEBUG);
#   log_and_print 代码不变, 只改注释口径 — 小欧-2026-11-03
# 2026-11-08 小欧 用户提示补漏: log_and_print docstring 增「公共函数说明」块(职责/适用/不适用/通道/幂等) +
#   「level 上屏机制速查」块(①level 是档位声明非阈值 ②上屏判定==精确匹配 ③WARNING 档默认 DEBUG 不上屏
#   ④观测行须显式 WARNING ⑤换算点 to_level_int 非法回落 INFO) — 小欧-2026-11-08

import logging

from app.logger.config import SafeRotatingFileHandler, LogConfig, LOG_DIR
from app.logger.shared_handler import setup_logger, ConsoleMirrorHandler
from app.logger.api_logger import APILogger
from app.logger.console_writer import console_put  # 小欧 2026-08-30 控制台镜像离线化(根治 case09 挂起)
from app.logger.levels import RECOVERED, log_recovered, to_level_int  # ② 已自愈档(25) — 小欧 2026-10-06

api_logger = APILogger()
logger = setup_logger(__name__)

# 2026-11-03 小欧 - log_and_print 文件通道专用 logger: 摘掉共享装配挂上的控制台镜像 handler, 两通道互不串扰
#   (共用 logging.level 一个值); refresh_log_levels 只改 handler 级别, 不会加回 handler — 小欧-2026-11-03
_file_logger = setup_logger(__name__ + ".file_only")
_file_logger.handlers = [h for h in _file_logger.handlers if not isinstance(h, ConsoleMirrorHandler)]


def log_and_print(msg: str, level: str = "DEBUG") -> None:
    """【公共函数】同时输出到日志文件和控制台 — 小欧 2026-07-23 (2026-08-30 小欧 print→console_put 离线化)

    公共函数说明(全模块共用, 经 __all__ 导出):
    - 职责: 一条消息既进日志文件、又上控制台, 收口"logger.info(msg)+print(msg)"双输出为单点。
    - 适用: 需要控制台可见且文件留痕的观测行(业务步骤/安全/异常/取消/任务起止/冷却等)。
    - 不适用: 纯流水(仅文件)用 logger.info; 纯控制台不需要文件用 print 即可。
    - 通道: 文件通道=_file_logger(不挂控制台 handler), 控制台通道=console_put 唯一一条, 两通道互不串扰。
    - 幂等: 同一行恰好一条文件记录 + 至多一条控制台行, 无重复。

    两通道职责分离, 共用 logging.level 一个配置值、两种用法(北京老陈令 2026-11-03, 不得拆成两个设置):
    - 文件通道 = _file_logger(不挂控制台 handler), 按「该行声明档位」落盘, 唯一裁决点是文件 handler 的
      logging.level(>= 阈值, 原逻辑; 调试模式开时强制 DEBUG); 任何档位恰好一行, 无重复。
    - 控制台通道 = console_put 唯一一条, 唯一裁决点是 logging.level 精确匹配: level == 该值才上屏,
      不连带更高/更低级别 → 控制台只看到所选档自己的行。
    level 由调用点按"该行属于哪一档"决定: 业务步骤/安全/异常/取消/任务起止一律传 WARNING
    (值=WARNING 时可见); INFO 档=常规流水 — 小欧-2026-11-03

    【level 上屏机制速查】(用户提示 2026-11-08, 后续排查直接看这里):
     ① level 是"该行属于哪一档"的声明, 不是过滤阈值; 默认 DEBUG。
     ② 控制台上屏判定 = 精确匹配(==): _lv == LogConfig.get_console_level_int() 才 console_put,
        NOT >= 阈值 —— 档位不相等那行永远不上屏(2026-11-03 老陈令: 是哪个级别就只打哪个级别)。
     ③ 当前 logging.level=WARNING → console_int=30; 默认 DEBUG 换算 _lv=10, 10 != 30 → 只落文件不上屏。
     ④ 业务/异常/取消/任务起止/冷却等观测行, 必须显式声明 level="WARNING" 才在 WARNING 档上屏;
        文件通道仍 >= 阈值完整落盘, 不随上屏档位丢失。
     ⑤ 唯一换算点 to_level_int(name, default) 内部 .upper(), "warning"/"WARNING"/logging.WARNING(30) 皆可,
        非法档位名回落 default=INFO 不吞行(该行照常落文件, 只是不上屏)。
    """
    _lv = to_level_int(level, logging.INFO)  # 非法档位名不吞行: 按常规流水落盘, 控制台上屏判定自然不等
    _file_logger.log(_lv, msg)
    if _lv == LogConfig.get_console_level_int():
        console_put(msg)


__all__ = [
    "SafeRotatingFileHandler",
    "LogConfig",
    "LOG_DIR",
    "setup_logger",
    "APILogger",
    "logger",
    "api_logger",
    "log_and_print",
    "RECOVERED",
    "log_recovered",
]
