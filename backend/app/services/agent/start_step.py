# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-10-07 小欧 修复: 摘要输入只取"注入的历史" agent._injected_history_msgs, 不再从 conversation_history
#   反推(猜首条system/末条task)。① 原实现把含末尾本轮task的历史喂给摘要LLM, 模型当成待执行指令→
#   越权调工具(实测glm-5.2: finish=tool_calls并写文件); ② summary.py:69 是"追加"system而非替换,
#   带上原system会让feed出现两条system→模型困惑。
# 2026-08-17 小健 新建: start 任务输入装配完整过程独立模块(北京老陈驱动, 痛斥 start 业务割裂散落多处)——把
#   start 全部业务收拢一个文件: 注入会话历史 / 超窗判定 / C4 锚定摘要 / 装配入口; 自 initialize_run_state.py 与
#   react_cycle.py 迁入, 单一归属; react_cycle 只保留薄调用(不 import chat 层, 解耦)
# 2026-08-17 小健 三思三省彻底收敛(老陈驱动): 契约构造业务自 sse_events 迁入本模块——新增 _build_start_contract
#   在单模块内算 context_summary 快照(message_count/total_tokens) + 构造 MetaStep(type="start", step=0),
#   并据 orchestrator 注入的运行元数据 agent._start_meta(ai_service/task_id/next_step/user_input/session_id/
#   链字段/warning)装配; assemble_start_step 改为③态直接 _build_start_contract, 不再依赖 chat 层 _start_step_factory
#   闭包/factory; 业务彻底单归属 start_step.py, sse_events 删除 build_start_step/send_start_step — 小健 2026-08-17
# 2026-08-17 小健 最合理核查修复(老陈追问"是否最合理"): ① DRY——_start_meta 删除 ai_service 冗余键(与
#   agent.llm_client 同对象, orchestrator 构造 agent 时注入), _build_start_contract 直接读 agent.llm_client;
#   _start_meta 仅装 agent 拿不到的 chat 数据(task_id/next_step/user_input/session_id/链字段/warning);
#   ② KISS/SLAP——assemble_start_step/_build_start_contract 去掉无谓 async(内部零 await), 同步函数直线返回
#     (注: 2026-10-07 因摘要需 await LLM, assemble_start_step 已改回 async, 本条仅记当时结论)
# 2026-08-17 小健 全系统DRY扫描收敛(老陈指示按10大规范): task_id 改读 agent.task_id(base_agent:59 权威持有,
#   orchestrator 构造时注入), 不再依赖 _start_meta["task_id"]; _start_meta 只承载 next_step/session_id/user_input/
#   链字段/warning(react_cycle 拿不到的必需运行数据), 与 ai_service 删除同属真冗余收敛(单一归属) — 小健 2026-08-17
# 2026-08-17 小健 常量归属迁移(北京老陈驱动, 压缩/裁剪常量融入专场常量文件): 本模块 import 的压缩/裁剪常量源头
#   MAX_CONTEXT_TOKENS/MAX_CONTEXT_RATIO/COMPACTION_ENABLED 由 app.constants / compaction 包迁至 agent 层根
#   compaction_constants.py, 导入路径随之更新为 app.services.agent.compaction_constants(局部导入防包级依赖)
# 2026-08-17 小健 阈值重构(北京老陈 2026-08-17 定案, start超窗=上下文×1/2): 超窗基准改读运行时窗口
#   agent.message_builder.MAX_CONTEXT_TOKENS(agent_runner 已用 llm_service.context_limit 覆盖, 与 loop 同基准),
#   不再读全局常量; 门限=运行时窗口 × START_TRIGGER_RATIO; 删除 MAX_CONTEXT_TOKENS=200000 死值兜底
# 2026-08-17 小健 开关定名(北京老陈 2026-08-17): COMPACTION_ENABLED→START_COMPACTION_ENABLED(仅限 start 域), 值 True
# 2026-08-18 - 小欧 - start契约改造: _build_start_contract 改产 StartStep(删 next_step 依赖, step 固定 0, content=context_summary, user_message 顶层化); assemble_start_step 返回类型改 StartStep
# 2026-08-18 - 小欧 - 三堂会审复核(回归修复): _build_start_contract 补 _start_meta None/非 dict 防御, 防 _meta.get AttributeError, 兑现既声明的「无 _start_meta 返回 None 旁路兼容」契约
# 2026-08-20 - 小欧 - 11.3-A 跨任务注入基线快照: assemble_start_step 完成时调 TaskTelemetry 记录注入上下文基线(固定不漂移), 供后续任务 context_overview/injected 对比
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.5: _build_start_contract 构造 StartStep 改传
#   start_model=_ai.llm_model(ModelRef 单结构), 删 display_name=f"{provider} ({model})" 拼装与
#   provider=/model= 分离入参(设计要求2: display_name 不再落库, 前端派生)
# 2026-08-29 - 小沈 - 修复: _compact_injected_history 摘要回填后加末条 tool 孤儿守卫, 丢弃尾随无配对 assistant 的 tool 消息(中段已被丢→孤儿→LLM 400)
# 2026-09-23 - 小欧 - compaction配置化: _maybe 读 tuning.compaction.start_enabled/start_trigger_ratio
# 2026-10-07 北京老陈 _build_injected_history: 原名 _inject_conversation_history(会调 inject_history 写
#   conversation_history)→ 改名并只构建+留存 _injected_history_msgs; 同批历史原被写两次(本阶段写205条,
#   随后 react_loop init_history 清空再写), 现 conversation_history 唯一写入点在 react_loop 装配段。
# 2026-10-07 北京老陈 _maybe_compact_injected_history: 判定数据源 conversation_history → _injected_history_msgs
#   (口径=注入历史, 不含 system/task; init_history 已推迟, 此刻 conversation_history 为空)。
# 2026-10-07 北京老陈 _compact_injected_history: 改返回摘要文本, 不再装配 conversation_history、不碰 system/task。
# 2026-10-07 北京老陈 assemble_start_step: 判定+摘要下沉回本函数并置于契约构造之前; 因摘要 await LLM,
#   本函数改 async(调用方 react_loop 已加 await)。_start_summary 首行清零防异常残留上次值。
# 2026-10-07 北京老陈 _compact_injected_history: 摘要 await(30~60s)前后各查一次 check_cancelled,
#   避免长等待期间暂停/取消/新消息无响应; 被取消返回空串由调用方零退化装配原历史。
# 2026-10-07 北京老陈: 校正 5 处与代码不符的 docstring(判定数据源/摘要调用方/init_history 阶段/步骤序号/前置条件)。
# 2026-10-08 小欧 摘要前降本(开关 tuning.compaction.summary_prune_tool_output): 保尾区 tool 原样、只清零更早的,
#   编排为 preserve_recent_budget/find_tail_start(split_turn) 算边界 + prune_tool_output_keeping_tail(prune) 执行,
#   本模块零算法; 逐条浅拷贝隔离防清零原地改污染 _injected_history_msgs(摘要失败时零退化要用)。 — 小欧-2026-10-08
# 2026-10-08 小欧 北京老陈裁定"不能误导用户" — set_injected_context 增传 last_user_text: 遥测原从 conversation_history
#   末条取 summary, 首帧时那正是用户刚发的本轮提问, 标签"最近"等于把自己的提问回显一遍(实测四条帧全是用户原话);
#   改由注入源取最近一条历史提问, 语义才成立。 — 小欧-2026-10-08
"""
start_step — start 任务输入装配完整过程(单一模块, 一个入口)

职责(SRP): 仅承载「start 前置装配环节」全部业务——
  - _build_injected_history: 构建注入历史并存 agent._injected_history_msgs(不写 conversation_history)
  - _maybe_compact_injected_history: 超窗判定(C4, 读 _injected_history_msgs, 置 _needs_compact 标记)
  - _compact_injected_history: C4 锚定摘要生成(超窗时产出摘要文本, 不装配 conv)
  - _build_start_contract: 契约构造(context_summary 快照 + StartStep, 自 sse_events 迁入)
  - assemble_start_step: 唯一对外入口(async; 构建注入历史 → 判定 → 摘要 → 契约)
依据: [1] 10.1.1(功能逻辑) / 10.1.2(字段清单) / 10.1.6(C4 清洗) / 10.1.7④⑤(装配落点) / 10.1.8 S3/S4/S5。
"""
from typing import Any, Dict, List, Optional

