# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-17 小健 新建: 14.9.2 目录树【待补代码】落地, 依据 14.3.2 select + 14.5 装配过滤
#   2026-08-17 小健 补全: 各函数 docstring 补全适用场景/使用方法/前置条件/输入输出(043ed9c54)
#   2026-08-17 小健 改名: split_half_turn→truncate_oversized_message(名符其实); 模块函数引用同步
#   2026-08-17 小健 常量归属迁移(北京老陈驱动): 压缩/裁剪常量权威迁至 agent 层根 compaction_constants.py, 本模块导入路径由 compaction.compaction_constants 改为 app.services.agent.compaction_constants
# 2026-10-25 小欧 - find_tail_start 增 align_turn 参数(北京老陈令): True=切点对齐 user 边界, 整轮不拆
#   (user 与其回答同进退), 供 loop 裁剪杜绝"user 在旧段被丢、回答留保尾"的悬空; 默认 False, 压缩/降本
#   调用点(split_history_window / start_step 摘要前降本)行为不变 — 小欧-2026-10-25
# 2026-10-25 小欧 - 新增 find_recent_rounds_start(北京老陈令): 触发/预算计算不变, 仅裁剪发生时最近 N 个
#   FC 工具轮(assistant(tool_calls)+其 tool 结果)硬保护, 第 N+1 步起才按预算整轮裁; N 由
#   tuning.trim.keep_recent_rounds 配置(5-20, 默认 5), 不足 N 轮返回 prefix=不裁 — 小欧-2026-10-25
# 2026-10-26 小欧 - 三堂会审修复(北京老陈令): find_recent_rounds_start 不足N轮返回 prefix 修复(原 len(messages)
#   致保护区为空照裁); 新增 count_system_prefix 消除 prefix 计算三处重复(DRY) — 小欧-2026-10-26
# 2026-10-26 小欧 - 队列预算公式改(北京老陈令): budget_for_queue = budget_base × trigger_ratio² - 保护区token,
#   docstring 保护区/预算链说明同步更新 — 小欧-2026-10-26
# 2026-10-29 小欧 - 新增 resolve_protect_rounds(北京老陈令断案"系统路径整体最佳"): 保护区轮数与启动摘要注入件尾部
#   轮数收敛为单一真源(tuning.trim.keep_recent_rounds, clamp 5~20), 杜绝两处各自定5在调参时语义分裂(增强: 同一
#   保真哲学一个旋钮; 默认 5=5 零行为变化) — 小欧-2026-10-29
# 2026-10-29 小欧 - 魔法数字清账(北京老陈令): resolve_protect_rounds 夹取字面量 5/20 迁 PROTECT_ROUNDS_MIN/MAX
#   常量; preserve_recent_budget docstring 公式漂移订正为 TAIL_TOKEN_* 常量名(代码 2026-08-17 已用常量, 仅文档滞后)
#   — 小欧-2026-10-29
# 2026-10-30 小欧 - 三堂会审收尾(北京老陈令): ①truncate_oversized_message 的 _raw 写入改调
#   MessageBuilder.keep_full_raw —— 原裸写使二次截断把已存全文覆盖成本次截断头(实测 6000→4013), 与其
#   docstring"_raw 原内容"承诺相违; ②PROTECT_ROUNDS_MIN/MAX/KEEP_RECENT_ROUNDS 三常量 import 上提模块顶,
#   删 resolve_protect_rounds 函数内重复 import(每次调用重解析) — 小欧-2026-10-30
"""compaction.split_turn — 保尾切分原语(tail_start + 半轮劈分) — 小健 2026-08-17

职责(SRP): 仅承载「保尾 token 预算 + 半轮劈分」的切分原语, 供 assembler 装配线切分历史窗口。
设计文档: [4] 14.9.2 splitTurn / 14.3.2 select() / 10.1.8 S5 compaction 全模块。

切分只做位置/预算计算, 注入与摘要归 assembler/summary; token 估算复用 MessageBuilder._estimate_tokens(DRY);
system 恒保留, 切分保 FC 配对(保留 assistant(tool_calls) 必带其 tool);
absolute_start 供 assembler 定位 new_block(对应 generate_chunked_summary 增量块)。
"""
from typing import List, Dict, Tuple

from app.services.agent.compaction_constants import (
    KEEP_RECENT_ROUNDS,               # 2026-10-30 小欧: 保护区轮数默认值(原函数内重复 import, 上提模块顶)
    PROTECT_ROUNDS_MAX,               # 2026-10-30 小欧: 保护区轮数夹取上限(同上)
    PROTECT_ROUNDS_MIN,               # 2026-10-30 小欧: 保护区轮数夹取下限(同上)
    SPLIT_TURN_MAX_ASSISTANT_CHARS,
    TAIL_TOKEN_MAX,
    TAIL_TOKEN_MIN,
    TAIL_TOKEN_RATIO,
)
from app.services.agent.message_builder import MessageBuilder


