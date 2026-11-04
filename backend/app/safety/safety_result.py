# -*- coding: utf-8 -*-
"""safety_result — 安全检查结果契约(安全层单一定义源) — 小欧 2026-10-18

编辑历史:
2026-10-18 - 小欧 - 新建: SafetyResult 契约回迁系统层, 自 app/tools/tool_types.py 迁入。
  生产者(delete/write/read_path_check、shell_command_risk、shell_danger_command、
  path_legality_router、path_tool_safety_checker、dual_path_check、shell_path_check)全部在
  app/safety/ 内; 消费者在 app/services/(safety_gate/hitl_gateway/tool_facade)与工具层
  只读字段(execute_shell_command 只读 blocked/needs_confirm, 不 import 本类)。
  契约随生产者走, 落在安全层即免去用工具层模块迁就安全语义。禁 backward 双份契约。
2026-10-18 - 小欧 - 新增 SafetyLevel StrEnum + CONFIRM_LEVELS / BLOCK_LEVELS, safety_level 取值单源化。
  病根: 原 safety_level 自由字符串, 且 path_auth 一个标签同时覆盖放行/硬拦/任务级授权/临时授权/沙箱裁决
  五种语义 —— 标签只回答"为什么", 标签与分支必然对不上, 同一句文案还会配出不同分类。
  改法: 据"标签只回答为什么、怎么办由 blocked/needs_confirm 精确表达"拆成两个**互斥命名空间**,
  前缀即区分: 确认命名空间 13 项(needs_confirm=True, 唯一有消费者的地方, 进 HITL 弹窗、前端按标签渲染)、
  硬拦命名空间 4 项(blocked=True, 不进弹窗, 仅诊断留痕)。两空间永不重叠。
  放行结果一律不带标签(空串): 无确认无拦截, 无"分类"可言。字段注释同步收窄为"取值必须取自 SafetyLevel"。
2026-10-19 - 小欧 - 删孤儿枚举 DELETE_SAFE: 全库无生产者(删线确认档恒为 DELETE_OUTSIDE_WHITELIST,
  见 delete_path_check), 仅 safety_gate._resolve_trust_impact 与前端 SAFETY_LEVEL_CONFIG 防御性列出 ——
  按 YAGNI 从枚举/CONFIRM_LEVELS 移除, 两处消费点同步清理(前端键集须与 CONFIRM_LEVELS 恒等)。

分层: 本文件只持契约(纯 dataclass, 无任何逻辑), 不做任何判定。
"""
from dataclasses import dataclass
from enum import StrEnum
from typing import Optional


class SafetyLevel(StrEnum):
    """safety_level 取值单源 — 小欧 2026-10-18

    标签只回答"**为什么**", 不回答"怎么办" —— 怎么办由 blocked / needs_confirm 两个布尔精确表达。
    据此拆成两个**互斥**命名空间, 前缀即区分, 两空间永不重叠(此前 path_auth 一个标签同时
    覆盖放行/硬拦/任务级授权/临时授权/沙箱裁决五种语义, 标签与分支必然对不上):

    ┌ 确认命名空间(needs_confirm=True, 唯一有消费者的地方) ── 进 HITL 弹窗, 前端按标签渲染 ┐
      delete_outside_whitelist  白名单外删除/递归删, 需临时授权     delete_path_check
      write_forbidden       非系统禁区写入, 任务级授权            write_path_check
      write_outside_whitelist 白名单外写入, 需临时授权           write_path_check
      shell_medium_risk     中风险命令(重启/改执行策略/杀进程…); 命令层, 与路径无关, 作用域=整条命令
      shell_delete_confirm  命令含删除动作, 需确认               命令内路径动作=删
      shell_write_confirm   命令含写入动作, 需确认               命令内路径动作=写
      shell_read_confirm    命令含读取动作, 需确认               命令内路径动作=读
      shell_command_confirm 命令无路径动作(整条命令级), 需确认
      sql_execute_confirm   execute_sql 整条确认          (execute = 执行, 自带动词)
      task_deal_confirm      create_task / delete_task 整条确认 (deal = 处理/处置)
      registry_deal_confirm  registry_write / registry_delete 整条确认 (deal = 处理/处置)
      tool_confirm           未细分域的工具级确认(兜底; 不谎称命令/写/删)
    └──────────────────────────────────────────────────────────────────────────────────────┘
    ★ 命令内【路径的读/写/删】各有归属, 二者不重复编码:
      · 动作**越权**时(路径不在允许范围/命中禁区) → 三线标签:
        写 WRITE_FORBIDDEN / WRITE_OUTSIDE_WHITELIST; 删 DELETE_OUTSIDE_WHITELIST; 读线从不确认
      · 动作**合规但命令仍需确认**时(工具元数据策略) → 本表的 shell_*_confirm 四类, 按命令实际动作取档。
    ┌ 硬拦命名空间(blocked=True) ── 不进弹窗, 标签只作诊断留痕, 前端不消费 ────────────────┐
      path_forbidden        路径硬拦: 磁盘根/系统保护目录/系统禁区/代码目录/允许根集自身及上级
                            (R6 根集外递归删除亦归此 —— 同属路径策略硬拦, 非命令层问题)
      block_command         危险命令/命令层输入非法/非法 shell 元字符
      block_path_invalid    路径非法: 空值/`..`穿越/格式化失败/安全判定不可用(fail-closed)
      block_unregistered    工具未注册
    └──────────────────────────────────────────────────────────────────────────────────────┘

    放行结果一律不带标签(空串): 无确认无拦截, 无"分类"可言。
    """
    # ── 确认命名空间(进 HITL 弹窗) ──
    DELETE_OUTSIDE_WHITELIST = "delete_outside_whitelist"
    WRITE_FORBIDDEN = "write_forbidden"
    WRITE_OUTSIDE_WHITELIST = "write_outside_whitelist"
    SHELL_MEDIUM_RISK = "shell_medium_risk"
    SHELL_DELETE_CONFIRM = "shell_delete_confirm"
    SHELL_WRITE_CONFIRM = "shell_write_confirm"
    SHELL_READ_CONFIRM = "shell_read_confirm"
    SHELL_COMMAND_CONFIRM = "shell_command_confirm"
    SQL_EXECUTE_CONFIRM = "sql_execute_confirm"
    TASK_DEAL_CONFIRM = "task_deal_confirm"
    REGISTRY_DEAL_CONFIRM = "registry_deal_confirm"
    TOOL_CONFIRM = "tool_confirm"       # 未细分域的工具级确认(诚实兜底: 不谎称是命令/写/删)
    # ── 硬拦命名空间(不进弹窗) ──
    PATH_FORBIDDEN = "path_forbidden"
    BLOCK_COMMAND = "block_command"
    BLOCK_PATH_INVALID = "block_path_invalid"
    BLOCK_UNREGISTERED = "block_unregistered"


