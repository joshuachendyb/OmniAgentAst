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
# 2026-10-31 小欧 - 三堂会审整改(北京老陈令): ①find_tail_start 增 estimator 形参(缺省原文口径) —— 摘要路径
#   按 feed 口径判"该裁", 保尾边界也必须按 feed 算, 否则判与裁两把尺(实测预算 8000 时现役保尾 6 条/2648 tok,
#   按 feed 应为 14 条/6981 tok, 即白丢 8 条本可容纳的尾部上下文); ②truncate_tool_call_args 由 assembler 迁入
#   —— 与 truncate_oversized_message 同为"单条消息超长就截"的切分原语, 装配线只编排不持原语;
#   ③其原文改存 _args_raw(keep_full_raw 带 key), 不再与 content 原文抢 _raw 同一字段 — 小欧-2026-10-31
# 2026-10-31 小欧 - 实测修正(北京老陈令): 原"从 JSON 文本中间切"会让 arguments 变成非法 JSON, 真机 provider
#   agnes 直接 400 "Assistant tool call arguments must be valid JSON"(DeepSeek 不校验, 故不能靠猜), 与"截参数是
#   防 400 的最后防线"初衷相反; 现改结构化裁剪 _fit_args_json(解析→长字符串值保首→重序列化, 键名/短值/层级
#   全保留), 非法原文退化为合法 JSON 信封; 顺带修 fn 非 dict 的 TypeError、arguments 为结构体时 str(dict)
#   产出 Python repr 的问题。 — 小欧-2026-10-31
# 2026-10-31 小欧 - 无 user 边界的 delta 段改判当前轮: 原默认 last_turn=len(messages) 把整段当旧轮(参数只保 500,
#   实测 361 字), 模型认不出自己刚写的文件; 改取最后一轮 FC 决策起点作当前轮(仅它按 4000), 其余仍按 500。— 小欧-2026-10-31
# 2026-10-31 小欧 - 删 find_tail_start 循环尾空 continue; docstring 订正 FC 配对来源(align_turn + 调用方剪孤儿)。— 小欧-2026-10-31
"""compaction.split_turn — 保尾切分原语(tail_start + 半轮劈分) — 小健 2026-08-17

职责(SRP): 仅承载「保尾 token 预算 + 半轮劈分」的切分原语, 供 assembler 装配线切分历史窗口。
设计文档: [4] 14.9.2 splitTurn / 14.3.2 select() / 10.1.8 S5 compaction 全模块。

切分只做位置/预算计算, 注入与摘要归 assembler/summary; token 估算复用 MessageBuilder._estimate_tokens(DRY);
system 恒保留; FC 配对: align_turn 对齐 user 边界(整轮不拆), 非 align_turn 可能切在配对中间, 由调用方剪孤儿。
absolute_start 供 assembler 定位 new_block(对应 generate_chunked_summary 增量块)。
2026-10-31 小欧: 本模块两类原语 —— 位置/预算计算(find_tail_start 等) + 单条超长截断
  (truncate_oversized_message 截 content / truncate_tool_call_args 截 tool_calls.arguments), 体积估算
  一律可按调用方口径(estimator)传入, 保证"按什么尺判就按什么尺裁"。— 小欧-2026-10-31
"""
import json
from typing import Dict, List