def preserve_recent_budget(usable_tokens: int) -> int:
    """保尾 token 预算 = min(TAIL_TOKEN_MAX, max(TAIL_TOKEN_MIN, usable*TAIL_TOKEN_RATIO)) — 小健 2026-08-17

    适用场景: 任何需要"保尾 token 预算"处的统一计算(如 split_history_window 算保尾窗口)。
    使用方法: 传可用预算 token 数, 返回夹取后的保尾预算。
    输入: usable_tokens 可用预算 token 数。
    输出: int 保尾预算, 范围 [TAIL_TOKEN_MIN=2000, TAIL_TOKEN_MAX=8000]。
    前置条件: 无; 不是固定轮数而是 token 预算上限 8K。
    设计文档: [4] 14.3.2 select() 的 preserveRecentBudget()。
    """
    return min(TAIL_TOKEN_MAX, max(TAIL_TOKEN_MIN, int(usable_tokens * TAIL_TOKEN_RATIO)))


def count_system_prefix(messages: List[Dict]) -> int:
    """统计消息列表头部连续 system 消息数量 — 小欧 2026-10-26"""
    prefix = 0
    for msg in messages:
        if msg.get("role") == "system":
            prefix += 1
        else:
            break
    return prefix


def find_tail_start(messages: List[Dict], budget_tokens: int,
                    align_turn: bool = False) -> int:
    """定位尾部窗口起始下标, 满足 token 预算且不拆散 FC 对 — 小健 2026-08-17

    适用场景: 压缩前确定保尾区的起点下标(该下标之后原样保留)。
    使用方法: 传消息列表 + 保尾预算, 返回尾部起点下标(供切片 messages[:start]/[start:])。
    输入: messages 消息列表; budget_tokens 保尾 token 预算;
          align_turn 2026-10-25 小欧(北京老陈令): True=切点对齐到 user 边界(整轮不拆,
          user 与其回答同进退), loop 裁剪用; False=原行为(压缩/降本调用点不变)。
    输出: int 保尾起点下标; 空列表返回 0。
    前置条件: 无; 保尾三原则——system 恒保留(下标头不可动); 遇 assistant(tool_calls) 该对整体保留;
              倒序累计超预算即停; 保底返回 system 之后下标。
    设计文档: [4] 14.3.2 select()(从最新往前逐轮累计, 预算内整轮保留)。
    """
    if not messages:
        return 0
    prefix = count_system_prefix(messages)
    if prefix and MessageBuilder._estimate_tokens(messages[:prefix]) > budget_tokens:
        return prefix
    used = 0
    tail_start = prefix
    for i in range(len(messages) - 1, prefix - 1, -1):
        cost = MessageBuilder._estimate_tokens([messages[i]])
        if used + cost > budget_tokens:
            break
        used += cost
        tail_start = i
        if messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
            continue
    # 2026-10-25 小欧 align_turn: 切点须落在一轮起点(user), 整轮不拆 — loop 裁剪用(北京老陈令)
    if align_turn and tail_start > prefix and messages[tail_start].get("role") != "user":
        j = tail_start
        while j > prefix and messages[j].get("role") != "user":
            j -= 1
        if messages[j].get("role") == "user":
            extra = MessageBuilder._estimate_tokens(messages[j:tail_start])
            if used + extra <= budget_tokens:
                tail_start = j  # 回退到该轮 user 起点, 整轮保留
            else:
                k = tail_start
                while k < len(messages) and messages[k].get("role") != "user":
                    k += 1
                tail_start = k if k < len(messages) else j  # 超预算丢整轮; 无下轮则回退保本轮
    return tail_start


