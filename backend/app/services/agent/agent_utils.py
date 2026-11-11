# -*- coding: utf-8 -*-
# 编辑历史:
#   2026-10-30 小欧 token_estimate 新建: chars→token 估算收口为唯一实现——refs.budget._tokens_of 与
#     compaction.prune._released_tokens 原各写一份同款单行(DRY 违反), 本轮 5 处调用点改本函数 — 小欧-2026-10-30
#   2026-10-30 小欧 落位说明: 与唯一真源 CHARS_PER_TOKEN 同域(services.agent), 引用域本就依赖
#     compaction_constants, 沿同一方向复用; 未放 app/utils 以免 utils 反向依赖 services — 小欧-2026-10-30
#   2026-10-31 小欧 改名合并(北京老陈令): token_estimate.py → agent_utils.py, agent 层公用函数收口一处;
#     同批并入 start_step.start_compress_summary_threshold(超窗判定与锚点增量阈值唯一真源),
#     调用方(refs/budget、refs/notice、compaction/prune、start_step)导入路径同步改 — 小欧-2026-10-31
#   2026-10-31 小欧 新增 trim_conv_threshold(北京老陈令): loop 裁剪触发阈值 =
#     (窗口 - 输出缓冲 - tools预留) × 调节系数, 与 start_compress_summary_threshold 同款模式;
#     消费方 message_builder._trim_signal 的 abs_trigger 改调本函数 — 小欧-2026-10-31
#   2026-10-31 小欧 新增 trim_budget_base(北京老陈令): 裁剪预算基准 = 窗口 - 输出缓冲 - tools预留,
#     单点给出; trim_conv_threshold 改为以它为乘数底数, message_builder._trim_signal 内联算式删除,
#     refs.limits.budget_base 同步改调本函数(引用域与裁剪域预算口径合一) — 小欧-2026-10-31
#   2026-10-31 小欧 改名(北京老陈令): start_compress_summary_threshold → compress_summary_threshold,
#     去掉 start 前缀以表明它只管「窗口×限制系数」这一口径, 非 start 阶段专用; 调用方(start_step
#     两处、导入)同步改名, 零行为变化 — 小欧-2026-10-31
#   2026-10-31 小欧 新增 trim_queue_budget(北京老陈令): 队列预算 = 裁剪预算基准 × 调节系数²,
#     原 message_builder.trim_history 内联算式删除改调本函数; 至此 loop 裁剪三个口径
#     (基准/触发线/队列预算)全部单点 — 小欧-2026-10-31
#   2026-10-31 小欧 新增 conv_threshold(北京老陈令): start 压缩前 conv 超窗判定线 = 窗口 × 调节系数,
#     直接对窗口取比例(不扣 buffer/tools 预留); 消费方 start_step._compact_injected_history —
#     超此线才阶梯裁剪到 trim_conv_threshold(目标线)以内再压缩 — 小欧-2026-10-31
#   2026-11-07 小欧 新增 fmt_tok: token 体积紧凑文案(<1000 原值, ≥1000 折K, ≥1_000_000 折M, 带 tok 单位);
#     消费方 start_step 摘要提示; 与 estimate_tokens 同域(SRP: token 估算与格式化同归本模块) — 小欧-2026-11-07

"""services.agent.agent_utils — agent 域公用函数收口 — 小欧 2026-10-31

职责(单一职责): 只承载 agent 域内被多处复用的纯计算函数(文本→token 估算、压缩摘要阈值、裁剪触发阈值)。

为什么放这里而不放 app/utils: 本模块依赖 services.agent.compaction_constants 的常量真源;
  放进 app/utils 会让底层 utils 反向依赖 services 层(层级倒置), 沿 2026-10-30 token_estimate
  既定方向 — 公用函数与它的常量真源同域。

不做的事(SRP):
  - 不数「消息列表」的预算占用。MessageBuilder._estimate_tokens 估算的是含 tool_calls 结构开销的
    消息列表总量(_total_chars 口径), 输入口径与该函数不同, 不并入。
  - 不做裁剪动作本身(分区/切点/重建): 那是 message_builder.trim_history 的职责, 本模块只给阈值。
"""
from app.config import get_config
from app.services.agent.compaction_constants import (
    COMPACTION_BUFFER,
    START_LIMIT_RATIO,
    TOOLS_TOKEN_RESERVE,
    TRIM_TRIGGER_RATIO,
)

