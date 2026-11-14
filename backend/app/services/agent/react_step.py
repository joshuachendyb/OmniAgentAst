# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-01 chendyg 状态集中管理重构v2
#   - 状态用 status_table, 数据 handler 自己写
#   - _dispatch_handler 基于 event type 推断状态
#   - handler 保留 add_observation/add_assistant_message, 不绕路
# 2026-07-17 小沈 FC重命名: import/LLMResponseError同步
# 2026-07-17 小欧 B3扩展+修正: 检测reasoning-only空转并软引导(修正has_tool_results屏蔽使已调工具后仍可警告); 改add_observation→add_assistant_message(避免空tool_call_id孤立tool消息致LLM参数不合法, 参照edca06261昨天修正); warning去具体工具名
# 2026-07-18 小欧 修复: 删llm_client._cancelled死分支
# 2026-07-18 小欧 修复: 更新docstring状态推断规则
# 2026-07-18 小欧 修复: 抽取_EV_FINAL/_EV_RETRY/_EV_ERROR常量
# 2026-07-18 小欧 FinalStep多态自包含终态重构:
#   【病根】原react_cycle中取消/截断/无终态等路径用MetaStep(cancelled)表示终态,
#          与answer_handler的FinalStep(completed)不一致; _dispatch_handler基于event.type位置推断终态,
#          逻辑分散且易遗漏(如空响应路径set_failed但不产出终态step)。
#   【思路】统一终态语义: 所有终态路径改用FinalStep(outcome=xxx),
#          _dispatch_handler改为outcome驱动终态声明(不依赖位置/类型); 可恢复错误仍用ErrorStep。
#   【改法】①场景B/C/D/循环结束无终态: MetaStep(cancelled)→FinalStep(outcome="cancelled")
#          ②_dispatch_handler: 从位置驱动改为outcome驱动(set_failed/set_cancelled/set_completed)
#          ③可恢复错误(ErrorStep)和可恢复拒绝(_RECOVERABLE_ERRORS)保持不变
# 2026-07-18 - 小欧 - 终态判定修复: _dispatch_handler 用循环内单独捕获的 final_event 读 outcome, 不取末事件last_event(末事件未必是final,脆弱); 同时修正过时注释 MetaStep(cancelled)→FinalStep(outcome="cancelled")
# 2026-07-18 - 小欧 - 可恢复异常从外层except移入per-step内层try, continue回卷while真重试, 不再误标failed
# 2026-07-18 - 小欧 - _should_retry_truncated_tool O(n²)嵌套循环→单遍O(n)
# 2026-07-19 小欧 控制台打印修复: if thought→if thought or reasoning(空content有reasoning的action step也能输出)
# 2026-07-19 小欧 推理空转不持久化: _finalize_cycle(finally出口)开头直调agent.message_builder.pop_temp_messages()弹掉残留标记推理再持久化; 落点单一收口(KISS-DIRECT), 生产直调无防御守卫, 测试mock缺message_builder属测试缺陷
# 2026-07-19 小欧 R1优化: B3空转警告(场景C reasoning-only子分支)改幂等注入+复用_temp_reasoning标记收口; 已存在相同标记消息则跳过,杜绝连续空转累积重复警告(history堆积/持久化残留); 终态统一由pop_temp_messages弹掉,零新机制(DRY/KISS); 正常answer无工具分支(else)不变仍持久化
# 2026-07-22 小欧 LLM 响应后提取 usage.total_tokens → message_builder.last_total_tokens，供下轮增量裁剪用
# 2026-07-22 小欧 usage 扩展: 三字段(prompt/completion/total)累加 accumulated_usage; emit MetaStep(type="usage") 逐次报告本次消耗
# 2026-07-22 小欧 MetaStep usage: 从 **_usage 解包改为手动三字段，精确控制输出
# 2026-07-23 小欧 - log_and_print统一: 3处print()替换为log_and_print()(Thought/Error/Cancel控制台输出), 导入log_and_print
# 2026-08-08 小欧 相同工具调用死循环检测(场景F)新增:
#   【病根】超时根因: LLM连续40+步逐字重复同一Thought并反复调用完全相同工具+相同参数
#          (write写同一diff_tool.py), 每次工具均success, 现有_consecutive_reasoning_only仅拦"纯推理无工具
#          调用"空转, 本模式漏检, 致死循环直抵max_steps=10000。
#   【方案】_tool_call_signature计算action调用签名(含并行pending); _check_same_tool_loop返回int连续计数(count=第N次),
#           双阈值: count==2/3/4(_SAME_TOOL_WARN_ROUNDS起)注入user role纠偏消息尝试唤醒, count>=5硬终止failed;
#           签名变化重置count=1+清纠偏标记; 正常任务签名各异零误伤, 增强不退化。
# 2026-08-08 小欧 双阈值实施: 单阈值(bool终止)升级为双阈值(3纠偏+5硬终止), 新增_warn_same_tool_loop
# 2026-08-08 小欧 双阈值调整(北京老陈 2026-08-08 指示"第2次就发纠偏; 2/3/4次发, >=5结束"):
#   - 纠偏: 第2次(count==2)即发第1条(原第3次), 第2/3/4次各发1条共3条(原第3/4次共2条)
#   - 硬终止: count>=5(原count>5第6次, 收紧回第5次)
#   - 实现: _SAME_TOOL_WARN_ROUNDS 3→2, _SAME_TOOL_WARN_MAX 2→3; 判定改 _SAME_TOOL_WARN_ROUNDS<=cnt<5 区间发纠偏,
#     cnt>=5 硬终止; _warned_same_tool_loop 为 int 计数(发纠偏条数, 上限_SAME_TOOL_WARN_MAX),
#     重置/初始化点(签名变化/非action/initialize_run_state)由 False 改 0;
#     deny_counts 让位判断 not _warned_same_tool_loop 真值语义不变(int>0即已发)
# 2026-08-09 - 小欧 - 拆分: 用户暂停阻塞由 task_pause_check(产SSE) 改为
#   wait_for_resume(纯阻塞不产SSE)。原 task_pause_check 在 react_cycle→agent_runner 路径产出的SSE字符串
#   被 agent_runner 以"跳过非Step事件"丢弃(死路); 前端暂停/恢复提示由 openai._stream_with_control 的
#   task_pause_check_and_yield 统一下发(职责单一无重复)。ast语法✓
# 2026-08-09 - 小欧 - task007核查问题A: 相同工具纠偏消息为"面向LLM的反馈指令", role由assistant改为user,
#   文本增强紧迫感(点明"强制终止后果"+要求改工具/直接结束), 强化LLM服从。带_temp_same_tool_warn标记
#   仍受通用_temp_*前缀清除(tool_retry_engine/pop_temp_messages v1.6)保护, 持久化前被pop_temp_messages
#   统一弹掉, 不污染history/压缩。ast语法✓
# 2026-08-10 - 小欧 - R1 实施: finally 新增 clear_temp_auth() (task 级清零点); 授权段移入 try 内(依赖本清零点)
# 2026-08-10 - 小欧 - 任务目录级临时授权确认实施: 复用现有 HITL paused 流(前端零改动): try 内(while 前) 消费 agent._task_auth_paths,
#   create_confirmation → MetaStep(paused, confirm_id, tool_name="task_dir_authorization") →
#   await wait_for_confirmation_result → 确认后批量 grant_temp_auth(recursive=True);
#   落区判定(授权前分流): 系统禁区不授权 / 非系统禁区仅写可授权(删硬拦) / 白名单外入单;
#   异常兜底: 确认超时/拒绝/异常 → 跳过不授权不阻塞, 任务继续(任务内仍可单点工具授权)
# 2026-08-10 - 小欧 - 撤销任务目录级批量授权 (北京老陈 2026-08-10): 「任务中目录解析功能点去掉」—
#   移除 try 内 while 前的任务目录级 HITL 批量授权段(create_confirmation/paused/grant_temp_auth);
#   目录权限全部走 LLM 工具参数路径进临时名单; 保留 R1 clear_temp_auth(task 级清零点); 同步撤销 initialize_run_state 的授权挂载
# 2026-08-10 - 小欧 - 撤销残留清理: 删除死 import HITL_TIMEOUT(批量授权已撤销, 无任何引用, 死代码)


