# -*- coding: utf-8 -*-
# 编辑历史:
# 记录 2026-07-16 小欧 清理L1护栏: 删除超长外置/退化检测/退化纠正/降级兜底/工具结果提取, 仅保留重复检测(dedup)
# 记录 2026-07-17 小欧 新增reasoning-only空转防御: 复用_dedup_repeat剔除循环重复+连续REASONING_ONLY_MAX_ROUNDS(默认3)轮纯推理无工具无答案即终止; 字段_consecutive_reasoning_only在action/正常answer/真空处归零(防御增强不退化正常流程)
# 记录 2026-07-17 小欧 计数器修正: 判断改>REASONING_ONLY_MAX_ROUNDS(默认3,即第4轮终止); 补全error/未知类型分支归零, 使不变量"仅reasoning-only累加、其余出口归零"严格成立(复核3遍)
# 记录 2026-07-17 小欧 重复检测升级: 用句子频率法(v2)替换固定200字chunk, 100%命中率98.4%压缩率; 删除DUP_CHUNK, 新增SENTENCE_MIN_REPEAT=3, REPEAT_CHECK_MIN_LEN=500改250; 排除markdown表行防假阳性(复核3遍+边缘测试14场景)
# 记录 2026-07-18 小欧 修复FAILED终态返回空响应(病根+思路+逻辑): 
#                【病根】response_text仅由final事件填充(e2e_helpers.py:365/agent_runner.py:163), 
#                     失败终态设计上不补FinalStep→LLM硬失败时正文为空(unit-09暴露);
#          而2026-07-13设计"失败终态仅ErrorStep不补FinalStep", 致LLM硬失败(如HTTP400内容审核,
#            今日unit-09暴露)时响应正文为空、无诊断信息; 
#           【思路】在error/unknown分支补发FinalStep填充响应正文; 
#           【逻辑】①FinalStep先于ErrorStep产出, 使derive_status_from_steps(storage.py:49迁移兜底)最后终态=error→仍判failed不翻转 ②_dispatch_handler中error优先于final→终态仍FAILED不退化 ③复用reasoning-only终止分支emit FinalStep既有模式, 不造新范式
# 记录 2026-07-18 小欧 FinalStep终态规整重构(多态自包含):
# 【病根】response_text仅由final事件填充, 失败终态无FinalStep→body空;
# 【重构】FinalStep多态: outcome/error_type/error_message 三字段;
#         失败→单条 FinalStep(outcome="failed", error_type, error_message);
#         取消→FinalStep(outcome="cancelled"); ErrorStep仅可恢复;
#         agent_runner守卫兜底无final路径; derive读final.outcome。
# 【增强】response_text全路径非空; 失败细节自包含; 内部set_failed全覆盖。
# 2026-07-18 - 小欧 - 修复#6拼写错 yiled→yield (2处)
# 2026-07-19 - 小欧 - 推理空转不持久化(Hermes字面): reasoning-only拆好/坏两分支; 好的带_temp_reasoning标记注入conversation_history(供模型续写, wire副本由prepare_messages_for_llm strip标记), 终端统一由react_cycle._finalize_cycle(finally出口)直调agent.message_builder.pop_temp_messages()弹掉标记再持久化, 落点单一收口(KISS-DIRECT)无防御守卫; 坏的(有去重)跳过不注入不持久不发射ThoughtStep。注: 生产直调message_builder为本代码既有假设, 单测MockMb缺该方法属测试缺陷
# 2026-08-18 小欧 - §10.3.3(1): 所有分支(error/unknown/reasoning-only终止/正常answer)前发射ThoughtStartStep; FinalStep删thought=加reasoning=
# 2026-08-18 - 小欧 - §10.4.4 P4(severity): retrying MetaStep 加 severity="info"
# 2026-08-28 小欧 - yield日志审计: 3处 print()→logger(error/error/info, DRY违规修复); 三堂会审无逻辑修正
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
import re
import time
from collections import Counter
from typing import Dict

from app.services.agent.steps import ThoughtStep, ThoughtStartStep, FinalStep, MetaStep  # 2026-08-18 小欧 ThoughtStartStep新增
from app.utils.text_utils import format_tool_call_markup
from app.logger import logger


# ── 重复检测(版本2026-07-17: 句子频率法替代固定chunk) ──
REPEAT_CHECK_MIN_LEN = 250     # 重复检测启动门槛: 不足250字不检(短内容无危害)
SENTENCE_MIN_REPEAT = 3        # 2026-07-17 - 小欧 - 句子频率法: 同一句出现≥3次标记为重复(覆盖A-B交替/非200倍数块)
DUP_RATIO = 0.5                # 重复占总长比例阈值, 占比过半才截断, 宁漏判不误伤, 禁止降低

REASONING_ONLY_MAX_ROUNDS = 3   # 2026-07-17 - 小欧 - 连续reasoning-only(纯推理无工具无答案)终止门限: 用>判断, 容忍连续3轮继续, 第4轮(>3)才终止; 正常LLM每轮给answer或tool, 永不进此分支; 仅防御空转


