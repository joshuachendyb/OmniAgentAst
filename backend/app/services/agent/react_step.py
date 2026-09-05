
# -*- coding: utf-8 -*-
# 编辑历史:
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-01 chendyg 状态集中管理重构v2
#   - 状态用 status_table, 数据 handler 自己写
#   - _dispatch_handler 基于 event type 推断状态
#   - handler 保留 add_observation/add_assistant_message, 不绕路
# 2026-07-17 小沈 FC重命名: import/LLMResponseError同步
# 2026-07-17 小欧 B3扩展+修正: 检测reasoning-only空转并软引导(修正has_tool_results屏蔽使已调工具后仍可警告); 改add_observation→add_assistant_message(避免空tool_call_id孤立tool消息致LLM参数不合法, 参照edca06261昨天修正); warning去具体工具名
# 2026-07-18 小欧 #27 fix: 删llm_client._cancelled死分支
# 2026-07-18 小欧 #28 fix: 更新docstring状态推断规则
# 2026-07-18 小欧 #29 fix: 抽取_EV_FINAL/_EV_RETRY/_EV_ERROR常量
# 2026-07-18 小欧 FinalStep多态自包含终态重构:
#   【病根】原react_cycle中取消/截断/无终态等路径用MetaStep(cancelled)表示终态,
#          与answer_handler的FinalStep(completed)不一致; _dispatch_handler基于event.type位置推断终态,
#          逻辑分散且易遗漏(如空响应路径set_failed但不产出终态step)。
#   【思路】统一终态语义: 所有终态路径改用FinalStep(outcome=xxx),
#          _dispatch_handler改为outcome驱动终态声明(不依赖位置/类型); 可恢复错误仍用ErrorStep。
#   【改法】①场景B/C/D/循环结束无终态: MetaStep(cancelled)→FinalStep(outcome="cancelled")
#          ②_dispatch_handler: 从位置驱动改为outcome驱动(set_failed/set_cancelled/set_completed)
#          ③可恢复错误(ErrorStep)和可恢复拒绝(_RECOVERABLE_ERRORS)保持不变
# 2026-07-18 - 小欧 - 修复#7 _dispatch_handler 用循环内单独捕获的 final_event 读 outcome, 不取末事件last_event(末事件未必是final,脆弱); 修复#9 stale注释 MetaStep(cancelled)→FinalStep(outcome="cancelled")
# 2026-07-18 - 小欧 - F1 fix: 可恢复异常从外层except移入per-step内层try, continue回卷while真重试, 不再误标failed
# 2026-07-18 - 小欧 - F3 fix: _should_retry_truncated_tool O(n²)嵌套循环→单遍O(n)
# 2026-07-19 小欧 控制台打印修复: if thought→if thought or reasoning(空content有reasoning的action step也能输出)
# 2026-07-19 小欧 推理空转不持久化: _finalize_cycle(finally出口)开头直调agent.message_builder.pop_temp_messages()弹掉残留标记推理再持久化; 落点单一收口(KISS-DIRECT), 生产直调无防御守卫, 测试mock缺message_builder属测试缺陷
# 2026-07-19 小欧 R1优化: B3空转警告(场景C reasoning-only子分支)改幂等注入+复用_temp_reasoning标记收口; 已存在相同标记消息则跳过,杜绝连续空转累积重复警告(history堆积/持久化残留); 终态统一由pop_temp_messages弹掉,零新机制(DRY/KISS); 正常answer无工具分支(else)不变仍持久化
# 2026-07-22 小欧 LLM 响应后提取 usage.total_tokens → message_builder.last_total_tokens，供下轮增量裁剪用
# 2026-07-22 小欧 usage 扩展: 三字段(prompt/completion/total)累加 accumulated_usage; emit MetaStep(type="usage") 逐次报告本次消耗
# 2026-07-22 小欧 MetaStep usage: 从 **_usage 解包改为手动三字段，精确控制输出
# 2026-07-23 小欧 - log_and_print统一: 3处print()替换为log_and_print()(Thought/Error/Cancel控制台输出), 导入log_and_print
# 2026-08-08 小欧 相同工具调用死循环检测(场景F)新增:
#   【病根】P6_01(file_not_found)超时根因: LLM连续40+步逐字重复同一Thought并反复调用完全相同工具+相同参数
#          (writetext写同一diff_tool.py), 每次工具均success, 现有_consecutive_reasoning_only仅拦"纯推理无工具
#          调用"空转, 本模式漏检, 致死循环直抵max_steps=10000。
#   【方案】_tool_call_signature计算action调用签名(含并行pending); _check_same_tool_loop返回int连续计数(count=第N次),
#           双阈值: count==2/3/4(_SAME_TOOL_WARN_ROUNDS起)注入assistant role纠偏消息尝试唤醒, count>=5硬终止failed;
#           签名变化重置count=1+清纠偏标记; 正常任务签名各异零误伤, 增强不退化。
# 2026-08-08 小欧 v1.6 双阈值实施: 单阈值(bool终止)升级为双阈值(3纠偏+5硬终止), 新增_warn_same_tool_loop
# 2026-08-08 小欧 v1.7 双阈值调整(北京老陈 2026-08-08 指示"第2次就发纠偏; 2/3/4次发, >=5结束"):
#   - 纠偏: 第2次(count==2)即发第1条(原第3次), 第2/3/4次各发1条共3条(原第3/4次共2条)
#   - 硬终止: count>=5(原count>5第6次, 收紧回第5次)
#   - 实现: _SAME_TOOL_WARN_ROUNDS 3→2, _SAME_TOOL_WARN_MAX 2→3; 判定改 _SAME_TOOL_WARN_ROUNDS<=cnt<5 区间发纠偏,
#     cnt>=5 硬终止; _warned_same_tool_loop 为 int 计数(发纠偏条数, 上限_SAME_TOOL_WARN_MAX),
#     重置/初始化点(签名变化/非action/initialize_run_state)由 False 改 0;
#     deny_counts 让位判断 not _warned_same_tool_loop 真值语义不变(int>0即已发)
# 2026-08-09 - 小欧 - P4拆分(见doc-8月优化修复代码三堂会审报告v1.1): 用户暂停阻塞由 task_pause_check(产SSE) 改为
#   wait_for_resume(纯阻塞不产SSE)。原 task_pause_check 在 react_cycle→agent_runner 路径产出的SSE字符串
#   被 agent_runner 以"跳过非Step事件"丢弃(死路); 前端暂停/恢复提示由 openai._stream_with_control 的
#   task_pause_check_and_yield 统一下发(职责单一无重复)。ast语法✓
# 2026-08-09 - 小欧 - task007核查问题A: 相同工具纠偏消息为"面向LLM的反馈指令", role由assistant改为user,
#   文本增强紧迫感(点明"强制终止后果"+要求改工具/直接结束), 强化LLM服从。带_temp_same_tool_warn标记
#   仍受通用_temp_*前缀清除(tool_retry_engine/pop_temp_messages v1.6)保护, 持久化前被pop_temp_messages
#   统一弹掉, 不污染history/压缩。ast语法✓
# 2026-08-10 - 小欧 - R1 实施(第二次代码更新): finally 新增 clear_temp_auth() (task 级清零点, 3.2.12/3.2.13); I1 授权段移入 try 内(见 I1/I2 v1.43 实现, 依赖本清零点)
# 2026-08-10 - 小欧 - I2/I3/I4 实施(第二次代码更新, 第五批): 任务目录级临时授权确认(3.2.13) —
#   I2 复用现有 HITL paused 流(前端零改动): try 内(while 前) 消费 agent._task_auth_paths(I1 挂载),
#   create_confirmation → MetaStep(paused, confirm_id, tool_name="task_dir_authorization") →
#   await wait_for_confirmation_result → 确认后批量 grant_temp_auth(recursive=True);
#   I3 落区判定(授权前分流): 系统禁区不授权 / 非系统禁区仅写可授权(删硬拦) / 白名单外入单;
#   I4 异常兜底: 确认超时/拒绝/异常 → 跳过不授权不阻塞, 任务继续(任务内仍可单点工具授权)
# 2026-08-10 - 小欧 - 撤销 I2/I3/I4 (北京老陈 2026-08-10): 「任务中目录解析功能点去掉」—
#   移除 try 内 while 前的任务目录级 HITL 批量授权段(create_confirmation/paused/grant_temp_auth);
#   目录权限全部走 LLM 工具参数路径进临时名单(3.2.12); 保留 R1 clear_temp_auth(task 级清零点); 同步撤销 initialize_run_state 的 I1
# 2026-08-10 - 小欧 - 撤销 I2 残留清理(三堂会审核查): 删除 L83 死 import HITL_TIMEOUT(I2 已撤销, react_cycle 内无任何引用, 死代码)