# 2026-08-12 - 小欧 - A1越层前置: safety 提升为顶层 app.safety, clear_temp_auth 的 import 由 app.services.safety.temp_auth 改 app.safety.temp_auth(配合 tools 禁 app.services 守护规则)
# 2026-08-13 - 小欧 - 可恢复错误判定修复: ①_RECOVERABLE_ERRORS 补 "timeout"(HITL确认超时是用户侧软拒绝,
#   原判FAILED与 _add_denial_feedback 注入的"改用其他工具"引导自相矛盾; 纳入后由 _deny_counts 累计>=3才FAILED);
#   ②可恢复异常路径不再 set RETRYING(计数已在 except 内+1), 消除与主循环 RETRYING 处理双累加
#   (一次异常计2次→上限3实际第2次即FAILED, 重试机会减半); 来源B(_dispatch_handler retrying)仍走主循环计数, 两来源各自单计
# 2026-08-13 - 小欧 - task_id 对称清理: finally 新增 reset_current_task_id()(与 set 对称, set在 action_handler)
#   【病根】set_current_task_id 全仓唯一set点, reset_current_task_id(context)零调用; 当前每SSE请求独立asyncio.Task,
#     ContextVar随任务结束丢弃故不漏, 但长连接/复用context(手动测试/常驻入口)会跨请求泄漏task_id
#   【改法】与 clear_temp_auth 并列在 task 级 finally 调 reset_current_task_id(), 对称set/reset, 行为零退化
# 2026-08-14 - 小欧 - llm 独立为 app 顶层能力层目录(services/llm→app/llm), 本文件 import 路径同步
# 2026-08-16 - 小欧 - start 装配: start 装配进 agent.steps(占 step 0), 取消 orchestrator 旁路。
#   注入模式: 工厂由 orchestrator 注入 agent._start_step_factory(chat 层数据闭包捕获), 本处只读 agent 属性
#   (system_prompt=_sys_prompt, previous_messages=context), 不 import chat 层; start 落库走 agent_runner 事件流
# 2026-08-17 - 小健 - 代码问题复核整改(北京老陈驱动, 复核3遍):
#   步号唯一: 首轮前取消(llm_call_count 尚未在 _process_single_step 开头 +1 =0)时, FinalStep step=0 与
#       start(占 step0) 双 step0 冲突; 改用 `step=agent.llm_call_count or 1` 接续唯一步号, 消除与 start 重复。
# 2026-08-17 - 小健 - 新增 _compact_injected_history(agent), 当 initialize_run_state
#   已置 agent._needs_compact=True 且 COMPACTION_ENABLED 放开 R4 时: 对 conversation_history 做一次 LLM 锚定
#   摘要, 以 assistant 消息回填(system[:1] + 摘要 + 最新 task[-1:]); tools=None 走 llm_stream Text 模式;
#   回填新列表赋值 conversation_history(压缩生效); 摘要为空/异常则原样保留零退化; 主循环 while 前 await 调用
# 2026-08-17 - 小健 - start 业务过程收敛(老陈驱动, 痛斥输入装配割裂): start 装配段(initialize_run_state 后、
#   while 前)扩展为任务输入装配完整段——注入会话历史(_inject_conversation_history) → 超窗判定(_maybe_compact)
#   → context_summary 快照 → 构造 StartStep → emit, 一气呵成; 历史注入/超窗标记自 initialize_run_state 收拢至此
# 2026-08-17 - 小健 - start 业务物理独立模块(老陈驱动, 痛斥"一个事情到处乱放"): 新增 start_step.py 单一承载 start
#   全部业务(_inject_conversation_history/_maybe_compact_injected_history/_compact_injected_history/assemble_start_step),
#   自本文件移除 _assemble_start_step 与 _compact_injected_history 定义, 改为模块级薄 import(assemble_start_step
#   as _assemble_start_step / _compact_injected_history); 主流程调用点不动
#   MaxSteps 语义、编辑历史条目名不变; 本文件退回启动编排薄层 — 小健 2026-08-17
# 2026-08-17 - 小健 - start 业务彻底单归属(老陈驱动, 三思三省): 契约构造迁入 start_step(_build_start_contract),
#   装配数据来源由 chat 层 _start_step_factory 闭包改为 orchestrator 注入的 agent._start_meta(dict 运行元数据);
#   本文件对 start 的接缝不变——仍『initialize_run_state → assemble_start_step(agent, context) → emit → 超窗 C4 回填』,
#   仅数据来源改读 _start_meta(build_start_step 逻辑已在 start_step 模块内直接构造, 详见 start_step.py) — 小健 2026-08-17
# 2026-08-17 - 小健 - 最合理核查(老陈追问): assemble_start_step 改同步(内部零 await), 调用点去 await — 小健 2026-08-17
# 2026-08-17 - 小健 - 注释纠偏(北京老陈 2026-08-17): 超窗回填段注释去掉「依赖 COMPACTION_ENABLED 开关」表述——
#   开关仅限 start 超窗判定(start_step)使用; 触发条件只据 start 超窗置的 _needs_compact 标记(getattr 判断) — 小健 2026-08-17
# 2026-08-18 小欧 - 步骤信号: same_tool_loop终止FinalStep的 thought= 改 reasoning=(FinalStep已删thought参数)
# 2026-08-18 - 小欧 - 错误/用量仅SSE: handle_react_error/empty_response/chunk_buffer_timeout 改 MetaStep(type="error")(删ErrorStep import); _dispatch_handler 改读 _kwargs 取 error_type; usage emit 处 append _usage_events; 各 error/retrying/usage 加 severity(warn/info)
# 2026-08-20 - 小欧 - token 四层同构累计修复: 任务起点(run_react_cycle)读 DB 一次缓存 _session_acc_base/_chain_acc_base 到 agent 并初始化 session/chain 累计=基线(无 LLM 调用任务也正确反映历史累计, 杜绝日志/前端误显 0); usage 块改用缓存基线(消除每轮双 DB 连接冗余读取); DB 异常降级为零基线不阻断主链路
# 2026-08-20 - 小欧 - 真实缺陷复核三遍修复(review 3x 确认后按最佳不退化): ①A(遥测 usage 门控): on_llm_call/build_stats_step/context_overview 原置于 `if _usage` 内, 无 usage 响应时 llm_calls/stats/context_overview 全丢; 移出到 response 分支末尾必发(usage 存在行为完全不变, 纯增强), 补 isinstance 守卫 error/finish_reason 计算; ②C2(裁剪token死活): on_trim 原只传 bool -> 透传 message_builder._trimmed_tokens_this_round, 裁掉token数不再恒0。
# 2026-08-20 - 小欧 - 运行中DB即时落库(北京老陈裁定"每轮即时落库"): 每轮 emit usage(MetaStep type=usage) 后同步 update_task/session_accumulation 落库, 供运行中他方查询/断线中间态读取实时累计; DB 读-加-写(当前DB值+本轮token)与内存态基线口径一致, 会话缺 session_id 守卫跳过; DB 异常降级 warning 不阻断主链路; 配套 agent_runner 移除重复 update 防同批 token 翻倍累加
# 2026-08-20 - 小欧 - 输出截断事件收口: 新增 MetaStep(type="truncated") 统一"输出截断"事件, 仅触发于 LLM 输出截断 2 处(场景D)——重试分支(content=连续第N次+已注入重试Observation)与连续截断取消分支(content=连续N次+任务取消, 于 FinalStep 前下发), severity=warn; 上下文裁剪/工具结果截断已有 context_overview.truncated / observation data.truncated 通道, 不重复新增(DRY); MetaStep 不落库不占 steps, 不影响 total_steps
# 2026-08-21 - 小欧 - 差异设计落地: 每轮 token 累计落库块之后新增运行中 checkpoint——
#   调 agent.telemetry.checkpoint_llm_calls() 增量持久化 llm_calls(整表重写+idx_llm_calls_task_call 唯一索引幂等去重);
#   目的: 任务中途崩溃时监控数据最多丢最后一轮, 不再全丢; getattr 守卫无 telemetry 场景零影响, 主链路零改动
# 2026-08-22 - 小欧 - model结构化归一: 三处属性迁移——LLM 调用日志行改读
#   llm_client.llm_model.model; log_llm_call 改传 llm_model=llm_client.llm_model(prompt_logger 签名归一);
#   telemetry.on_llm_call 改传 tele_model=llm_client.llm_model — 全链 ModelRef 归一
# 2026-08-23 - 小欧 - 并发模型快照修复: 三处改读任务快照 agent._task_llm_model 优先——
#   防共享单例被并发还原后本任务后续轮次记录到他人模型(与 base_agent 快照/telemetry.finalize 同步落地)
# 2026-08-23 - 小欧 - 落盘文件A/B 实施(文档落码): _process_single_step 在 prepare_messages_for_llm()
#   之后调 agent.file_persist.append_conv_blocks(llm_call_count, messages) 增量落文件B(稳定 _msg_id 去重),
#   随即 pop("_msg_id") 防泄漏 LLM wire; getattr 守卫 writer 未挂载空转, 旁路不阻塞主链路
# 2026-08-28 小欧 - KISS修正(三堂会审yield链审查): 5处 emit_final_with_stats 调用点 async for→for(配合 step_emitter.emit_final_with_stats 改 sync 返回 (final, stats) 二元组); 原 async 体内零await, 纯伪异步包装; 行为等价无backward
# 2026-09-02 - 小欧 - 重试通知落点: _process_single_step
#   async for 内拆包前拦截 ("meta", {...}) → yield MetaStep(type=retrying, step=llm_call_count, severity=info,
#   wait_time) 走 StepEmitter 与既有 retrying 同路径发前端位置2🔁; 命中即 continue(未命中照旧拆包走既有分支);
#   LLM底层 L1/L2/FC降级重试通知全链落点收口
# 2026-09-05 小健 拆分(react_cycle.py拆四): 常量+守卫群→react_inference.py, _dispatch_handler(含状态推断)→react_dispatch.py,
#   run_react_cycle+_finalize_cycle→react_loop.py; 本文件由 react_cycle.py git mv 改名(历史/blame不断),
#   余部仅剩 _process_single_step — 逐字复制, 只改import
# 2026-09-06 小欧 事件发布改造: _process_single_step 由 async generator 改
#   普通 async 返 List(事件经 task_state.get_stream_buffer(agent.task_id).publish 直写 event_log); 11处发射点位
#   (retrying/chunk/usage/stats/context_overview/empty error/截断 final/截断重试前/ObservationStep/same_tool_loop final)
#   全收口 publish, 按序极化见 emit_final_with_stats 三处先publish再 for 拆二元组 publish;
#   消费改 for await _dispatch_handler(list) 逐条 publish; _publish = _buf.publish 函数顶部绑定一次 — 小欧-2026-09-06
# 2026-09-06 小欧 消费判别统一: _process_single_step 消费判别段改 payload 单判别——
#   meta分支→payload["type"]=="retrying", response分支→payload非空, chunk分支→payload为None;
#   判别结果仍以 chunk_type/chunk_data 喂下方 chunk/response 既有处理体(逐行不动);
#   _task_llm_model 快照口径不变; 发射形态保留 publish(await _publish(emit(...).to_dict()))
# 2026-09-06 小欧 发布改造遗漏修复(路径1审计, 小沈发现): 连续截断上限取消分支原裸 return
#   漏改为 return[](改造时其余5出口全[]唯独此分支落空); 调用方 react_loop `for event in await
#   _process_single_step(agent, chunk_buffer)` 对 None 迭代抛 TypeError('NoneType' object is not iterable),
#   _is_recoverable_error(TypeError)=False → 外层 except Exception → set_failed 无条件覆盖: 本应 cancelled
#   (final(cancelled)+final_stats 已 publish 已落库) 实际 status=FAILED → chat_tasks.status 落 failed,
#   与 chat_task_steps 终态=cancelled 自相矛盾, SSE 多刷一条 error; 单测盲区: 直调 _process_single_step
#   读 event_log 不看返回值; 改为 return[](与其余同风格, 事件已全量 publish), 并补
#   test_run_react_cycle_truncation_max_cancelled 全循环回归 — 小欧 2026-09-06

