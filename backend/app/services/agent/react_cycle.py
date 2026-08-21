
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
"""
run_react_cycle — ReAct 循环核心（薄调度）

职责: 循环调度 + 类型分派 + 状态推断，不含业务逻辑
业务逻辑在 handlers/ 目录
"""

import asyncio
import json
import time
from typing import Any, Dict, Optional, AsyncGenerator

from app.logger import logger, log_and_print
from app.llm.error_classifier import SystemErrorClassifier
from app.logger.prompt_logger import get_prompt_logger
from app.config import get_config
from app.services.agent.steps import ChunkStep, MetaStep, ObservationStep, FinalStep  # 2026-08-18 小欧 P3: ErrorStep→MetaStep(type="error"), 删ErrorStep import
from app.services.agent.status_table import AgentStatus, set_status, set_failed, set_completed, set_cancelled
from app.services.agent.initialize_run_state import initialize_run_state
from app.services.agent.start_step import assemble_start_step as _assemble_start_step
from app.services.agent.start_step import _compact_injected_history  # S5(10.1.8): C4 摘要回填, 独立模块 — 小健 2026-08-17
from app.services.agent.handlers import (
    handle_action, handle_answer,
)
from app.services.agent.llm_stream import call_llm_with_fallback
from app.services.agent.tool_cache_manager import get_openai_tools
from app.db import db                                          # 11.1 新增: 读 DB 会话/链历史累计 — 小欧 2026-08-20
from app.services.chat import storage                          # 11.1 新增: query_session_accumulation / query_chain_accumulation — 小欧 2026-08-20

_MAX_CONSECUTIVE_TRUNCATIONS = 3

# 相同工具调用死循环防御(双阈值纠偏/硬终止): LLM连续调用完全相同工具+相同参数时,
# 第2次(count==2)、第3次(count==3)、第4次(count==4)各注入一条assistant role纠偏消息尝试唤醒调整(共3条);
# count>=5(第5次)判定死循环硬终止。
# 2026-08-08 - 小欧 - P6_01(file_not_found)超时根因: LLM连续40+步逐字重复同一Thought并反复调用
#   相同writetext(diff_tool.py), 每次均success, 现有_consecutive_reasoning_only仅拦"纯推理无工具"
#   空转, 本模式漏检, 致死循环直抵max_steps=10000。v1.6升级为由单阈值硬终止改为双阈值(纠偏+硬终止)。
# v1.7(北京老陈 2026-08-08): 纠偏起点提前——第2次(count==2)就发第1条纠偏(原第3次), 第2/3/4次共发3条,
#   硬终止 count>=5(原count>5第6次)收紧; 给LLM尽早调整机会(第2次发现完全相同即提醒)。
_SAME_TOOL_WARN_ROUNDS = 2             # 纠偏起点阈值: count==2(第2次相同调用)注入第1条警告 — 小欧 2026-08-08
_SAME_TOOL_WARN_MAX = 3                # 纠偏最大条数: 第2/3/4次共3条 — 小欧 2026-08-08
_MAX_CONSECUTIVE_SAME_TOOL_CALLS = 5   # 硬终止阈值: count>=5(第5次相同调用)时硬终止 — 小欧 2026-08-08

# 可恢复的拒绝/拦截错误: 拒绝≠失败(符合人类认知, 助手应换工具继续) — 小欧 2026-07-13
# 反馈已写入LLM历史(_add_denial_feedback), 循环回THINKING由主循环 EXECUTING→THINKING 处理;
# 仅当"同一工具+同类型错误"累计>=3次才置 FAILED(说明LLM陷入死胡同) — 北京老陈 2026-07-13。
# 2026-08-13 - 小欧 - 三堂会审修复#2: 补 "timeout" — 确认超时(action_handler:263 发 error_type="timeout")
#   是用户侧等待超时(软拒绝, 应换工具/重试继续), 判 FAILED 与 _add_denial_feedback 注入的"改用其他工具"
#   引导自相矛盾; 纳入可恢复后由 _deny_counts 累计>=3 才 FAILED(与 user_rejected 同语义)。
_RECOVERABLE_ERRORS = {"user_rejected", "blocked", "timeout"}