from app.config import get_config  # 小欧 2026-09-23 compaction配置化读 tuning.compaction.*
from app.logger import logger


def _build_injected_history(agent, context: Optional[Dict[str, Any]]) -> None:
    """构建注入历史并存到 agent._injected_history_msgs(不写 conversation_history) — 北京老陈 2026-10-07

    适用场景: start 装配第一步——从 context.previous_messages 构建 history_msgs。
    使用方法: 直接调用, 传 agent + context; context 无 previous_messages 则空转安全。
    输入: agent; context 含 previous_messages 历史消息列表。
    输出: 无(内部置 agent._injected_history_msgs)。
    前置条件: 无。
    关联逻辑: 跳过 previous_messages 末条 user(防与本轮 task 重复); tool_calls 逐元素 isinstance 校验
      (非 dict 元素剥离, 防 provider 400); 合法输入输出与原实现 100% 一致。
    """
    if not context or not isinstance(context, dict):
        agent._injected_history_msgs = []
        return
    prev = context.get("previous_messages")
    if not prev or not isinstance(prev, list):
        agent._injected_history_msgs = []
        return
    last_user_idx = -1
    for i in range(len(prev) - 1, -1, -1):
        if prev[i].get("role") == "user":
            last_user_idx = i
            break
    history_msgs = []
    for i, msg in enumerate(prev):
        if i == last_user_idx:
            continue
        role = msg.get("role")
        if role == "tool":
            entry = {"role": "tool", "tool_call_id": msg.get("tool_call_id", ""), "content": msg.get("content", "")}
            # FC协议需要name字段 — 小欧 2026-07-10
            name = msg.get("name")
            if name:
                entry["name"] = name
            history_msgs.append(entry)
        elif role == "assistant":
            tc_raw = msg.get("tool_calls")
            # 历史重载边界校验 — 小欧 2026-07-18
            # 病根: 持久化 assistant.tool_calls 若含非dict元素(截断/畸形LLM响应落库),
            #       原样回传致 provider 400("Can only get item pairs from a mapping")并触发FC降级。
            # 修复: 仅保留dict元素, 非dict一律剥离; 剥离后为空则回退content分支(无退化)。
            if isinstance(tc_raw, list):
                tc = [t for t in tc_raw if isinstance(t, dict)]
            elif isinstance(tc_raw, dict):
                tc = [tc_raw]
            else:
                tc = []
            if tc:
                history_msgs.append({
                    "role": "assistant",
                    "tool_calls": tc,
                    "content": msg.get("content"),
                })
            elif msg.get("content"):
                history_msgs.append({"role": "assistant", "content": msg["content"]})
        elif role == "user" and msg.get("content"):
            history_msgs.append({"role": "user", "content": msg["content"]})
        elif role == "system" and msg.get("content"):
            history_msgs.append({"role": "system", "content": msg["content"]})
    agent._injected_history_msgs = history_msgs