def _dedup_repeat(content: str) -> str:
    """【卡顿循环重复去重】基于句子频率, 非通用去重工具
    【设计意图】LLM陷入卡顿循环时(如A-B交替/简单块重复), 剔除原样重复句子, 保留首次有效内容
    【防误伤边界】① 长度<REPEAT_CHECK_MIN_LEN 不检测; ② 句子数<10不检测;
        ③ 排除markdown表行(行首|); ④ 重复占比>DUP_RATIO才截断; ⑤ 仅精确句子匹配, 非语义相似
    【调用前提】content 为 final/推理文本; 返回截断后文本"""
    if len(content) < REPEAT_CHECK_MIN_LEN:
        return content
    parts = re.split(r'(?<=[。\n])', content)
    parts = [p for p in parts if len(p.strip()) > 0]
    if len(parts) < 10:
        return content
    counter = Counter(parts)
    repeated = {s for s, cnt in counter.items()
                if cnt >= SENTENCE_MIN_REPEAT
                and not s.strip().startswith('|')}
    if not repeated:
        return content
    result = []
    seen = set()
    for p in parts:
        if p in repeated and p in seen:
            continue
        if p in repeated:
            seen.add(p)
        result.append(p)
    deduped = "".join(result)
    if len(deduped) >= len(content):
        return content
    ratio = 1 - len(deduped) / len(content)
    if ratio < DUP_RATIO:
        return content
    logger.warning(f"[L1-C2b] 检测到无意义重复(final {len(content)}字, 重复占比 {ratio:.0%}), 已去重截断")
    return deduped


async def handle_answer(agent, parsed: Dict):
    """统一处理所有非action的LLM返回类型（answer/error/unknown）
    
    由 _dispatch_handler(react_cycle.py) 分派，接收 llm_stream.py 构建的 type：
    - type="answer" → 正常终态流程（最终答复）
    - type="error"  → LLM 流式异常 → FinalStep(outcome="failed") → set_failed
    - 其他未知 type → 按 error 处理（兜底）
    
    type 产生于 llm_stream.py（见该模块头部），不由 LLM 输出，是 agent 推断。"""
    step = agent.llm_call_count
    parsed_type = parsed.get("type", "answer")

    # ── type="error" │ yield FinalStep(outcome=failed) ──
    if parsed_type == "error":
        content = parsed.get("content", "") or "LLM流式错误"
        agent._consecutive_reasoning_only = 0   # 2026-07-17 - 小欧 - error非reasoning-only, 归零防残留(不变量: 仅reasoning-only分支累加)
        agent.message_builder.add_assistant_message(content)
        # 2026-08-28 小欧 yield日志审计: print→logger统一(DRY违规修复)
        logger.error(f"[answer] step={step} error={content}")
        yield agent._step_emitter.emit(ThoughtStartStep(step=step))   # 2026-08-18 小欧 thought-start
        for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
            step=step, response="任务执行失败",
            outcome="failed", error_type="llm_error", error_message=content,
        )):
            yield _s
        return

    # ── 未知类型 │ yield FinalStep(outcome=failed) ──
    if parsed_type != "answer":
        logger.warning(f"[handle_answer] 未知返回类型: {parsed_type}, 设置为FAILED")
        agent._consecutive_reasoning_only = 0   # 2026-07-17 - 小欧 - 未知类型非reasoning-only, 归零防残留
        content = parsed.get("content", "") or parsed.get("thought", "") or ""
        # 2026-08-28 小欧 yield日志审计: print→logger统一(DRY违规修复)
        logger.error(f"[answer] step={step} unknown_type={parsed_type} content={content}")
        if content:
            agent.message_builder.add_assistant_message(f"[无效响应:{parsed_type}] {content}")
        yield agent._step_emitter.emit(ThoughtStartStep(step=step))   # 2026-08-18 小欧 thought-start
        for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
            step=step, response="任务执行失败",
            outcome="failed", error_type="unknown_response",
            error_message=f"LLM返回未知响应类型: {parsed_type}",
        )):
            yield _s
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
            severity="info",
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
        if agent._consecutive_reasoning_only > REASONING_ONLY_MAX_ROUNDS:
            logger.warning(f"[handle_answer] 连续{agent._consecutive_reasoning_only}轮reasoning-only无进展(step={step}), 终止任务")
            yield agent._step_emitter.emit(ThoughtStartStep(step=step))   # 2026-08-18 小欧 thought-start
            for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
                step=step,
                response="模型反复思考未产出有效结果，任务已终止（疑似陷入无效循环）",
                reasoning=_deduped,
                outcome="failed",
            )):
                yield _s
            return
        if _deduped == reasoning:
            # ── 好的: 无重复 → 贴便签(仿Hermes: content空 + 双字段reasoning/reasoning_content以OpenAI为主兼容DeepSeek) ── 小欧 2026-07-19
            logger.info(f"[handle_answer] LLM返回推理内容(step={step}), 注入临时推理(连续reasoning-only={agent._consecutive_reasoning_only})")
            agent.message_builder.conversation_history.append({
                "role": "assistant",
                "content": "",
                "reasoning": _deduped,
                "reasoning_content": _deduped,
                "_temp_reasoning": True,
            })
            yield agent._step_emitter.emit(ThoughtStep(
                step=step, content=_deduped, reasoning="",
            ))
        else:
            # ── 坏的: 有重复去重 → 不注入不持久不发射, 仅warning ── 小欧 2026-07-19
            logger.warning(f"[handle_answer] reasoning检测到重复去重(step={step}), 跳过注入")
        return

    agent._consecutive_reasoning_only = 0   # 2026-07-17 - 小欧 - 正常final answer, 归零空转计数(防御残留)
    thought = parsed.get("thought", content)

    yield agent._step_emitter.emit(ThoughtStartStep(step=step))   # 2026-08-18 小欧 thought-start

    if thought:
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content=thought, reasoning=reasoning,
        ))

    # ══ 重复检测(≥250字才检) — DB 入库前唯一保留的护栏 ══
    if len(content) >= REPEAT_CHECK_MIN_LEN:
        deduped = _dedup_repeat(content)
        if deduped != content:
            content = deduped

    # 2026-08-28 小欧 yield日志审计: print→logger统一(DRY违规修复)
    logger.info(f"[answer] step={step} final response_len={len(content)}")
    for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
        step=step, response=content,
        outcome="completed", reasoning=reasoning,
    )):
        yield _s
    agent.message_builder.add_assistant_message(content)
