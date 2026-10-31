
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-13 - 小欧 - #2 add_tool_result构造失败兜底追加最小tool消息防结果丢失
# 2026-07-19 - 小欧 - add_assistant_tool_call/_append_observation新增reasoning参数传递
# 2026-07-19 - 小欧 - 推理空转不持久化(Hermes字面): ①新增pop_temp_messages()弹掉所有_temp_reasoning标记消息(改更早仅尾部→全表,防B3穿插隔开); ②prepare_messages_for_llm浅拷贝[dict()]隔离篡改+strip _temp_reasoning防泄漏wire。逻辑: 好的reasoning注入时带标记, 终端路径pop弹掉后再持久化; 坏的不注入故无需清理
# 2026-07-22 - 小欧 - MAX_CONTEXT_CHARS→MAX_CONTEXT_TOKENS 命名统一（值200000不变），构造参数+self属性+3处使用同步更新
# 2026-07-22 - 小欧 - 新增 last_total_tokens + _estimate_tokens; trim_history 改增量+绝对值双条件; _trim_to_budget 全 token 单位
# 2026-07-22 - 小欧 - 修复: reset_per_run 补充 self.last_total_tokens = None, 清除跨run残留
# 2026-07-22 - 小欧 - 修复: trim_history 日志路径未覆盖 _rebuild_and_validate 返回 None 的情况，将日志移入 if 分支 + else warning
# 2026-07-22 - 小欧 - 补充 assistant 消息四种存储形态类注释(源自对话梳理: action轮只存tool_calls, answer/reasoning-only/异常才存content)
# 2026-07-23 - 小欧 - #13 react_cycle崩溃修复: trim_history 加 try/except 防御性保护(message_builder状态退化时跳过裁剪保留原历史, 不抛异常到 react_cycle 导致循环崩溃)
# 2026-08-08 - 小欧 - v1.6双阈值扩展: ①pop_temp_messages判断条件由_temp_reasoning改为通用_temp_*前缀(兼容_temp_same_tool_warn, 绝后新增标记漏清理); ②prepare_messages_for_llm剥离_temp_*内部标记防泄漏LLM
# 2026-08-09 - 小欧 - v1.7发送即清(北京老陈 2026-08-09 指示): prepare_messages_for_llm浅拷贝messages后, 由conversation_history源中
#   立即剔除本轮已发送的_temp_*临时消息(纠偏/推理仅活"本轮发送这一次"), 防死循环长历史中残留/重复携带/污染压缩与持久化;
#   与终态pop_temp_messages安全网双保险(reasoning-only/纠偏正常脱落)。ast语法✓
# 2026-08-17 - 小健 - S5(compaction 落地 943a77917): ①add_tool_result 新增 summary 形参, 工具层 llm_data.summary
#   透传 stash `_summary` 供 compaction.use_tool_summary 复用(DRY, 14.9.6 C2 前置, 与 observation_formatter 拼接解耦);
#   ②prepare_messages_for_llm 新增 _COMPACTION_TEMP_KEYS=("_summary","_pruned","_compressed","_raw","_truncated"),
#   浅拷贝后一并剥离, 与 _temp_* 同段清空, 防泄漏 LLM 请求/污染 wire(对齐 14.9.3②/14.9.6 C2 剥离要求)。
# 2026-08-17 - 小健 - compaction 函数改名同步: add_tool_result 注释3处 t1_reuse_summary→use_tool_summary(供 compaction.use_tool_summary 复用/防空转)
# 2026-08-17 - 小健 - 常量归属迁移(北京老陈驱动): 压缩/裁剪常量(MAX_CONTEXT_TOKENS/MAX_CONTEXT_RATIO/COMPACTION_BUFFER/CHARS_PER_TOKEN/TEMP_HISTORY_CHAR_LIMIT) 由 app.constants 迁至 app.services.agent.compaction_constants, 导入路径同步改
# 2026-08-17 - 小健 - 阈值重构(北京老陈 2026-08-17 定案, loop裁剪=上下文×3/4): trim_history 绝对值触发 self.MAX_CONTEXT_TOKENS(skip覆盖后运行时窗口)×TRIM_TRIGGER_RATIO 替换原×MAX_CONTEXT_RATIO; 构造默认 self.MAX_CONTEXT_TOKENS 由全局 MAX_CONTEXT_TOKENS(200000) 改 DEFAULT_CONTEXT_LIMIT(262144), 运行时仍被 agent_runner 覆盖为 context_limit
# 2026-08-20 - 小欧 - C2修复(真实缺陷复核确认): trim_history 新增瞬时裁剪token指标 `_trimmed_tokens_this_round`(每轮重置0, 实际裁剪时= rough_current-裁剪后估算, 与 `_trimmed_this_round` 同周期), 供 react_cycle on_trim 透传落 task_metrics.trim_tokens; 原 on_trim 只拿到 bool、token 数恒0 且 finalize 丢弃 → 裁剪遥测死链路。
# 2026-08-23 - 小欧 - 落盘文件A/B 实施(文档落码): __init__ 加 _msg_id_counter 自增计数 +
#   prepare_messages_for_llm 开头单点惰性补 _msg_id(不进 LLM wire, 由 react_cycle 写盘后 pop)——文件B 稳定去重依赖;
#   v3.29 单点化定案: conversation_history 全程同批 dict 引用(trim/inject/rebuild 不复制), 补标一次永久携带,
#   各 add_*/inject_history/trim_history 零改动(最小侵入)
# 2026-08-29 - 小沈 - 修复: _trim_fc_pairs 丢弃 tool_call_id 为空/None 的孤儿 tool 消息(原 elif not tool_call_id 分支误保留→发LLM 400); KISS仅删该分支
# 2026-09-20 - 小欧 - B组修复(锚演进): add_user_message 增可选 user_message_id 参数(未传自动合成负id, 内部维护
#   current_user_msg_id 锚单点), __init__ 增 _synth_user_msg_id 合成计数与 current_user_msg_id 属性;
#   prepare_messages_for_llm 浅拷贝后剥离 user_message_id 防泄漏 LLM wire(conversation_history 源保留锚)。compliance: SRP/DRY/KISS
# 2026-09-20 - 小欧 - D-4修复: _total_chars 将 reasoning/reasoning_content 计入预算(DeepSeek 长 reasoning 20K字符
#   原估0 token, 严重低估导致上下文越界); _estimate_tokens 复用 _total_chars 自动生效, 最小侵入。compliance: SRP/DRY/KISS
# 2026-09-23 - 小欧 - trim配置化: __init__ 新增 _trim_trigger_ratio/_compaction_buffer 读 tuning.trim.* 兜底常量; trim_history 增量/绝对值/budget 三处改用实例值
# 2026-09-23 - 小欧 - wiring假保存修复: _cap_temp_history 改读 tuning.content.temp_history_char_limit 兜底常量（此前设置页可改实际不生效）
# 2026-09-28 - 小欧 - 锚属性名修复(设计文档[76] 6.3): 新增只读 property current_user_msg_id(读私有 _current_user_msg_id)。
#   根因: agent_runner 用 getattr(mb, 'current_user_msg_id', None) 读锚恒 None(私有/公开名不匹配), 9-20 锚回填与
#   D-1 两修复因此从未生效 → 注入消息 task_id 恒 NULL。补公开只读口修根因, 封装禁外部直读私有。compliance: SRP/KISS
# 2026-10-04 小欧 - _estimate_tokens 取整方式: 系数改浮点(1.8)后 `chars // c` 返回 float, 改 int(chars / c) 保 int 契约
# 2026-10-05 - 小欧 - wire 推理字段去冲突(北京老陈裁定): prepare_messages_for_llm 剥离段追加 内部字段 reasoning
#   → API 标准 reasoning_content(单次改名, 同 fc_message_types.message_to_dict 规则)后删除, 空的 reasoning_content 不上线。
#   根因: reasoning-only 轮(handle_answer.py:182 / react_step.py:532 两处裸 dict)把两个字段写进同一消息,
#   sensenova 拒绝 reasoning 与 reasoning_content 并存 → HTTP 400 "inference request is invalid", 且被 error_classifier
#   误分类 CLIENT(重试无用) → B3 空转后必然 400。实测: 单字段任一 200 / 双字段 400 / 修后形状 200。
#   收口在唯一出站边界, 覆盖全部生产者(含未来新增), 不改写入点。compliance: SRP/DRY/KISS-DIRECT/禁backward
# 2026-10-13 小欧 - 文档[28] 4.1.6: init_history 增 refs 形参, 输入框引用正文拼入 user 消息**前置**区块。
#   入库/历史保持干净(user_input 在 orchestrator:433 已定格为用户原文, 不含 refs),
#   拼进 content 字符串可规避 prepare_messages_for_llm 的内部键剥离清单(_COMPACTION_TEMP_KEYS)。
# 2026-10-20 - 小欧 - 裁剪顺序缺陷修复(线上 400 实证, 2026-10-20 15:41 E2E P0-04a):
#   _trim_to_budget 原「反向遇 tool 先收 tool 再收 assistant + 扁平 reverse」, 单 tool_call 对 reverse 后恰好还原,
#   但一条 assistant 带 N≥2 并行 tool_calls 时首个 tool 落到 assistant 之前(tool(A)→assistant(A,B)→tool(B)),
#   上游严格顺序校验报 "tool result's tool id(...) not found (2013)"。
#   改为复用 fc_message_types.fc_atomic_units 按 FC 单元原子收集: 单元整体保留/丢弃, 组内升序展开保证
#   assistant→tool(s); _trim_fc_pairs 增顺序合法性判定(assistant 声明位置 < tool 响应位置), 乱序对双侧剔除兜底。
#   compliance: SRP/DRY(单元划分唯一源)/KISS-DIRECT
# 2026-10-20 小欧 - 预算跳过回归修复: _trim_to_budget 原「超预算即 break」在最新一轮超大+紧预算时
#   返回空 → LLM 丢失全部 FC 历史(fuzz 17% 场景; 旧实现对超预算 tool 对是跳过继续扫更早)。
#   改 break→continue: 超预算单元整体跳过, 继续尝试更早单元, 单元原子性保证不留半对。
# 2026-10-24 小欧 - 新增 get_last_tool_summary() 读方法: 返回末条 role:tool 消息摘要(_summary 优先, 回退 content 截200字),
#   供 react_inference._warn_same_tool_loop 纠偏注入让 LLM 看到上一次工具返回; SRP(message_builder 拥有 conversation_history 读写) — 小欧-2026-10-24
# 2026-10-25 小欧 - _rebuild_and_validate 末条 user 位置修复(北京老陈令): 原 system+user+trimmed 把全部 user
#   推到 trimmed 前面, 末条 user(本轮 task 提问)被 FC 对盖住; link 长链 trim 后 LLM 看不到新任务提问(实测复现)。
#   改为 system+other_users+trimmed+last_user, 末条 user 始终在尾部 — 小欧-2026-10-25
# 2026-10-25 小欧 - _rebuild_and_validate 交错序修复(北京老陈令): 上条只把末条 user 移到尾部, other_users
#   仍全堆在 trimmed 前, 多 user 注入(delta D1/D3 / 全量 B 路径)trim 后 user/assistant/tool 交错丢失。
#   改为 other_users+trimmed 按 original_order 合并排序保交错; trim_history 传 original_order 入参。
#   无 other_users 时退化为原逻辑(零退化) — 小欧-2026-10-25
# 2026-10-25 小欧 - trim_history 重构为轮次级滑动(北京老陈令, 复用优先不自造): 删自写的
#   _split_into_turns/_trim_by_turn_sliding; 改调 compaction.find_tail_start(align_turn=True,
#   切点对齐 user 边界整轮不拆) + remove_dangling_tool_calls(剪劈开半轮孤儿); 替代原"分桶裁剪
#   (user 永保只裁 FC 对)"导致的悬空 user 堆积(实测 39 任务会话裁后 14 user 连续悬空); 局部 import 防循环依赖 — 小欧-2026-10-25
# 2026-10-25 23:09 小欧 - trim_history 触发基准改预算口径(北京老陈定): 绝对值触发基准由 MAX_CONTEXT_TOKENS 改 budget_base(=MAX_CONTEXT_TOKENS-_compaction_buffer-_tools_token_reserve, 与裁剪预算同源单口径), TRIM_TRIGGER_RATIO 默认 0.75→0.9, 预算单点计算供触发与 find_tail_start 共用删重复 _budget — 小欧-2026-10-25
# 2026-10-25 23:55 小欧 - trim_history 三项加固(北京老陈令): ①over-trim bug 修复 tail_start 改队列拆分(实测 max 每次丢 15~19 万 tok 预算允许上下文, keep_recent_rounds 是"留至少 N 轮"非"只留 N 轮"); ②接 C2 truncate_oversized_message 裁前截断 >4000 字符超长单条(防单条 tool 结果超出预算致整轮丢弃); ③接 C3 CompactionCooldown 重复触发抑制(修复后 rebuilt≈budget_base>触发阈值致每轮无可裁, cooldown 抑制 N 轮内重复进入, rough>budget_base 强制裁剪防 400) — 小欧-2026-10-25
# 2026-10-25 小欧 - 信号计算与裁剪逻辑分离: ①_trim_signal() 抽为独立函数返回 bool, 结果存 _trim_signal_result; ②信号计算移至调用方(react_step: 先 _trim_signal 判信号, 触发后调 trim_history); ③trim_history 仅读信号结果做裁剪不再算信号; ④术语统一(水位→阈值调节系数/倒挂→重复触发抑制/空转→无可裁/溢窗→窗口溢出/拦→抑制/强裁→强制裁剪; budget_base=裁剪预算, TRIM_TRIGGER_RATIO=阈值调节系数, 乘积=触发阈值) — 小欧-2026-10-25
# 2026-10-26 小欧 - 三堂会审修复(北京老陈令): ①删 backward 兼容(信号计算回退) trim_history 只读信号不算信号(禁止backward); ②user 边界对齐移入 fallback 分支(原在两分支后是死代码); ③protected 删重复计算; ④count_system_prefix 消除 prefix 三处重复(DRY); ⑤"头部保护区"→"头部"(术语修正); ⑥_trim_signal docstring 删错误初始值版(矛盾信息) — 小欧-2026-10-26
# 2026-10-26 小欧 - 队列预算公式改(北京老陈令): budget_for_queue = budget_base × trigger_ratio² - 保护区token(原 budget_base - 保护区token), 队列只能用触发阈值再乘系数后的剩余预算; 保护区/预算链注释同步更新 — 小欧-2026-10-26
# 2026-10-29 小欧 - trim_history 队列幸存者语义替换收口(北京老陈令"接上吧"): 保留旧轮 tool 消息 _summary 换一行真摘要, 同日三堂会审终态修订: ①新换条数对比 swap 前旗数只计本轮(上一轮旧旗不再谎报"换摘要N条"); ②无裁剪且零新换保留原历史直接返回(不重建/不动裁剪旗/不复位冷却, 杜绝幻影重建); ③未裁剪分支不跑 remove_dangling_tool_calls("保留原历史"下禁止静默动刀, 实测孤儿 assistant 被无声删除); swap 门槛 USE_SUMMARY_MIN_CHARS=300 归 compaction_constants — 小欧-2026-10-29
# 2026-10-29 小欧 - 保护区轮数改唯一解析(北京老陈令断案"系统路径整体最佳"): _keep_recent_rounds 由原地夹取算式改调 split_turn.resolve_protect_rounds(), 与 start_step 注入件尾部轮数同源单一真源(tuning.trim.keep_recent_rounds, clamp 5~20, 默认5=5零行为变化); KEEP_RECENT_ROUNDS 本域导入摘除(解析下沉 split_turn, 死导入清除) — 小欧-2026-10-29
# 2026-10-29 小欧 - 魔法数字清账(北京老陈令): get_last_tool_summary 纠偏预览截长 200→TOOL_SUMMARY_PREVIEW_CHARS, _trim_signal 过短历史下限 5→TRIM_MIN_MESSAGES, trim 兜底上限 _max_rounds*2+5→*TRIM_CEILING_ROUND_FACTOR+TRIM_CEILING_ROUNDS_MARGIN(常量归 compaction_constants), 各值原内联字面量直迁零行为变化 — 小欧-2026-10-29
# 2026-10-29 小欧 - trim_history 队列剩余段接 C2 use_tool_summary(北京老陈令"接上吧"): 裁剪后仍保留的旧轮里, tool 消息有 _summary 且 content 更长者整条换一行语义摘要(原文存_raw); 逐条浅拷贝隔离(mutate 原地字典, 防污染 conversation_history 与保护区引用); 保护区(最近N轮)零接触保保真; 与保头截断同批共存(先截后换兼容: _truncated 不阻塞 swap, _compressed 才跳过); 跨任务重载历史无 _summary 属已知边界不重灌 — 小欧-2026-10-29
# 2026-10-30 小欧 - 三堂会审撤销接线(北京老陈令, 实测取证后裁定): 队列幸存者语义替换(use_tool_summary)从 trim_history 摘除。
#   取证: 全库工具 llm_data.summary 均为一行状态/计数(read_text_file.py:142 "读文件X，成功：40行，2048字节"、
#   search_files.py:105 命中数、read_docx.py:74 段数字符数), 不含正文; 实测 1898 字符观察(含 40 行文件正文)
#   被换成 48 字符状态行, 正文本轮内不可见且留"读过了"误导痕迹。保留 c2 的另三处修复: 无裁剪即保留原历史
#   (不重建/不动裁剪旗/不复位冷却)、未裁剪不跑 remove_dangling_tool_calls、裁剪分支照旧。_summary stash
#   继续保留(get_last_tool_summary 死循环纠偏消费), 不再用于改写 tool content — 小欧-2026-10-30
# 2026-10-30 小欧 - 三堂会审收尾(北京老陈令): ①get_last_tool_summary 改 content 优先 —— 工具 _summary 只是
#   一行状态/计数, 优先它会让死循环纠偏提示失去"上次到底返回了什么"的判据, 改回改造前实际生效行为(content
#   为空才回退 _summary); ②新增 keep_full_raw 单点(DRY): prune 两处与 split_turn 一处的"原文存 _raw"
#   同构写入收口, 统一"只保留最长者"守卫(split_turn 二次截断原会把全文 _raw 吃成截断头, 违反其 docstring) — 小欧-2026-10-30
# 2026-10-30 小欧 - 三堂会审二轮(北京老陈令"坐实问题再修"): trim_history 队列预算不足分支修复 —— 原 else 在
#   "未溢窗但 阈值×系数² 预算不够"时直接 tail_start=keep_from 走"丢光队列", 与本文档第 6 条"预算不足保留原历史"
#   相反(实测 12 个旧轮一次清空/51 条→只留保护区); 拆为 溢窗分支(行为不变, 注释订正) + 退回硬剩余预算判定 — 小欧-2026-10-30
# 2026-10-30 小欧 - 新增 ensure_file_ref_rules(): 插话带引用时 system 消息早已建好, 需幂等补注
#   【文件引用】格式约定(否则模型看到引用正文却不知 [[文件:...]] 输出约定); 标记位 _file_ref_rules_injected
#   由 init_history/reset_per_run 同步维护, 保证整个会话内规则最多出现一次 — 小欧-2026-10-30
# 2026-10-31 小欧 - DEFAULT_CONTEXT_LIMIT 导入源改 app.constants(常量自 compaction_constants 迁入系统层,
#   单一真源), 值与行为零变化 — 小欧-2026-10-31
"""
MessageBuilder — conversation_history 状态管理器

将分散在 base_react.py 和 react_agent_mixin.py 中的
conversation_history操作集中管理。

无状态工具函数已迁入 message_utils.py,遵循 SRP。

【生命周期与会话绑定说明 — 小沈 2026-05-20】:
MessageBuilder 实例生命周期必须与 Agent 实例强绑定,
严禁全局共享单例,防止多会话并发状态污染。

【FC-only重构 — 小沈 2026-06-11】:
- 删除 add_assistant / flush_temp_to_history / add_parse_error
- _append_observation 只存FC协议格式(role=assistant tool_calls + role=tool)
- _trim_to_budget 统一裁剪,按原始顺序重排
"""