# chars→token 换算系数 — 小欧 2026-10-31
# 意义: 本文件是全仓唯一定义处, 与消费它的估算函数 estimate_tokens 同址; 其他模块一律导入, 禁止另立。
# 取值: 1.86 字/token —— 2483 次真实调用实测(消息字符 + tools schema 口径) Σ字符/Σprompt_tokens=1.860;
#   原 2.25 系统性低估 21%(中位 25%、p90 55%), 改后取实测下界(系数取小=估算偏大=偏保守, 不低估撞窗)。
CHARS_PER_TOKEN = 1.86


def estimate_tokens(content) -> int:
    """估算文本 content 的 token 数(整数, 向下取整); None/空 → 0。

    适用场景: 任意纯文本的体积估算(引用正文、旧 tool 输出释放量等)。
    使用方法: 直接调用, 传文本(或可 str() 的对象)。
    输入: content —— 任意对象; None 视为空。
    输出: int, token 数(向下取整)。
    设计边界: str() 兜底 —— 引用正文恒为 str, 但 compaction 的 tool 消息 content 可能已是非字符串
      历史脏值, 原 _released_tokens 用 str() 兜底, 此处保持同一鲁棒性。
    """
    return int(len(str(content or "")) / CHARS_PER_TOKEN)


def compress_summary_threshold(ctx: int) -> int:
    """压缩摘要阈值: 超窗判定与锚点增量阈值的唯一真源 — 小欧 2026-10-31

    适用场景: ①超窗判定(start_step._maybe_compact_injected_history)
              ②锚点增量阈值(start_step._assemble_anchor_delta);
              ③其余按「窗口 × 限制系数」取压缩摘要 limit 的场景(与 start 阶段无关的调用方同样可用)。
    使用方法: 传运行时上下文窗口 token 数, 返回压缩摘要 limit token 数。
    输入: ctx = agent.message_builder.MAX_CONTEXT_TOKENS(agent_runner 已覆盖为模型 context_length)。
    输出: int(ctx × 限制系数)。
    前置条件: ctx > 0。
    公式: int(ctx × tuning.compaction.start_limit_ratio), 缺省 START_LIMIT_RATIO=0.5。
    关联逻辑: 原两处重复算式抽为一个函数(DRY)。术语: 本值是「压缩摘要 limit」—— 由「限制系数」
      (0.5)乘窗口得出; 不是 loop 裁剪的「调节系数」(tuning.trim.trigger_ratio), 两者不得混用。
      两处同源后, 超窗判定与增量复用同尺, 不会一处改了另一处不动。
    """
    return int(ctx * float(get_config().get(
        'tuning.compaction.start_limit_ratio', START_LIMIT_RATIO)))


def trim_budget_base(ctx: int) -> int:
    """loop 裁剪预算基准: 触发判定与队列预算的共同分母 — 小欧 2026-10-31

    适用场景: ①_trim_signal 的信号三元组(供 trim_history 后续判定)
              ②trim_conv_threshold 的乘数底数。
    使用方法: 传运行时上下文窗口 token 数, 返回可用内容预算 token 数。
    输入: ctx = MessageBuilder.MAX_CONTEXT_TOKENS(agent_runner 已覆盖为模型 context_length)。
    输出: ctx - 输出缓冲 - tools 预留。
    前置条件: 无; ctx 过小时结果为负, 由调用方按既有语义处理(恒触发/让位)。
    公式: ctx - tuning.trim.compaction_buffer - tuning.trim.tools_token_reserve;
      缺省 COMPACTION_BUFFER=20000 / TOOLS_TOKEN_RESERVE=30000。
    关联逻辑: 引用域 refs.limits 的 budget_base 同用本函数(预算口径全仓一处), 不再各自写算式。
    """
    cfg = get_config()
    return (int(ctx)
            - int(cfg.get('tuning.trim.compaction_buffer', COMPACTION_BUFFER))
            - int(cfg.get('tuning.trim.tools_token_reserve', TOOLS_TOKEN_RESERVE)))


def trim_conv_threshold(ctx: int) -> int:
    """loop 裁剪触发阈值: 「绝对值触发」条件的唯一真源 — 小欧 2026-10-31

    适用场景: message_builder._trim_signal 的 abs_trigger 判定(粗估 > 本阈值即触发裁剪)。
    使用方法: 传运行时上下文窗口 token 数, 返回触发阈值 token 数。
    输入: ctx = MessageBuilder.MAX_CONTEXT_TOKENS(agent_runner 已覆盖为模型 context_length)。
    输出: int(trim_budget_base(ctx) × 调节系数)。
    前置条件: 无; 预算基准为负时本值亦为负, 即恒触发。
    公式: trim_budget_base(ctx) × tuning.trim.trigger_ratio; 缺省 TRIM_TRIGGER_RATIO。
    关联逻辑: 预算基准由 trim_budget_base 单点给出(与 trim_history 溢窗判据/队列预算同源),
      本函数只负责「基准 × 调节系数」这一乘积口径。术语: 「调节系数」只服务 loop 裁剪,
      与压缩摘要的「限制系数」(compress_summary_threshold)不得混用。
    取整说明: 与 compress_summary_threshold 同款向下取整, 阈值最多低不到 1 token。
    """
    return int(trim_budget_base(ctx) * float(get_config().get(
        'tuning.trim.trigger_ratio', TRIM_TRIGGER_RATIO)))


