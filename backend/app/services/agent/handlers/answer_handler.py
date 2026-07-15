# -*- coding: utf-8 -*-
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
import os
import time
from typing import Dict, Tuple

from app.config import get_config
from app.services.agent.steps import ThoughtStep, FinalStep, ErrorStep, MetaStep
from app.services.agent.llm_stream import call_llm_with_fallback
from app.services.agent.tool_cache_manager import get_openai_tools
from app.utils.text_utils import format_tool_call_markup
from app.logger import logger


# ═══════════════════════════════════════════════════════════════
# final 质量护栏 — 小欧 2026-07-15
# 设计意图: 仅在 final 出口做纯函数检查(重复/外置) + 退化纠正机会, 不改动 SSE/observation/工具/编排层
# 复用: get_config().get_project_root() 取项目根(经核对 agent 无 config 属性)
# 依赖: os / time / logger / ThoughtStep / FinalStep / MetaStep / call_llm_with_fallback / get_openai_tools 已导入
# 注释约定: 每个函数标注【设计意图】【防误伤边界】【调用前提】, 便于后续检测问题
# ═══════════════════════════════════════════════════════════════

# ── 退化检测 ──
DEGRADE_LEN_THRESHOLD = 60     # 老陈拍板: <60字 + 规划词开头 + 无完成态 → 退化
_DEGRADE_HINTS = ("接下来", "下一步", "仍然需要", "正在进入", "先获取", "进入处理阶段")
_COMPLETE_MARKERS = (
    "已", "完成", "成功", "失败", "不存在", "生成", "创建", "删除", "保存",
    "报告", "文件", "结果", "数据", "日志",
)

# ── 重复检测 ──
REPEAT_CHECK_MIN_LEN = 500     # 重复检测启动门槛: 不足500字不检(短内容无危害)
DUP_CHUNK = 200                # 检测窗口: 匹配 LLM 卡顿循环周期(老陈经验值200), 禁止降低防误伤
DUP_RATIO = 0.5                # 重复块占总长比例阈值, 占比过半才截断, 宁漏判不误伤, 禁止降低

# ── 超长外置 ──
EXTERNAL_THRESHOLD = 2500      # 老陈拍板: final 答复专属门限, 超2500即外置, 不复用死常量
EXTERNAL_HEAD = 625            # ≈ EXTERNAL_THRESHOLD 的 1/4, final 预览长度

# ── 退化纠正机会 ──
MAX_CORRECT_TIMES = 1          # 退化纠正次数上限(跨 loop 累计), 防无限 loop; 实测可放宽


def _is_degenerate(content: str) -> bool:
    """【退化检测】判断 final 是否退化(仅规划句/无实质结论)
    【设计意图】机械检查, 不替换内容; 给后续纠正机会做判定依据
    【防误伤边界】① 长度>=60 直接判非退化(不足60才可疑); ② 不以规划词开头→非退化;
        ③ 以规划词开头但含完成态标记→非退化(如"接下来请查看 report.pdf"含.pdf不触发);
        ④ 宁漏判不误伤(流畅退化不触发, 仅捕明显规划句退化)
    【调用前提】content 为格式化后的 final 文本"""
    s = content.strip()
    if not s or len(s) >= DEGRADE_LEN_THRESHOLD:
        return False
    if s.startswith(_DEGRADE_HINTS):
        if not any(m in s for m in _COMPLETE_MARKERS):
            return True
    return False


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


def _externalize_if_long(agent, content: str, step: int) -> str:
    """【超长自动外置】机械保障, 内容不丢
    【设计意图】类型1有意义超长(如研究报告)截断=误伤, 故存文件+摘要指路, 不截断
    【防误伤边界】① ≤阈值原样返回(零影响, 与当前行为一致); ② 写文件异常→返回原内容(不影响系统);
        ③ 阈值2500为 final 答复专属, 不复用死常量
    【调用前提】agent 有 task_id; 返回原内容或"前625字+文件路径" """
    if len(content) <= EXTERNAL_THRESHOLD:
        return content
    try:
        project_root = get_config().get_project_root()
    except Exception:
        return content
    if not project_root:
        return content
    task_id = getattr(agent, "task_id", str(step))
    filename = f"final_detail_{task_id}_{time.strftime('%Y%m%d%H%M%S')}.md"
    reports_dir = os.path.join(project_root, "reports")
    try:
        os.makedirs(reports_dir, exist_ok=True)
        file_path = os.path.join(reports_dir, filename)
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        logger.warning(f"[L1-C1] final 超长({len(content)}>{EXTERNAL_THRESHOLD}), 已外置至 {file_path}")
        return f"{content[:EXTERNAL_HEAD]}\n\n... [完整内容已保存至: {file_path}]"
    except Exception as e:
        logger.warning(f"[L1-C1] 外置文件失败: {e}, 返回原内容")
        return content


