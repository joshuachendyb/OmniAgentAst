# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-08-17 小健 新建: 14.9.2 目录树【待补代码】装配线 + 14.9.6 K3 trim_orphan_pairs_proactive
#   2026-08-17 小健 补全: 各函数 docstring 补全适用场景/使用方法/前置条件/输入输出(043ed9c54)
#   2026-08-17 小健 改名: extract_new_block→get_new_messages_since, trim_orphan_pairs_proactive→remove_dangling_tool_calls;
#                        模块职责/函数引用/与 prune 协同描述同步(编辑历史保留原名)
#   2026-10-08 小欧 - remove_dangling_tool_calls 双向剪孤儿: 原 tool 侧判据恒真(seen_ids 由同一份 messages 的
#     tool 收集, "该 id 在 seen_ids"永远成立)→ tool 侧从未真被剪过, 连缺 tool_call_id 的也因 None in seen_ids 留下,
#     与函数名/文档承诺不符; 现 tool 侧改比对调用方 id 集合(assistant.tool_calls), 双向各剪一次, 不改结构与入参。 — 小欧-2026-10-08
#   2026-10-31 小欧 - 新增 shrink_to_budget(北京老陈令): 阶梯循环收缩到 token 预算(截单条→清远段 tool→丢远轮次
#     保60%→只保25%), 每级后复检、达标即停、纯本地零 LLM; 原 start_step._compact_injected_history 内联四段
#     迁入本模块, 调用方只给目标预算。— 小欧-2026-10-31
#   2026-10-31 小欧 - shrink_to_budget 两项升级(北京老陈令): ①第2级由"远段全清零"改为"保首+清零"——
#     长 tool 输出留 TOOL_SUMMARY_HEAD_CHARS(=SPLIT_TURN_MAX_ASSISTANT_CHARS/8, 500) 首段, 短条仍清零
#     (保首对短条几乎零释放且模板撑大); ②新增 estimator 形参(缺省原文口径)让"门限判定"与"裁剪"共用一把尺,
#     摘要路径传 estimate_feed_tokens, 治"按 feed 判该裁、按原文裁到 0.755ctx"的过裁。— 小欧-2026-10-31
#   2026-10-31 小欧 - 新增 truncate_tool_call_args + 阶梯补到五级(北京老陈令): 实测 write 90 万字参数(484,992 tok)
#     旧四级跑完一点未减——参数不在 content、单轮无轮可丢, 阶梯对它全空转, 该场景必 400; 现截 assistant
#     tool_calls.arguments(旧轮 TOOL_SUMMARY_HEAD_CHARS=500 字 / 当前轮 SPLIT_TURN_MAX_ASSISTANT_CHARS=4000 字,
#     全部复用既有门限, 不新增常量), 原文存 _raw, id/name/tool 结果不动保 FC 配对; 该级排在"丢远轮"之前
#     (截参数保全部轮次, 丢轮丢整段对话, 前者破坏性小得多; 且早/中轮巨参数若不先截, 丢轮会把那一整轮丢掉)。— 小欧-2026-10-31
#   2026-10-31 小欧 - 三堂会审整改(北京老陈令): ①truncate_tool_call_args 迁出至 split_turn(与 truncate_oversized
#     _message 同为单条超长截断原语), 本模块只做装配编排; ②第2/4/5级 find_tail_start 一律传 estimator —— 保尾边界
#     与超预算判定必须同一把尺(feed 口径下预算 8000 可保 14 条/6981 tok, 原文口径只保 6 条/2648 tok, 白丢 8 条)。— 小欧-2026-10-31
#   2026-10-31 小欧 - 补 _args_raw 字段口径注记; 第2级日志分列压缩/清零释放; 第4/5级判据改 start>prefix。— 小欧-2026-10-31
"""compaction.assembler — 装配适配(保尾区保留 + 压缩消息注入 + 配对修剪) — 小健 2026-08-17

职责(SRP): 仅承载「装配」三步:
  - split_history_window: 按 tail_start 切出 {old_head, tail_part, absolute_tail_start}
  - inject_compressed_summary: 用摘要 assistant 消息替换 old_head, 保 system + 摘要 + tail + 最新 task
  - remove_dangling_tool_calls: FC 配对前置修剪(K3, 设计文档 [4] 14.9.6 K3)
    + shrink_to_budget: 阶梯循环收缩到 token 预算(每级后复检, 达标即停, 全程零 LLM)
设计文档: [4] 14.5 装配过滤(tail_start_id 之后原样保留、之前被摘要覆盖) + 14.9.6 K3 + 10.1.8 S5。

装配只编排注入/保留, 摘要生成归 summary; K3 复用既有 _trim_fc_pairs 思路(不重造);
old_head 原样保留(不破坏原库), 摘要仅运行时回填(list 组合新列表, 不改入参);
remove_dangling_tool_calls 与 keep_valuable_messages(C3 prune 删 tool)协同闭环保配对。

2026-10-31 小欧 增 shrink_to_budget: 把"缩到预算"的阶梯循环收口为本模块公用函数(start 压缩前清洗的
  编排逻辑), 复用 split_turn/prune 原语, 不新增切分算法; 调用方只给目标 token 预算。第2级为
  「长 tool 输出保首段 + 短条清零」, 并支持自定义体积估算函数(摘要路径按实际 feed 口径估)。— 小欧-2026-10-31
2026-10-31 小欧 增 truncate_tool_call_args: 第3级, 截 assistant tool_calls.arguments 保首段(旧轮 500 /
  当前轮 4000), 专治单轮巨型参数对第1/2级免疫的场景 — 小欧-2026-10-31
2026-10-31 小欧 三堂会审整改: truncate_tool_call_args 迁至 split_turn(单条超长截断原语与 content 截断同域),
  本模块只留装配编排; 保尾边界统一按调用方 estimator 计(见 shrink_to_budget)。— 小欧-2026-10-31

字段名口径(以代码为准): tool_calls 参数原文存 `_args_raw`(编辑历史早期写作 `_raw`, 系迁移前旧名)。
"""
from typing import Dict, List, Tuple