# 2026-09-11 小欧 - final_stats 移出循环链: emit_final_with_stats 改返回一元组(final,), 2 处调用点删除
#   `await _publish(_fs[1].to_dict())`(由 runner 延后单发, 杜绝残缺组装即发) — 小欧-2026-09-11
# 2026-09-12 小欧 - 终态长短信号分离: 新增 _emit_publish 发射统一收口——
#   ① chunk(非推理)/action 当场登记 _final_short_ctx(替代 agent_runner 扫描累积);
#   ② completed final 当场分流: 一律先缓存完整长条 _pending_final_db(供扫描落库), 短判定(有正文chunk+非action轮)
#     → 剥五键短条(type/step/timestamp/outcome/duration) publish, 长判定(return_direct/action轮/failed/cancelled)
#     → 完整长条(=缓存同源)原样 publish; event_log 只进应转发形态(实时长/重连短)根治;
#   ③ 12 处 publish 调用点全改走 _emit_publish;
#   ④ import 补 Dict 类型标注。非 final 事件原样 publish 逐字节等价, 无 backward — 小欧-2026-09-12
# 2026-09-20 - 小欧 - 注入机制修复(北京老陈定案): _absorb_inbox 重构——
#   ①多条注入合并为同一用户输入块(末条已 user 则并入防连续 user 交替性), 单条独立成新 user 轮(铁约束);
#   ②吸收时经 storage.insert_user_message 落库拿真实 user_message_id, 会话/session 缺失或 DB 异常
#     静默 fallback(null 锚); ③吸收后写回真实 uid 到目标 user 消息并演进 builder 锚(供 assistant 回复配对落库)。
#   compliance: SRP(数据层 drain_inbox 承接)/KISS-DIRECT/禁止backward
# 2026-09-20 - 小欧 - 可恢复异常与锚演进修复: ①_absorb_inbox锚更新条件反转(_cur守卫致首次None永不演进→回填uid必空); ②insert_user_message异常静默吞掉无日志; ③add_user_message单条注入显式传uid消除合成负id中间态
# 2026-09-20 - 小欧 - 单条注入铁约束回归修正: _absorb_inbox单条注入改条件传参——落库成功传真实uid,
#   落库失败(_uid=None)回退单参调用(合成负id占位, 行为等价), 兼容既有 add_user_message 单参铁约束断言。
# 2026-09-28 小欧 注入落位规则实施: _absorb_inbox 删 str 兼容分支/删重落库/超长截断/删锚写回;
#   三堂会审修过时注释(与删落库矛盾的"落库成功/单参铁约束"表述);
#   末条合并规则修正: _merge_into_last 去掉 len>1 条件, 单条注入末条user也并入(防连续user) — 小欧-2026-09-28
# 2026-09-29 - 小欧 - _absorb_inbox 落位规则 docstring 改写: 删"落库成功/单参铁约束"等已随代码删除的过时表述, 只留"必须在 trim_history 之前(否则 user token 不计入 always_keep_tokens 预算)"这一条有效约束  小欧-2026-09-29
# 2026-10-01 小欧 - 落库重试锁: _process_single_step 内 update_task 补 retry_locked=3。运行期逐步落库后每事件写事务翻倍, SQLite busy_timeout 仅 500ms, 并发多任务下撞写锁概率显著上升; 原缺省 retry_locked=0 致撞锁即降级 warning(丢 token 明细), 必修
# 2026-10-04 小欧 - 正名 context_overview 发射节奏注释(原称"每次必发", 实受下方 if 门控: 首轮/裁剪轮/每5轮), 逻辑未动
# 2026-10-04 小欧 - usage 帧新增 context_window(运行时上下文窗口, 取 message_builder.MAX_CONTEXT_TOKENS,
#   由 agent_runner 按 llm_service.context_length 覆盖): 前端据此算占窗率, 不新增数据源
# 2026-10-07 北京老陈 history_context 首帧前移: 第1轮那次移除(改由 react_loop 在 emit start 之前发,
#   压缩决策后即知真实水位); 帧构造收归 telemetry.build_history_context_step(与 react_loop 共用, DRY);
#   裁剪轮/每5轮的水位更新条件不变。
# 2026-10-13 小欧 截断分支 tool_result 补 raw_data:None, 与 observation_builder 的 tool_result 契约保持同构(每元素自包含),
#   前端按 raw_data 渲染时不会读到 undefined; data_text 不变(LLM 与 history_loader 回放的唯一文本源) — 小欧-2026-10-13
# 2026-10-24 小欧 - 死循环纠偏注释修正(北京老陈令): 场景F 注释 "assistant role" 改 "user role"(实现本为 user, 注释写错) — 小欧-2026-10-24
# 2026-10-25 小欧 - 信号计算外移: trim_history 调用前加 _trim_signal() 判信号, 信号触发后才调 trim_history(信号计算与裁剪逻辑分离, 调用方控制流程) — 小欧-2026-10-25
# 2026-10-30 小欧 - _absorb_inbox 注入合并超长截断方向修正为**保尾部** —— 插话正文前可能拼引用区块,
#   原 `[:_max_chars]` 切尾部会先丢引用、再丢用户消息开头; 保尾部才能留下用户真正写的话, 截断处留显式标记 — 小欧-2026-10-30
# 2026-10-31 小欧 - 注释订正(北京老陈指正): 第一行动态状态位是位置2, 原注释序号写错(2026-09-17 重排前是第4位), 全文统一为"位置2" — 小欧-2026-10-31
# 2026-11-01 小欧 - 裁剪可见性(北京老陈令): trim_history 真裁剪发生时补一条 notice(kind=trimming, phase=done)，
#   与 summarizing 信封同构——此前 trim 只进 telemetry(task_metrics.trim_count/trim_tokens)，SSE 零帧前端无感知；
#   瞬时动作单发 done 不占位置2，token 数读唯一真源 _trimmed_tokens_this_round；未真裁(空转/冷却)零发射 — 小欧-2026-11-01
# 2026-11-03 小欧 - log_and_print 增 level 参数: 3 处异常/取消调用点(empty_response/consecutive_truncation/
#   same_tool_loop)显式传 level="WARNING", 不受控制台级别静音 — 小欧-2026-11-03
# 2026-11-07 小欧 - 裁剪 notice token 文案收口 agent_utils.fmt_tok(DRY): 原始 int 改紧凑 K/M 两档,
#   与 start_step 摘要提示、refs.notice._tokens_text 三处统一公有真源 — 小欧-2026-11-07
# 2026-11-07 小欧 - loop 重试改用 notice 通道(有 done 终态清除): react_step:399 LLM429重试 +
#   react_loop:332 单步异常重试, 原 MetaStep(retrying) 无 done 拼留; 改 emit_notice(retrying,start)+
#   首chunk emit_notice(retrying,done) 清位置2 — 小欧-2026-11-07
# 2026-11-08 小欧 - 图片 parts 展开从 prepare_messages_for_llm 拆出, 改在
#   append_conv_blocks/log_llm_call 之后调 expand_vision_parts(防 base64 入库/入日志) — 小欧-2026-11-08
# 2026-11-08 小欧 设计[15]落码: payload type=="pause" 帧 → emit_notice(rate_limit_wait, start/done)(前端 pause 倒计时, 可中断), 与 retrying 同机理
# 2026-11-11 小欧 展开调用更名 expand_vision_parts → expand_attachment_parts(附件/URL 占位泛化) — 小欧-2026-11-11
# 2026-11-15 小欧 - 块标志改用 app.wire_prefix(ENV_WS_OPEN/ENV_REFS_OPEN), 消除对 workspace_block/render 的字面量再导出依赖 — 小欧-2026-11-15