# 2026-08-12 - 小欧 - A1越层前置: safety 提升为顶层 app.safety, clear_temp_auth 的 import 由 app.services.safety.temp_auth 改 app.safety.temp_auth(配合 tools 禁 app.services 守护规则)
# 2026-08-13 - 小欧 - 三堂会审修复#2/#36: #2 _RECOVERABLE_ERRORS 补 "timeout"(HITL确认超时是用户侧软拒绝,
#   原判FAILED与 _add_denial_feedback 注入的"改用其他工具"引导自相矛盾; 纳入后由 _deny_counts 累计>=3才FAILED);
#   #36 可恢复异常路径不再 set RETRYING(计数已在 except 内+1), 消除与主循环 RETRYING 处理双累加
#   (一次异常计2次→上限3实际第2次即FAILED, 重试机会减半); 来源B(_dispatch_handler retrying)仍走L614计数, 两来源各自单计
# 2026-08-13 - 小欧 - 三堂会审修复#29: finally 新增 reset_current_task_id()(与 set 对称, set在action_handler.py:882)
#   【病根】set_current_task_id 全仓唯一set点, reset_current_task_id(context.py:38)零调用; 当前每SSE请求独立asyncio.Task,
#     ContextVar随任务结束丢弃故不漏, 但长连接/复用context(手动测试/常驻入口)会跨请求泄漏task_id
#   【改法】与 clear_temp_auth 并列在 task 级 finally 调 reset_current_task_id(), 对称set/reset, 行为零退化
# 2026-08-14 - 小欧 - llm 独立为 app 顶层能力层目录(services/llm→app/llm), 本文件 import 路径同步
# 2026-08-16 - 小欧 - S4(10.1.1③/10.1.7④): start 装配进 agent.steps(占 step 0), 取消 orchestrator 旁路。
#   P4 注入模式: 工厂由 orchestrator 注入 agent._start_step_factory(chat 层数据闭包捕获), 本处只读 agent 属性
#   (system_prompt=_sys_prompt, previous_messages=context), 不 import chat 层; start 落库走 agent_runner 事件流
# 2026-08-17 - 小健 - 三堂会审修复(北京老陈驱动, 11 bug 复核3遍):
#   S4(步号唯一): 首轮前取消(llm_call_count 尚未在 _process_single_step 开头 +1 =0)时, FinalStep step=0 与
#       start(占 step0) 双 step0 冲突; 改用 `step=agent.llm_call_count or 1` 接续唯一步号, 消除与 start 重复。
# 2026-08-17 - 小健 - S5(10.1.8, 943a77917): 新增 _compact_injected_history(agent), 当 initialize_run_state
#   已置 agent._needs_compact=True 且 COMPACTION_ENABLED 放开 R4 时: 对 conversation_history 做一次 LLM 锚定
#   摘要, 以 assistant 消息回填(system[:1] + 摘要 + 最新 task[-1:]); tools=None 走 llm_stream Text 模式;
#   回填新列表赋值 conversation_history(压缩生效); 摘要为空/异常则原样保留零退化; 主循环 while 前 await 调用
# 2026-08-17 - 小健 - start 业务过程收敛(老陈驱动, 痛斥输入装配割裂): start 装配段(initialize_run_state 后、
#   while 前)扩展为任务输入装配完整段——注入会话历史(_inject_conversation_history) → 超窗判定(_maybe_compact)
#   → context_summary 快照 → 构造 StartStep → emit, 一气呵成; 历史注入/超窗标记自 initialize_run_state 收拢至此
# 2026-08-17 - 小健 - start 业务物理独立模块(老陈驱动, 痛斥"一个事情到处乱放"): 新增 start_step.py 单一承载 start
#   全部业务(_inject_conversation_history/_maybe_compact_injected_history/_compact_injected_history/assemble_start_step),
#   自本文件移除 _assemble_start_step 与 _compact_injected_history 定义, 改为模块级薄 import(assemble_start_step
#   as _assemble_start_step / _compact_injected_history); 主流程调用点不动(L569 _assemble_start_step / L578 _compact)
#   MaxSteps 语义、编辑历史条目名不变; 本文件退回启动编排薄层 — 小健 2026-08-17
# 2026-08-17 - 小健 - start 业务彻底单归属(老陈驱动, 三思三省): 契约构造迁入 start_step(_build_start_contract),
#   装配数据来源由 chat 层 _start_step_factory 闭包改为 orchestrator 注入的 agent._start_meta(dict 运行元数据);
#   本文件对 start 的接缝不变——仍『initialize_run_state → assemble_start_step(agent, context) → emit → 超窗 C4 回填』,
#   仅数据来源改读 _start_meta(build_start_step 逻辑已在 start_step 模块内直接构造, 详见 start_step.py) — 小健 2026-08-17
# 2026-08-17 - 小健 - 最合理核查(老陈追问): assemble_start_step 改同步(内部零 await), 调用点去 await — 小健 2026-08-17
# 2026-08-17 - 小健 - 注释纠偏(北京老陈 2026-08-17): S5 超窗回填段注释去掉「依赖 COMPACTION_ENABLED 放开 R4」表述——
#   开关仅限 start 超窗判定(start_step)使用; 触发条件只据 start 超窗置的 _needs_compact 标记(getattr 判断) — 小健 2026-08-17
# 2026-08-18 小欧 - §10.3.3(4): same_tool_loop终止FinalStep的 thought= 改 reasoning=(FinalStep已删thought参数)
# 2026-08-18 - 小欧 - §10.4.4 P2/P3/P4/P5/P6: handle_react_error/empty_response/chunk_buffer_timeout 改 MetaStep(type="error")(删ErrorStep import); _dispatch_handler 改读 _kwargs 取 error_type; usage emit 处 append _usage_events; 各 error/retrying/usage 加 severity(warn/info)
# 2026-08-20 - 小欧 - 11.1 token 四层同构累计三堂会审修复: 任务起点(run_react_cycle)读 DB 一次缓存 _session_acc_base/_chain_acc_base 到 agent 并初始化 session/chain 累计=基线(无 LLM 调用任务也正确反映历史累计, 杜绝日志/前端误显 0); usage 块改用缓存基线(消除每轮双 DB 连接冗余读取); DB 异常降级为零基线不阻断主链路
# 2026-08-20 - 小欧 - 真实缺陷复核三遍修复(review 3x 确认后按最佳不退化): ①A(遥测 usage 门控): on_llm_call/build_stats_step/context_overview 原置于 `if _usage` 内, 无 usage 响应时 llm_calls/stats/context_overview 全丢; 移出到 response 分支末尾必发(usage 存在行为完全不变, 纯增强), 补 isinstance 守卫 error/finish_reason 计算; ②C2(裁剪token死活): on_trim 原只传 bool -> 透传 message_builder._trimmed_tokens_this_round, 裁掉token数不再恒0。
# 2026-08-20 - 小欧 - 11.1b 运行中DB即时落库(北京老陈裁定"每轮即时落库"): 每轮 emit usage(MetaStep type=usage) 后同步 update_task/session_accumulation 落库, 供运行中他方查询/断线中间态读取实时累计; DB 读-加-写(当前DB值+本轮token)与内存态基线口径一致, 会话缺 session_id 守卫跳过; DB 异常降级 warning 不阻断主链路; 配套 agent_runner S2 移除重复 update 防同批 token 翻倍累加
# 2026-08-20 - 小欧 - 解决问题18(2.4④ truncated): 新增 MetaStep(type="truncated") 统一"输出截断"事件, 仅触发于 LLM 输出截断 2 处(场景D)——重试分支(content=连续第N次+已注入重试Observation)与连续截断取消分支(content=连续N次+任务取消, 于 FinalStep 前下发), severity=warn; 上下文裁剪/工具结果截断已有 context_overview.truncated / observation data.truncated 通道, 不重复新增(DRY); MetaStep 不落库不占 steps, 不影响 total_steps
# 2026-08-21 - 小欧 - 12.2-Q5-D3(按文档[1]12.2 diff设计落地): 每轮 token 累计落库块之后新增运行中 checkpoint——
#   调 agent.telemetry.checkpoint_llm_calls() 增量持久化 llm_calls(整表重写+idx_llm_calls_task_call 唯一索引幂等去重);
#   目的: 任务中途崩溃时监控数据最多丢最后一轮, 不再全丢; getattr 守卫无 telemetry 场景零影响, 主链路零改动
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.5/6.7: 三处 F8 属性迁移——:398 LLM 调用日志行改读
#   llm_client.llm_model.model; :401 log_llm_call 改传 llm_model=llm_client.llm_model(prompt_logger 签名归一);
#   :508 telemetry.on_llm_call 改传 tele_model=llm_client.llm_model — 全链 ModelRef 归一
# 2026-08-23 - 小欧 - 三轮三堂会审修复(P1): :398/:404/:509 三处改读任务快照 agent._task_llm_model 优先——
#   防共享单例被并发还原后本任务后续轮次记录到他人模型(与 base_agent 快照/telemetry.finalize 同步落地)
# 2026-08-23 - 小欧 - 落盘文件A/B 实施(文档[1]11.8.4 D2/11.9 P2): _process_single_step 在 prepare_messages_for_llm()
#   之后调 agent.file_persist.append_conv_blocks(llm_call_count, messages) 增量落文件B(稳定 _msg_id 去重),
#   随即 pop("_msg_id") 防泄漏 LLM wire; getattr 守卫 writer 未挂载空转, 旁路不阻塞主链路
# 2026-08-28 小欧 - KISS修正(三堂会审yield链审查): 5处 emit_final_with_stats 调用点 async for→for(配合 step_emitter.emit_final_with_stats 改 sync 返回 (final, stats) 二元组); 原 async 体内零await, 纯伪异步包装; 行为等价无backward
# 2026-09-02 - 小欧 - 设计文档v1.21§5.5落码(工具结果显示与taskinfo显示分析与设计-小欧-2026-09-01.md): _process_single_step
#   :435 async for 内拆包前拦截 ("meta", {...}) → yield MetaStep(type=retrying, step=llm_call_count, severity=info,
#   wait_time) 走 StepEmitter 与既有 retrying 同路径发前端位4🔁; 命中即 continue(未命中照旧拆包走既有分支);
#   LLM底层 L1/L2/FC降级重试通知全链落点收口
# 2026-09-05 小健 8.4拆分(react_cycle.py拆四): 常量+守卫群→react_inference.py, _dispatch_handler(含状态推断)→react_dispatch.py,
#   run_react_cycle+_finalize_cycle→react_loop.py; 本文件由 react_cycle.py git mv 改名(历史/blame不断),
#   余部仅剩 _process_single_step — 逐字复制, 只改import