def handle_react_error(agent, error, step):
    """统一处理ReAct循环中的错误 — 返回MetaStep(type="error")仅SSE不落库 — 小欧 2026-08-18 P3
    _last_error由step_emitter.emit统一出口记录, 守卫读此填充final"""
    error_type = SystemErrorClassifier.classify_error(error).name.lower()
    logger.error(f"[ErrorHandler] 错误类型={error_type}: {error}")
    return MetaStep(step=step, type="error", content=str(error), error_type=error_type, severity="warn")


def _is_recoverable_error(error) -> bool:
    """判断错误是否可恢复（FC格式错误/网络错误/超时） — chendyg 2026-07-01"""
    try:
        from app.llm.core import LLMResponseError
        if isinstance(error, LLMResponseError):
            return True
    except ImportError:
        pass
    if isinstance(error, asyncio.TimeoutError):
        return True
    try:
        import httpx
        if isinstance(error, (
            httpx.TimeoutException, httpx.ConnectError, httpx.NetworkError,
            httpx.ProxyError, httpx.TooManyRedirects,
        )):
            return True
    except ImportError:
        pass
    return False


def _should_retry_truncated_tool(agent, llm_response: Dict) -> bool:
    """检测LLM应答是否因输出截断导致工具调用遗漏
    
    条件:
    1. 返回类型是answer
    2. 内容很短(<500字,可能截断)
    3. 对话历史中存在带tool_calls的assistant消息(LLM之前处于工具模式)
    4. 该tool_call**未被成功执行**(无对应tool角色响应) — P0-2修复 2026-06-23 小欧
    E-3修复 2026-06-25 小欧: 阈值100→500,覆盖更多截断场景
    """
    if llm_response.get("type") != "answer":
        return False
    content = llm_response.get("content", "")
    if not content or len(content) > 500:
        return False
    history = agent.message_builder.conversation_history
    _seen_response = False
    for msg in reversed(history):
        role = msg.get("role")
        if role in ("tool", "observation"):
            _seen_response = True
        elif role == "assistant" and msg.get("tool_calls"):
            return not _seen_response
    return False


def _tool_call_signature(llm_response: Dict) -> str:
    """计算action响应的工具调用签名(全部调用含并行) — 小欧 2026-08-08
    用于相同工具调用死循环检测: 签名=tool_name+规范化tool_params的排序JSON,
    连续多步完全相同签名即判死循环。sort_keys保证字典顺序无关, 参数内容变化即签名变化。"""
    calls = []
    _primary = (llm_response.get("tool_name", "") or "",
                llm_response.get("tool_params") or {})
    calls.append(_primary)
    for _pc in llm_response.get("_pending_calls") or []:
        calls.append((_pc.get("tool_name", "") or "", _pc.get("tool_params") or {}))
    return json.dumps(calls, sort_keys=True, ensure_ascii=False)


def _check_same_tool_loop(agent, llm_response: Dict) -> int:
    """相同工具调用死循环检测(计数) — 小欧 2026-08-08
    count语义="第几continuous相同调用": 首个相同签名(count基准起始)。
    无上次签名(首调用)计count=1; 与上轮签名相同则count+1; 签名变化则重置count=1并清纠偏计数。
    返回int连续计数供调用方分支(count==2/3/4纠偏 / count>=5硬终止)。action语义下调用; 非action由调用方归零。"""
    _sig = _tool_call_signature(llm_response)
    if _sig and _sig == getattr(agent, "_last_tool_call_sig", None):
        agent._consecutive_same_tool_calls = getattr(agent, "_consecutive_same_tool_calls", 0) + 1
    else:
        agent._consecutive_same_tool_calls = 1      # 新签名起点=1, 标记同步重置 — 小欧 2026-08-08
        agent._warned_same_tool_loop = 0            # int计数(发纠偏次数)重置 — 小欧 2026-08-08
    agent._last_tool_call_sig = _sig
    return agent._consecutive_same_tool_calls