def _maybe_compact_injected_history(agent) -> None:
    """C4 超窗标记(10.1.7⑤ / 10.1.8 S5): 构建注入历史后估算 token, 超窗则置 _needs_compact — 小健 2026-08-17

    适用场景: start 装配第二步——构建注入历史后判定是否超窗, 为同函数内摘要生成铺标记。
    使用方法: 直接调用, 传 agent; 超窗置 agent._needs_compact=True(仅标记不触发 LLM)。
    输入: agent 含 _injected_history_msgs(由 _build_injected_history 构建留存; 不读 conversation_history)。
    输出: 无(置 agent._needs_compact 布尔标记)。
    前置条件: _build_injected_history 已执行。
    关联逻辑: 估算复用 MessageBuilder._estimate_tokens(DRY); 门限=运行时上下文窗口 × START_TRIGGER_RATIO(北京老陈 2026-08-17 定案, start 超窗=上下文×1/2)。
    2026-10-07 北京老陈: 数据源由 conversation_history 改 _injected_history_msgs(判定口径=注入历史,
      不含 system/task; init_history 已推迟到 react_loop 装配段, 此刻 conversation_history 为空)。
    """
    agent._needs_compact = False
    from app.services.agent.compaction_constants import (  # 小健 2026-08-17: 常量权威迁 agent/compaction_constants(局部导入防包级依赖)
        START_COMPACTION_ENABLED,
        START_TRIGGER_RATIO,
    )
    _start_enabled = bool(get_config().get('tuning.compaction.start_enabled', START_COMPACTION_ENABLED))  # 小欧 2026-09-23 compaction配置化
    if not _start_enabled:
        return
    from app.services.agent.message_builder import MessageBuilder
    # 2026-10-07 北京老陈: 判定改读 _injected_history_msgs(注入历史本体), 不读 conversation_history。
    #   init_history 已推迟到压缩后装配, 此处 conversation_history 尚无 system/task 容器;
    #   判定只关心"注入历史有多大", 故以 _injected_history_msgs 为准(与压缩输入同源, 零猜测)。
    history = list(getattr(agent, "_injected_history_msgs", None) or [])
    if not history:
        return
    # 上下文窗口基准 = 运行时 context_limit(agent_runner 已覆盖 message_builder.MAX_CONTEXT_TOKENS, 与 loop 同基准);
    # MessageBuilder 构造自带默认无需兜底 — 小健 2026-08-17
    _ctx = agent.message_builder.MAX_CONTEXT_TOKENS
    _start_ratio = float(get_config().get('tuning.compaction.start_trigger_ratio', START_TRIGGER_RATIO))  # 小欧 2026-09-23 compaction配置化
    _threshold = int(_ctx * _start_ratio)
    rough = MessageBuilder._estimate_tokens(history)
    if rough > _threshold:
        agent._needs_compact = True
        logger.debug(f"[start_step] 历史超窗({rough}>{_threshold}=ctx{_ctx}×{_start_ratio}), 置 _needs_compact")