"""react_step — 单步ReAct调度(react_cycle.py 余部改名, 8.4拆分后专注"单步编排")

职责: 单步编排(LLM调用准备→流式调用→响应分发), 不包含主循环调度/类型分派/推断基元。
老名react_cycle已消亡, 引用从 react_loop/react_dispatch/react_inference/react_step 各取所需。
"""

import time
from typing import AsyncGenerator
from app.logger import logger, log_and_print
from app.logger.prompt_logger import get_prompt_logger
from app.services.agent.steps import ChunkStep, MetaStep, ObservationStep, FinalStep
from app.services.agent.status_table import AgentStatus, set_status, set_failed, set_cancelled
from app.services.agent.llm_call import call_llm_with_fallback
from app.services.agent.tool_cache_manager import get_openai_tools
from app.services.agent.react_inference import (
    _should_retry_truncated_tool,
    _MAX_CONSECUTIVE_TRUNCATIONS,
    _SAME_TOOL_WARN_ROUNDS,
    _MAX_CONSECUTIVE_SAME_TOOL_CALLS,
    _check_same_tool_loop,
    _warn_same_tool_loop,
)
from app.services.agent.react_dispatch import _dispatch_handler
from app.db import db
from app.services.chat import storage

async def _process_single_step(agent, chunk_buffer) -> AsyncGenerator:
    """单步ReAct调度: LLM调用→响应处理→分发 — 小欧 2026-06-25 / 小欧 2026-07-09 加分区注释"""

    # ── Phase 1: LLM 调用准备 ──────────────────────────────────
    agent.llm_call_count += 1
    agent.message_builder.trim_history()  # 唯一裁剪入口 — 小欧 2026-07-01
    agent.telemetry.on_trim(
        getattr(agent.message_builder, "_trimmed_this_round", False),
        getattr(agent.message_builder, "_trimmed_tokens_this_round", 0),
    )  # 11.3 C2修复(复核确认): 透传裁剪token数, 防 on_trim 恒0死数据 — 小欧 2026-08-20
    _first_token_marked = False           # 11.2-B 首 chunk 只记一次首包时延 — 小欧 2026-08-20
    messages = agent.message_builder.prepare_messages_for_llm()
    # 11.8-H2: 文件B 增量落盘(loop顺序/结构保真/增量前缀) — 小欧 2026-08-23
    # call_no = agent.llm_call_count(本次调用序号, 上方刚自增) — 文档[1]11.7.10-2
    # 经注入的 agent.file_persist 调用(与 telemetry 同模式, agent 层零 chat 依赖); writer 未挂载时空转 — 小欧 2026-08-23
    _fp = getattr(agent, "file_persist", None)
    if _fp is not None:
        _fp.append_conv_blocks(agent.llm_call_count, messages)   # 读 _msg_id 去重(#10 修正)
    for _m in messages:
        _m.pop("_msg_id", None)        # 剥离内部标记后再发 LLM(防泄漏 wire) — #10 修正 小欧 2026-08-23
    openai_tools = get_openai_tools(agent)

    _task_llm = getattr(agent, "_task_llm_model", None) or getattr(agent.llm_client, "llm_model", None)   # 任务快照优先(三堂会审 P1) — 小欧 2026-08-22
    logger.info(f"[LLM] 调用#{agent.llm_call_count}, messages={len(messages)}, tools={len(openai_tools)}, model={getattr(_task_llm, 'model', '?')}")

    prompt_logger = get_prompt_logger()
    prompt_logger.log_llm_call(
        round_number=agent.llm_call_count,
        messages=messages,
        llm_model=_task_llm,   # 归一: 传 ModelRef 结构(任务级快照, 防单例还原竞态) — 小欧 2026-08-22
        call_type="tools",
        tools=openai_tools,
    )

    if not openai_tools:
        logger.error("[_process_single_step] 无可用工具")

    # ── Phase 2: LLM 流式调用 ──────────────────────────────────
    llm_response = None
    _call_start = time.time()                   # 11.2-C LLM 调用计时 — 小欧 2026-08-20
    async for chunk_or_response in call_llm_with_fallback(agent, messages, openai_tools):
        if isinstance(chunk_or_response, tuple) and chunk_or_response[0] == "meta":
            # 小欧 2026-09-02: LLM 底层 L1/L2/降级重试通知 → 标准 retrying 事件发前端
            _m = chunk_or_response[1]
            yield agent._step_emitter.emit(MetaStep(
                type=_m["type"],
                step=agent.llm_call_count,
                content=_m["content"],
                severity="info",
                wait_time=_m.get("wait_time"),
            ))
            continue
        chunk_type, chunk_data = chunk_or_response   # 既有拆包(仅非meta时执行, 原 :436)

        if chunk_type == "chunk":
            content = chunk_data.content if hasattr(chunk_data, 'content') else str(chunk_data)
            is_reasoning = getattr(chunk_data, 'is_reasoning', False)
            chunk_buffer.append(content)
            if not _first_token_marked:          # 首 chunk 记首包时延 — 小欧 2026-08-20
                agent.telemetry.mark_first_token()
                _first_token_marked = True
            chunk_step = ChunkStep(
                step=agent.llm_call_count,
                content=content,
                is_reasoning=is_reasoning,
            )
            yield agent._step_emitter.emit(chunk_step)
        elif chunk_type == "response":
            llm_response = chunk_data
            _call_dur = time.time() - _call_start
            chunk_buffer.clear()
            # LLM usage 处理: 裁剪触发 + 累积消耗 + 逐次报告 — 小欧 2026-07-22
            _usage = llm_response.get("usage") if isinstance(llm_response, dict) else None
            if _usage and isinstance(_usage, dict):
                # 裁剪触发: 记录精确 total_tokens 供下轮增量裁剪
                _tt = _usage.get("total_tokens")
                if _tt is not None:
                    agent.message_builder.last_total_tokens = int(_tt)
                # 累积消耗: 三个字段逐次累加
                for _k in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    _v = _usage.get(_k)
                    if _v is not None:
                        agent.accumulated_usage[_k] += int(_v)
                # 逐次报告: emit MetaStep(type="usage") 带本次 usage 三个值
                # 2026-08-18 小欧 P6: usage剔step_json, append _usage_events明细供agent_runner终态insert_token读
                _ue = getattr(agent, "_usage_events", None)
                if _ue is not None:
                    _ue.append({"step": agent.llm_call_count, "prompt_tokens": _usage.get("prompt_tokens"), "completion_tokens": _usage.get("completion_tokens"), "total_tokens": _usage.get("total_tokens")})
                # 11.1 token 四层同构累计 — 任务级用 agent 内存态逐轮累加(跨轮累计,不读DB,避免任务内DB未回写致不累计);
                #   会话级/链级在缓存基线(任务开始前历史累计, 见 run_react_cycle 初始化, 任务内恒定)上叠加当前任务运行累计 — 小欧 2026-08-20
                _llm_call_count_token = {
                    "prompt_tokens": int(_usage.get("prompt_tokens") or 0),
                    "completion_tokens": int(_usage.get("completion_tokens") or 0),
                    "total_tokens": int(_usage.get("total_tokens") or 0),
                }
                _K = ("prompt_tokens", "completion_tokens", "total_tokens")
                # 任务级: agent 内存态(初始0)逐轮 += 本轮 → 任务内天然累计
                agent.task_accumulated_tokens = {k: agent.task_accumulated_tokens[k] + _llm_call_count_token[k] for k in _K}
                # 会话级: 基线(历史累计, 任务内恒定, 见 run_react_cycle 初始化) + 当前任务运行累计
                _ZERO = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
                _sess_base = getattr(agent, "_session_acc_base", None) or _ZERO
                agent.session_accumulated_tokens = {k: _sess_base[k] + agent.task_accumulated_tokens[k] for k in _K}
                # 链累计（计算派生，不落库）— 基线(历史链累计, 任务内恒定) + 当前任务运行累计
                _chain_base = getattr(agent, "_chain_acc_base", None) or _ZERO
                agent.chain_accumulated_tokens = {k: _chain_base[k] + agent.task_accumulated_tokens[k] for k in _K}
                _usage_step = MetaStep(
                    step=agent.llm_call_count,
                    type="usage",
                    content="",
                    prompt_tokens=_usage.get("prompt_tokens"),
                    completion_tokens=_usage.get("completion_tokens"),
                    total_tokens=_usage.get("total_tokens"),
                    severity="info",
                    llm_call_count_token=_llm_call_count_token,                  # 11.1 新增 — 小欧 2026-08-20
                    task_accumulated_tokens=agent.task_accumulated_tokens,         # 11.1 新增
                    session_accumulated_tokens=agent.session_accumulated_tokens,   # 11.1 新增
                    chain_accumulated_tokens=agent.chain_accumulated_tokens,       # 11.1 新增
                )
                yield agent._step_emitter.emit(_usage_step)

                # 11.1b 运行中DB即时落库（每轮 update 任务/会话累计，供运行中他方查询/断线中间态读取）— 小欧 2026-08-20
                #   用户裁定"每轮即时落库"; DB 读-加-写(当前DB值+本轮token) 与内存态基线口径一致;
                #   DB 异常降级不阻断主链路; agent_runner S2 已同步移除 update 防重复累加(翻倍)。
                try:
                    # 落库 offload 出事件循环(后端卡死修复 小欧 2026-08-24)
                    await db.atxn("chat", lambda conn: (
                        storage.update_task_accumulation(conn, task_id=agent.task_id, llm_call_count_token=_llm_call_count_token),
                        storage.update_session_accumulation(conn, session_id=agent._start_meta.get("session_id"), llm_call_count_token=_llm_call_count_token)
                        if (getattr(agent, "_start_meta", None) and agent._start_meta.get("session_id")) else None))
                except Exception as _sce_e:
                    logger.warning(f"[react_cycle] 每轮token累计落库失败(降级, 不影响主链路): {_sce_e}")

                # 12.2-Q5: 运行中checkpoint llm_calls(唯一索引幂等去重) — 中途崩溃监控数据不再全丢 — 小欧 2026-08-21
                _tel = getattr(agent, "telemetry", None)
                if _tel is not None:
                    _tel.checkpoint_llm_calls()

            # 11.2-C 遥测 + 11.2-B stats/11.3 context_overview —— 不依赖 usage，每次 LLM 响应必发（11.2-C 逐次明细）
            # 修复A(小欧 2026-08-20 复核确认): 原置于 usage 门控内, 无 usage 的响应 llm_calls/stats/context_overview 全丢,
            #   违背 11.2-C"每次调用一行"、11.2-B"每轮 stats"契约; 移出后 usage 存在不改变行为(纯增强不退化) — 小欧 2026-08-20
            _llm_err = None
            _fin = llm_response.get("finish_reason") if isinstance(llm_response, dict) else None
            if isinstance(llm_response, dict) and llm_response.get("error"):
                _llm_err = str(llm_response["error"])[:80]
            agent.telemetry.on_llm_call(
                _usage, duration=_call_dur,
                tele_model=getattr(agent, "_task_llm_model", None)
                           or getattr(agent.llm_client, "llm_model", None),   # 任务快照优先(三堂会审 P1 防还原竞态) — 小欧 2026-08-22
                error_type=_llm_err, finish_reason=_fin,
            )
            # 11.2-B stats 事件（独立模块产出 MetaStep(type="stats", ...)）— 小欧 2026-08-20
            _stats_step = agent.telemetry.build_stats_step()   # → MetaStep(type="stats", step_count/llm_call_count/retry_count/duration)
            yield agent._step_emitter.emit(_stats_step)
            # 11.3 context_overview 事件（独立模块产出 MetaStep(type="context_overview", ...)）
            _overview = agent.telemetry.build_context_overview()
            _llm_n = agent.llm_call_count
            if _llm_n == 1 or getattr(agent.message_builder, "_trimmed_this_round", False) or _llm_n % 5 == 0:
                yield agent._step_emitter.emit(MetaStep(
                    step=_llm_n, type="context_overview", content=_overview.get("summary", ""),
                    message_count=_overview["message_count"], estimated_tokens=_overview["estimated_tokens"],
                    truncated=_overview["truncated"],
                    injected_message_count=_overview["injected_message_count"],
                    injected_estimated_tokens=_overview["injected_estimated_tokens"],
                    injected_ratio=_overview["injected_ratio"],
                    severity="info",
                ))

    # ── Phase 3: 响应分发 ──────────────────────────────────────
    set_status(agent, AgentStatus.EXECUTING)

    step = agent.llm_call_count

    # ── 场景A: 空响应 — LLM未返回有效数据 ──────────────────────
    if not llm_response or not isinstance(llm_response, dict):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        log_and_print(f"{time.strftime('%H:%M:%S')} [Error] step={step}, empty_response")  # 小欧 2026-07-02 控制台
        set_failed(agent, "LLM返回空响应，任务终止")
        yield agent._step_emitter.emit(MetaStep(
            step=step, type="error", content="LLM返回空响应，任务终止", error_type="empty_response", severity="warn"
        ))
        return

    # ── 场景C: LLM直接回答/纯推理 → 注入复核warning（不重试）— 小健 2026-07-03
    # 设计: fall through到正常分发, warning进history,
    # 下轮循环LLM会看到这条observation并重新思考 — 小欧 2026-07-09
    # 2026-07-17 - 小欧 - 扩展: 原仅检content(有content的answer), reasoning-only(空转)被漏检;
    #   现也检reasoning, 且reasoning-only不受has_tool_results限制(否则已调工具后空转仍沉默, 恰是task-2ffbc517场景);
    #   与answer_handler的硬终止(A增强版)互补: 本处软引导, 引导失败则由A硬终止兜底。
    if (llm_response.get("type") == "answer"
            and (llm_response.get("content") or llm_response.get("reasoning"))):
        _content = llm_response.get("content", "") or ""
        _reasoning = llm_response.get("reasoning", "") or ""
        if not _content:
            # reasoning-only(纯推理无工具无答案空转): 必警告, 不受has_tool_results限制
            logger.warning(f"[B3] LLM返回reasoning-only(空转)未调用工具(step={step})")
            obs_text = ("[Observation] 警告: 你当前仅在推理未调用工具, 若已掌握所需信息请直接给出最终答案, "
                        "否则应调用工具获取信息, 避免空转")
            # 小欧 R1优化(2026-07-19): B3空转警告幂等注入+复用_temp_reasoning标记收口,
            #   已存在相同标记消息则跳过,杜绝连续空转累积重复警告(history堆积/持久化残留);
            #   终态由_finalize_cycle.pop_temp_messages统一弹掉,符合"空转不持久化"设计,零新机制(DRY/KISS)
            _hist = agent.message_builder.conversation_history
            if not any(m.get("role") == "assistant" and m.get("_temp_reasoning") and m.get("content") == obs_text
                       for m in _hist):
                _hist.append({
                    "role": "assistant",
                    "content": obs_text,
                    "reasoning": "",
                    "reasoning_content": "",
                    "_temp_reasoning": True,
                })
        else:
            has_tool_results = any(
                msg.get("role") == "tool"
                for msg in agent.message_builder.conversation_history
            )
            if not has_tool_results:
                logger.warning(f"[B3] LLM返回answer但未调用任何工具(step={step})")
                obs_text = "[Observation] 警告: 你未调用任何工具-->必须复核3遍用户任务:[1]问答任务补充说明;[2] 多步任务就继续调用工具"
                agent.message_builder.add_assistant_message(obs_text)  # 2026-07-17 - 小欧 - 同reasoning-only分支: 改add_assistant_message避免孤立tool消息致LLM参数不合法

    # ── 场景D: 输出截断重试 — 检测preamble截断,注入重试observation ── 小健 2026-07-03
    if _should_retry_truncated_tool(agent, llm_response):
        content = llm_response.get("content", "")
        agent._consecutive_truncations = getattr(agent, '_consecutive_truncations', 0) + 1
        logger.warning(f"[run_react_cycle] 检测到LLM输出截断(step={step}, 连续第{agent._consecutive_truncations}次, content={content[:50]})")

        if agent._consecutive_truncations >= _MAX_CONSECUTIVE_TRUNCATIONS:
            logger.error(f"[run_react_cycle] LLM连续截断{_MAX_CONSECUTIVE_TRUNCATIONS}次, 停止重试")
            log_and_print(f"{time.strftime('%H:%M:%S')} [Cancel] step={step}, consecutive_truncation")  # 小欧 2026-07-02 控制台
            # 解决问题18(2.4④): 连续截断取消前发 MetaStep(type="truncated") 统一"输出被截断"事件 — 小欧 2026-08-20
            yield agent._step_emitter.emit(MetaStep(
                step=step, type="truncated",
                content=f"LLM连续{_MAX_CONSECUTIVE_TRUNCATIONS}次输出截断，任务取消",
                severity="warn",
            ))
            for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
                step=step,
                response=f"LLM连续{_MAX_CONSECUTIVE_TRUNCATIONS}次输出截断",
                outcome="cancelled",
            )):
                yield _s
            set_cancelled(agent)
            return

        obs_text = "[Observation] 工具调用输出不完整，请重新调用该工具并补充完整参数"
        _retry_tc_id = ""
        history = agent.message_builder.conversation_history
        for i in range(len(history) - 1, -1, -1):
            msg = history[i]
            if msg.get("role") == "assistant" and msg.get("tool_calls"):
                _retry_tc_id = msg["tool_calls"][-1].get("id", "")
                break
        agent.message_builder.add_observation(
            obs_text, {"tool_call_id": _retry_tc_id, "tool_calls": [], "llm_content": content},
        )
        # 解决问题18(2.4④): 输出截断重试前发 MetaStep(type="truncated") 统一"输出被截断"事件 — 小欧 2026-08-20
        yield agent._step_emitter.emit(MetaStep(
            step=step, type="truncated",
            content=f"LLM输出截断(连续第{agent._consecutive_truncations}次)，已注入重试Observation",
            severity="warn",
        ))
        yield agent._step_emitter.emit(ObservationStep(
            step=step,
            tool_result=[{"tool_name": "truncated_output", "llm_data": {"summary": "LLM工具调用输出截断", "action": {}, "status": {"exec_code": "error", "message": obs_text}}, "llm_data_text": "", "data_text": obs_text, "other_data": {}}],
        ))
        return