"""react_step — 单步ReAct调度(react_cycle.py 余部改名, 拆分后专注"单步编排")

职责: 单步编排(LLM调用准备→流式调用→响应分发), 不包含主循环调度/类型分派/推断基元。
老名react_cycle已消亡, 引用从 react_loop/react_dispatch/react_inference/react_step 各取所需。
"""

import time
from typing import (  # X2: 补 Dict 类型标注（4.1.1 _emit_publish 类型标注需要）— 小欧 2026-09-12
    Dict,
    List,
)

from app.config import (
    get_config,  # 2026-09-28 小欧: 注入截断读 tuning.content 配置(与 message_builder._cap_temp_history 同键, DRY)
)
from app.db import db
from app.logger import log_and_print, logger
from app.logger.prompt_logger import get_prompt_logger
from app.services.agent.agent_utils import (
    fmt_tok,  # 2026-11-07 小欧: 裁剪 notice token 文案收口 fmt_tok
)
from app.services.agent.compaction_constants import (
    TEMP_HISTORY_CHAR_LIMIT,  # 2026-09-28 小欧: 同上, 默认值兜底
)
from app.services.agent.llm_call import call_llm_with_fallback
from app.services.agent.react_dispatch import _dispatch_handler
from app.services.agent.react_inference import (
    _MAX_CONSECUTIVE_SAME_TOOL_CALLS,
    _MAX_CONSECUTIVE_TRUNCATIONS,
    _SAME_TOOL_WARN_ROUNDS,
    _check_same_tool_loop,
    _should_retry_truncated_tool,
    _warn_same_tool_loop,
)
from app.services.agent.status_table import AgentStatus, set_cancelled, set_failed, set_status
from app.services.agent.steps import ChunkStep, FinalStep, MetaStep, ObservationStep
from app.services.agent.tool_cache_manager import get_openai_tools
from app.wire_prefix import ENV_WS_OPEN
from app.services.chat import storage