def _warn_same_tool_loop(agent, llm_response: Dict, count: int) -> None:
    """注入纠偏提醒(带_temp_same_tool_warn标记, 终态统一清理) — 小欧 2026-08-08
    连续相同调用达count==2/3/4(第2/3/4次)时各注入一条assistant role观察消息尝试唤醒LLM调整;
    最多注入3条(第2/3/4次, _warned_same_tool_loop为int计数), 标记供pop_temp_messages
    弹掉防止持久化污染。原布尔幂等→int计数(北京老陈 2026-08-08 指示"第2次就发纠偏")。"""
    if getattr(agent, "_warned_same_tool_loop", 0) >= _SAME_TOOL_WARN_MAX:
        return  # 最多警告3次(第2/3/4次) — 小欧 2026-08-08
    _tool = llm_response.get("tool_name", "") or ""
    _sig = _tool_call_signature(llm_response)
    obs_text = (
        f"[Warning] 你的上一次操作无效: 已连续 {count} 次调用相同的工具 {_tool} 且参数**完全相同**, "
        f"签名={_sig[:80]}..., 并未获得任何新信息。这是较严重的重复循环。"
        "请立即根据以下提示调整, 否则系统将强制终止本次任务: "
        "1) 改用其他工具或不同的参数; 2) 若确无新进展, 请直接给出结论结束任务, 不要再次重复调用同一工具。"
    )
    agent.message_builder.conversation_history.append({
        "role": "user",
        "content": obs_text,
        "_temp_same_tool_warn": True,
    })
    agent._warned_same_tool_loop = getattr(agent, "_warned_same_tool_loop", 0) + 1
    logger.info(f"[run_react_cycle] LLM连续{count}次调用相同工具 {_tool}, 注入纠偏警告(第{agent._warned_same_tool_loop}条)")
    log_and_print(f"{time.strftime('%H:%M:%S')} [Loop] step={agent.llm_call_count} same tool warn={_tool}")