def _extract_tool_results(conversation_history: list, max_len: int = 3000) -> str:
    """【退化纠正机会】从对话历史提取工具执行结果摘要, 作为 correction prompt 的增强上下文
    【设计意图】让 LLM 纠正时基于已有 observation 重新总结, 避免凭空重述
    【防误伤边界】① 仅取 role=="tool" 的消息(observation), 不混入其他角色;
        ② 截断到 max_len(默认3000)防 correction prompt 超长; ③ 无工具结果返回空串(LLM 仅知退化)
    【调用前提】conversation_history 为 message_builder 维护的对话列表"""
    parts = []
    total = 0
    for msg in conversation_history:
        if msg.get("role") != "tool":
            continue
        text = msg.get("content", "")
        if not text:
            continue
        if total + len(text) > max_len:
            parts.append(text[:max(0, max_len - total)])
            break
        parts.append(text)
        total += len(text)
    return "\n".join(parts)


def _safe_degrade_final(content: str) -> str:
    """【纠正失败降级】仍退化→安全降级输出
    【设计意图】纠正机会失败(LLM 仍退化/error)时的兜底, 输出明确诚实, 替代旧"追加提示"逻辑
    【防误伤边界】① 非破坏(不删原内容, 仅追加说明); ② 明确告知用户去哪看结果, 而非噪声提示;
        ③ 与旧 _append_degradation_hint 等价但更清晰(旧:"可能不完整"; 新:"见历史/产物")
    【调用前提】content 为原退化 final; 返回增强后的 final"""
    reports_dir = os.path.join(get_config().get_project_root(), "reports")
    return (content + "\n\n（任务已执行，但自动总结未完整生成；工具执行结果见上方对话历史，"
            f"产物文件见 {reports_dir} 目录。如结论关键，请查看历史中的工具输出。）")