def trim_queue_budget(ctx: int) -> int:
    """loop 裁剪队列预算: 「可裁队列」能占用的 token 上限 — 小欧 2026-10-31

    适用场景: message_builder.trim_history 的队列预算(protected 之外还允许留多少),
      配合 find_tail_start(align_turn=True) 决定队尾切点。
    使用方法: 传运行时上下文窗口 token 数, 返回队列预算 token 数(尚未扣保护区占用)。
    输入: ctx = MessageBuilder.MAX_CONTEXT_TOKENS(agent_runner 已覆盖为模型 context_length)。
    输出: int(trim_budget_base(ctx) × 调节系数²)。
    前置条件: 无; 结果为负表示连保护区都超预算, 调用方应走"不裁队列"分支。
    公式: trim_budget_base(ctx) × tuning.trim.trigger_ratio²; 缺省 TRIM_TRIGGER_RATIO。
    关联逻辑: 与 trim_conv_threshold(基准 × 系数, 一次方 = 触发线)同基准、差一次幂 ——
      触发线之上再乘一次系数, 保证"裁完必低于触发线"(裁剪有效), 否则裁了仍触发即死循环;
      基准由 trim_budget_base 单点给出, 本函数只负责这一乘积口径。
    取整说明: 与 trim_conv_threshold 同款向下取整。
    """
    _ratio = float(get_config().get('tuning.trim.trigger_ratio', TRIM_TRIGGER_RATIO))
    return int(trim_budget_base(ctx) * _ratio * _ratio)


def conv_threshold(ctx: int) -> int:
    """start 压缩前 conv 超窗判定线: 窗口 × 调节系数 — 小欧 2026-10-31

    适用场景: start_step._compact_injected_history 进入压缩前的唯一判定——注入历史估算
      超过本阈值才做阶梯裁剪, 未超则不裁直接压缩(零行为变化)。
    使用方法: 传运行时上下文窗口 token 数, 返回判定线 token 数。
    输入: ctx = MessageBuilder.MAX_CONTEXT_TOKENS(agent_runner 已覆盖为模型 context_length)。
    输出: int(ctx × 调节系数), 缺省 TRIM_TRIGGER_RATIO=0.8。
    前置条件: ctx > 0。
    关联逻辑: 与 trim_conv_threshold 分工——本函数=「要不要裁」(直接对窗口取比例, 不扣
      buffer/tools 预留); trim_conv_threshold=「裁到哪」(对裁剪预算基准取比例)。
      因基准 = 窗口 - 50000, 故目标线恒低于判定线, 裁完必落在判定线之下。
    取整说明: 与 trim_conv_threshold 同款向下取整。
    """
    return int(int(ctx) * float(get_config().get(
        'tuning.trim.trigger_ratio', TRIM_TRIGGER_RATIO)))


def fmt_tok(n: int) -> str:
    """token 体积紧凑文案: <1000 原值, ≥1000 折K一位, ≥1_000_000 折M一位, 带 tok 单位 — 小欧 2026-11-07

    适用场景: 给用户看的提示/notice 中 token 体积的紧凑表达(如 "38.0Ktok"/"1.5Mtok")。
    使用方法: 直接调用, 传 token 数(int)。
    输入: n —— token 数; 负数或 None 视为 0。
    输出: str, 如 "500tok" / "38.0Ktok" / "1.5Mtok"。
    关联逻辑: 与 estimate_tokens 同域——估算出 int 后由本函数转紧凑文案(SRP: 估算与格式化同归本模块)。
    """
    n = int(n or 0)
    if n < 0:
        n = 0
    if n >= 1_000_000:
        return f"{n / 1_000_000:.1f}Mtok"
    if n >= 1000:
        return f"{n / 1000:.1f}Ktok"
    return f"{n}tok"


__all__ = ["estimate_tokens", "compress_summary_threshold",
           "trim_budget_base", "trim_conv_threshold", "trim_queue_budget",
           "conv_threshold", "fmt_tok"]