def find_recent_rounds_start(messages: List[Dict], n_rounds: int) -> int:
    """最近 n_rounds 个 FC 工具轮的起点下标(该下标及其之后为保护区) — 小欧 2026-10-25(北京老陈令)

    FC 工具轮 = 一次工具调用步: assistant(tool_calls) 及其全部 tool 结果。
    loop 裁剪发生时最近 N 步硬保护(裁剪切点不得侵入本区), 第 N+1 步起才允许按预算整轮裁。
    user 消息不参与轮数定义(loop 中 user 就 1~5 条, 必保是另一层职责)。

    保护区构成:
      hist[keep_from:] = 倒数第N个 asst(tool_calls) + 其 tool 结果
                      + 倒数第N-1个 asst(tool_calls) + 其 tool 结果
                      + ... + 倒数第1个 asst(tool_calls) + 其 tool 结果
                      + 末条 final answer(如有)

    保护区 token 用途:
      budget_for_queue = budget_base × trigger_ratio² - estimate_tokens(保护区)
      队列只能用触发阈值再乘系数后的剩余预算; 保护区超预算则不裁队列(budget_for_queue<0)

    示例(N=5):
      [system] [user] ... [asst(tool)] [tool] [asst(tool)] [tool] ... [asst(tool)] [tool] [asst(final)]
                    ↑ prefix              ↑ keep_from
                    |                     |
                    |-- 队列(可裁) --|--- 保护区(不裁) ---|
      保护区 = 倒数第5个 asst(tool) 起至末尾, 含其 tool 结果 + 末条 final answer

    边界情况:
      保护区 token > budget_base → budget_for_queue<0 → 不裁队列, 只保保护区
      工具轮 < N → keep_from=prefix → 保护区=全部非system → 队列空 → 不裁

    输入: messages 消息列表; n_rounds 保护轮数(规范 5-20, 默认 5, 经
          tuning.trim.keep_recent_rounds 配置)。
    输出: 从后往前数第 n_rounds 个 assistant(tool_calls) 的下标; 工具轮总数不足 n_rounds
          时返回 prefix(system 之后下标, 保护区覆盖全部非 system 消息, 即不裁)。
    """
    if not messages:
        return 0
    prefix = count_system_prefix(messages)
    count = 0
    for i in range(len(messages) - 1, prefix - 1, -1):
        m = messages[i]
        if m.get("role") == "assistant" and m.get("tool_calls"):
            count += 1
            if count >= n_rounds:
                return i
    # 工具轮不足 N: 返回 prefix → 保护区=全部非 system → 队列=空 → 不裁
    return prefix


def resolve_protect_rounds() -> int:
    """保护区/注入件尾部轮数唯一解析(单一真源): tuning.trim.keep_recent_rounds, 夹取 5~20 — 小欧-2026-10-29

    适用场景: 运行时裁剪保护区(message_builder._keep_recent_rounds)与启动摘要注入件尾部轮数
      (start_step._extract_summary_tail)共用同一保真哲学("最近 N 个 FC 工具轮不许 degrade"),
      必须同源同值——两处各自定 5 会在运维调参时语义分裂(调保护区 10 而注入件仍 5)。
    使用方法: 直接调用, 返回轮数; 消费方(find_recent_rounds_start / 附件提取)持返回值走流程。
    输出: int, clamp 到 [PROTECT_ROUNDS_MIN, PROTECT_ROUNDS_MAX], 默认 KEEP_RECENT_ROUNDS。
    关联逻辑: 与 message_builder 旧夹取表达式同式(收敛后该处改调本函数, 全域只此一处算式)。
    """
    from app.config import get_config   # app.config 零业务依赖, 不入循环
    return max(PROTECT_ROUNDS_MIN, min(PROTECT_ROUNDS_MAX, int(get_config().get('tuning.trim.keep_recent_rounds', KEEP_RECENT_ROUNDS))))


def truncate_oversized_message(tool_msgs: List[Dict]) -> List[Dict]:
    """半轮劈分: 单一 tool 消息超长时压缩其 content(不拆配对外散) — 小健 2026-08-17

    适用场景: 超长单条 tool/assistant 消息需控窗但又不想拆散 FC 对时, 对该条做头部截断。
    使用方法: 传该轮的消息列表, 返回截断处理后的新列表(超长条保留头段+标记)。
    输入: tool_msgs 单轮消息列表。
    输出: 新列表; 超长条(>SPLIT_TURN_MAX_ASSISTANT_CHARS=4000)截为头段 + "…[split_turn]",
          带 `_raw` 原内容与 `_truncated=True` 标记。
    前置条件: 无; 只对单条消息做内容截断, 不把轮次消息拆成两段(与「保尾不动刀」语义一致);
              真正的对级劈分由 find_tail_start 逐条累计天然完成。
    设计文档: [4] 14.3.2 splitTurn「该轮内部劈分——只保留该轮后半段消息」。
    """
    result: List[Dict] = []
    for msg in tool_msgs:
        if msg.get("role") in ("tool", "assistant"):
            raw = str(msg.get("content", "") or "")
            if len(raw) > SPLIT_TURN_MAX_ASSISTANT_CHARS:
                m = dict(msg)
                # 2026-10-30 小欧: _raw 写入收口 MessageBuilder.keep_full_raw(DRY) —— 原裸写会在二次
                #   截断时把已存的全文覆盖成本次的截断头, 与 docstring"_raw 原内容"承诺相违
                MessageBuilder.keep_full_raw(m, raw)
                m["content"] = raw[:SPLIT_TURN_MAX_ASSISTANT_CHARS] + "…[split_turn]"
                m["_truncated"] = True
                result.append(m)
                continue
        result.append(msg)
    return result