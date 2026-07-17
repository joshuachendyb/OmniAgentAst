# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-16 - 小欧 - 清理L1护栏: 删除超长外置/退化检测/退化纠正/降级兜底/工具结果提取, 仅保留重复检测(dedup)
# 2026-07-17 - 小欧 - 新增reasoning-only空转防御: 复用_dedup_repeat剔除循环重复+连续REASONING_ONLY_MAX_ROUNDS(默认3)轮纯推理无工具无答案即终止; 字段_consecutive_reasoning_only在action/正常answer/真空处归零(防御增强不退化正常流程)
"""
answer_handler — 统一处理所有"说"类型(action以外的答案/错误/未知)

从react_cycle.py拷出_handle_answer函数+_handle_llm_error+_handle_unknown
合并为统一handler，减少react_cycle分派分支

Author: 小沈 - 2026-06-09
v2.0: 新增错误消息检测，LLM返回错误时设FAILED而非COMPLETED — 小欧 2026-06-28
v3.0: reasoning-only分支+tool call文本格式化 — 小欧 2026-07-12
v4.0: 合并error/unknown处理，react_cycle只分两路 — 小欧 2026-07-12
v4.1: reasoning-only分支改add_assistant_message(reasoning)合法注入(工具调用意图已由llm_stream提前提取为action,本分支仅处理纯推理文本) — 小欧 2026-07-16
"""
import time
from typing import Dict

from app.services.agent.steps import ThoughtStep, FinalStep, ErrorStep, MetaStep
from app.utils.text_utils import format_tool_call_markup
from app.logger import logger


# ── 重复检测 ──
REPEAT_CHECK_MIN_LEN = 500     # 重复检测启动门槛: 不足500字不检(短内容无危害)
DUP_CHUNK = 200                # 检测窗口: 匹配 LLM 卡顿循环周期(老陈经验值200), 禁止降低防误伤
DUP_RATIO = 0.5                # 重复块占总长比例阈值, 占比过半才截断, 宁漏判不误伤, 禁止降低

REASONING_ONLY_MAX_ROUNDS = 3   # 2026-07-17 - 小欧 - 连续reasoning-only(纯推理无工具无答案)终止门限: 正常LLM每轮给answer或tool, 不会连续3轮纯推理; 3=宽松止损防误伤(2更激进), 仅防御空转


def _dedup_repeat(content: str) -> str:
    """【卡顿循环重复去重】仅针对 LLM 原样重复, 非通用去重工具
    【设计意图】类型2无意义重复(模型卡顿循环)截断不误伤(重复段无价值); 去重后若仍超长交给超长外置处理
    【防误伤边界】① 长度<2*DUP_CHUNK 不检测(零影响); ② 仅识别原样完全重复, 不识别语义相似;
        ③ 重复占比>DUP_RATIO(=0.5)才截断, 宁漏判不误伤; ④ DUP_CHUNK/DUP_RATIO 禁止降低(防结构化报告表头重复<15%误伤)
    【调用前提】content 为 final 文本; 返回截断后文本(保留首次有效内容)"""
    if len(content) <= DUP_CHUNK * 2:
        return content
    step = DUP_CHUNK
    chunks = [content[i:i + step] for i in range(0, len(content) - step + 1, step)]
    seen = {}
    second_pos = None
    for idx, ch in enumerate(chunks):
        if ch in seen:
            second_pos = idx * step  # 第二次出现起点(字符位置)
            break
        seen[ch] = idx
    if second_pos is None:
        return content
    repeat_len = len(content) - second_pos
    if repeat_len / len(content) < DUP_RATIO:
        return content  # 重复占比低, 不触发(防误伤)
    logger.warning(f"[L1-C2b] 检测到无意义重复(final {len(content)}字, 重复占比 {repeat_len / len(content):.0%}), 已去重截断")
    return content[:second_pos] + "\n\n... [已截断重复内容]"