# ── 场景F: 相同工具调用死循环检测(双阈值纠偏/硬终止) ──────────
    # 2026-08-08 - 小欧 - P6_01(file_not_found)超时根因修复:
    #   【病根】LLM连续40+步逐字重复同一Thought并反复调用完全相同工具+相同参数(writetext写同一diff_tool.py),
    #          每次工具执行均success, 现有_consecutive_reasoning_only仅拦"纯推理无工具调用"空转, 本模式漏检,
    #          致死循环直抵max_steps=10000(约40+分钟)。
    #   【方案】对action响应计算工具调用签名(tool_name+规范化tool_params, 含并行pending),
    #          _check_same_tool_loop返回int连续计数(count=第N次), 双阈值:
    #          count==2/3/4(_SAME_TOOL_WARN_ROUNDS起)各注入assistant role纠偏消息(尝试唤醒调整, 最多3条);
    #          count>=5(_MAX_CONSECUTIVE_SAME_TOOL_CALLS)判定死循环硬终止failed。
    #          正常任务LLM每轮工具/参数各异或需新信息, 签名必不同, count重置, 零误伤(增强不退化)。
    if llm_response.get("type") == "action":
        _cnt = _check_same_tool_loop(agent, llm_response)
        if _SAME_TOOL_WARN_ROUNDS <= _cnt < _MAX_CONSECUTIVE_SAME_TOOL_CALLS:
            # count==2/3/4: 各发1条纠偏(共3条, 内部幂等上限_SAME_TOOL_WARN_MAX) — 小欧 2026-08-08
            _warn_same_tool_loop(agent, llm_response, _cnt)
        elif _cnt >= _MAX_CONSECUTIVE_SAME_TOOL_CALLS:    # count>=5(第5次相同调用): 硬终止 — 小欧 2026-08-08
            logger.warning(f"[run_react_cycle] LLM连续{_cnt}步调用相同工具(step={step}), 判定死循环, 终止")
            log_and_print(f"{time.strftime('%H:%M:%S')} [Cancel] step={step}, same_tool_loop")  # 小欧 2026-08-08 控制台
            set_failed(agent, f"模型连续{_cnt}步重复调用相同工具, 疑似死循环, 任务终止")
            for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
                step=step,
                response="模型反复调用相同工具未取得进展，任务已终止（疑似死循环）",
                reasoning=llm_response.get("reasoning", "") or llm_response.get("thought", ""),
                outcome="failed",
                error_type="same_tool_loop",
                error_message=f"模型连续{_cnt}步重复调用相同工具，疑似死循环",
            )):
                yield _s
            return
    else:
        # 非action(正常answer/final): 死循环检测仅在action语义下, 归零防残留(含纠偏标记) — 小欧 2026-08-08
        agent._consecutive_same_tool_calls = 0
        agent._last_tool_call_sig = None
        agent._warned_same_tool_loop = 0            # int计数归零 — 小欧 2026-08-08

    # ── 场景E: 正常分发 ─────────────────────────────────────────
    agent._consecutive_truncations = 0
    async for event in _dispatch_handler(agent, llm_response):
        yield event


