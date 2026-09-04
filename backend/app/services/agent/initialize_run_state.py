# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - 统一TaskID: _tracked_task_id → agent.task_id
# 2026-07-18 - 小欧 - 【病根】历史重载边界(_inject_conversation_history)把 DB(execution_steps)持久化的 assistant.tool_calls 原样注入 message_builder, 零校验; 若某条 tool_calls 含非dict元素(截断/畸形LLM响应落库), 下轮回传即触发 provider 400("Can only get item pairs from a mapping")并 FC 降级→AgentStatus.FAILED。
#            【解决思路】注入边界对 tool_calls 逐元素 isinstance(t, dict) 校验: list仅留dict元素 / 单dict归一为[dict] / 其余置空回退content分支; 合法 list-of-dict 输入输出100%不变(增强不退化), 调用方零改动。
# 2026-08-08 - 小欧 - 新增相同工具死循环检测状态初始化(_consecutive_same_tool_calls/_last_tool_call_sig)
# 2026-08-08 - 小欧 - v1.6 双阈值升级: 新增纠偏幂等标记初始化(_warned_same_tool_loop=False)
# 2026-08-08 - 小欧 - v1.7 阈值调整(北京老陈 2026-08-08 指示"第2次就发纠偏; 2/3/4次发, >=5结束"): _warned_same_tool_loop 由布尔幂等标记改 int 纠偏条数计数(第2/3/4次共3条), 初始化 False→0
# 2026-08-10 - 小欧 - I1 (第二次代码更新): 新增任务文本目录解析(_parse_task_auth_paths), 仅解析不授权不产 SSE, 挂 agent._task_auth_paths; 同步新增 _TASK_PATH_RE 正则
# 2026-08-10 - 小欧 - 撤销 I1 (北京老陈 2026-08-10): 「任务中目录解析功能点去掉」— 删除 _parse_task_auth_paths/_TASK_PATH_RE 及调用,
#   目录权限全部走 LLM 工具参数路径进临时名单(3.2.12); 同步撤销 react_cycle 的 I2/I3/I4 任务级批量确认段; 保留 R1 clear_temp_auth
# 2026-08-11 - 小欧 - 三堂会审复核落地(P2-3): I1撤销后 _parse_task_auth_paths 已删, List 无消费处, 移除死 import(代码卫生)
# 2026-08-16 - 小欧 - S4(10.1.2②): sys_prompt 取到后存 agent._sys_prompt, 供 react_cycle 前置装配 start 读取(start 的 system_prompt 字段, 10.1.1③ 装配时机=initialize_run_state 后 loop 前)
# 2026-08-17 - 小健 - S5(10.1.8, 943a77917): 新增 _maybe_compact_injected_history(agent), 注入历史后估 token
#   超窗(MAX_CONTEXT_TOKENS×MAX_CONTEXT_RATIO)置 agent._needs_compact=True; 仅置标记不触发 LLM(实际压缩
#   归 react_cycle _compact_injected_history); COMPACTION_ENABLED=False 期间行为同现状零退化; 估算复用
#   MessageBuilder._estimate_tokens(DRY)
# 2026-08-17 - 小健 - start 业务过程收敛(老陈驱动, 痛斥输入装配割裂): 从 initialize_run_state() 移除
#   历史注入 _inject_conversation_history 与超窗标记 _maybe_compact_injected_history 两处调用, 收拢到
#   react_cycle 的 start 装配段(emit 前一气呵成); 本文件退化为纯状态重置 + init_history(system+task 装载);
#   两函数仍保留本模块供 react_cycle 延迟导入复用(单一归属不变)
# 2026-08-17 - 小健 - start 业务物理独立模块(老陈驱动, 痛斥"一个事情到处乱放"): 新增 start_step.py 承载 start
#   全部业务(inject/超窗判定/C4回填/装配入口), 自本文件移除 _inject_conversation_history 与
#   _maybe_compact_injected_history 两函数定义(迁入 start_step.py)及 COMPACTION_ENABLED import;
#   本文件退化为纯状态重置 + init_history, 不再持有任何 start 装配私有逻辑(单一归属, 依赖不反向)
# 2026-08-18 - 小欧 - §10.4.4 P3(error全仅SSE): 重置区加 agent._last_error=None(防跨任务残留)
# 2026-08-18 - 小欧 - §10.4.4 P6(usage剔step_json): 重置区加 agent._usage_events=[]
"""
_initialize_run_state — 每次运行前初始化Agent状态

职责: 重置steps/message_builder/status/llm_call_count, 注入system prompt和task

Author: 小沈 - 2026-05-31
"""

from typing import Any, Dict, Optional

from app.constants import MAX_CONSECUTIVE_CHUNKS
from app.services.agent.status_table import AgentStatus, set_status
from app.services.agent.chunk_buffer import ChunkBuffer
from app.logger import logger
from app.logger.prompt_logger import get_prompt_logger
from app.db import db


def initialize_run_state(
    agent, task: str, task_id: Optional[str], context: Optional[Dict[str, Any]] = None
) -> ChunkBuffer:
    """初始化每轮运行状态:重置steps/注入system prompt和task — 小沈 2026-06-17 参数名self→agent"""
    agent.steps = []
    agent.message_builder.reset_per_run()
    set_status(agent, AgentStatus.THINKING)
    agent.llm_call_count = 0
    agent._consecutive_truncations = 0
    agent._retry_count = 0
    # 2026-08-08 - 小欧 - 相同工具调用死循环检测状态初始化(防跨任务残留): 连续相同工具签名计数+上次签名+纠偏幂等标记
    agent._consecutive_same_tool_calls = 0
    agent._last_tool_call_sig = None
    agent._warned_same_tool_loop = 0   # v1.7双阈值: 纠偏注入条数计数(int, 第2/3/4次共3条), 落码新增字段 — 小欧 2026-08-08
    agent._last_error = None  # 2026-08-18 - 小欧 - P3: 每轮重置, step_emitter.emit统一出口记录, 守卫读此填充final
    agent._usage_events = []  # 2026-08-18 - 小欧 - P6: 每轮重置, react_cycle usage emit时append, agent_runner终态insert_token读
    # 【#42修复】更新tracker任务描述为实际task内容 — chendyg 2026-06-26
    if task and agent._task_tracker and agent.task_id:
        try:
            with db.get_conn("task_tracker") as conn:
                conn.execute(
                    "UPDATE tasks SET task_description = ? WHERE task_id = ?",
                    (task[:200], agent.task_id),
                )
        except Exception:
            logger.error(f"[initialize_run_state] 更新任务描述失败: task_id={agent.task_id}")
    if task_id:
        agent.task_id = task_id

    agent._on_session_init(task, context)
    sys_prompt = agent._get_system_prompt()
    agent._sys_prompt = sys_prompt  # S4(10.1.2②): start 装配用(system_prompt 来源=本处 _get_system_prompt, 供 react_cycle 前置装配 start 读取) — 小欧 2026-08-16

    prompt_logger = get_prompt_logger()
    prompt_logger.log_system_prompt(
        step_name="运行时系统Prompt注入",
        prompt_content=sys_prompt,
        source=f"{agent.__class__.__name__}._get_system_prompt()",
    )
    prompt_logger.log_task_prompt(
        task_content=task,
        context=context if context else None,
        source=f"{agent.__class__.__name__}.initialize_run_state",
    )

    agent._on_before_loop(sys_prompt, task, context)
    agent.message_builder.init_history(sys_prompt, task)

    return ChunkBuffer(MAX_CONSECUTIVE_CHUNKS)