from app.logger import logger
from app.services.agent.agent_utils import (
    CHARS_PER_TOKEN,  # 2026-10-31 小欧: 系数唯一真源(与估算函数同址)
)
from app.services.agent.compaction.split_turn import (
    count_system_prefix,
    find_tail_start,
    preserve_recent_budget,
    truncate_oversized_message,
    truncate_tool_call_args,
)
from app.services.agent.compaction_constants import (
    TOOL_SUMMARY_HEAD_CHARS,
)


def split_history_window(messages: List[Dict], context_length: int,
                         reserve: int) -> Tuple[List[Dict], List[Dict], int]:
    """把历史切为 {old_head(待压缩), tail_part(保尾原样保留), absolute_tail_start} — 小健 2026-08-17

    适用场景: C4 锚定摘要压缩前, 把对话历史切成"待压缩旧段 + 保尾新区"。
    使用方法: 对消息列表 + 模型上下文/预留调用, 返回三要素供后续注入摘要。
    输入: messages 消息列表; context_length 模型上下文上限; reserve 输出预留 buffer。
    输出: (old_head 待压缩段, tail_part 保尾段, absolute_tail_start 保尾起点下标)。
    前置条件: context_length > reserve; messages 非空。
    设计文档: [4] 14.3.2 select() 返回 {head, tail_start_id} + 14.5 装配过滤。
    2026-11-01 小欧 - 形参键名统一 context_limit → context_length — 小欧-2026-11-01
    """
    budget = preserve_recent_budget(max(1, context_length - reserve))
    tail_start = find_tail_start(messages, budget)
    old_head = messages[:tail_start]
    tail_part = messages[tail_start:]
    return old_head, tail_part, tail_start