#: 确认命名空间取值集合 —— 前端 SAFETY_LEVEL_CONFIG 的键集必须与此完全相等(一致性测试锁定)
CONFIRM_LEVELS = frozenset({
    SafetyLevel.DELETE_OUTSIDE_WHITELIST,
    SafetyLevel.WRITE_FORBIDDEN, SafetyLevel.WRITE_OUTSIDE_WHITELIST,
    SafetyLevel.SHELL_MEDIUM_RISK, SafetyLevel.SHELL_DELETE_CONFIRM,
    SafetyLevel.SHELL_WRITE_CONFIRM, SafetyLevel.SHELL_READ_CONFIRM,
    SafetyLevel.SHELL_COMMAND_CONFIRM, SafetyLevel.SQL_EXECUTE_CONFIRM,
    SafetyLevel.TASK_DEAL_CONFIRM, SafetyLevel.REGISTRY_DEAL_CONFIRM,
    SafetyLevel.TOOL_CONFIRM,
})

#: 硬拦命名空间取值集合 —— 仅诊断留痕, 前端不消费
BLOCK_LEVELS = frozenset({
    SafetyLevel.PATH_FORBIDDEN, SafetyLevel.BLOCK_COMMAND,
    SafetyLevel.BLOCK_PATH_INVALID, SafetyLevel.BLOCK_UNREGISTERED,
})


@dataclass
class SafetyResult:
    """安全检查结果 — 替代raw dict — 小欧 2026-06-25

    字段全部为安全裁决语义, 由各判定分支直接构造(kwarg), 丢一个字段即 TypeError。
    """
    blocked: bool = False
    needs_confirm: bool = False
    message: str = ""
    safety_level: str = ""          # 取值必须取自 SafetyLevel; 空串=放行(无确认无拦截, 无分类可言)
    auto_confirm: bool = False
    auth_path: Optional[str] = None
    sandbox_required: bool = False  # 沙箱预检触发标记: 由 path_tool_safety_checker 四条置位路径点亮,
                                     #   action_handler 仅对 True 者调 SandboxExecutor.pre_execute;
                                     #   缺省 False 不改变既有安全流(非破坏性工具不进沙箱预检)

    @staticmethod
    def pass_result() -> "SafetyResult":
        """放行结果工厂(每次新建实例, 防共享单例被下游改写) — 小欧 2026-10-17(三线/通道统一放行)

        供 path_legality_router / dual_path_check / shell_path_check 复用, 免三份拷贝与循环导入。
        """
        return SafetyResult(blocked=False, needs_confirm=False, message="")


__all__ = ["SafetyResult", "SafetyLevel", "CONFIRM_LEVELS", "BLOCK_LEVELS"]