from app.logger import logger
from app.services.agent.compaction_constants import (
    KEEP_RECENT_ROUNDS,  # 2026-10-30 小欧: 保护区轮数默认值(原函数内重复 import, 上提模块顶)
    PROTECT_ROUNDS_MAX,  # 2026-10-30 小欧: 保护区轮数夹取上限(同上)
    PROTECT_ROUNDS_MIN,  # 2026-10-30 小欧: 保护区轮数夹取下限(同上)
    SPLIT_TURN_MAX_ASSISTANT_CHARS,
    TAIL_TOKEN_MAX,
    TAIL_TOKEN_MIN,
    TAIL_TOKEN_RATIO,
    TOOL_SUMMARY_HEAD_CHARS,  # 2026-10-31 小欧: 旧轮 tool 输出/工具参数保首门限(4000 的 1/8, 迁入用)
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
                    align_turn: bool = False, estimator=None) -> int:
    """定位尾部窗口起始下标, 满足 token 预算且不拆散 FC 对 — 小健 2026-08-17

    适用场景: 压缩前确定保尾区的起点下标(该下标之后原样保留)。
    使用方法: 传消息列表 + 保尾预算, 返回尾部起点下标(供切片 messages[:start]/[start:])。
    输入: messages 消息列表; budget_tokens 保尾 token 预算;
          align_turn 2026-10-25 小欧(北京老陈令): True=切点对齐到 user 边界(整轮不拆,
          user 与其回答同进退), loop 裁剪用; False=原行为(压缩/降本调用点不变)。
          estimator 2026-10-31 小欧: 体积估算函数, 缺省 MessageBuilder._estimate_tokens(原文口径)。
          **必须与调用方判定所用的尺一致** —— 摘要路径按 feed 体积判"该裁", 此处也要按 feed 算预算,
          否则同一份预算在 feed 口径下能装 2 倍以上的尾部消息, 会白丢尾部上下文(实测 6 条 vs 14 条);
          loop 裁剪不传即维持原行为。
    输出: int 保尾起点下标; 空列表返回 0。
    前置条件: 无; 保尾三原则——system 恒保留(下标头不可动); 倒序逐条累计, 超预算即停;
              保底返回 system 之后下标。FC 配对不在本函数保证, 由 align_turn 对齐 user 边界,
              非 align_turn 时切点可能落在配对中间, 由调用方剪孤儿。
    设计文档: [4] 14.3.2 select()(从最新往前逐轮累计, 预算内整轮保留)。
    """
    if not messages:
        return 0
    estimate = estimator or MessageBuilder._estimate_tokens
    prefix = count_system_prefix(messages)
    if prefix and estimate(messages[:prefix]) > budget_tokens:
        return prefix
    used = 0
    tail_start = prefix
    for i in range(len(messages) - 1, prefix - 1, -1):
        cost = estimate([messages[i]])
        if used + cost > budget_tokens:
            break
        used += cost
        tail_start = i
    # 2026-10-25 小欧 align_turn: 切点须落在一轮起点(user), 整轮不拆 — loop 裁剪用(北京老陈令)
    if align_turn and tail_start > prefix and messages[tail_start].get("role") != "user":
        j = tail_start
        while j > prefix and messages[j].get("role") != "user":
            j -= 1
        if messages[j].get("role") == "user":
            extra = estimate(messages[j:tail_start])
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
    from app.config import get_config  # app.config 零业务依赖, 不入循环
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


def _clip_json_strings(node, budget: int):
    """递归把 JSON 结构里超长的字符串值截到 budget 字(保首), 键名/短值/层级原样 — 小欧 2026-10-31

    存在理由: tool_calls.arguments 在 wire 上必须是**合法 JSON 字符串**(实测 agnes 直接 400
    "Assistant tool call arguments must be valid JSON"), 所以体积只能从"字符串值"里省, 不能从
    JSON 文本中间切。
    """
    if isinstance(node, str):
        return node if len(node) <= budget else node[:budget] + "…[split_turn]"
    if isinstance(node, list):
        return [_clip_json_strings(x, budget) for x in node]
    if isinstance(node, dict):
        return {k: _clip_json_strings(v, budget) for k, v in node.items()}
    return node