async def _correct_degenerate(agent, original_content: str) -> Tuple[str, bool]:
    """【退化纠正机会】给 LLM 重新生成的机会(非简单重试)
    【设计意图】退化检测命中后, 不追加提示直接输出, 而是注入增强上下文(退化告知+历史工具结果)让 LLM 重生成;
        LLM 自己决定结束(answer)或继续工具(action)。
    【与重试本质区别】重试=重发相同请求无上下文; 纠正=给不同增强上下文(明确告知退化+引导基于observation总结)
    【4 分支控制流】
        LLM 返回 type=answer:
          ├─ 内容非退化 → 纠正成功(调用方重过重复/超长门禁)
          └─ 仍退化      → 调用方 _safe_degrade_final 兜底
        LLM 返回 type=action:
          └─ loop=True → 调用方 yield continue_loop(react_cycle 真 loop, LLM 自决定)
        LLM 返回 type=error/无响应:
          └─ loop=False, 返回原内容 → 调用方 _safe_degrade_final 兜底
    【防误伤边界】① correction prompt 以 user role 写入 conversation_history(用 add_user_message, 与 React observation 注入一致, 透明可追溯),
        供后续 loop 使用; ② 消费 chunk 不 emit 原始 chunk(避免暴露系统 prompt);
        ③ 仅取末条 response, 遇 error/无响应→返回原内容(由调用方降级); ④ llm_call_count+1 计入 max_steps 兜底
    【返回】(新content, loop): loop=True 表示 LLM 决定继续工具调用(交 react_cycle 真 loop)
    【调用前提】agent 持有 llm_client / message_builder; 在 handle_answer 内调用"""
    agent.llm_call_count += 1
    tool_summary = _extract_tool_results(agent.message_builder.conversation_history, max_len=3000)
    correction = (
        "[System] 你刚才的最终答复是退化的(仅规划句/无实质结论), 不符合预期。\n"
        "请基于对话对话已有的工具执行结果重新给出最终总结:\n"
        "1. 若已完成,直接给结论/结果,说明完成什么、产物在哪\n"
        "2. 严禁复述'下一步计划/正在处理'\n"
        "3. 若确实还需继续调用工具, 分析后直接调用相应工具\n"
        f"[历史工具结果摘要]\n{tool_summary}"
    )
    agent.message_builder.add_user_message(correction)   # 写 history(user role, 与observation一致)
    messages = agent.message_builder.prepare_messages_for_llm()
    openai_tools = get_openai_tools(agent)
    parsed = None
    async for ct, cd in call_llm_with_fallback(agent, messages, openai_tools):
        if ct == "response":
            parsed = cd          # 消费chunk, 取末条response(不emit原始chunk)
    if parsed is None:
        return original_content, False
    if parsed.get("type") == "action":
        return original_content, True          # loop=True: LLM决定继续工具
    # answer/error → 返回新content(error时由调用方降级)
    return parsed.get("content", original_content), False


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
    if not content and reasoning:
        logger.info(f"[handle_answer] LLM返回推理内容(step={step}), 注入助理消息继续循环")
        agent.message_builder.add_assistant_message(reasoning)
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content=reasoning, reasoning="",
        ))
        return

    thought = parsed.get("thought", content)

    if thought:
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content=thought, reasoning=reasoning,
        ))

    # ═══════════════════════════════════════════════════════
    # final 质量护栏 — 小欧 2026-07-15(退化先→重复短路→超长兜底 + 退化纠正机会)
    # 设计意图: 仅在 final 出口做机械检查(重复/外置) + 退化纠正机会, 不改动 SSE/observation/工具/编排层
    # 顺序: 退化最优先(纠正/降级) → 非退化再过重复检测(短路) → 最后超长外置(兜底)
    # 防误伤红线: 所有检查非破坏; 纠正失败→_safe_degrade_final 兜底; 短路控制流避免层层递进多余处理
    # ═══════════════════════════════════════════════════════

    # ══ 退化检测(最优先) — 非破坏, 给 LLM 纠正机会 ══
    # 控制流:
    #   退化检测命中 →
    #     _correct_degenerate(增强上下文重调 LLM)
    #     ├─ type=answer(非退化) → 纠正成功, 重过重复/超长门禁
    #     ├─ type=answer(仍退化) → _safe_degrade_final 降级
    #     ├─ type=action         → continue_loop MetaStep(LLM 自决定继续, 不产 FinalStep)
    #     └─ type=error/无响应    → _safe_degrade_final 降级
    #   非退化 → 重复检测(短路) → 超长外置(兜底) → FinalStep
    if _is_degenerate(content):
        yield agent._step_emitter.emit(ThoughtStep(
            step=step, content="检测到最终答复退化，正在请求 LLM 重新生成...", reasoning="",
        ))
        if getattr(agent, "_degrade_correct_total", 0) >= MAX_CORRECT_TIMES:
            content = _safe_degrade_final(content)        # 防无限: 达上限直接降级
        else:
            agent._degrade_correct_total = getattr(agent, "_degrade_correct_total", 0) + 1
            new_content, loop = await _correct_degenerate(agent, content)
            if loop:
                # LLM 决定继续工具: correction prompt 已写入 history(user), 交 react_cycle 真 loop
                # 不 yield FinalStep, react_cycle._dispatch_handler 的 else 分支不设终态→主循环继续
                yield MetaStep(type="continue_loop", step=agent.llm_call_count,
                               content="退化纠正: LLM请求继续工具调用")
                return
            content = new_content
            if _is_degenerate(content):
                content = _safe_degrade_final(content)        # 纠正失败→降级(非破坏)

    # ══ 重复检测(≥500字才检, 短路) ══
    if len(content) >= REPEAT_CHECK_MIN_LEN:
        deduped = _dedup_repeat(content)
        if deduped != content:
            content = deduped  # 重复→去重后短路, 不检超长

    # ══ 超长外置(兜底, 内部≤2500原样) ══
    content = _externalize_if_long(agent, content, step)

    print(f"{time.strftime('%H:%M:%S')} [Final] step={step}, response={content}")  # 小欧 2026-07-12 恢复answer分支终态日志(94eac9723合并时误删)
    yield agent._step_emitter.emit(FinalStep(
        step=step, response=content, thought=thought,
    ))
    agent.message_builder.add_assistant_message(content)
