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
# 2026-08-30 小欧 - 恢复[Final]终态全文打印(65f4de7f7"print→logger"把response=全文误改response_len, 终态正文不再上控制台; log_and_print复用07-23收口+08-30离线化双写)
# 2026-09-02 小欧 - 配额类终态保真修复: error分支error_type透传(原写死llm_error丢粒度quota_exceeded/rate_limit/idle_timeout), errormessage已透传; KISS直线, 不新增事件类型 - 小欧-2026-09-02
# 2026-09-01 - 小欧 - 方案A实施: 删除正常answer终态的污染版ThoughtStep(thought=parsed.get("thought", content)恒退化为完整答案, 致历史回放reasoning/response双渲); 终态正文/推理由FinalStep单一承载; 保留ThoughtStartStep(实时光标)与reasoning-only分支/工具轮ThoughtStep(正当); 方案详见 doc-9月优化/final步骤历史回放重复显示-问题分析与修复方案-小欧-2026-09-01.md
# 2026-09-02 小欧 - 缺陷#4修复(测试验证 test_answer_handler_edge_cases): handle_answer 入口加 parsed=None 防御。
#   病根: 上游LLM流异常/HTTP400等极端情况下 parsed 可能为 None, L105 parsed.get("type","answer") 抛 AttributeError 崩掉整个SSE流;
#   修复: 入口 `if parsed is None` → 置空 dict, 后续走既有"真空→系统重试"分支(emit retrying MetaStep 由编排层重试), 不新增分支/不造新范式;
#   三堂会审: 合规(SRP/DRY/KISS/SLAP/YAGNI) + 合理(空dict语义=空响应, 复用既有重试机制) + 关联(崩溃→优雅重试, 正常answer/error/unknown/reasoning-only四分支零影响) - 小欧-2026-09-02
# 2026-09-03 小欧 - fix: error/unknown分支set_failed移到emit_final_with_stats之前,
#   使build_final_stats_step读到agent.status=FAILED→final_status='failed'→前端badge兜底生效(改前set_failed在yield之后致final_status='executing'→badge卡running) - 小欧-2026-09-03
# 2026-09-05 小健 - answer_focus第一阶段(10.3): 三件集中+余部改名handle_answer.py
#   搬一(8.1): _dedup_repeat+REPEAT_*三常量迁text_utils.dedup_repeat, 删import re/Counter, 改L186/L224调用点 - 小健-2026-09-05
#   搬二(8.2): 4处终态改调入emit_failed_final/emit_completed_final工厂, 删延迟import set_failed(11/12并行), 空转终止补09-03顺序 - 小健-2026-09-05
#   搬三(8.3): 计数5处直写改调reasoning_guard(note_progress×4 + note_reasoning_only×1), 删REASONING_ONLY_MAX_ROUNDS常量 - 小健-2026-09-05
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

from app.services.agent.steps import ThoughtStep, ThoughtStartStep, FinalStep, MetaStep  # 2026-08-18 小欧 ThoughtStartStep新增
from app.utils.text_utils import format_tool_call_markup, dedup_repeat, REPEAT_CHECK_MIN_LEN  # 小健 2026-09-05：去重函数归位文本层；门槛常量随迁，供L182预检引用
from app.services.agent.reasoning_guard import note_progress, note_reasoning_only  # 小健 2026-09-05：空转计数唯一写者收口
from app.logger import logger, log_and_print