def _fit_args_json(args_text: str, limit: int) -> str:
    """把超长 arguments 压成「合法 JSON + 保首 + 尽量留结构」, 总长不超 limit 量级 — 小欧 2026-10-31

    两种策略(先优后劣):
      ① 能解析成 dict/list → 逐级收紧"单个字符串值预算"(limit → 2/3 → 1/2 → 1/3 → 1/4 → 64),
         取第一个整体 <= limit 的结果 —— 键名/短值(如 path)/嵌套层级全保留, 只砍长正文;
      ② 原文本身不是合法 JSON(历史坏数据) 或结构本身(键名)就超预算 → 退化为合法 JSON 信封
         {"_truncated":true,"_original_chars":N,"_head":"<首段>"}, 头部可读性仍保留。
    输出必为合法 JSON —— 这是 provider 的硬要求, 比"多留几个字"重要(不合法 = 整请求 400)。
    """
    try:
        parsed = json.loads(args_text)
    except Exception:
        parsed = None
    if isinstance(parsed, (dict, list)):
        for _b in (limit, limit * 2 // 3, limit // 2, limit // 3, limit // 4, 64):
            text = json.dumps(_clip_json_strings(parsed, _b), ensure_ascii=False)
            if len(text) <= limit:
                return text
    env = {"_truncated": True, "_original_chars": len(args_text), "_head": ""}
    head = args_text[: max(1, limit // 2)]
    while True:
        env["_head"] = head
        text = json.dumps(env, ensure_ascii=False)
        if len(text) <= limit or not head:
            return text
        head = head[: len(head) * 2 // 3]


def truncate_tool_call_args(messages: List[Dict]) -> List[Dict]:
    """截断 assistant tool_calls.arguments 超长参数, 保首段 + 留原文 — 小欧 2026-10-31

    适用场景: shrink_to_budget 第3级——「单轮/中段塞进巨型 tool 参数」(如 write 90 万字正文), 第1/2级
      (截 content / 清 tool 输出)对它空转(参数不在 content 里), 不截就只能靠丢整轮, 那是拿整段对话换体积。
    使用方法: 传消息列表, 返回参数已截断的新列表(无超长参数则原样返回元素, 不拷贝)。
    输入: messages 消息列表。
    输出: List[Dict]; 超长 arguments 压成合法 JSON(长字符串值保首 + "…[split_turn]"), 原文经
          MessageBuilder.keep_full_raw 存 _args_raw(与 content 的 _raw 分字段), 置 _truncated=True
          (与第1级同一标记, 请求前随 _COMPACTION_TEMP_KEYS 剥离)。
    保首门限(复用既有常量, 不新增参数):
      - 最后一条 user 之前的旧轮: TOOL_SUMMARY_HEAD_CHARS(= SPLIT_TURN_MAX_ASSISTANT_CHARS/8, 500 字)——
        旧轮参数只为摘要/回看"当时写了哪个文件、开头写了什么", 与第2级 tool 输出保首同一把尺。
      - 当前轮(最后一条 user 起): SPLIT_TURN_MAX_ASSISTANT_CHARS(4000 字)——与第1级对 content 的截断同门限;
        当前轮不设成"一点不动", 因为走到这一级时已别无他法(不截 → 请求 400 全盘皆输), 4000 字足以让模型
        认出自己写过什么, 而 90 万字参数照样能压到 2.1k tok。
      - 无 user 边界(链中途切出的 delta 段): 取最后一轮 FC 决策起点作当前轮, 仅它保 4000, 其余按旧轮
        500(2026-10-31 小欧: 原默认整段按旧轮, 实测把当前轮参数压到 361 字)。
    前置条件: 无; 不动 tool_calls 的 id/name 与 tool 消息, FC 配对关系不变。
    关联逻辑: 全链路唯一处理 arguments 体积的位置(PASS3_ARGS_* 两个常量至今无消费方);
      **截后必须仍是合法 JSON**(实测 agnes 400 "arguments must be valid JSON", DeepSeek 不校验)——
      故按结构化裁剪(见 _fit_args_json), 不走"从文本中间切"; 真值可由 _args_raw 还原。
    位置: 2026-10-31 小欧 由 assembler 迁入(北京老陈令): 与 truncate_oversized_message 同为"单条超长就截"
      的切分原语, assembler 只做装配编排(层级一致), 不持原语。 — 小欧-2026-10-31
    """
    last_turn = 0
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_turn = i
            break
    else:
        # 2026-10-31 小欧: 链中途切出的 delta 段没有 user 边界, 原默认 len(messages) 把**整段**当旧轮
        #   (参数只保 500 字, 实测 361 字), 把模型正在处理的最后一轮当成"回看摘要", 认不出自己写过什么。
        #   改取最后一轮 FC 决策的起点作当前轮: 仅它享受 4000, 其余仍按旧轮 500(压缩力度不退化)。
        for i in range(len(messages) - 1, -1, -1):
            if messages[i].get("role") == "assistant" and messages[i].get("tool_calls"):
                last_turn = i
                break
    result: List[Dict] = []
    hit = 0
    for idx, msg in enumerate(messages):
        calls = msg.get("tool_calls")
        if msg.get("role") != "assistant" or not calls:
            result.append(msg)
            continue
        limit = SPLIT_TURN_MAX_ASSISTANT_CHARS if idx >= last_turn else TOOL_SUMMARY_HEAD_CHARS
        new_calls: List[Dict] = []
        raw_args = ""
        for tc in calls:
            if isinstance(tc, dict):
                # 2026-10-31 小欧: function 非 dict 视为缺失(原 {**fn} 直接 TypeError, 畸形落库数据会整轮崩);
                #   arguments 可能是结构体(provider/上游差异), 统一转 JSON 文本再按体积判断, 不 str(dict) 出 Python repr
                fn_raw = tc.get("function")
                fn = fn_raw if isinstance(fn_raw, dict) else {}
                _a = fn.get("arguments")
                args_text = json.dumps(_a, ensure_ascii=False) if isinstance(_a, (dict, list)) else str(_a or "")
                if len(args_text) > limit:
                    if len(args_text) > len(raw_args):
                        raw_args = args_text
                    tc = {**tc, "function": {**fn, "arguments": _fit_args_json(args_text, limit)}}
                    hit += 1
            new_calls.append(tc)
        if raw_args:
            m = dict(msg)
            m["tool_calls"] = new_calls
            m["_truncated"] = True
            MessageBuilder.keep_full_raw(m, raw_args, "_args_raw")   # 2026-10-31 小欧: 参数原文独立字段, 不与 content 的 _raw 互覆
            result.append(m)
            continue
        result.append(msg)
    if hit:
        logger.info(f"[shrink] 第3级截 tool_call 参数: {hit} 个调用"
                    f"(旧轮 {TOOL_SUMMARY_HEAD_CHARS} 字 / 当前轮 {SPLIT_TURN_MAX_ASSISTANT_CHARS} 字)")
    return result