async def _compact_injected_history(agent) -> str:
    """C4 锚定摘要生成(10.1.7⑤/10.1.8 S5) — 小健 2026-08-17

    适用场景: start 装配第三步——超窗时生成注入历史的锚定摘要。
    使用方法: 由 assemble_start_step await 调用; 只生成摘要文本, 不装配 conversation_history。
    输入: agent 含 _injected_history_msgs(注入历史本体, 由 _build_injected_history 留存)。
    输出: str 摘要文本; 空串表示未产出(调用方按零退化装配原历史)。同时复位 _needs_compact。
    前置条件: _maybe_compact_injected_history 已置 _needs_compact=True。
    关联逻辑: 摘要生成/模板/截断全归 compaction 模块(SRP); tools=None 走 llm_stream Text 模式;
      摘要只归档 _injected_history_msgs(不含 system/task); await 前后各查一次取消(见编辑历史)。
      2026-10-07 北京老陈: 摘要前对拷贝副本调 prune.clear_tool_outputs 清零 tool 结果(降本 38%),
      开关 tuning.compaction.summary_prune_tool_output; 原 _injected_history_msgs 不受影响,
      保证摘要失败/取消时调用方零退化装配原历史仍拿到完整历史。
    """
    from app.services.agent.compaction.summary import generate_anchored_summary

    # 摘要只归档注入的历史(不含 system/task): 原实现把含末尾 task 的整条历史喂LLM, 模型当待执行指令
    #   → 越权调工具(实测 glm-5.2 finish=tool_calls 并写文件)
