
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-09-05 小健 8.4拆分(react_cycle.py拆四): 提取 常量(原行154-176)+守卫函数群(原行179-285),
#   逐字复制只改import — 死循环/截断/可恢复错误 判定与阈值, 供 loop/dispatch/step 共用

"""react_inference — 状态推断基元(常量 + 守卫判定函数群)

相同工具死循环双阈值/截断重试判定/可恢复错误/error_step 统一入口, 无编排逻辑。

8.4拆分自 react_cycle.py(老名消亡) — 小健 2026-09-05
"""

import asyncio
import json
import time
from typing import Dict
from app.logger import logger, log_and_print
from app.llm.error_classifier import SystemErrorClassifier
from app.services.agent.steps import MetaStep

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
# 2026-08-24 - 小欧 - 后端卡死修复: 每轮 token 累计落库(update_task_accumulation/update_session_accumulation)与任务启动 token 基线读取(query_session/query_chain_accumulation)
#   经 db.atxn 进子线程 offload 出事件循环, loop 不再被同步 sqlite3 I/O + time.sleep 锁重试独占, 根治 /health 超时/console 冻结; storage.* 与连接管理零改动复用
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