import json
from typing import Any, Dict, List, Optional

from app.config import get_config  # 小欧 2026-07-08
from app.logger import logger  # 小欧 2026-07-01: 裁剪日志
from app.constants import DEFAULT_CONTEXT_LIMIT  # 2026-10-31 小欧: 常量迁系统层 app/constants.py(单一真源), 自 compaction_constants 迁出
from app.services.agent.compaction_constants import (  # 2026-08-17 小健: 压缩/裁剪常量权威迁本域, 改自 app.constants 导入
    COMPACTION_BUFFER, CHARS_PER_TOKEN, COOLDOWN_ROUNDS, TEMP_HISTORY_CHAR_LIMIT, TRIM_TRIGGER_RATIO,
    TOOL_SUMMARY_PREVIEW_CHARS,     # 2026-10-29 小欧: 死循环纠偏预览截长(魔法数字清账)
    TOOLS_TOKEN_RESERVE,
    TRIM_CEILING_ROUND_FACTOR,      # 2026-10-29 小欧: 裁剪兜底上限公式系数(魔法数字清账)
    TRIM_CEILING_ROUNDS_MARGIN,
    TRIM_MIN_MESSAGES,
)
from app.services.agent.fc_message_types import (
    FcMessage, SystemMessage, UserMessage, AssistantMessage, ToolResultMessage, ToolCall,
    message_to_dict, dict_to_message,
)
from app.services.refs.render import render_refs_block  # 2026-10-30 小欧 A19: 渲染区块迁 refs 域, 首发/插话共用