async def _dispatch_handler(agent, llm_response):
    """按type分派handler，基于 event type 推断状态 — chendyg 2026-07-01 / 小欧 2026-07-13 去掉 recoverable
    
    type 路由表（知识备忘 — 小欧 2026-07-15）：
    ┌────────┬─────────────────┬───────────────────┐
    │ type   │ handler          │ 状态              │
    ├────────┼─────────────────┼───────────────────┤
    │ action │ handle_action    │ 继(不设终态)       │
    │ answer │ handle_answer    │ → FinalStep →     │
    │        │                  │   set_completed   │
    │ error  │ handle_answer    │ → ErrorStep →     │
    │        │ (error 分支)     │   set_failed      │
    │ 其他   │ handle_answer    │ → ErrorStep →     │
    │        │ (未知类型分支)   │   set_failed      │
    └────────┴─────────────────┴───────────────────┘
    type 产生于 llm_stream.py call_llm_stream() 末尾，
    规则：有 tool_calls → action；仅文本 → answer；异常 → error。
    type 不由 LLM 输出，由 agent 推断（详见 llm/core.py 头部）。
    
    状态推断规则:
    - 含 retrying → set_status(RETRYING)
    - 含 final → set_completed（按 outcome 子规则: failed→set_failed, cancelled→set_cancelled）
    - 含 error → 区分可恢复(拒绝/拦截,不失败,循环继续) 与 不可恢复(set_failed)
    - 其他 → 不设置状态,继续
    """
    parsed_type = llm_response.get("type", "answer")
    step = agent.llm_call_count
    thought = llm_response.get("thought", "")
    reasoning = llm_response.get("reasoning", "")
    if thought or reasoning:  # 2026-07-19 小欧 修复: reason-only action step也输出控制台
        reasoning_part = f"\n{time.strftime('%H:%M:%S')} === 推理 ===\n{reasoning}" if reasoning else ""
        log_and_print(f"{time.strftime('%H:%M:%S')} [Thought] step={step}, {thought}{reasoning_part}")  # 小欧 2026-07-02 控制台
    if parsed_type == "action":
        handler = handle_action(agent, llm_response)
    else:
        handler = handle_answer(agent, llm_response)

    _EV_FINAL, _EV_RETRY, _EV_ERROR = "final", "retrying", "error"
    seen_types = set()
    last_error_event = None
    final_event = None
    async for event in handler:
        seen_types.add(event.type)
        if event.type == _EV_ERROR:
            last_error_event = event
        elif event.type == _EV_FINAL:
            final_event = event
        yield event

    if _EV_RETRY in seen_types:
        set_status(agent, AgentStatus.RETRYING, "触发重试")
    elif _EV_FINAL in seen_types:
        # outcome 驱动终态声明: 读 FinalStep.outcome, 不依赖位置/类型 — 小欧 2026-07-18
        # 用循环内单独捕获的 final_event(真实 FinalStep), 不取末事件 last_event(#7: 末事件未必是final, 脆弱)
        oc = getattr(final_event, "outcome", "completed")
        if oc == "failed":
            set_failed(agent, getattr(final_event, "error_message", "") or final_event.get_content())
        elif oc == "cancelled":
            set_cancelled(agent)
        else:
            set_completed(agent)
    elif _EV_ERROR in seen_types:
        # 无 final → 可恢复错误(blocked/user_rejected/timeout, 循环继续)或原子异常(旧数据)
        error_event = last_error_event
        _kw = getattr(error_event, "_kwargs", {}) or {}
        err_type = _kw.get("error_type", "")
        error_msg = error_event.get_content() if hasattr(error_event, 'get_content') else ""
        if err_type in _RECOVERABLE_ERRORS:
            # 拒绝/拦截是可恢复的(拒绝≠失败, 符合人类认知): 不置终态, 反馈已进LLM历史,
            # 主循环 EXECUTING→THINKING 让LLM换工具。 — 小欧 2026-07-13
            # 计数按"同工具+同类型错误"累计(北京老陈 2026-07-13): 不同工具被拒不限次数
            # (往往是参数问题, 换工具/换参数即可); 仅同一工具同一类拒绝累计≥3次才说明LLM
            # 陷入死胡同, 必须停止 loop → FAILED。故用 per-(tool,type) 字典。
            # 工具名缺失时不累计(无法分键, 避免空名合并误累计), 保持可恢复回THINKING, 不误杀。
            _tool = llm_response.get("tool_name", "") or getattr(error_event, "tool_name", "")
            if _tool:
                _key = (str(_tool), str(err_type))
                _deny = getattr(agent, "_deny_counts", {}) or {}
                _deny[_key] = _deny.get(_key, 0) + 1
                agent._deny_counts = _deny
                if _deny[_key] >= 3:
                    # 2026-08-08 小欧 机制冲突修复: 场景F(双阈值 count==2/3/4 纠偏)已注入纠偏消息且LLM尚未调整
                    #   (_warned_same_tool_loop>0)时, 本处累计口径让位给纠偏, 给LLM调整机会,
                    #   避免"纠偏刚注入即被deny_counts判FAILED"致纠偏形同虚设(COM_03真实场景: 连续3次
                    #   delete被R6拦截, step=22纠偏与FAILED同轮触发, 响应仅6字"任务执行失败")。
                    #   连续同签名死循环由场景F count>=5(第5次)硬终止兜底; 非连续死胡同(签名变化重置标记)
                    #   仍由本处累计≥3次拦截, 语义不退化。 — 小欧 2026-08-08
                    if not getattr(agent, "_warned_same_tool_loop", 0):
                        set_failed(agent, f"工具 {_tool} 被反复{err_type}(≥3次), LLM陷入死胡同, 停止循环")
        else:
            set_failed(agent, error_msg)
    else:
        # 正常成功执行(无 error/retrying/final, 且确为 action 执行了工具): 重置该工具的拒绝计数
        # — 北京老陈 2026-07-13: 同工具成功后证明其未陷死胡同, 旧计数清零, 避免长会话里一次早已
        # 解决的历史拒绝在后续被误累计触发 FAILED(增强不退化, 逻辑无漏洞)。answer/final 步不重置。
        if llm_response.get("type") == "action":
            _tool = llm_response.get("tool_name", "")
            if _tool:
                _deny = getattr(agent, "_deny_counts", {}) or {}
                _deny.pop((str(_tool), "user_rejected"), None)
                _deny.pop((str(_tool), "blocked"), None)
                agent._deny_counts = _deny