def get_new_messages_since(messages: List[Dict], last_tail_start: int) -> List[Dict]:
    """提取 tail_start 之后的增量块(供 generate_chunked_summary) — 小健 2026-08-17

    适用场景: C5 增量块式摘要时, 取上次压缩之后新增的对话段喂 LLM(降本)。
    使用方法: 传完整消息列表 + 上次保尾起点, 返回其后增量段。
    输入: messages 消息列表; last_tail_start 上次保尾起点下标。
    输出: messages[last_tail_start:] 增量块列表。
    前置条件: 0 <= last_tail_start <= len(messages)。
    设计文档: [4] 14.9.6 C5「new_block 由 assembler 切分(tail_start 之后的增量)」。
    """
    return messages[last_tail_start:]


def inject_compressed_summary(messages: List[Dict], summary_text: str,
                              tail_start: int, keep_tail: int = 1) -> List[Dict]:
    """用摘要 assistant 消息替换 old_head, 保 system + 摘要 + tail + 最新 task — 小健 2026-08-17

    适用场景: 摘要生成后, 把待压缩旧段替换为摘要消息, 端到端完成压缩回填。
    使用方法: 传原消息 + 摘要文本 + 保尾起点, 返回新列表(不改动入参 messages)。
    输入: messages 消息列表; summary_text 摘要文本; tail_start 保尾起点; keep_tail 保尾最新条数(默认1)。
    输出: 新列表 = system 段 + 摘要 assistant 消息 + 保尾最新 keep_tail 条。
    前置条件: summary_text 非空(为空则原样返回 messages, 零退化)。
    设计文档: [4] 14.5「tail_start_id 之后原样保留, 之前被摘要覆盖」; 10.1.7 ⑤「保 system + 最新 task」。
    不改动入参(messages)(不破坏原库, 对应 14.3 "压缩截断不破坏原库")。
    """
    if not summary_text:
        return messages
    system_msgs = [m for m in messages[:tail_start] if m.get("role") == "system"]
    tail_msgs = messages[tail_start:]
    # 保最新 tail 条(通常为用户最新 task), 避免摘要顶掉最新输入
    if len(tail_msgs) > keep_tail:
        tail_msgs = tail_msgs[-keep_tail:]
    return system_msgs + [{"role": "assistant", "content": summary_text}] + tail_msgs


def remove_dangling_tool_calls(messages: List[Dict]) -> List[Dict]:
    """双向剪孤儿: 无结果的 assistant(tool_calls) + 无调用方的 tool — 小健 2026-08-17

    适用场景: 凡做删除式裁剪(C3 prune 删 tool / keep_valuable_messages)必须随后调用, 保 FC 配对。
    使用方法: 对裁剪后的消息列表调用, 返回清理孤儿后的新列表。
    输入: messages 消息列表。
    输出: 过滤后的新列表——assistant 的 tool_calls 全部拿到对应 tool 结果才留;
          tool 的 tool_call_id 确有调用方(某 assistant 的 tool_calls 引用了它)才留; 其余角色原样透传。
    前置条件: 无; 双向剪除孤儿, 防 (a) assistant 带 tool_calls 无 tool 结果 (b) tool 无调用方,
              两者回传 provider 均 400。
    设计文档: [4] 14.9.6 K3。
    2026-10-08 小欧 修判据空转: 原 seen_ids 由同一份 messages 的 tool 收集 → "该 id 在 seen_ids"恒真
      (自己也在集合里) → tool 侧从未真被剪过, 连缺 tool_call_id 的也因 None in seen_ids 留下, 与函数名不符;
      现 tool 侧改比对"调用方 id 集合"(assistant.tool_calls), 双向各剪一次。仅改判据不改结构与入参。 — 小欧-2026-10-08
    """
    tool_ids = {m.get("tool_call_id") for m in messages if m.get("role") == "tool"}
    called_ids = {
        tc.get("id")
        for m in messages if m.get("role") == "assistant"
        for tc in (m.get("tool_calls") or [])
        if isinstance(tc, dict)
    }
    result: List[Dict] = []
    for m in messages:
        if m.get("role") == "assistant" and m.get("tool_calls"):
            # 只留"全部 tool_calls 都拿到结果"的决策, 防留一个指向不存在结果的调用
            if all(tc.get("id") in tool_ids for tc in m["tool_calls"] if isinstance(tc, dict)):
                result.append(m)
            continue
        if m.get("role") == "tool":
            # 只留"确有调用方"的 tool 结果, 防留一条无对应 tool_calls 的孤立结果
            if m.get("tool_call_id") in called_ids:
                result.append(m)
            continue
        result.append(m)
    return result