# 2026-10-07 北京老陈 摘要前降本(开关 tuning.compaction.summary_prune_tool_output): 保尾区 tool 原样、只清零更早的;
    #   编排=split_turn 两函数算边界 + prune_tool_output_keeping_tail 执行, 本模块零算法; 实测省 48890 tok(36%), 摘要 2048 字符/六段 6/6。
    #   ⚠ 逐条浅拷贝: 清零原地改 dict, 直接传会污染 _injected_history_msgs(摘要失败时零退化要用)。
    _src = getattr(agent, "_injected_history_msgs", None) or []
    _hist_for_summary = [dict(m) for m in _src]
    if not _hist_for_summary:
        agent._needs_compact = False
        return ""
    try:
        from app.services.agent.compaction_constants import (
            COMPACTION_BUFFER, SUMMARY_PRUNE_TOOL_OUTPUT,
        )
        if bool(get_config().get('tuning.compaction.summary_prune_tool_output',
                                 SUMMARY_PRUNE_TOOL_OUTPUT)):
            from app.services.agent.compaction.prune import prune_tool_output_keeping_tail
            from app.services.agent.compaction.split_turn import (
                find_tail_start, preserve_recent_budget,
            )
            _ctx = int(getattr(agent.message_builder, "MAX_CONTEXT_TOKENS", 0) or 0)
            _tail_budget = preserve_recent_budget(max(1, _ctx - COMPACTION_BUFFER))
            _tail_start = find_tail_start(_hist_for_summary, _tail_budget)
            _hist_for_summary, _released = prune_tool_output_keeping_tail(
                _hist_for_summary, _tail_start)
            logger.info(
                f"[start_step] 摘要前降本(保尾保留+旧轮清零): 省 {_released} tok; "
                f"保尾区保留最近 {len(_hist_for_summary) - _tail_start} 条(预算 {_tail_budget} tok)")
    except Exception as e:
        # 清零是纯优化, 失败不得影响摘要主链(降级为全量喂)
        logger.warning(f"[start_step] 摘要前清零 tool 结果失败, 降级为全量喂: {type(e).__name__}: {e!r}")
    try:
        _task_id = getattr(agent, "task_id", None)
        if _task_id:
            from app.services.task.task_runtime import check_cancelled
            if await check_cancelled(_task_id):
                logger.info("[start_step] 摘要前检测到任务取消, 跳过摘要(调用方零退化装配原历史)")
                agent._needs_compact = False
                return ""
        summary_text = await generate_anchored_summary(agent, _hist_for_summary)
        if _task_id and await check_cancelled(_task_id):
            logger.info("[start_step] 摘要后检测到任务取消, 丢弃摘要结果(调用方零退化装配原历史)")
            summary_text = ""
    except Exception as e:
        logger.warning(f"[start_step] 锚定摘要失败, 返回空(调用方零退化装配原历史): {type(e).__name__}: {e!r}")
        summary_text = ""
    if summary_text:
        logger.debug(f"[start_step] 锚定摘要生成完成 (len={len(summary_text)})")
    agent._needs_compact = False
    return summary_text


def _build_start_contract(agent, previous_messages: Optional[List]) -> Optional["StartStep"]:
    """构造 start 任务输入契约 StartStep(单一归属) — 小健 2026-08-17; 小欧 2026-08-18 改产 StartStep

    适用场景: start 装配第四步——据 orchestrator 注入的运行元数据(_start_meta)算 context_summary 快照,
    构造 StartStep(type="start", step=0, content=context_summary); 自 sse_events 迁入(start 契约构造业务完整归此模块)。
    使用方法: 由 assemble_start_step 调用; previous_messages 用于快照 message_count/total_tokens。
    输入: agent 含 _sys_prompt(initialize_run_state 已取) / llm_client(orchestrator 构造时注入, provider/model)
          + _start_meta(dict: user_input/session_id/context_link_mode/context_root_task_id/warning,
          orchestrator 注入); previous_messages 历史消息列表(空列表则快照 message_count=0)。
    输出: StartStep(type="start", step=0) —— 任务输入契约: 任务头部 + system_prompt + user_message(顶层) + context_summary。
    前置条件: _start_meta 已注入(缺则返回 None 旁路兼容); step 固定 0(弃用 next_step, 不再依赖轮数)。
    依赖方向: 仅 agent 属性 + StartStep/MessageBuilder(俱 agent 层), 不 import chat 层(解耦)。
    设计文档: start契约设计章节。
    """
    from app.services.agent.steps import StartStep  # 局部导入防包级环
    from app.services.agent.message_builder import MessageBuilder

    _meta = getattr(agent, "_start_meta", None)
    _ai = getattr(agent, "llm_client", None)
    if _ai is None or not isinstance(_meta, dict):
        return None   # 不再依赖 next_step(弃用)，仅需 llm_client 供 provider/model;
                      # 三堂会审复核(小欧 2026-08-18): 缺 _start_meta 或非 dict 亦旁路返回 None, 防下方 _meta.get AttributeError(回归修复)
    _prev = previous_messages or []
    context_summary = {
        "session_id": _meta.get("session_id"),
        "context_link_mode": _meta.get("context_link_mode"),
        "context_root_task_id": _meta.get("context_root_task_id"),
        "message_count": len(_prev),
        "total_tokens": MessageBuilder._estimate_tokens(_prev),
    }
    return StartStep(
        step=0,                                   # start 固定轮数 0（不再调 next_step）
        context_summary=context_summary,          # content 承载 context_summary(10.1.2 <第2步>3)
        user_message=_meta.get("user_input") or "",   # user_input 顶层化(<第2步>4)
        task_id=getattr(agent, "task_id", None),
        start_model=_ai.llm_model,                # 归一: 直接传 ModelRef, 不再拼 display_name(设计要求2) — 小欧 2026-08-22
        system_prompt=getattr(agent, "_sys_prompt", ""),
        warning=_meta.get("warning"),
    )