async def handle_answer(agent, parsed: Dict):
    """统一处理所有非action的LLM返回类型（answer/error/unknown）
    
    由 _dispatch_handler(react_cycle.py) 分派，接收 llm_stream.py 构建的 type：
    - type="answer" → 正常终态流程（最终答复）
    - type="error"  → LLM 流式异常 → FinalStep(outcome="failed") → set_failed
    - 其他未知 type → 按 error 处理（兜底）
    
    type 产生于 llm_stream.py（见该模块头部），不由 LLM 输出，是 agent 推断。"""
    # 2026-09-02 小欧 缺陷#4修复: parsed=None 防御(上游LLM流异常/HTTP400极端场景可能传 None)
    #   置空dict后: parsed_type默认"answer"→content/reasoning皆空→走既有"真空→系统重试"分支, 不新增逻辑
    if parsed is None:
        parsed = {}
    step = agent.llm_call_count
    parsed_type = parsed.get("type", "answer")

    # ── type="error" │ yield FinalStep(outcome=failed) ──
    if parsed_type == "error":
        content = parsed.get("content", "") or "LLM流式错误"
        err_type = parsed.get("error_type") or "大模型错误"
        note_progress(agent)  # 小健 2026-09-05：空转计数唯一写者收口(原注解 2026-07-17 小欧 error非reasoning-only 归零防残留 缀回行尾，语义不变)
        agent.message_builder.add_assistant_message(content)
        # 2026-08-28 小欧 yield日志审计: print→logger统一(DRY违规修复)
        logger.error(f"[answer] step={step} error={content} error_type={err_type}")
        yield agent._step_emitter.emit(ThoughtStartStep(step=step))   # 2026-08-18 小欧 thought-start
        for _s in agent._step_emitter.emit_failed_final(
            step=step, response="任务执行失败", error_type=err_type, error_message=content,
        ):  # 小健 2026-09-05：set_failed 内聚工厂内(09-03顺序铁律)
            yield _s
        return

    # ── 未知类型 │ yield FinalStep(outcome=failed) ──
    if parsed_type != "answer":
        logger.warning(f"[handle_answer] 未知返回类型: {parsed_type}, 设置为FAILED")
        note_progress(agent)  # 小健 2026-09-05：空转计数唯一写者收口(原注解 2026-07-17 小欧 未知类型非reasoning-only 归零防残留 缀回行尾，语义不变)
        content = parsed.get("content", "") or parsed.get("thought", "") or ""
        # 2026-08-28 小欧 yield日志审计: print→logger统一(DRY违规修复)
        logger.error(f"[answer] step={step} unknown_type={parsed_type} content={content}")
        if content:
            agent.message_builder.add_assistant_message(f"[无效响应:{parsed_type}] {content}")
        yield agent._step_emitter.emit(ThoughtStartStep(step=step))   # 2026-08-18 小欧 thought-start
        for _s in agent._step_emitter.emit_failed_final(
            step=step, response="任务执行失败", error_type="unknown_response",
            error_message=f"LLM返回未知响应类型: {parsed_type}",
        ):  # 小健 2026-09-05：set_failed 内聚工厂内(09-03顺序铁律)
            yield _s
        return

    # ── type="answer" ──
    content = format_tool_call_markup(parsed.get("content", ""))
    reasoning = format_tool_call_markup(parsed.get("reasoning", ""))

    # 真·空：content和reasoning都空 → 系统重试通知(MetaStep.retrying)，由 RETRYING 态驱动编排层重试 — 小欧 2026-07-13 删 recoverable
    if not content and not reasoning:
        logger.warning(f"[handle_answer] LLM返回空内容(step={step}), 触发系统重试")
        note_progress(agent)  # 小健 2026-09-05：空转计数唯一写者收口(原注解 2026-07-17 小欧 真空非reasoning空转 归零防残留误累计 缀回行尾，语义不变)
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
        _deduped = dedup_repeat(reasoning)     # 小健 2026-09-05
        if note_reasoning_only(agent):  # 小健 2026-09-05：唯一 +=1 收口 guard 内，超限返回 True 走终止分支
            logger.warning(f"[handle_answer] 连续{agent._consecutive_reasoning_only}轮reasoning-only无进展(step={step}), 终止任务")
            yield agent._step_emitter.emit(ThoughtStartStep(step=step))   # 2026-08-18 小欧 thought-start
            for _s in agent._step_emitter.emit_failed_final(
                step=step,
                response="模型反复思考未产出有效结果，任务已终止（疑似陷入无效循环）",
                reasoning=_deduped,
            ):  # 小健 2026-09-05：error_type/message 缺省空串，set_failed 取 response 兜底(补09-03顺序)
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

    note_progress(agent)  # 小健 2026-09-05：空转计数唯一写者收口(原注解 2026-07-17 小欧 正常final answer 归零空转计数 缀回行尾，语义不变)
    # 2026-09-01 小欧 方案A: 删除污染版 ThoughtStep(thought恒退化=content, 致历史回放 reasoning/response 双渲);
    #   终态正文/推理由 FinalStep 单一承载。保留 reasoning-only 分支(L189)与工具轮 ThoughtStep 不动。
    yield agent._step_emitter.emit(ThoughtStartStep(step=step))   # 2026-08-18 小欧 thought-start

    # ══ 重复检测(≥250字才检) — DB 入库前唯一保留的护栏 ══
    if len(content) >= REPEAT_CHECK_MIN_LEN:
        deduped = dedup_repeat(content)   # 小健 2026-09-05
        if deduped != content:
            content = deduped

    # 2026-08-30 小欧 恢复[Final]终态全文打印: 65f4de7f7(08-28)把response=全文误改为response_len, 终态正文不再上控制台; log_and_print复用07-23统一收口+08-30控制台离线化(事件循环零阻塞)
    log_and_print(f"{time.strftime('%H:%M:%S')} [Final] step={step}, response_len={len(content)}, response={content}")
    for _s in agent._step_emitter.emit_completed_final(
        step=step, response=content, reasoning=reasoning,
    ):  # 小健 2026-09-05：completed 由 dispatch 外层置状态，工厂不提前置
        yield _s
    agent.message_builder.add_assistant_message(content)