# 2026-10-31 小欧 - 超长插话保尾部时前置注入块会被切掉, 按块标志点名打日志 — 小欧-2026-10-31
from app.wire_prefix import ENV_REFS_OPEN


async def _absorb_inbox(agent) -> int:
    """B机制: 每轮 LLM 调用前合并本任务 inbox 积压的新 user 消息, 返回吸收条数 — 小欧 2026-09-20
    编排语义(SRP): drain_inbox(数据层取走) → add_user_message(消息层并入历史)。
    置于 trim_history 之前: 让本轮注入的 user 消息计入 trim 预算(always_keep_tokens = system+user,
      message_builder 预算计算), 否则 available_budget 偏大会多保留 FC 对致超上下文。
    注: user 消息在 trim_history 中**永保**(只裁 observation(tool)
      与 assistant, 重建时 user 全量放回), 故注入内容不会被裁掉; 顺序只影响预算精度。
    落位规则(2026-09-28 修正):
      ① 末条已是 user → **并入末条**(不论本次 drain 出几条) → 避免连续 user 破 OpenAI 交替性;
         该分支不演进锚, 锚保持末条原有 uid(注入行的答案落在末条那一行, 与前端渲染一致)。
      ② 末条非 user(生产常态: 上一轮已产出 assistant/tool 结果) → 独立成新 user 轮,
         add_user_message(_merged, user_message_id=_uid) 使锚演进到注入 uid(末条 = _uids[-1])
         → 终态 update_user_message_final 把答案落在最后一条注入行, 与 live 顺序一致。
      ※ 原「单条注入一律独立成新 user 轮 + 缺失降级单参合成负 id」的表述已被取代: 独立成轮以"末条非 user"为前提; 单参降级是死代码 ——
        inbox 唯一写入者 inject_message_to_task 入口强制 uid>0(task_registry), orphan 只搬运
        已校验元组, 故 _uids 必非空且全为正整数(YAGNI 已删)。
    2026-09-28 小欧: ①inbox 已是(内容,uid)元组, 删 str 兼容分支(禁 backward);
      ②uid 随消息同行 → 删 insert_user_message 重落库(原双重落库是 uid 丢失的派生后果, 落库权责归一至 API 入口);
      ③_merged 超长保留尾部; ④无锚写回块 — 锚演进单点在 add_user_message(user_message_id=),
      并入末条天然不动旧锚(「并入末条覆盖旧锚」缺陷由此消亡)。
    2026-10-30 小欧: ③的截断方向修正为**保尾部**——插话正文前可能拼引用区块,
      切头部会先丢引用、再丢用户消息开头; 保尾部才能留下用户真正写的话。"""
    from app.services.task.task_registry import drain_inbox
    _injected = await drain_inbox(agent.task_id)
    if not _injected:
        return 0
    # 元组形态已成唯一契约(2026-09-28), uid 随消息同行, 故不再需要重落库取 id
    _contents = [m[0] for m in _injected]
    _uids = [m[1] for m in _injected]
    _merged = "\n".join(_contents)
    # 2026-09-28 小欧: 超长保留尾部; 上限与 message_builder._cap_temp_history 同键(DRY)
    #   2026-10-30 小欧: 原 `[:_max_chars]` 切掉的是尾部 → 插话拼在前的引用区块与用户正文一起被反序丢弃。
    #   refs 在前、user_input 在后, 保尾部 = 保用户真话, 截断处留显式标记。
    _max_chars = int(get_config().get('tuning.content.temp_history_char_limit', TEMP_HISTORY_CHAR_LIMIT))
    if len(_merged) > _max_chars:
        # 2026-10-31 小欧 - 保尾必然牺牲前置块, 按块标志点名, 不静默 — 小欧-2026-10-31
        _dropped = _merged[:-_max_chars]
        _cut = [name for tag, name in ((ENV_WS_OPEN, "事项目录块"), (ENV_REFS_OPEN, "引用块"))
                if tag in _dropped]
        logger.warning(f"[B] 注入合并超长({len(_merged)}>{_max_chars}), 保留尾部"
                       + (f", 前置块被截: {'/'.join(_cut)}" if _cut else ""))
        _merged = "…[注入前文过长, 已截断]\n" + _merged[-_max_chars:]
    # 落库权责归一至 API 入口(前端 POST /sessions/{id}/messages), 此处不再 insert_user_message;
    # uid 取自 inbox 元组。锚取**最后一条**(锚取最后一条 uid):
    #   终态 update_user_message_final 只回填锚所在那一行 → 刷新后 carrier 把 assistant 渲在该行,
    #   与 live 一致(assistant 追加到末尾 → 答案在最后一条注入之后)。
    #   若锚取第一条, 刷新后答案会出现在第一条注入行处, 与 live 顺序不一致。
    # 不变量(2026-09-28 21:29 会审核验): inbox 唯一写入者是 inject_message_to_task,
    #   其入口强制 uid>0(task_registry), orphan 路径只搬运已校验元组 → _uids 必非空且全为正整数,
    #   故原 `_uids[0] if _uids else None` 的 else None 与 `if _uid is not None` 单参降级均为死代码(YAGNI), 一并删。
    _uid = _uids[-1]
    _hist = getattr(agent.message_builder, "conversation_history", None)
    _last = _hist[-1] if isinstance(_hist, list) and _hist else None
    _merge_into_last = (
        isinstance(_last, dict) and _last.get("role") == "user"   # 末条已是 user → 并入避免连续 user
    )
    # 并入末条, 不产生连续 user; 否则独立成轮(2026-09-28 小欧: 原"单参铁约束"过时)
    if _merge_into_last:
        _last["content"] = str(_last.get("content") or "") + "\n" + _merged
    else:
        # 锚演进单点在 add_user_message, 此处不写回
        agent.message_builder.add_user_message(_merged, user_message_id=_uid)
    # 2026-09-28 小欧: 原日志恒打 uid, 但并入末条分支根本没用该 uid(锚不变),
    #   打印它会误导排障。改打真实生效的形态。
    logger.info(
        f"[B] 每轮LLM前吸入新消息: task={agent.task_id} len={len(_merged)} "
        f"形态={'并入末条user(锚不变)' if _merge_into_last else f'独立成轮(锚uid={_uid})'}"
    )
    return len(_injected)