async def assemble_start_step(agent, context: Optional[Dict]) -> Optional["StartStep"]:
    """start 任务输入装配完整过程(唯一对外入口, 单模块单归属) — 小健 2026-08-17; 小欧 2026-08-18 改产 StartStep

    适用场景: run_react_cycle 在 initialize_run_state 之后、while 之前调用一次, 完成 start 全部业务。
    使用方法: 传 agent + context, await 返回 StartStep(调用方 emit); 无 _start_meta 时返回 None。
    业务顺序(不可乱): ① 构建注入历史 → ② 超窗判定(C4) → ③ 锚定摘要生成 → ④ 构造任务输入契约 StartStep
    输入: agent 含 _sys_prompt(initialize_run_state 已取) / llm_client / _start_meta(orchestrator 注入的运行元数据);
          context 含 previous_messages(注入历史 + 快照 message_count/total_tokens)。
    输出: StartStep(type="start", step=0) 或 None(无 _start_meta 时保持旁路兼容);
          摘要文本挂 agent._start_summary(供调用方装配 conversation_history)。
    前置条件: initialize_run_state 已执行(agent.steps 已重置、_sys_prompt 已就绪; init_history 不在此阶段)。
    依赖方向: 只读 agent 属性 + context, 不 import chat 层(解耦); 运行元数据由 orchestrator 注入 _start_meta。
    设计文档: start契约设计章节。
    2026-10-07 北京老陈: 判定与摘要下沉回本函数, 置于契约构造之前; 因摘要需 await LLM, 本函数改 async。
    """
    agent._start_summary = ""    # 首行清零, 防后续步骤抛异常时残留上次任务的值
    # ① 构建注入历史(只留存 agent._injected_history_msgs, 不写 conversation_history)
    _build_injected_history(agent, context)
    # ② 超窗判定(C4, 读 _injected_history_msgs)
    _maybe_compact_injected_history(agent)
    # ③ 锚定摘要生成(超窗时; 结果挂 agent._start_summary 供调用方装配)
    if getattr(agent, "_needs_compact", False):
        agent._start_summary = await _compact_injected_history(agent)
    # 11.3-A 跨任务注入基线快照（独立模块 TaskTelemetry 存储，固定不漂移）— 小欧 2026-08-20
    _tele = getattr(agent, "telemetry", None)
    if _tele is not None:
        _prev = context.get("previous_messages") if isinstance(context, dict) else None
        _prev = _prev or []
        from app.services.agent.message_builder import MessageBuilder
        _tele.set_injected_context({
            "message_count": len(_prev),
            "estimated_tokens": MessageBuilder._estimate_tokens(_prev),
            # 2026-10-08 小欧 传最近一条历史提问: telemetry 原从 conv 末条取, 首帧时那正是本轮提问,
            #   标签叫"最近"等于回显用户自己的话。改由注入源取, 语义才成立。
            "last_user_text": next(
                (str(m.get("content") or "") for m in reversed(_prev)
                 if m.get("role") == "user" and (m.get("content") or "").strip()), ""),
        })
    # ④ 构造任务输入契约(StartStep): 据 _start_meta 运行元数据 + previous_messages 快照, 缺 _start_meta 则 None
    _prev_msgs = context.get("previous_messages") if isinstance(context, dict) else None
    return _build_start_contract(agent, _prev_msgs)