def shrink_to_budget(messages: List[Dict], limit_tokens: int,
                     allow_prune: bool = True, estimator=None) -> List[Dict]:
    """阶梯循环收缩: 逐级收紧, 直到估算 <= limit_tokens — 小欧 2026-10-31

    适用场景: 「要送进 LLM 的消息列表本身超窗」的入口(如 start 压缩前清洗)——先裁到预算内再调 LLM,
      否则压缩请求自己就会撞窗 400。
    使用方法: 传消息列表 + 目标 token 预算, 返回收缩后的列表; 已达标则原样返回同一对象(零拷贝)。
    输入: messages 消息列表; limit_tokens 目标 token 上限(如 trim_conv_threshold(ctx));
          allow_prune 是否允许第2级动远段 tool 输出(对应 tuning.compaction.summary_prune_tool_output);
          estimator 体积估算函数, 缺省 MessageBuilder._estimate_tokens(原文口径)。
          摘要路径必须传 estimate_feed_tokens —— 判断与裁剪要用同一把尺, 否则"按 feed 判该裁、
          按原文裁到 0.755ctx"会过裁; loop 裁剪不传即维持原行为。
    输出: List[Dict] —— 收缩后的消息列表(各级均为新列表, 不修改入参元素内容以外的结构)。
    前置条件: limit_tokens > 0; messages 元素为 dict。
    阶梯(每级动作不同、结果单调变小, 每级后复检, 达标立即返回):
      1. truncate_oversized_message                       单条 content >4000 字符截断(原文存 _raw)
      2. 保首 + 清零                                        保尾不动; 更早的"长" tool 输出保留首段
        (TOOL_SUMMARY_HEAD_CHARS=500, 4000 的 1/8), 短的(<520 字)清零
      3. truncate_tool_call_args                          截 assistant tool_calls.arguments(旧轮 500 字 /
        当前轮 4000 字); 排在丢轮之前——截参数保全部轮次, 丢轮丢整段对话, 前者破坏性小得多;
        也是"单轮巨型参数"的唯一出路(第1/2级不碰参数, 第4/5级对单轮空转)
      4. find_tail_start(align_turn=True)                 丢远轮次, 只保 60% 预算
      5. find_tail_start(align_turn=True)                 只保 25% 预算(最近 1~2 轮)
        (第2/4/5级的保尾边界一律传 estimator —— 按什么尺判超预算就按什么尺算能保多少,
         否则 feed 口径下本可容纳的尾部消息会被原文口径白丢。)
      五级后仍超: 记 ERROR 并返回当前结果(调用方放行, 不阻塞主链)。
    边界: 头部连续 system 恒保留(各级切轮次都不动头部); find_tail_start 返回 <=prefix 表示无可再丢,
      该级空转; 五级动作互不相同, 不会死循环。
    设计边界: 只负责「缩到预算」, 不判断「要不要缩」(门限判定归调用方), 全程零 LLM 调用。
    2026-10-31 小欧 第2级由"全清零"升级为"保首+清零"(北京老陈令): 原 clear_tool_outputs 把远段 tool
      全抹成空串, 摘要 LLM 只看得到空白; 改为超长条留可读首段、短条仍清零(短条保首几乎零释放反撑大)。— 小欧-2026-10-31
    2026-10-31 小欧 补参数截断层(北京老陈令): 实测 write 90 万字参数(484,992 tok)旧四级跑完一点未减,
      日志"四级后仍超 ... 放行并留证"——参数全链路无截断路径, 该场景必 400; 复用 500/4000 两个既有门限。— 小欧-2026-10-31
    2026-10-31 小欧 第3级为何不受 allow_prune 支配(三堂会审整改): allow_prune 是"摘要质量 vs 成本"的偏好开关
      (用户可关掉远段 tool 清零, 宁可多花 token), 而第3级是"不截就 400"的硬防线 —— 走到这一级说明前面几级
      已全部空转, 再尊重偏好就是拿整个请求换开关, 故无视 allow_prune 无条件执行。 — 小欧-2026-10-31
    """
    from app.services.agent.compaction.prune import (
        compress_long_tool_output,
        prune_tool_output_keeping_tail,
    )
    from app.services.agent.message_builder import (
        MessageBuilder,  # 局部 import 防循环(compaction ↔ message_builder)
    )

    if not messages:
        return list(messages)
    limit_tokens = int(limit_tokens)
    if limit_tokens <= 0:
        return list(messages)
    est = estimator or MessageBuilder._estimate_tokens
    cur = est(messages)
    if cur <= limit_tokens:
        return messages
    prefix = count_system_prefix(messages)
    for level in range(1, 6):
        if level == 1:
            messages = truncate_oversized_message(messages)
        elif level == 2:
            if allow_prune:
                tail = find_tail_start(messages, preserve_recent_budget(limit_tokens),
                                       estimator=est)
                far = [dict(m) for m in messages[:tail]]   # compress 原地改 dict, 先拷一层防污染入参
                rest = [dict(m) for m in messages[tail:]]
                _before = est(far)
                # protect_tokens: 只压"比保首还长"的(≈520 字), 短条保首几乎零释放且模板反撑大
                far, _rel_compress = compress_long_tool_output(
                    far, min_release=0,
                    protect_tokens=int((TOOL_SUMMARY_HEAD_CHARS + 20) / CHARS_PER_TOKEN))
                far, _rel_prune = prune_tool_output_keeping_tail(far, len(far))  # 短条清零(已压条靠 _compressed 守卫跳过)
                messages = far + rest
                # 分列两块释放量(压缩/清零), 原只报合并总数 — 小欧-2026-10-31
                logger.info(f"[shrink] 第2级保首{TOOL_SUMMARY_HEAD_CHARS}字+清零: "
                            f"压缩释放 {_rel_compress} tok / 清零释放 {_rel_prune} tok / "
                            f"本级共释放 {_before - est(far)} tok, 保尾 {len(rest)} 条")
        elif level == 3:
            # 2026-10-31 小欧 排在"丢轮"之前(北京老陈令): 截参数保留全部轮次, 丢轮丢整段对话, 前者破坏性小得多;
            #   且早/中轮的巨参数若不先截, 第4/5级会把那一整轮直接丢掉 — 小欧-2026-10-31
            # 2026-10-31 小欧 本级不受 allow_prune 支配(三堂会审整改): allow_prune 只是"摘要质量 vs 成本"的偏好,
            #   本级是"不截就 400"的硬防线, 走到这里说明前面各级已空转, 再尊重偏好等于拿整个请求换开关。— 小欧-2026-10-31
            messages = truncate_tool_call_args(messages)
        else:
            ratio = 0.6 if level == 4 else 0.25
            start = find_tail_start(messages, int(limit_tokens * ratio), align_turn=True, estimator=est)
            # 判据用 >prefix: 切点落回 system 区时本轮未丢条目, 免白跑一次剪孤儿 — 小欧-2026-10-31
            if start > prefix:
                messages = remove_dangling_tool_calls(messages[:prefix] + messages[start:])
        cur = est(messages)
        logger.info(f"[shrink] 第{level}级后: {cur} tok / 目标 {limit_tokens}")
        if cur <= limit_tokens:
            return messages
    logger.error(f"[shrink] 五级后仍超 {cur} > {limit_tokens}, 放行并留证")
    return messages