async def _process_single_step(agent, chunk_buffer) -> List:
    """单步ReAct调度: LLM调用→响应处理→分发 — 小欧 2026-06-25 / 小欧 2026-07-09 加分区注释
    事件发布改造: 普通 async 返 List, 事件经 publish 直写 event_log(11处发射收口), 由主循环订阅消费 — 小欧 2026-09-06"""

    # ── StreamBuffer 绑定 + publish 本地别名(回调事件收发, 消费端订阅 event_log) — 小欧-2026-09-06
    from app.services.task.task_state import get_stream_buffer
    _buf = get_stream_buffer(agent.task_id)
    if _buf is None:
        raise RuntimeError(f"[react_step] StreamBuffer缺失(task={agent.task_id})")
    _publish = _buf.publish

    # 发射统一收口(2026-09-12 小欧): 本函数定义后, 全部 publish 调用点改走 _emit_publish
    #   (chunk / handler 全事件含 completed final / 截断取消 / 死循环 / 其余 MetaStep/Observation):
    #   ① 登记长短判定上下文 chunk_steps/action_steps(发射侧实时登记, 替代 agent_runner 扫描累积);
    #   ② final 当场分流(统一先缓存长条, 再按长短判定决定 publish 形态, 见下方代码块/注1):
    #      一律先 agent._pending_final_db = dict(step_dict)(完整长条, 供扫描落库, 保 DB step 序号=事件顺序不变式);
    #      其后再分流: 短判定(有正文chunk的completed)→剥五键短条 publish; 长判定(其余)→完整条(=长条)原样 publish,
    #      event_log 只进应转发形态(有正文 chunk 的 completed→短五键; 其余→完整条);
    #   ③ 非 final 事件原样 publish(行为逐字节等价, 无 backward)。
    #   [G2 根治] event_log 终态唯一形态(发射即定, finally 不再覆写, 见 4.2.4), 实时/重连读同一形态。
    #   [竞态] final_stats 延后单发已是 DB 就绪信号, final 实时先到仅驱动快照(读内存流不读 DB) — 小欧 2026-09-12
    async def _emit_publish(step_dict: Dict):
        _st = step_dict.get("type", "")
        _ctx = getattr(agent, "_final_short_ctx", None)
        if _st == "chunk" and not step_dict.get("is_reasoning") and _ctx is not None:
            _ctx["chunk_steps"].add(step_dict.get("step", 0))   # 正文 chunk 轮登记(与 agent_runner 扫描语义等价)
        elif _st == "action" and _ctx is not None:
            _ctx["action_steps"].add(step_dict.get("step", 0))  # action 轮登记(预览/canonical 同一步号, 与扫描语义等价)
        if _st == "final":
            _fs_step = step_dict.get("step", 0)
            # 长短判定(原 agent_runner 逻辑, 整体上移发射侧; 语义逐条等价)
            _short = (
                step_dict.get("outcome") == "completed"
                and _fs_step not in (_ctx["action_steps"] if _ctx is not None else ())
                and _fs_step in (_ctx["chunk_steps"] if _ctx is not None else ())
            )
            # 长条缓存: 完整 dict 供扫描落库(DB 回放完整 response) — KISS: 终态唯一, 单值覆盖安全
            agent._pending_final_db = dict(step_dict)
            # 长短分流(北京老陈 2026-09-12 定案, 勿误解):
            #   短条场景(_short=True): 前端只发五键短条(duration 带运行时长); 完整长条只进 _pending_final_db→DB, 绝不转发前端。
            #   长条场景(_short=False: error/failed/cancelled/return_direct): 完整长条必须发前端
            #     (response=错误/取消文本是前端唯一正文载体), 同时完整长条进 _pending_final_db 落库。
            #     ≠"长条只存DB"仅适用于短条场景, 不适用于此场景 — 小欧 2026-09-12
            if _short:
                step_dict = {k: step_dict[k] for k in ("type", "step", "timestamp", "outcome", "duration")}  # 2026-09-11 小欧: 短信号带 duration, 重连回放与实时一致
        await _publish(step_dict)

    # ── Phase 1: LLM 调用准备 ──────────────────────────────────
    agent.llm_call_count += 1
    # 2026-09-20 小欧 B机制(北京老陈定案, 机会②): 每轮 LLM 调用前合并本任务 inbox 积压的新 user 消息
    #   ——工具执行期间的新消息不打断工具(安全底线), 于下一轮 LLM 调用前并入本轮上下文, 全轮覆盖(含 answer 轮)不漏
    #   [KISS] 单一吸收点(所有轮共用 _absorb_inbox 这一处), 无积压则零开销跳过;
    #   置于 trim_history 之前: 新消息参与本轮 prepare 前的一致性组装, 不滞留尾部跨轮 — 小欧-2026-09-20
    await _absorb_inbox(agent)
    if agent.message_builder._trim_signal():  # 信号触发后才裁剪 — 小欧 2026-10-25
        agent.message_builder.trim_history()
        # 2026-11-01 小欧 - 裁剪可见性(北京老陈令): 真裁剪发生时发一条 notice(kind=trimming, phase=done)。
        #   发射形态=本文件同行 MetaStep(retrying/truncated) 同款 _emit_publish 直发(全函数唯一发射收口；
        #   禁走 await 属性方法——测试桩 emitter 为同步 Mock, await 属性返回值必炸)；phase 必须显式
        #   done(sseParser 缺省回落 'start' 会误占位置2)；token 数读唯一真源 _trimmed_tokens_this_round；
        #   未真裁(_trimmed_this_round=False: 空转/冷却)零发射不刷屏 — 小欧-2026-11-01
        if getattr(agent.message_builder, "_trimmed_this_round", False):
            await _emit_publish(agent._step_emitter.emit(MetaStep(
                step=agent.llm_call_count, type="notice",
                content=f"裁剪历史对话(裁掉约{fmt_tok(getattr(agent.message_builder, '_trimmed_tokens_this_round', 0))})",
                kind="trimming",
                phase="done",
            )).to_dict())
    agent.telemetry.on_trim(
        getattr(agent.message_builder, "_trimmed_this_round", False),
        getattr(agent.message_builder, "_trimmed_tokens_this_round", 0),
    )  # 11.3 C2修复(复核确认): 透传裁剪token数, 防 on_trim 恒0死数据 — 小欧 2026-08-20
    _first_token_marked = False           # 11.2-B 首 chunk 只记一次首包时延 — 小欧 2026-08-20
    # prepare_messages_for_llm 为 async(返回纯文本 wire 副本, 图片仍是占位)
    messages = await agent.message_builder.prepare_messages_for_llm()
    # 文件B 增量落盘(loop顺序/结构保真/增量前缀) — 小欧 2026-08-23
    # call_no = agent.llm_call_count(本次调用序号, 上方刚自增)
    # 经注入的 agent.file_persist 调用(与 telemetry 同模式, agent 层零 chat 依赖); writer 未挂载时空转 — 小欧 2026-08-23
    _fp = getattr(agent, "file_persist", None)
    if _fp is not None:
        _fp.append_conv_blocks(agent.llm_call_count, messages)   # 读 _msg_id 去重
    for _m in messages:
        _m.pop("_msg_id", None)        # 剥离内部标记后再发 LLM(防泄漏 wire) — 小欧 2026-08-23
    openai_tools = get_openai_tools(agent)

    _task_llm = getattr(agent, "_task_llm_model", None) or getattr(agent.llm_client, "llm_model", None)   # 任务快照优先(三堂会审) — 小欧 2026-08-22
    logger.info(f"[LLM] 调用#{agent.llm_call_count}, messages={len(messages)}, tools={len(openai_tools)}, model={getattr(_task_llm, 'model', '?')}")

    prompt_logger = get_prompt_logger()
    prompt_logger.log_llm_call(
        round_number=agent.llm_call_count,
        messages=messages,
        llm_model=_task_llm,   # 归一: 传 ModelRef 结构(任务级快照, 防单例还原竞态) — 小欧 2026-08-22
        call_type="tools",
        tools=openai_tools,
    )

    # 2026-11-08 小欧: 落盘/日志已取占位原文, 此处才展开图片 parts(避免 base64 入库/入日志); 覆盖全部 user 消息
    # 2026-11-14 小欧 第7章7.4: 传 session_id 供附件记录会话收权(跨会话 id 回落降级文本)
    messages = await agent.message_builder.expand_attachment_parts(
        messages, _task_llm,
        session_id=(getattr(agent, "_start_meta", None) or {}).get("session_id"))

    if not openai_tools:
        logger.error("[_process_single_step] 无可用工具")

    # ── Phase 2: LLM 流式调用 ──────────────────────────────────
    llm_response = None
    _call_start = time.time()                   # 11.2-C LLM 调用计时 — 小欧 2026-08-20
    async for item in call_llm_with_fallback(agent, messages, openai_tools):
        _p = getattr(item, "payload", None)          # 路径2 唯一判别: payload非空=终结响应/通知, 否则原生chunk — 小欧 2026-09-06
        if _p is not None:
            if _p.get("type") == "pause":
                # 2026-11-08 小欧(设计[15]三堂会审): A 态 pause 帧 → rate_limit_wait notice(前端倒计时, 可中断)
                #   首个正常 chunk 到达时发 done 清除(与 retrying 同机理); pause_seconds 由后端算好 wait_text 下发, 前端零逻辑
                await agent._step_emitter.emit_notice("rate_limit_wait", "start",
                                                       _p.get("content") or f"模型限速，{_p.get('wait_text', '')}后恢复（429·延时）")
                agent._pause_notice_active = True
                continue
            if _p.get("type") == "retrying":
                # 2026-11-07 小欧 改用 notice 通道(有 done 终态清除): 原 MetaStep(retrying) 无 done,
                #   重试成功后位置2 残留; 改 emit_notice(retrying, start) + 首个 chunk 时发 done 清除
                await agent._step_emitter.emit_notice("retrying", "start", _p.get("content", "正在重试"))
                agent._retrying_notice_active = True
                continue
            chunk_type, chunk_data = "response", _p  # 终结响应: 喂下方 response 分支(原 "response" 拆包语义)
        else:
            chunk_type, chunk_data = "chunk", item   # 原生 chunk: 喂下方 chunk 分支(原 "chunk" 拆包语义)

        if chunk_type == "chunk":
            if getattr(agent, "_pause_notice_active", False):
                # 2026-11-08 小欧(设计[15]三堂会审): pause 恢复清除——首个正常 chunk 到达 → 发 notice(rate_limit_wait, done) 清位置2
                await agent._step_emitter.emit_notice("rate_limit_wait", "done", "恢复")
                agent._pause_notice_active = False
            if getattr(agent, "_retrying_notice_active", False):
                # 2026-11-07 小欧 重试恢复清除: 首个正常 chunk 到达 → 发 notice(retrying, done) 清位置2
                await agent._step_emitter.emit_notice("retrying", "done", "已恢复")
                agent._retrying_notice_active = False
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
            await _emit_publish(agent._step_emitter.emit(chunk_step).to_dict())
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
                # 2026-08-18 小欧: usage剔step_json, append _usage_events明细供agent_runner终态insert_token读
                _ue = getattr(agent, "_usage_events", None)
                if _ue is not None:
                    _ue.append({"step": agent.llm_call_count, "prompt_tokens": _usage.get("prompt_tokens"), "completion_tokens": _usage.get("completion_tokens"), "total_tokens": _usage.get("total_tokens")})
                # token 四层同构累计 — 任务级用 agent 内存态逐轮累加(跨轮累计,不读DB,避免任务内DB未回写致不累计);
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
                    # 2026-10-04 小欧: 随 usage 帧下发当前任务模型上下文窗口(运行时权威值, agent_runner 已按 llm_service.context_length 覆盖),
                    #   前端据此算"本轮 P / 窗口"占用率; 不新增数据源, 复用 message_builder 唯一真源 — 小欧 2026-10-04
                    context_window=int(getattr(agent.message_builder, "MAX_CONTEXT_TOKENS", 0) or 0),
                )
                await _emit_publish(agent._step_emitter.emit(_usage_step).to_dict())

                # 运行中DB即时落库（每轮 update 任务/会话累计，供运行中他方查询/断线中间态读取）— 小欧 2026-08-20
                #   用户裁定"每轮即时落库"; DB 读-加-写(当前DB值+本轮token) 与内存态基线口径一致;
                #   DB 异常降级不阻断主链路; agent_runner 已同步移除 update 防重复累加(翻倍)。
                try:
                    # 落库 offload 出事件循环(后端卡死修复 小欧 2026-08-24)
                    # retry_locked=3 — 小欧 2026-10-01: 实时落库后每事件写事务翻倍,
                    #   SQLite busy_timeout 仅 500ms, 并发多任务下撞写锁概率显著上升;
                    #   原缺省 retry_locked=0 致撞锁即失败降级为 warning(丢 token 明细), 必须补足重试。
                    await db.atxn("chat", lambda conn: (
                        storage.update_task_accumulation(conn, task_id=agent.task_id, llm_call_count_token=_llm_call_count_token),
                        storage.update_session_accumulation(conn, session_id=agent._start_meta.get("session_id"), llm_call_count_token=_llm_call_count_token)
                        if (getattr(agent, "_start_meta", None) and agent._start_meta.get("session_id")) else None), retry_locked=3)
                except Exception as _sce_e:
                    logger.warning(f"[react_cycle] 每轮token累计落库失败(降级, 不影响主链路): {_sce_e}")

                # 12.2-Q5: 运行中checkpoint llm_calls(唯一索引幂等去重) — 中途崩溃监控数据不再全丢 — 小欧 2026-08-21
                _tel = getattr(agent, "telemetry", None)
                if _tel is not None:
                    _tel.checkpoint_llm_calls()

            # 遥测 + stats —— 不依赖 usage，每次 LLM 响应必发（遥测逐次明细）
            #   context_overview 另受下方 if 门控(首轮/裁剪轮/每5轮), 非每轮必发 — 小欧 2026-10-04
            # 修复(小欧 2026-08-20 复核确认): 原置于 usage 门控内, 无 usage 的响应 llm_calls/stats/context_overview 全丢,
            #   违背"每次调用一行"、"每轮 stats"契约; 移出后 usage 存在不改变行为(纯增强不退化) — 小欧-2026-08-20
            _llm_err = None
            _fin = llm_response.get("finish_reason") if isinstance(llm_response, dict) else None
            if isinstance(llm_response, dict) and llm_response.get("error"):
                _llm_err = str(llm_response["error"])[:80]
            agent.telemetry.on_llm_call(
                _usage, duration=_call_dur,
                tele_model=getattr(agent, "_task_llm_model", None)
                           or getattr(agent.llm_client, "llm_model", None),   # 任务快照优先(三堂会审 防还原竞态) — 小欧 2026-08-22
                error_type=_llm_err, finish_reason=_fin,
            )
            # stats 事件（独立模块产出 MetaStep(type="stats", ...)）— 小欧 2026-08-20
            _stats_step = agent.telemetry.build_stats_step()   # → MetaStep(type="stats", step_count/llm_call_count/retry_count/duration)
            await _emit_publish(agent._step_emitter.emit(_stats_step).to_dict())
            # history_context 事件（独立模块产出 MetaStep(type="history_context", ...)）
            # 首帧(step=0)由 react_loop 在 emit start 之前发出, 此处只发裁剪轮/每5轮水位更新。
            _llm_n = agent.llm_call_count
            if getattr(agent.message_builder, "_trimmed_this_round", False) or _llm_n % 5 == 0:
                _hc_step = agent.telemetry.build_history_context_step(step=_llm_n)
                if _hc_step is not None:
                    await _emit_publish(_hc_step.to_dict())

    # ── Phase 3: 响应分发 ──────────────────────────────────────
    set_status(agent, AgentStatus.EXECUTING)

    step = agent.llm_call_count

    # ── 场景A: 空响应 — LLM未返回有效数据 ──────────────────────
    if not llm_response or not isinstance(llm_response, dict):
        logger.error(f"[run_react_cycle] _call_llm返回无效响应: {type(llm_response)}")
        log_and_print(f"{time.strftime('%H:%M:%S')} [Error] step={step}, empty_response", level="WARNING")  # 小欧 2026-07-02 控制台
        set_failed(agent, "LLM返回空响应，任务终止")
        await _emit_publish(agent._step_emitter.emit(MetaStep(
            step=step, type="error", content="LLM返回空响应，任务终止", error_type="empty_response", severity="warn"
        )).to_dict())
        return []  # 普通 async 返 List, 空响应无事件 — 小欧-2026-09-06

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
            # 2026-10-09 北京老陈裁定: 警告已由 reasoning_guard.notify_stagnation 统一发出, 此处仅留日志。
            #   本块与 handle_answer 的 reason-only 分支条件等价, 且在 _dispatch_handler 之前执行
            #   (与 handle_answer 的 reason-only 分支同条件, 两处都发则一轮收到两条重复警告); 且它是 assistant 消息, 角色语义错误。
            logger.warning(f"[B3] LLM返回reasoning-only(空转)未调用工具(step={step}), 已由notify_stagnation发警告")
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
            log_and_print(f"{time.strftime('%H:%M:%S')} [Cancel] step={step}, consecutive_truncation", level="WARNING")  # 小欧 2026-07-02 控制台
            # 解决问题18(2.4④): 连续截断取消前发 MetaStep(type="truncated") 统一"输出被截断"事件 — 小欧 2026-08-20
            await _emit_publish(agent._step_emitter.emit(MetaStep(
                step=step, type="truncated",
                content=f"LLM连续{_MAX_CONSECUTIVE_TRUNCATIONS}次输出截断，任务取消",
                severity="warn",
            )).to_dict())
            _fs = agent._step_emitter.emit_final_with_stats(FinalStep(
                step=step,
                response=f"LLM连续{_MAX_CONSECUTIVE_TRUNCATIONS}次输出截断",
                outcome="cancelled",
            ))
            await _emit_publish(_fs[0].to_dict())
            set_cancelled(agent)
            return []  # 4C(5.8.2)审计修复(小欧-2026-09-06): 裸return→return[](防None被主循环L163 for迭代抛TypeError→外层except set_failed覆盖终态); 事件已全量publish, 与L444/L475同风格

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
        await _emit_publish(agent._step_emitter.emit(MetaStep(
            step=step, type="truncated",
            content=f"LLM输出截断(连续第{agent._consecutive_truncations}次)，已注入重试Observation",
            severity="warn",
        )).to_dict())
        # 2026-10-04 小欧 字段精简(第六章第0步): 删 llm_data_text(硬编码空串, 零消费) — 小欧-2026-10-04
        # 2026-10-13 小欧: 补 raw_data 字段, 与 observation_builder 的 tool_result 契约保持同构。
        #   此处截断分支无原始 result 可给, 故为 None(前端按 raw_data 渲染时不会读到 undefined)。
        await _emit_publish(agent._step_emitter.emit(ObservationStep(
            step=step,
            tool_result=[{"tool_name": "truncated_output", "llm_data": {"summary": "LLM工具调用输出截断", "action": {"tool": "truncated_output", "tool_zh": "输出截断", "params": {}}, "status": {"exec_code": "error", "message": obs_text}}, "data_text": obs_text, "raw_data": None, "other_data": {}}],
        )).to_dict())
        return []  # 4C(5.8.2): 普通 async 返 List — 小欧-2026-09-06