def _finalize_cycle(agent):
    """循环后收尾: 状态回调+任务追踪 — 小健 2026-06-17 从finally提取"""
    agent.message_builder.pop_temp_messages()  # 小欧 2026-07-19 安全网: 清除残留标记推理再持久化
    agent._on_after_loop()
    agent._step_emitter.complete_task(agent.status == AgentStatus.COMPLETED)


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
    openai_tools = get_openai_tools(agent)

    logger.info(f"[LLM] 调用#{agent.llm_call_count}, messages={len(messages)}, tools={len(openai_tools)}, model={getattr(agent.llm_client, 'model', '?')}")

    prompt_logger = get_prompt_logger()
    prompt_logger.log_llm_call(
        round_number=agent.llm_call_count,
        messages=messages,
        model=getattr(agent.llm_client, 'model', 'unknown'),
        provider=getattr(agent.llm_client, 'provider', 'unknown'),
        call_type="tools",
        tools=openai_tools,
    )

    if not openai_tools:
        logger.error("[_process_single_step] 无可用工具")

    # ── Phase 2: LLM 流式调用 ──────────────────────────────────
    llm_response = None
    _call_start = time.time()                   # 11.2-C LLM 调用计时 — 小欧 2026-08-20
    async for chunk_or_response in call_llm_with_fallback(agent, messages, openai_tools):
        chunk_type, chunk_data = chunk_or_response

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
                    with db.get_conn_with_retry("chat") as _conn_r:
                        storage.update_task_accumulation(_conn_r, task_id=agent.task_id, llm_call_count_token=_llm_call_count_token)
                        if getattr(agent, "_start_meta", None) and agent._start_meta.get("session_id"):
                            storage.update_session_accumulation(_conn_r, session_id=agent._start_meta.get("session_id"), llm_call_count_token=_llm_call_count_token)
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
                model=getattr(agent.llm_client, "model", None),
                provider=getattr(agent.llm_client, "provider", None),
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
            async for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
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
            async for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
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