async def handle_answer(agent, parsed: Dict):
    """统一处理所有非action的LLM返回类型（answer/error/unknown）
    
    由 _dispatch_handler(react_cycle.py) 分派，接收 llm_stream.py 构建的 type：
    - type="answer" → 正常终态流程（最终答复）
    - type="error"  → LLM 流式异常 → ErrorStep → set_failed
    - 其他未知 type → 按 error 处理（兜底）
    
    type 产生于 llm_stream.py（见该模块头部），不由 LLM 输出，是 agent 推断。"""
    step = agent.llm_call_count
    parsed_type = parsed.get("type", "answer")

    # ── type="error" │ yiled ErrorStep ──
    if parsed_type == "error":
        content = parsed.get("content", "") or "LLM流式错误"
        agent.message_builder.add_assistant_message(content)
        print(f"{time.strftime('%H:%M:%S')} [Error] step={step}, error={content}")
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="llm_error", error_message=content,
        ))
        return

    # ── 未知类型 │ yiled ErrorStep ──
    if parsed_type != "answer":
        logger.warning(f"[handle_answer] 未知返回类型: {parsed_type}, 设置为FAILED")
        content = parsed.get("content", "") or parsed.get("thought", "") or ""
        print(f"{time.strftime('%H:%M:%S')} [Error] step={step}, type={parsed_type}, content={content}")
        if content:
            agent.message_builder.add_assistant_message(f"[无效响应:{parsed_type}] {content}")
        yield agent._step_emitter.emit(ErrorStep(
            step=step, error_type="unknown_response",
            error_message=f"LLM返回未知响应类型: {parsed_type}",
        ))
        return

    # ── type="answer" ──
    content = format_tool_call_markup(parsed.get("content", ""))
    reasoning = format_tool_call_markup(parsed.get("reasoning", ""))

    # 真·空：content和reasoning都空 → 系统重试通知(MetaStep.retrying)，由 RETRYING 态驱动编排层重试 — 小欧 2026-07-13 删 recoverable
    if not content and not reasoning:
        logger.warning(f"[handle_answer] LLM返回空内容(step={step}), 触发系统重试")
        agent._consecutive_reasoning_only = 0   # 2026-07-17 - 小欧 - 真空非reasoning空转, 归零防残留误累计
        agent.message_builder.add_assistant_message("")
        yield agent._step_emitter.emit(MetaStep(
            type="retrying",
            step=step,
            content="LLM返回空内容，触发重试",
            wait_time=1,
        ))
        return

    # reasoning-only：LLM只返回推理没给最终答案 → 注入助理消息继续循环
    # 注：若推理内嵌 <tool_call> XML（LLM降级旧格式），已在 llm_stream.py 的 type 判定前
    #     提取为合法 action 执行，不会走到本分支。
    #     本分支仅处理"纯推理、无工具调用意图"的情形，以合法 assistant(content) 保留上下文。— 小欧 2026-07-16
    # reasoning-only: LLM只返回推理没给最终答案也没调工具 → 注入助理消息继续循环
    # 2026-07-17 - 小欧 - 防御增强(不退化正常流程):
    #   ① reasoning先_dedup_repeat剔除原样循环重复(复用L1-C2b同函数), 压缩history防触发trim破坏;
    #   ② 连续reasoning-only达REASONING_ONLY_MAX_ROUNDS即终止, 切断LLM退化空转(如task-2ffbc517);
    #   正常任务LLM每轮给answer或tool, 永不进本分支, 计数恒0, 完全不受影响。
    if not content and reasoning:
        _deduped = _dedup_repeat(reasoning)
        agent._consecutive_reasoning_only += 1
        if agent._consecutive_reasoning_only >= REASONING_ONLY_MAX_ROUNDS:
            logger.warning(f"[handle_answer] 连续{agent._consecutive_reasoning_only}轮reasoning-only无进展(step={step}), 终止任务")
            yield agent._step_emitter.emit(FinalStep(
                step=step,
                response="模型反复思考未产出有效结果，任务已终止（疑似陷入无效循环）",
                thought=_deduped,
            ))
            return
        logger.info(f"[handle_answer] LLM返回推理内容(step={step}), 注入助理消息继续循环(连续reasoning-only={agent._consecutive_reasoning_only})")
        agent.message_builder.add_assistant_message(_deduped)
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content=_deduped, reasoning="",
        ))
        return

    agent._consecutive_reasoning_only = 0   # 2026-07-17 - 小欧 - 正常final answer, 归零空转计数(防御残留)
    thought = parsed.get("thought", content)

    if thought:
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content=thought, reasoning=reasoning,
        ))

    # ══ 重复检测(≥500字才检) — DB 入库前唯一保留的护栏 ══
    if len(content) >= REPEAT_CHECK_MIN_LEN:
        deduped = _dedup_repeat(content)
        if deduped != content:
            content = deduped

    print(f"{time.strftime('%H:%M:%S')} [Final] step={step}, response={content}")  # 小欧 2026-07-12 恢复answer分支终态日志(94eac9723合并时误删)
    yield agent._step_emitter.emit(FinalStep(
        step=step, response=content, thought=thought,
    ))
    agent.message_builder.add_assistant_message(content)