# ── 场景F: 相同工具调用死循环检测(双阈值纠偏/硬终止) ──────────
    # 2026-08-08 - 小欧 - 超时根因修复(file_not_found):
    #   【病根】LLM连续40+步逐字重复同一Thought并反复调用完全相同工具+相同参数(write写同一diff_tool.py),
    #          每次工具执行均success, 现有_consecutive_reasoning_only仅拦"纯推理无工具调用"空转, 本模式漏检,
    #          致死循环直抵max_steps=10000(约40+分钟)。
    #   【方案】对action响应计算工具调用签名(tool_name+规范化tool_params, 含并行pending),
    #          _check_same_tool_loop返回int连续计数(count=第N次), 双阈值:
    #          count==2/3/4(_SAME_TOOL_WARN_ROUNDS起)各注入user role纠偏消息(尝试唤醒调整, 最多3条);
    #          count>=5(_MAX_CONSECUTIVE_SAME_TOOL_CALLS)判定死循环硬终止failed。
    #          正常任务LLM每轮工具/参数各异或需新信息, 签名必不同, count重置, 零误伤(增强不退化)。
    if llm_response.get("type") == "action":
        _cnt = _check_same_tool_loop(agent, llm_response)
        if _SAME_TOOL_WARN_ROUNDS <= _cnt < _MAX_CONSECUTIVE_SAME_TOOL_CALLS:
            # count==2/3/4: 各发1条纠偏(共3条, 内部幂等上限_SAME_TOOL_WARN_MAX) — 小欧 2026-08-08
            _warn_same_tool_loop(agent, llm_response, _cnt)
        elif _cnt >= _MAX_CONSECUTIVE_SAME_TOOL_CALLS:    # count>=5(第5次相同调用): 硬终止 — 小欧 2026-08-08
            logger.warning(f"[run_react_cycle] LLM连续{_cnt}步调用相同工具(step={step}), 判定死循环, 终止")
            log_and_print(f"{time.strftime('%H:%M:%S')} [Cancel] step={step}, same_tool_loop", level="WARNING")  # 小欧 2026-08-08 控制台
            set_failed(agent, f"模型连续{_cnt}步重复调用相同工具, 疑似死循环, 任务终止")
            _fs = agent._step_emitter.emit_final_with_stats(FinalStep(
                step=step,
                response="模型反复调用相同工具未取得进展，任务已终止（疑似死循环）",
                reasoning=llm_response.get("reasoning", "") or llm_response.get("thought", ""),
                outcome="failed",
                error_type="same_tool_loop",
                error_message=f"模型连续{_cnt}步重复调用相同工具，疑似死循环",
            ))
            await _emit_publish(_fs[0].to_dict())
            return []  # 4C(5.8.2): 普通 async 返 List — 小欧-2026-09-06
    else:
        # 非action(正常answer/final): 死循环检测仅在action语义下, 归零防残留(含纠偏标记) — 小欧 2026-08-08
        agent._consecutive_same_tool_calls = 0
        agent._last_tool_call_sig = None
        agent._warned_same_tool_loop = 0            # int计数归零 — 小欧 2026-08-08

    # ── 场景E: 正常分发 ─────────────────────────────────────────
    agent._consecutive_truncations = 0
    # _dispatch_handler 返 list, 逐条 publish 收口(事件直写 event_log) — 小欧-2026-09-06
    for event in await _dispatch_handler(agent, llm_response):
        await _emit_publish(event.to_dict())
    return []  # 4C(5.8.2): 普通 async 返 List, 事件已全量 publish, 列表空由主循环消费 — 小欧-2026-09-06