# 2026-10-13 小欧 - 文档[28] 4.1.6: 输入框引用渲染为「【引用】」区块。
#   设计要点：
#   ① 显式标注「以下为不可信数据」边界(S7/prompt injection 防护)：文件内容里的文字
#      一律当材料看，不得当指令执行；
#   ② 每条带来源/路径/行号，Agent 才可能回答"依据是第几行"；
#   ③ kind 白名单外的条目直接忽略(不把未知来源塞进上下文)；
#   ④ 正文原样透传，**不截断不降级**(v3.4 裁定：引用多少发多少)。
#   2026-10-30 小欧 A19: 渲染实现已迁 services/refs/render.py(首发/插话共用), 本模块只调用。

# 2026-10-13 小欧 - 北京老陈裁定：文件引用格式约定**条件注入系统提示**，禁止常驻。
#   实测常驻成本 88 token，占整份系统提示 70.3%（125 token 中占 70）。改为：
#   仅当本轮 refs 非空（即用户在文件页点过「发送到输入框」）时，随本轮 sys_prompt 追加，
#   平时零成本。放在 system 角色而非 user 消息里 —— 它是行为准则，不是用户的话。
_FILE_REF_RULES = """【文件引用】
- 回答中若需要指明依据，用固定标记输出，路径必须是相对项目根的相对路径：
  [[文件:<相对路径>]] —— 整份引用
  [[文件:<相对路径>#L12-L20]] —— 引用某一段(行号区间)
  不要写成裸路径或 markdown 链接，前端会把它渲染成可点击的卡片。"""