async def run_react_cycle(
    agent,
    task: str,
    context: Optional[Dict[str, Any]] = None,
    max_steps: Optional[int] = None,
    task_id: Optional[str] = None,
    start_time: Optional[float] = None,   # 11.2-B 同源起点（stream_orchestrator:198 → agent_runner → 此处）— 小欧 2026-08-20
):
    """ReAct循环:调用LLM→解析→分派handler→产出Step — chendyg 2026-07-01 状态集中管理重构v2"""
    if max_steps is None:
        max_steps = get_config().get_max_steps()

    chunk_buffer = initialize_run_state(agent, task, task_id, context)

    # 11.2/11.3 监控采集器（独立模块 app/monitoring/agent_telemetry.py）— 小欧 2026-08-20
    from app.monitoring.agent_telemetry import TaskTelemetry
    _start_meta = getattr(agent, "_start_meta", None) or {}
    _agent_tele = TaskTelemetry(
        task_id=task_id or getattr(agent, "task_id", ""),
        session_id=_start_meta.get("session_id", "") or "",
        agent=agent,
    )
    _agent_tele.on_start(start_time)
    agent.telemetry = _agent_tele

    # 11.1 token 四层同构：会话级/链级累计基线(任务开始前历史累计)读 DB 一次并缓存到 agent,
    #   任务内恒定; 同步初始化 session/chain 累计=基线(无 LLM 调用时也正确反映历史累计, 杜绝日志/前端误显 0) — 小欧 2026-08-20
    if getattr(agent, "_start_meta", None):
        try:
            _chain_root = agent._start_meta.get("context_root_task_id") or agent.task_id
            with db.get_conn_with_retry("chat") as _conn0:
                agent._session_acc_base = storage.query_session_accumulation(_conn0, session_id=agent._start_meta.get("session_id"))
                agent._chain_acc_base = storage.query_chain_accumulation(_conn0, context_root_task_id=_chain_root, current_task_id=agent.task_id)
            agent.session_accumulated_tokens = {k: agent._session_acc_base[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
            agent.chain_accumulated_tokens = {k: agent._chain_acc_base[k] for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
        except Exception as _e:
            logger.warning(f"[run_react_cycle] 初始化 token 累计基线失败(降级为零基线): {_e}")
            agent._session_acc_base = None
            agent._chain_acc_base = None

    # S4/S5(10.1.7④⑤/10.1.8): start 装配进 agent.steps(占 step 0) — 任务输入装配完整过程收拢为一个模块。
    #   P4 注入模式: 运行元数据由 orchestrator 注入 agent._start_meta(chat 层纯数据捕获),
    #   start_step.assemble_start_step 从 _start_meta/_sys_prompt/context 读齐装配, 不 import chat 层。
    #   落库: start 作为首个事件 yield → agent_runner 事件流分配 ai_message_id 并 append_step, 不再 execution_steps 双写。 — 小欧/小健 2026-08-17
    _start_step = _assemble_start_step(agent, context)  # 同步装配(内部零 await, KISS — 小健 2026-08-17)
    if _start_step is not None:
        yield agent._step_emitter.emit(_start_step)

    # S5(10.1.7⑤/10.1.8): C4 超窗锚定摘要回填 —— start 装配后、while 前一次性清洗注入的历史。
    #   仅当 start 超窗判定(start_step._maybe_compact_injected_history)置 _needs_compact(=True) 才触发;
    #   摘要以 assistant 消息回填, 保 system + 摘要 + 最新 task; 原库 conversation_history 被替换为新列表。
    #   关联逻辑(增强不退化): 未超窗时 _needs_compact=False, 本段跳过, 主链路零改动。 — 小健 2026-08-17
    if getattr(agent, "_needs_compact", False):
        await _compact_injected_history(agent)

    if max_steps <= 0:
        logger.warning(f"[run_react_cycle] max_steps={max_steps}, 直接终止")
        async for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
            step=len(agent.steps),  # S4: start 已 emit(step=0), 终态接续步号, 避免同消息下双 step=0 — 小欧 2026-08-16
            response=f"最大步骤数({max_steps})，无可执行步骤，任务取消",  # Bug2+5: max_steps<=0不是"已耗尽"; outcome=cancelled→消息一致 — 小欧 2026-07-23
            outcome="cancelled",  # 小欧 2026-07-18: MetaStep→FinalStep, max_steps=0终态统一
        )):
            yield _s
        set_cancelled(agent)
        _finalize_cycle(agent)
        return

    try:
        while agent.llm_call_count < max_steps:
            # ── 用户取消检测(循环粒度, 方案 B) ──
            # 小沈 2026-07-13: 本处采用"循环粒度取消"(方案 B), 不采用"流式中途打断"(方案 A)。
            # 选 B 不选 A 的原因(利弊权衡, 见 doc-7月优化/流式LLM中途取消方案取舍分析-小沈-2026-07-13.md):
    #   1) 正确性已满足: B 在每轮 LLM 调用前检测 check_cancelled, 取消即干净终止为
    #      FinalStep(outcome="cancelled")(2026-07-18 重构: 原 MetaStep(cancelled)→FinalStep),
    #      DB status 列落 cancelled, 终态语义 100% 正确, 绝不再误判 failed。
            #   2) 零回归风险: A 需给 LLMClient 加 set_stop_check 并在 httpx 流式热路径逐 chunk 轮询,
            #      涉及 client_sdk/llm_stream/call_llm_with_fallback 重试链路, 改动面大、易引入连接泄漏/
            #      异常语义混淆(CancelledError 是 BaseException 会绕过 except Exception), 必须配真实 LLM E2E。
            #   3) 体验代价可接受: B 的缺点是"长生成任务需等本轮 LLM 结束才停"; 多数 LLM 调用仅秒级,
            #      属可接受体验, 非语义缺陷。
            #   4) A 留作后续独立增强项, 待补单测+E2E 后单独排期, 不阻塞本次上线。
            # 注: 原 react_cycle 场景B 依赖 llm_client._cancelled, 该属性全局从未赋值(死代码),
            # 曾导致用户取消误走 empty_response→ErrorStep(failed)。 — 小沈 2026-07-13
            if task_id:
                from app.services.task.task_runtime import check_cancelled, wait_for_resume
                if await check_cancelled(task_id):
                    logger.info(f"[run_react_cycle] 检测到任务取消(task_id={task_id}), 终止为 cancelled")
                    async for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
                        # 2026-08-17 - 小健 - 三堂会审-S4修复: 首轮前取消(llm_call_count 尚未+1=0)时,
                        #   step=0 与 start(step=0)双 step0(与 S4"start占0,业务从1起"矛盾); or 1 接续唯一步号
                        step=agent.llm_call_count or 1,
                        response="任务已被用户取消", outcome="cancelled",  # 小欧 2026-07-18: MetaStep→FinalStep, 用户取消终态统一
                    )):
                        yield _s
                    set_cancelled(agent)
                    break
                # 用户暂停检测(循环粒度, 阻塞等待恢复) — 小欧 2026-07-13
                # 符合人类认知: 你喊暂停, 助手原地等(真BLOCK), 不空转、不误判为取消/完成。
                # 阻塞点在 wait_for_resume 内 pause_event.wait(); 恢复后回 THINKING 继续。
                # 注意: 此处只查暂停不查取消(取消已在上方处理); 暂停不再经 LLMClient._stop_check
                # 中断流式(已在 agent_runner 改为仅查取消), 故暂停在"下一轮循环顶"干净生效。
                # 2026-08-09 - 小欧 - P4 拆分: 原 task_pause_check 在此产出 SSE 字符串被 agent_runner
                #   以"跳过非Step事件"丢弃(死路), 改纯阻塞 wait_for_resume(不产 SSE);
                #   暂停/恢复 SSE 统一由前端消费路径 openai._stream_with_control 的
                #   task_pause_check_and_yield 下发, 职责单一无死路。
                await wait_for_resume(task_id)
            try:
                async for event in _process_single_step(agent, chunk_buffer):
                    yield event
            except Exception as _step_err:
                if _is_recoverable_error(_step_err):
                    agent._retry_count = getattr(agent, '_retry_count', 0) + 1
                    if agent._retry_count > 3:
                        logger.error(f"[run_react_cycle] 可恢复错误重试超限: {_step_err}")
                        set_failed(agent, f"可恢复错误重试已达上限(3次): {_step_err}")  # task007: 明确上限值 — 小欧 2026-07-23
                        break
                    logger.warning(f"[run_react_cycle] 可恢复异常, 第{agent._retry_count}次重试: {_step_err}")
                    yield agent._step_emitter.emit(MetaStep(
                        type="retrying",
                        step=agent.llm_call_count,
                        content=f"LLM请求异常，准备重试: {_step_err}",
                        severity="info",
                    ))
                    # 2026-08-13 - 小欧 - 三堂会审修复#36: 此处不再 set RETRYING(计数已在上方+1),
                    #   直接 continue 回循环顶重试; 否则主循环 L614 RETRYING 处理再+1 → 一次异常计2次,
                    #   上限3实际第2次异常即FAILED。来源B(_dispatch_handler L273 retrying)仍走
                    #   set RETRYING + L614 计数, 两来源各自单计互不干扰。
                    continue
                raise
            if agent.status in (AgentStatus.COMPLETED, AgentStatus.FAILED, AgentStatus.CANCELLED):
                break

            # ======== RETRYING 处理（react循环重试）========
            # 说明：本态是"可恢复错误后的重试中间态"。llm_call_count 已+1，
            # react循环回 THINKING 重新调用LLM（即第N次重试），并非原地重跑当前step。
            # 与 tool_retry_engine 的"工具级重试"（同工具重执行）及 base_service 的
            # HTTP请求重试是两套独立机制，勿混淆。 — 小欧 2026-07-12 修正矛盾注释
            if agent.status == AgentStatus.RETRYING:
                agent._retry_count = getattr(agent, '_retry_count', 0) + 1
                if agent._retry_count > 3:
                    set_failed(agent, "可恢复错误重试已达上限(3次)")  # task007: 明确上限值 — 小欧 2026-07-23
                    break
                set_status(agent, AgentStatus.THINKING, f"第{agent._retry_count}次重试")
            elif agent.status == AgentStatus.EXECUTING:
                set_status(agent, AgentStatus.THINKING)

            if chunk_buffer.should_force_stop():
                logger.warning(f"[run_react_cycle] chunk累积超时({agent.llm_call_count}步),强制停止")
                set_failed(agent, f"chunk累积超时({agent.llm_call_count}步)")
                yield agent._step_emitter.emit(MetaStep(step=agent.llm_call_count, type="error", content="响应累积超时，任务强制终止", error_type="chunk_buffer_timeout", severity="warn"))  # P3+P4: error全仅SSE+severity — 小欧 2026-08-18
                break

        if agent.status not in (
            AgentStatus.COMPLETED,
            AgentStatus.FAILED,
            AgentStatus.CANCELLED,
        ):
            logger.warning(f"[run_react_cycle] 循环结束无终态(status={agent.status}), 终止")
            async for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
                step=agent.llm_call_count,
                response=f"任务循环结束未设终态(status={agent.status})",  # Bug3: 循环自然退出不是"异常",用事实描述 — 小欧 2026-07-23
                outcome="cancelled",  # 小欧 2026-07-18: MetaStep→FinalStep, 循环结束无终态兜底统一
            )):
                yield _s
            set_cancelled(agent)

    except Exception as e:
        logger.error(f"[run_react_cycle] 不可恢复异常: {e}", exc_info=True)
        error_step = handle_react_error(agent, e, agent.llm_call_count)
        yield agent._step_emitter.emit(error_step)
        set_failed(agent, f"循环异常: {e}"[:200])

    finally:
        _finalize_cycle(agent)
        _tele = getattr(agent, "telemetry", None)   # 11.2-C 监控落库（独立模块，非阻塞降级）— 小欧 2026-08-20
        if _tele is not None:
            _tele.finalize_and_persist()
        # R1 (v1.43): task 级清零点 — clear_temp_auth 在 finally 收口, 使授权后所有提前 break/异常/循环自然退出
        #   均走 finally; 注意 max_steps<=0 提前 return 在 try 之前(Bug4修正: 该分支 I2 尚未运行,
        #   无任何授权产生, 故不经过 finally 也无泄漏; 注释已修正不再声称其走 finally)
        from app.tools.security.temp_auth import clear_temp_auth
        clear_temp_auth()
        # 2026-08-13 小欧 三堂会审修复#29: task结束对称清task_id(set在action_handler.py:882),
        #   防长连接/复用context时跨请求泄漏(当前独立asyncio.Task场景无泄漏, 属潜伏修复)
        from app.tools.context import reset_current_task_id
        reset_current_task_id()