class MessageBuilder:
    """conversation_history 唯一状态管理器 — 组装/存储/裁剪/准备

    ═══════════════════════════════════════════════════════════════
    assistant 消息进 conversation_history 的四种形态（DeepSeek实测）
    ═══════════════════════════════════════════════════════════════

    (a) Action 轮（调工具）── add_assistant_tool_call
        content=_fc.get("llm_content","") or None  → "" or None = None
        reasoning=_fc.get("llm_reasoning","") or None
        DeepSeek 调工具时 SSE 不发射 content 块（仅 reasoning_content→tool_calls），
        full_content="" → llm_content="" → content=None → model_dump(exclude_none=True) 排除。
        存入 history：{"role":"assistant", "tool_calls":[{...}]}
        → content 和 reasoning_content 都不进 history。

    (b) Answer 轮（最终回答）── add_assistant_message(content)
        content = full_content（LLM 的非推理文本）
        存入 history：{"role":"assistant", "content":"最终答案文本"}

    (c) Reasoning-only（thought-only）── 直接 append（answer_handler.py:172-178）
        parsed["reasoning"] 有值、parsed["content"] 为空 → 推理链注入供下轮续写。
        content 显式写 ""（非 None，不触发 exclude_none），带 _temp_reasoning 标记。
        存入 history：{"role":"assistant", "content":"", "reasoning":"...", "reasoning_content":"...", "_temp_reasoning":true}
        持久化前由 pop_temp_messages() 弹掉 _temp_reasoning 标记消息。

    (d) 异常/警告轮 ── B3 空转/未调工具/error/unknown 等
        存入 history：{"role":"assistant", "content":"[硬编码警告/错误文本]"}

    一句话：action 轮只存 tool_calls，content 和 reasoning_content 都不进 history。
            content（thought）仅在 answer / reasoning-only / 异常三种情况进 history。
    — 小欧 2026-07-22
    """

    def __init__(self, max_context_tokens: int = DEFAULT_CONTEXT_LIMIT):
        self.conversation_history: List[Dict[str, Any]] = []
        self.temp_history: List[Dict[str, Any]] = []
        self.MAX_CONTEXT_TOKENS = max_context_tokens
        self._max_rounds: int = get_config().get_max_rounds()  # 最多保留FC轮数(默认100) — 小欧 2026-07-08
        self._trim_trigger_ratio: float = float(get_config().get('tuning.trim.trigger_ratio', TRIM_TRIGGER_RATIO))  # 小欧 2026-09-23 trim配置化
        self._compaction_buffer: int = int(get_config().get('tuning.trim.compaction_buffer', COMPACTION_BUFFER))  # 小欧 2026-09-23 trim配置化
        self._tools_token_reserve: int = int(get_config().get('tuning.trim.tools_token_reserve', TOOLS_TOKEN_RESERVE))  # 2026-10-25 小欧 预算预留tools定义token
        # 2026-10-29 小欧 保护区轮数改唯一解析(北京老陈令断案): 与 start_step 注入件尾部轮数同源单一真源(split_turn.resolve_protect_rounds), 原地夹取算式收敛
        from app.services.agent.compaction.split_turn import resolve_protect_rounds  # 局部 import 防循环依赖(split_turn 顶层依赖本模块)
        self._keep_recent_rounds: int = resolve_protect_rounds()  # 最近N工具步硬保护(北京老陈令), 5-20 默认5
        # 重复触发抑制: 触发后 rough≤budget_base 时 find_tail_start 无可裁, cooldown 抑制 N 轮内重复进入 — 小欧 2026-10-25
        from app.services.agent.compaction.trigger import CompactionCooldown  # 局部 import 防循环依赖(compaction 依赖 message_builder)
        self._trim_cooldown = CompactionCooldown(cooldown_rounds=COOLDOWN_ROUNDS)
        self._trim_signal_result: Optional[tuple] = None  # 信号结果缓存, _trim_signal() 写入, trim_history() 读取 — 小欧 2026-10-25
        self.last_total_tokens: Optional[int] = None  # 上一轮 LLM 返回的精确 total_tokens（Provider 返回），用于增量触发 — 小欧 2026-07-22
        self._msg_id_counter: int = 0  # 自增计数器(文件B 去重单点化) — 小欧 2026-08-23
        # B组(锚演进 2026-09-20 小欧): user_message_id 锚单点——合成计数器(未传时自减负id, 与DB正id不冲突) + 当前锚
        self._synth_user_msg_id: int = 0
        self._current_user_msg_id: Optional[int] = None
        # 文件引用格式约定是否已进 system 消息(插话补注去重标记) — 小欧 2026-10-30
        self._file_ref_rules_injected: bool = False

    @property
    def current_user_msg_id(self) -> Optional[int]:
        """当前轮 user 消息真实 uid 锚(只读) — 小欧 2026-09-28 设计文档[76] 6.3
        此前只有私有 _current_user_msg_id, 而 agent_runner 用 getattr(mb, 'current_user_msg_id', None)
        取值恒为 None → 9-20 的锚回填与 D-1 两个修复因此从未生效(注入消息 task_id 恒 NULL)。
        补公开只读口(封装, 禁外部直读私有); 属性名保持与读取方一致(修根因)。"""
        return self._current_user_msg_id

    def reset_per_run(self) -> None:
        """每次 run_react_cycle 仅重置 conversation_history,缓存和计数保留跨会话"""
        self.conversation_history = []
        self.temp_history = []
        self.last_total_tokens = None  # 2026-07-22 - 小欧 - 修复: 清除上一轮残留, 增量裁剪从零开始
        self._trim_cooldown.mark_compacted()  # 2026-10-25 小欧 每 run 重置冷却计数, 新 run 不继承上轮冷却状态
        self._trim_signal_result = None  # 新 run 信号结果清空, 下次 _trim_signal() 重算 — 小欧 2026-10-25
        self._file_ref_rules_injected = False  # history 清空后标记位失效, 下次 init_history 重新判定 — 小欧 2026-10-30

    # =========================================================================
    # 第一组:conversation_history 写操作(统一入口)
    # =========================================================================

    def add_system_message(self, content: str) -> SystemMessage:
        """添加system消息 — 北京老陈 2026-06-25"""
        msg = SystemMessage(content=content)
        self.conversation_history.append(message_to_dict(msg))
        return msg

    def add_user_message(self, content: str, *, user_message_id: Optional[int] = None) -> UserMessage:
        """添加user消息 — 北京老陈 2026-06-25 — B组锚演进 2026-09-20 小欧
        user_message_id 锚: 显式传入(真实落库uid)则用之并演进 _current_user_msg_id(供回填);
        未传(注入吸收/init_history)自动合成负id占位锚(防漏wire一致性), 但**不演进** _current_user_msg_id,
        避免 agent_runner 终态回填用合成负 id 对 chat_user_message UPDATE 命中 0 行(空操作)。
        锚演进单点: 仅真实 uid 更新 _current_user_msg_id"""
        msg = UserMessage(content=content)
        if user_message_id is None:
            self._synth_user_msg_id -= 1
            user_message_id = self._synth_user_msg_id
        else:
            self._current_user_msg_id = user_message_id
        d = message_to_dict(msg)
        d["user_message_id"] = user_message_id
        self.conversation_history.append(d)
        return msg

    def add_assistant_tool_call(self, tool_calls: list,
                                content: Optional[str] = None,
                                reasoning: Optional[str] = None) -> AssistantMessage:
        """添加assistant工具调用消息 — 北京老陈 2026-06-25

        配对说明:
          此assistant(带N个tool_calls)与后续N条tool(通过tool_call_id关联)组成一对。
          调用顺序: add_assistant_tool_call → add_tool_result x N
          LLM收到的历史: ...→assistant(tool_calls=[id1,id2])→tool(id1)→tool(id2)→...
        — 小欧 2026-07-12 — 小欧 2026-07-19 新增 reasoning 参数: 存入 LLM 推理链到 conversation history
        """
        msg = AssistantMessage(content=content, tool_calls=tool_calls, reasoning=reasoning)
        self.conversation_history.append(message_to_dict(msg))
        return msg

    def add_tool_result(self, tool_call_id: str, content: str, summary: str = "") -> ToolResultMessage:
        """添加工具执行结果消息 — 北京老陈 2026-06-25

        与add_assistant_tool_call配对使用:
          每条tool通过tool_call_id关联回assistant中的某一条tool_call.id。
          同一轮的所有tool共用同一个assistant父消息。
        — 小欧 2026-07-12 — 小欧 2026-07-13 防御: 构造/序列化失败也兜底追加最小合法tool消息, 保证工具结果绝不丢失
        — 小健 2026-08-17 (14.9.6 C2 前置): 新增 summary 形参, 工具层 llm_data.summary 透传 stash 为 _summary,
          供 compaction.use_tool_summary 复用(DRY); 内部标记由 prepare_messages_for_llm 与 _temp_* 同段剥离。
        """
        try:
            msg = ToolResultMessage(content=content, tool_call_id=tool_call_id)
            d = message_to_dict(msg)
            if summary:
                d["_summary"] = summary          # 供 compaction.use_tool_summary 读取; 内部标记由 prepare_messages_for_llm 剥离
            self.conversation_history.append(d)
            return msg
        except Exception as e:
            logger.warning(f"[message_builder] add_tool_result构造失败(tool_call_id={tool_call_id}): {type(e).__name__}: {e!r}")
            # 兜底: 直接追加最小合法tool消息, 保证对话历史完整(结果不丢失) — 小欧 2026-07-13
            d = {
                "role": "tool",
                "content": content,
                "tool_call_id": tool_call_id,
            }
            if summary:
                d["_summary"] = summary          # 兜底分支同步 stash, 防 use_tool_summary 空转
            self.conversation_history.append(d)
            return None

    def init_history(self, sys_prompt: str, task_prompt: str,
                     refs: Optional[list] = None) -> None:
        """初始化conversation_history — 替代base_react.py L368-369

        2026-10-13 小欧 - 文档[28] 4.1.6: refs(输入框引用) 正文拼在 task_prompt **之前**，
        并带"不可信数据"边界声明(S7)。refs 为空时行为与原来完全一致(零退化)。

        同批：文件引用格式约定按 refs **条件注入本轮 sys_prompt**（不常驻，见 _FILE_REF_RULES 注释）。
        无 refs 时 sys_prompt 与改造前逐字节一致。
        """
        if not task_prompt or not task_prompt.strip():
            raise ValueError("task_prompt不能为空")
        self._file_ref_rules_injected = bool(refs)   # 与 ensure_file_ref_rules 共用标记, 防插话重复注入 — 小欧 2026-10-30
        if refs:
            sys_prompt = f"{sys_prompt}\n\n{_FILE_REF_RULES}"
        self.conversation_history = []
        self.add_system_message(sys_prompt)
        self.add_user_message(render_refs_block(refs) + task_prompt)

    def ensure_file_ref_rules(self) -> None:
        """幂等把【文件引用】格式约定补进当前 system 消息(已注入过则跳过) — 小欧 2026-10-30

        为什么需要: 首轮由 init_history 按 refs 条件注入; 中途插话(interject)带引用时
        system 消息早已建好, 既不能重发整份 sys_prompt, 也不能每插一次追加一遍规则。
        故以标记位收口, 保证整个会话内规则最多出现一次。
        无 system 消息时(极端历史形态)插到最前, 保持"行为准则属于 system 角色"的约定。
        """
        if self._file_ref_rules_injected:
            return
        for msg in self.conversation_history:
            if msg.get("role") == "system":
                msg["content"] = f"{msg.get('content') or ''}\n\n{_FILE_REF_RULES}"
                self._file_ref_rules_injected = True
                return
        self.conversation_history.insert(0, {"role": "system", "content": _FILE_REF_RULES})
        self._file_ref_rules_injected = True

    def inject_history(self, history_msgs: List[Dict]) -> None:
        """注入多轮对话历史到 system 和 task 之间 — 小欧 2026-07-02

        封装 history_msgs 插入 conversation_history 的列表操作：
        - history >= 2：[:1] + history_msgs + [1:]（system 之后、task 之前插入）
        - 否则：history_msgs + 现有（兜底追加）

        不转换消息格式，调用方负责构建好 history_msgs（如去掉最后一条 user 避免与 task 重复）。
        """
        if not history_msgs:
            return
        if len(self.conversation_history) >= 2:
            self.conversation_history = (
                self.conversation_history[:1]
                + history_msgs
                + self.conversation_history[1:]
            )
        else:
            self.conversation_history = history_msgs + self.conversation_history

    def _append_observation(self, observation_text: str, fc_context: Dict) -> None:
        """追加FC协议observation消息 — fc_context必传 — FC-only重构 2026-06-11 小沈
        北京老陈 2026-06-25: 使用类型安全方法替代原始message_to_dict调用

        FC协议要求: assistant(tool_calls)必须在role:tool之前,且每个tool_call_id唯一。
        始终添加assistant消息,确保配对完整。重复tool_call_id跳过assistant以避免重复。
        """
        tool_call_id = fc_context.get("tool_call_id", "")
        tool_calls = fc_context.get("tool_calls", [])
        # 检查是否已有相同tool_call_id的assistant消息(并行工具调用场景)
        has_existing_assistant = any(
            msg.get("role") == "assistant" and
            any(tc.get("id") == tool_call_id for tc in (msg.get("tool_calls") or []))
            for msg in self.conversation_history
        ) if tool_call_id else False
        if tool_calls and not has_existing_assistant:
            llm_content = fc_context.get("llm_content", "") or None
            llm_reasoning = fc_context.get("llm_reasoning", "") or None  # 2026-07-19 小欧 新增reasoning传递
            self.add_assistant_tool_call(tool_calls, content=llm_content, reasoning=llm_reasoning)
        elif tool_call_id and not has_existing_assistant:
            self.add_assistant_tool_call([])
        elif not has_existing_assistant:
            llm_content = fc_context.get("llm_content", "") or ""
            llm_reasoning = fc_context.get("llm_reasoning", "") or None  # 2026-07-19 小欧 新增reasoning传递
            self.add_assistant_tool_call([], content=llm_content, reasoning=llm_reasoning)
        self.add_tool_result(tool_call_id, observation_text)

    def add_observation(self, observation_text: str, fc_context: Dict) -> None:
        """添加observation — 裁剪统一在 _process_single_step — 小欧 2026-07-01"""
        self._append_observation(observation_text, fc_context)

    def get_last_tool_summary(self) -> str:
        """返回末条 role:tool 消息的摘要(content 优先, 回退 _summary, 截 TOOL_SUMMARY_PREVIEW_CHARS) — 小欧 2026-10-24 / 2026-10-30 改序
        供死循环纠偏注入: 让 LLM 看到上一次工具的具体返回, 判断为何不应再调同一工具。
        2026-10-30 小欧: 原 _summary 优先是反的 —— 全库工具 llm_data.summary 均为一两行状态/计数
        ("读文件X,成功:40行"), 优先它等于让纠偏提示只说"成功"、丢掉"到底返回了什么"这一判据,
        故改为 content 优先、content 为空才回退 _summary(即改造前实际生效行为)。"""
        for msg in reversed(self.conversation_history):
            if msg.get("role") == "tool":
                summary = msg.get("content") or msg.get("_summary") or ""
                if len(summary) > TOOL_SUMMARY_PREVIEW_CHARS:
                    summary = summary[:TOOL_SUMMARY_PREVIEW_CHARS] + "..."
                return summary
        return ""

    @staticmethod
    def keep_full_raw(msg: Dict[str, Any], raw: str) -> None:
        """把被裁剪/压缩前的原文写入 msg["_raw"], 只保留最长者 — 小欧 2026-10-30

        压缩/裁剪链路上多处都会写 `_raw`(prune 语义替换与保头截断、split_turn 超长截断),
        若逐处只写不判, 同一条消息被二次处理时 `_raw` 会被后一次的"已截断文本"覆盖, 全文丢失。
        收口为单点: 已有更长的 `_raw` 则不动。"""
        if raw and len(raw) > len(msg.get("_raw") or ""):
            msg["_raw"] = raw

    def add_assistant_message(self, content: str) -> AssistantMessage:
        """追加assistant最终回答到conversation_history — 2026-06-25 小欧 J-1修复: 封装统一入口
        北京老陈 2026-06-25: 返回类型化AssistantMessage对象"""
        msg = AssistantMessage(content=content)
        self.conversation_history.append(message_to_dict(msg))
        return msg

    def pop_temp_messages(self) -> int:
        """移除 conversation_history 中所有 _temp_* 标记的临时消息(兼容 _temp_reasoning/_temp_same_tool_warn),返回移除数量 — 小欧 2026-07-19 / 2026-08-08 扩展通用前缀
        【要点】推理空转(thought-only)临时推理(标记_temp_reasoning)与相同工具纠偏(标记_temp_same_tool_warn)均经此清理:
        好的分支注入时带标记, 终端路径调用本方法弹掉再持久化; bad分支不注入故无需清理
        【v1.6扩展】判断条件由仅_temp_reasoning改为通用_temp_*前缀, 杜绝后续新增_temp_*标记漏清理(进化不退化)
        【修正】必须移除全部标记消息(非仅尾部): 因B3 warning(无标记)会插在连续reasoning-only轮之间, 仅弹尾部会遗留被B3隔开的早期标记推理"""
        removed = 0
        kept = []
        for _m in self.conversation_history:
            if any(k.startswith("_temp_") for k in _m):
                removed += 1
            else:
                kept.append(_m)
        self.conversation_history = kept
        return removed


    # =========================================================================
    # 第二组:每轮 LLM 调用的消息组装
    # =========================================================================

    def prepare_messages_for_llm(self) -> List[Dict[str, Any]]:
        """准备发给LLM的完整消息列表 — 合并原split+merge+assemble

        不再拆出last_message再拼回,整个history作为一个List[Dict]贯穿流程。
        注入点(tools/summary/schema)在第一个非system消息前或末尾操作。

        MSG-001 小沈 2026-05-24: temp_history加入字符容量限制,从最旧开始移除
        """
        # temp_history容量保护:总字符超50000时从最旧截断,再构建messages
        self._cap_temp_history()
        # 惰性补 _msg_id(单点): conversation_history 内尚未打标的消息在此统一分配自增 id;
        # dict 引用全程稳定(trim/inject/rebuild 不复制), 补一次永久携带; 新增消息每轮被此处兜住
        # — 单点化(北京老陈 裁定:A/B 独立化最小侵入) — 小欧 2026-08-23
        for _m in self.conversation_history:
            if "_msg_id" not in _m:
                _m["_msg_id"] = self._msg_id_counter
                self._msg_id_counter += 1
        messages = [dict(msg) for msg in self.conversation_history]   # 浅拷贝防篡改 — 小欧 2026-07-19
        if self.temp_history:
            messages = messages + [dict(msg) for msg in self.temp_history]
        # 剥离内部标记防止泄漏到 LLM 请求(_temp_reasoning/_temp_same_tool_warn) — 小欧 2026-07-19 / 2026-08-08 通用前缀
        # 2026-08-17 - 小健 - S5(compaction): 一并剥离 compaction 内部标记(_summary/_pruned/_compressed/_raw/_truncated),
        #   因 _pruned/_summary 现为短下划线而非 _temp_ 前缀(compaction 模块落地备用后这些标记留 bool/短名前缀),
        #   统一在此浅拷贝后清空, 防泄漏 LLM 请求/污染 wire(对齐 14.9.3③/14.9.6 C2 剥离要求)。纯剥离不存在的字段零影响。
        # 2026-09-20 - 小欧 - B组(锚演进): 一并剥离 user_message_id(锚), conversation_history 源保留锚供 assistant 回复配对落库,
        #   wire 层不携带该内部锚(对齐 __all__ 同源锚演进)。自检: 剥离后 message 纯 payload 无内部锚 — SRP(锚=状态域, wire=传输域)
        _COMPACTION_TEMP_KEYS = ("_summary", "_pruned", "_compressed", "_raw", "_truncated", "user_message_id")
        # 2026-10-05 - 小欧 - wire 推理字段去冲突: 内部字段 reasoning 提升为 API 标准 reasoning_content(单次改名,
        #   同 message_to_dict 规则)后删除; 空 reasoning_content 不上线。服务商拒绝同一消息并存两个推理字段(见文件头)。
        for msg in messages:
            for _k in [k for k in msg if k.startswith("_temp_") or k in _COMPACTION_TEMP_KEYS]:
                msg.pop(_k, None)
            if msg.get("reasoning") and not msg.get("reasoning_content"):
                msg["reasoning_content"] = msg["reasoning"]
            msg.pop("reasoning", None)
            if not msg.get("reasoning_content"):
                msg.pop("reasoning_content", None)
        # 发送即清: 本轮发送的_temp_*临时消息(纠偏/推理)仅活"本轮发送这一次", 已浅拷贝进messages后
        # 由conversation_history源中立即剔除, 防后续轮次/压缩/持久化残留(北京老陈 2026-08-09 指示) — 小欧 2026-08-09
        self.conversation_history = [m for m in self.conversation_history
                                     if not any(k.startswith("_temp_") for k in m)]
        return messages

    def _cap_temp_history(self):
        """对temp_history加字符容量限制(最多50000字符),从最旧条目开始截断"""
        _temp_limit = int(get_config().get('tuning.content.temp_history_char_limit', TEMP_HISTORY_CHAR_LIMIT))  # 小欧 2026-09-23 wiring假保存修复
        while self._total_chars(self.temp_history) > _temp_limit and len(self.temp_history) > 1:
            self.temp_history.pop(0)

    # =========================================================================
    # 第三组:历史裁剪
    # =========================================================================

    # 裁剪信号(3触发 + 1守卫):
    #   | # | 条件 | 代码 |
    #   |---|------|------|
    #   | 1 | 增量触发 | rough - last_total_tokens > COMPACTION_BUFFER |
    #   | 2 | 绝对值触发 | rough > budget_base × 0.9 |
    #   | 3 | 消息数兜底 | msg_count > MAX_ROUNDS × 2 + 5 |
    #   | 守卫 | 新任务不裁 | msg_count <= 5 → return False |
    # 裁剪后达标标准(6条):
    #   | # | 标准 | 实现方式 |
    #   |---|------|----------|
    #   | 1 | 预算合规 | find_tail_start 从尾部累加到预算就停（隐式） |
    #   | 2 | FC 配对完整 | remove_dangling_tool_calls 剔除孤儿（显式） |
    #   | 3 | 最近 N 轮硬保护 | find_recent_rounds_start 确定保护区起点（显式） |
    #   | 4 | 切点对齐 user | find_tail_start(align_turn=True)（显式） |
    #   | 5 | system 恒首 | prefix 处理（隐式） |
    #   | 6 | 超长截断 | truncate_oversized_message 裁前截 >4000 字符（显式） |
    def _trim_signal(self) -> bool:
        """裁剪信号计算: 判断是否触发裁剪 — 小欧 2026-10-25

        三个触发条件(任一为真即 True):
        - 增量触发: 本轮粗估 - 上轮精确(last_total_tokens) > COMPACTION_BUFFER
        - 绝对值触发: 粗估 > 触发阈值(裁剪预算 × 阈值调节系数, 默认0.9)
        - 消息数兜底: msg_count > MAX_ROUNDS×2+5

        msg_count 计数规则:
          = conversation_history 列表长度, 每个消息对象(role 字段 dict)计 1 条
          消息类型        来源
          system          注入的 system prompt
          user            任务提问 + 注入历史 + inbox 吸收
          assistant       每轮 LLM 响应(含 tool_calls)
          tool            每个工具执行结果
          一轮可产生多条: 1 assistant + N tool(N=并行调用数)
          非: ReAct 轮次数, 非 token 数

        msg_ceiling = MAX_ROUNDS×2+5
          按每轮~2条(1 assistant + 1 tool) + 5 条开销粗估, 非精确映射
       
        进入本信号函数的 msg_count 初始值:
            link 任务(有历史注入): 1(system) + N(注入历史条数) + 1(任务提问)
            例: 10轮历史注入(~30条) → msg_count ≈ 32, guard 不拦, 信号计算正常走
            非 link 任务: 2=(system + 任务提问), guard 拦(msg_count ≤ 5), 前几轮不裁剪
            累积至 msg_count > 5 后才放行信号计算
      
        裁剪预算(budget_base) = MAX_CONTEXT_TOKENS - _compaction_buffer - _tools_token_reserve
        阈值调节系数(TRIM_TRIGGER_RATIO) = 0.9, 用于两处:
          ① 裁剪入口(触发阈值) = budget_base × ratio (一次方) — 决定何时触发裁剪
          ② 裁剪出口(队列预算) = budget_base × ratio² (二次方) — 决定队列可用预算
        第1轮无 last_total_tokens → 增量条件不成立, 只走绝对值 + 消息数。
        结果存储到 _trim_signal_result, 供 trim_history() 读取。
        返回 True 表示应触发裁剪。
        """
        msg_count = len(self.conversation_history)
        self._trimmed_this_round = False            # 每轮重置(主流程 _trim_signal 必调, 信号不触发时标志不泄漏)
        self._trimmed_tokens_this_round = 0
        if msg_count <= TRIM_MIN_MESSAGES:
            self._trim_signal_result = (False, 0, 0, False, False)
            return False
        rough_current = self._estimate_tokens(self.conversation_history)
        # 预算链: 窗口(262144) - 输出缓冲(20000) - tools预留(30000) = budget_base(212144)
        # 触发阈值 = budget_base × 0.9 = 190930; 队列预算 = budget_base × 0.9² - 保护区token
        budget_base = self.MAX_CONTEXT_TOKENS - self._compaction_buffer - self._tools_token_reserve
        delta_trigger = (self.last_total_tokens is not None and
                         rough_current - self.last_total_tokens > self._compaction_buffer)
        abs_trigger = rough_current > budget_base * self._trim_trigger_ratio
        msg_ceiling = self._max_rounds * TRIM_CEILING_ROUND_FACTOR + TRIM_CEILING_ROUNDS_MARGIN
        signal = delta_trigger or abs_trigger or msg_count > msg_ceiling
        self._trim_signal_result = (signal, rough_current, budget_base, delta_trigger, abs_trigger)
        return signal

    def trim_history(self) -> None:
        """轮次级滑动裁剪 — 调用方信号触发后执行 — 小欧 2026-07-22
        2026-10-25 小欧 重构为轮次级滑动(北京老陈令): user 与回答同轮同进退, 杜绝悬空 user 堆积。

        调用方应先调 _trim_signal() 判断是否触发, 触发后调本方法执行裁剪。

        裁剪流程:
        1. 重复触发抑制: rough≤budget_base 时 cooldown 抑制 N 轮内重复进入; rough>budget_base 接近窗口上限时强制裁剪防 400
        2. 裁前截断 >4000 字符超长单条(truncate_oversized_message), 防止单条 tool 结果超出预算致整轮丢弃
        3. 分区: 保护区=倒数1~N轮(不进裁剪队列), 队列=倒数第N+1及更早(传入find_tail_start), 队列预算=budget_base×系数²−保护区token
        4. 裁剪走 compaction 组合: find_tail_start(align_turn=True) 切点对齐 user 边界整轮不拆 + remove_dangling_tool_calls 清理孤儿 FC 对
        5. 保护区超出预算时仅保留保护区(硬保护, 容忍窗口溢出)
        6. 无旧轮可裁/预算不足时保留原历史直接返回(不重建/不动裁剪旗/不复位冷却); 仅裁剪分支跑 dangling 清理
           (未裁剪时 FC 配对本完整, "保留原历史"语义下禁止静默动刀) — 小欧-2026-10-30
           2026-10-30 细化(三堂会审修复): "预算不足"只对未溢窗成立; 粗估已超 budget_base 的真溢窗场景,
           队列整体让位保保护区(只额外留保护区那轮的提问 user) — 小欧-2026-10-30

        使用方式: 超阈值时裁剪一次, 裁后替换 conversation_history, 后续轮次在裁后历史基础上累积, 再次超阈值则再次裁剪(非每轮触发)
        """
        try:
            if self._trim_signal_result is None:
                return
            signal, rough_current, budget_base, delta_trigger, abs_trigger = self._trim_signal_result
            if not signal:
                return
            msg_count = len(self.conversation_history)  # 日志用

            # 重复触发抑制: 触发后 rough≤budget_base 时 find_tail_start 无可裁, cooldown 抑制 N 轮内重复进入; rough>budget_base 接近窗口上限时强制裁剪防 400 — 小欧 2026-10-25
            if rough_current <= budget_base and not self._trim_cooldown.allow():
                return

            # 复用 compaction 现成函数; 局部 import 防循环依赖(compaction 依赖 message_builder) — 小欧 2026-10-25
            from app.services.agent.compaction.split_turn import find_tail_start, find_recent_rounds_start, truncate_oversized_message, count_system_prefix
            from app.services.agent.compaction.assembler import remove_dangling_tool_calls

            hist = truncate_oversized_message(self.conversation_history)  # 裁前截断 >4000 字符超长单条, 防止单条 tool 结果超出预算致整轮丢弃 — 小欧 2026-10-25
            prefix = count_system_prefix(hist)
            # 最近 N 轮硬保护: 倒数 1~N 轮不进裁剪队列; 倒数第 N+1 轮及更早传入 find_tail_start — 小欧 2026-10-25
            # 保护区 = 从倒数第 N 个 assistant(tool_calls) 起至末尾的全部消息(含其 tool 结果 + 末条 final answer)
            # 保护区 token = estimate_tokens(保护区), 是 budget_base×系数² 的占用量, 队列只能用剩余预算
            keep_from = find_recent_rounds_start(hist, self._keep_recent_rounds)  # 倒数第 N 轮起点(保护区起点)
            protected = hist[keep_from:]  # 倒数 1~N 轮, 不裁
            queue = hist[prefix:keep_from]  # 倒数第 N+1 及更早, 传入裁剪函数
            # 队列预算 = budget_base×系数² - 保护区已占用; 保护区超预算时 budget_for_queue<0, 走 else 分支
            protected_tokens = self._estimate_tokens(protected)
            budget_for_queue = budget_base * self._trim_trigger_ratio * self._trim_trigger_ratio - protected_tokens
            if budget_for_queue > 0 and queue:
                tail_start = prefix + find_tail_start(queue, budget_for_queue, align_turn=True)
            elif rough_current > budget_base and queue:
                # 2026-10-30 小欧 溢窗分支(原 else 的一半, 行为不变, 注释订正): 粗估已超裁剪预算, 属真溢窗,
                #   队列整体让位保保护区 —— 只额外保留"保护区那轮的提问 user", 防有答无问 — 小欧-2026-10-30
                tail_start = keep_from
                j = tail_start
                while j > prefix and hist[j].get("role") != "user":
                    j -= 1
                if j > prefix and hist[j].get("role") == "user":
                    tail_start = j
            else:
                # 2026-10-30 小欧 修复(三堂会审发现, 实测 12 个旧轮被一次清空): 未溢窗、只是"阈值×系数²"
                #   这个偏保守的队列预算不够 → 原 else 直接按"丢光队列"处理, 与本文档第 6 条"预算不足时
                #   保留原历史直接返回"相反, 属过度裁剪。改为退回硬剩余预算(budget_base - 保护区)再判:
                #   留得下就留, 仍留不下才 tail_start=prefix(早退保留原历史) — 小欧-2026-10-30
                remaining = budget_base - protected_tokens
                tail_start = (prefix + find_tail_start(queue, remaining, align_turn=True)
                              if queue and remaining > 0 else prefix)
            # 三段结构:
            #   头部     = hist[:prefix]                 system 消息(保留)
            #   队列剩余 = hist[tail_start:keep_from]   裁剪区后的队列消息(保留)
            #   保护区   = hist[keep_from:]              倒数N轮(保留)
            #   裁剪区   = hist[prefix:tail_start]      旧消息(丢弃)
            #   rebuilt = 头部 + 队列剩余 + 保护区
            # 2026-10-30 小欧 三堂会审撤销接线(北京老陈令): 队列幸存者语义替换(use_tool_summary)已摘除——
            #   实测工具 _summary 只是一行状态/计数, 替换会把长观察正文换成"读文件成功", 信息灭失;
            #   trim 回归"只裁剪、不改写保留消息"的原语义 — 小欧-2026-10-30
            if tail_start <= prefix:
                logger.info(f"[trim_history] 无旧轮可裁或预算不足, 保留原历史({msg_count}条/{rough_current} tokens)")
                return
            rebuilt = hist[:prefix] + hist[tail_start:keep_from] + protected
            rebuilt = remove_dangling_tool_calls(rebuilt)   # 仅裁剪后清孤儿(只有裁剪才可能拆散配对)
            if len(rebuilt) >= 2:
                self.conversation_history = rebuilt
                self._trim_cooldown.mark_compacted()  # 裁剪成功复位冷却计数, 下 N 轮抑制重复触发 — 小欧 2026-10-25
                self._trimmed_this_round = True     # 11.3 实际裁剪置真 — 小欧-2026-08-20
                _trimmed_now = max(0, rough_current - self._estimate_tokens(rebuilt))  # 11.3 裁剪释放的 token 数 — 小欧-2026-08-20
                self._trimmed_tokens_this_round = int(_trimmed_now)
                trigger_reason = "delta" if delta_trigger else "abs" if abs_trigger else "msg_count"
                logger.info(f"[trim_history] 轮次滑动裁剪: {msg_count}条({rough_current} tokens) "
                            f"→ {len(rebuilt)}条(触发: {trigger_reason})")
            else:
                logger.info(f"[trim_history] 重建后不足2条, 保留原历史({msg_count}条/{rough_current} tokens)")
        except Exception:
            logger.warning(f"[trim_history] 异常, 跳过裁剪保留原历史", exc_info=True)

    # 2026-10-25 小欧 删除三个旧裁剪方法(北京老陈令, 禁止backward 死代码):
    #   _classify_messages / _trim_to_budget / _rebuild_and_validate 是"分桶 + user 永保 +
    #   只裁 FC 对"的错误设计(实测致悬空 user 堆积: 39 任务会话裁后 14 user 连续有问无答)。
    #   trim_history 已改调 compaction.find_tail_start(align_turn=True) +
    #   remove_dangling_tool_calls(整轮滑动), 这三个方法生产路径零调用, 删除。— 小欧-2026-10-25

    # =========================================================================
    # 第四组:observation 辅助
    # =========================================================================

    @staticmethod
    def _normalize_observation_prefix(text: str) -> str:
        """确保observation文本以 [Observation] 开头 — 替代 base_react.py 前缀处理"""
        # 【修复 小健 2026-05-24】防止双重[Observation]前缀
        if text.startswith("[Observation]"):
            return text
        for prefix in ["Observation:", "observation:"]:
            if text.startswith(prefix):
                text = text[len(prefix):].strip()
                break
        # 去掉前缀后再次检查,避免双重
        if text.startswith("[Observation]"):
            return text
        return f"[Observation] {text}"

    # 2026-10-25 小欧 删除 _is_observation_role / _trim_fc_pairs(北京老陈令):
    #   _is_observation_role 唯一调用方 _classify_messages 已删(分桶错误设计);
    #   _trim_fc_pairs 功能由 compaction.remove_dangling_tool_calls 承接(trim_history 改调它),
    #   生产路径零调用, 删除。— 小欧-2026-10-25

    @staticmethod
    def _total_chars(messages: List[Dict]) -> int:
        """计算消息列表总字符数 — 含tool_calls JSON 与 reasoning

        FC模式下assistant消息content可为None(tool_calls协议),
        但tool_calls包含JSON负载(tool名/参数/id),必须计入预算。
        # 2026-09-20 小欧 D-4修复: reasoning/reasoning_content 一并计入——
        DeepSeek 推理模型长 reasoning 若不计量, 预算被严重低估(20K字符估算=0), 上下文越界。
        """
        total = 0
        for msg in messages:
            content = msg.get("content")
            total += len(content) if content is not None else 0
            tool_calls = msg.get("tool_calls")
            if tool_calls:
                total += len(json.dumps(tool_calls, ensure_ascii=False))
            for _rk in ("reasoning", "reasoning_content"):
                _rv = msg.get(_rk)
                if _rv:
                    total += len(_rv)
        return total

    @staticmethod
    def _estimate_tokens(messages: List[Dict]) -> int:
        """纯数学估算 token 数 — chars/CHARS_PER_TOKEN(2.25, 中文主导, 2026-10-25 真实会话标定), 零外部依赖

        对标 OpenCode Token.estimate / Hermes estimate_tokens_rough
        2026-10-04 小欧: 系数 4→1.8→2.5(当日两次); 浮点系数下 // 返回 float, 故恒用 int(x / c) 显式取整
        """
        return int(MessageBuilder._total_chars(messages) / CHARS_PER_TOKEN)

