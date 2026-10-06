
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-13 - 小欧 - 移除事件循环内重复prompt日志写入(已由_append统一记录)
# 2026-07-14 - 小欧 - 运行期逐步落库chat_message_steps表, finally仅轻量终态更新; 三退出路径均写入steps, ai_message_id未分配时沿用原有写入逻辑保证完整性
# 2026-07-16 - 小欧 - FinalStep 事件更新 stream_state.current_thought; finalize_message 调用传 thought 参数
# 2026-07-18 - 小欧 - FinalStep多态自包含终态重构: 三退出路径统一产出FinalStep(outcome=xxx);
#   【病根】原②取消用MetaStep+手动写DB/日志/SSE, ③失败用ErrorStep+手动写DB/日志/SSE,
#          步骤构建→落库→日志→SSE四步散落在三条路径, 改一处漏一处;
#          且MetaStep/ErrorStep不含response_text, 导致body为空(unit-09)。
#   【改法】①import加FinalStep ②取消路径: 删MetaStep手动写逻辑, 改由finally守卫补FinalStep
#          ③失败路径: ErrorStep→FinalStep(outcome="failed"), 仍手动写(异常分支无守卫)
#          ④finally守卫: 检测current_execution_steps无type=final时, 按agent.status补发FinalStep
# 2026-07-18 - 小欧 - prompt-log生命周期归属修正: 生产者全权拥有创建(start_request)/写入(log_step_yield)/设态(set_terminal_status)/存盘(save), 消费者openai.py完全退出日志层
# 2026-07-18 - 小欧 - 修复: 删除失败路径(219)与守卫路径(259)的手动log_step_yield调用;_append(:93)已统一记一次, 消除终态FinalStep prompt-log双写
# 2026-07-22 - 小欧 - MAX_CONTEXT_CHARS→MAX_CONTEXT_TOKENS 运行时覆盖赋值同步
# 2026-07-23 - 小欧 - 修复: 热循环+finally共5处db.get_conn→get_conn_with_retry(指数退避重试)
#   【病根】每个ReAct步新建sqlite3连接写chat_history.db,多任务并发时写者间排他→锁30s超时→DB operation failed
#   【改法】①5处"db.get_conn("chat")"改为"db.get_conn_with_retry("chat")"(database.py新增指数退避重试)
#          ②finalize retry(L285)加except sqlite3.IntegrityError: break(UNIQUE不重试,YAGNI)
#          ③新增"import sqlite3"
#   【合规】KISS-DIRECT(不绕到上层重试引擎)+YAGNI(IntegrityError不重试)
# 2026-07-30 - 小沈 - Shell池清理: 导入shell_pool; finally块加shell_pool.cleanup_by_task(task_id)
# 2026-07-30 - 小沈 - except:pass补日志: reclaim_stream_buffer调度失败改为logger.debug记录
# 2026-08-13 - 小沈 - agent→chat反向引用回调解耦: 删除3条chat模块import(save_execution_steps_to_db/
#   allocate_and_insert_message/append_execution_step/finalize_message/_load_previous_messages/_log_task_end),
#   改为通过 db_ops 命名空间对象注入(调用方stream_orchestrator构造注入), 消除agent→chat反向依赖,
#   依赖方向变为 chat→agent 单向。db_ops 为 types.SimpleNamespace, 6个属性对应原6个chat函数,
#   KISS-DIRECT(一个参数替代6个回调, 不引入Protocol/ABC新抽象)。
# 2026-08-16 - 小欧 - finally 终态落库: finally log_task_end 旁 UPDATE chat_tasks 终态(update_task)+
#   token_usage 收终态逐 usage 入库(insert_token); total_steps 剔全部非业务MetaStep(对齐 _log_task_end 口径);
#   error 从末条 final 实算(无伪 _final_err); token llm_call_count 取 usage 的 step 序号(=agent.llm_call_count)
# 2026-08-16 - 小欧 - 三堂会审修复: update_task 的 error 提取原条件 `not stream_state` 恒 False(orchestrator 正常路径
#   stream_state 恒为 StreamState 实例 truthy)→任务失败时 chat_tasks error_type/error_message 永远为空(信息丢失);
#   改为按 `_terminal_status == "failed"` 判定后从末条 final 实取(异常分支必先 append final_dict, 取数可靠)
# 2026-08-18 小欧 - 通道路由: 通道路由(thought仅落库/thought-start仅SSE/其余SSE+落库); final短信号(completed不带response); reasoning替代thought
# 2026-08-18 - 小健 - 三堂会审修复(通道路由缺陷): ①通道路由新增 chunk 仅SSE不落库(total_steps自动剔除chunk虚高); ②final短信号改 step+action轮判定(_has_chunk_steps/_action_steps), 根治 return_direct 同轮先发正文chunk致response被剥的边界; ③短信号只改SSE, 落库与 stream_state.current_content 仍用完整 response 不退化
# 2026-08-18 - 小欧 - 弃用next_step: 删 next_step 参数; s=agent.llm_call_count or 1; 守卫 FinalStep(step=agent.llm_call_count or 1)
# 2026-08-18 - 小欧 - 错误全仅SSE: 通道路由 error/usage/paused/resumed/retrying/cancelled 划入仅SSE集合分支(不落库); 守卫改读 agent._last_error 填充final; insert_token 改读 agent._usage_events
# 2026-08-18 - 小欧 - 终态步骤集: _m_skip 收敛为 {cancelled,authorization_required,start}
# 2026-08-18 - 小欧 - start 信号: 通道路由新增 start 分支(_persist落库分配ai_message_id后合成 startinfo 仅SSE复用同id)
# 2026-08-18 - 小欧 - 三堂会审复核: 守卫(:326)/异常分支(:287) FinalStep step 取值的 agent 空防御统一(与 :322 getattr 防御对齐), 防 agent=None 时 AttributeError
# 2026-08-19 - 小欧 - v2.0核心数据模型重构: import update_user_message_final/safe_json_dumps;
#   update_task同with块内新增chat_user_message final回填(改动2)+chat_tasks.ai_message_id回填(改动9);
#   saved_content/saved_thought提前到if current_execution_steps外定义(修复作用域, backfill需要)
# 2026-08-20 - 小欧 - token 四层同构累计三堂会审修复: token_usage 落库 llm_call_count 去掉 agent.llm_call_count 终值回退(改 `or 0`), 用记录时步号, 防多事件同名 step 致 token_usage 重复行
# 2026-08-20 - 小欧 - start_time 同源透传: run_agent_in_background 将 stream_orchestrator 的 start_time 透传给 agent.run_react_cycle(原漏传 None), 任务真实起点同源, 供遥测首包时延/耗时计算与 stream_orchestrator 一致
# 2026-08-20 - 小欧 - 每轮即时落库的配套收敛(北京老陈裁定): 任务/会话 token 累计落库已前移 react_cycle 每轮即时写(运行中DB实时), 本文件 finally 块不再重复调 update_task/session_accumulation(防同批 token 重复累加翻倍), 仅保留 token_usage 明细 insert_token
# 2026-08-21 - 小欧 - 终态 update_task 补传 artifacts(telemetry._artifacts 内存态)
# 2026-08-21 - 小欧 - 差异设计落地: 终态 update_task 的 accumulated_usage 改
#   db_ops.query_task_acc 从 chat_tasks.task_accumulated_tokens 权威列读出写入(不再取 agent 内存快照, 单权威账);
#   finally 新增对账告警——token_usage 明细 SUM vs 权威累计列不一致即 warning(不阻断, DB 故障降级 warning);
#   签名新增 ai_message_id 参数(orchestrator eager 注入), 局部 None 初始化删除, prompt-logger 绑定
#   update_ai_message_id 迁至函数头 eager 执行; _persist 惰性分配双分支塌缩为单分支(恒 append_step);
#   finally legacy save_steps 兜底分支删除+chat_tasks.ai_message_id 终态回填块删除(创建时已写, 冗余 UPDATE 移除)
# 2026-08-21 - 小欧 - 对账告警三堂会审修复: 对账告警块补 db_ops 守卫(if db_ops and hasattr(db_ops, 'query_task_acc')),
#   防 db_ops=None/注入不完整时 AttributeError; 守卫风格与 update_task/insert_token 块一致(KISS/合规)
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26: ①startinfo 删 display_name 键(设计要求2:
#   display_name 后端零依赖仅前端派生); ②update_user_message_final 回填改传 task_model=ModelRef(provider,model)
#   (chat_user_message 落 chat_model JSON 单列); import 补 ModelRef
# 2026-08-23 - 小欧 - 三轮三堂会审修复: update_user_message_final 回填处 ModelRef(provider=None) 必抛
#   ValidationError——现网 FinalStep 均未传 final_model 致键值恒 None, 回填整体失败连带丢 response/reasoning;
#   改仅 provider/model 均非空才构造 ModelRef, 否则落 NULL(与旧行为等价)
# 2026-08-23 - 小欧 - 落盘文件A/B 实施(文档落码): update_task 成功后 agent.file_persist.finalize(status)
#   写 A/B footer(getattr 守卫+try/except); 补 finally 级兜底——db_ops 缺失/update_task 抛异常时
#   finalize("failed") 幂等收口(_closed 守卫), 杜绝 worker 协程悬挂
# 2026-08-24 - 小欧 - 后端卡死修复: 落库热路径(append_step/append_step失败终态/finalize/update_task+回填chat_user_message/insert_token/token对账)全部经 db.atxn 进子线程 offload 出事件循环,
#   loop 不再被同步 sqlite3 I/O + time.sleep 锁重试独占, 根治 /health 超时/console 冻结; storage.* 与连接管理零改动复用;
#   _fp.finalize(非DB文件写)移出事务块: 成功路径等价, 失败路径更稳(footer 失败不再连坐回滚 update_task 事务, 仅告警)
# 2026-08-24 - 小欧 - 终态必达加固: 新增 _persist_final(shield薄壳), 包裹 finally 内两处终态关键写
#   (finalize / update_task+回填chat_user_message)——finally 期间再收 cancel 时内层事务脱离外层继续执行,
#   重试 await 保终态落库必达(等待有界: 锁退避上限~3.5s); insert_token明细/对账告警非关键写不包(YAGNI)
# 2026-08-24 - 小欧 - 问题报告三堂会审修复: ①过时注释修正(save_execution_steps_to_db→DB落库finalize/update_task, 重构后函数已删除); ②孤儿task日志噪声抑制(_persist_final双重cancel下try/except捕获二次CancelledError, return None降级, logger.debug记知悉级, 不re-raise防重入)
# 2026-08-24 - 小沈 - ISS-001 根治: 原修复仅catch二次CancelledError但未retrieve孤儿task异常(注释自承认"异常由loop兜底记WARNING"即日志噪声仍在);
#   改用 add_done_callback 无条件调 t.exception() 确保异常必达retrieve, 从源头杜绝 "Task exception never retrieved" 日志噪声(三堂会审: CancelledError继承BaseException非Exception, 原报告建议except Exception有缺陷不采用)
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 整删finalize_message回调及其调用——删除stream_orchestrator.db_ops.finalize=传参与agent_runner行446-461的finalize调用块(原写chat_messages终态); 终态content/status/thought由append_execution_step(step_json)与_finalize_task_db(update_task+回填chat_user_message)承载, 系统对该表零写依赖
# 2026-08-30 - 小欧 - 落库收口(设计文档, 北京老陈 2026-08-30 批准): _persist 内对 thought 步骤仅规约 content/thought/reasoning 三字段文本(调公用 normalize_blank_lines, 新数据入库即净), 其它类型/其它字段绝不触碰(防 tool_result/命令输出代码块多空行语义被误伤); import 补 normalize_blank_lines
# 2026-08-30 - 小欧 - _finalize_task_db accumulated_usage双重编码修复: 去掉外层safe_json_dumps(根因: query_task_acc已返回dict, update_task内已调safe_json_dumps, 外层再包一次致双重编码前端解析失败显null)
# 2026-09-06 小欧 4C(与同批commit齐发): run_react_cycle 收敛普通 async后, 本层由
#   "async-for yield 逐条处理"改"订阅消费"——run_react_cycle 内事件已由 react_step/react_loop publish 直写
#   event_log(带 seq), 完成后取缓冲快照(list)逐条走既有的通道路由(_persist 落库/SSE 标记/current_content)不变;
#   SSE 实时性不受影响(stream_reader 独立协程按 seq 实时读), DB 落库由本层扫描完成(崩溃前已 publish 事件含
#   异常路径 error/final 全量可读不丢); 双发修正(设计): 订阅体内已 publish 事件不再 _append(否则 SSE 双发
#   违反 event_log 单一 seq), _append 仅保留自产事件(startinfo/异常final/守卫补发); 订阅体补 prompt-log
#   log_step_yield(原 _append 内记录, publish 不记, 订阅侧补齐); buffer 缺省 create_task_stream_buffer ensure
#   (react_loop/react_step 需缓冲 publish) — 小欧-2026-09-06
# 2026-09-06 小欧 4C: 终态 SSE 单发根治——publish 终态(final/final_stats)实时已被 stream_reader
#   按 seq 读走(完整条), finally 统一补发的剥离(短信号)/统计条改为"覆写 publish 原位(保 seq)", 不再 _append
#   新增 seq: 原实现 event_log 内 final 双条(publish 完整 + 补发短/完整)致 SSE final 双发(bug, 专项测试捕获);
#   覆写后 event_log 每种终态单条: 短信号场景前端仅见剥离条, 完整场景原位即完整, 守卫补发(无 publish 原条)仍 _append;
#   零新增抽象, 覆写幂等(同内容覆写等价); final_stats 同法去重 — 小欧-2026-09-06
# 2026-09-06 小欧 方案C三堂会审缺陷修复(独立user_rejected不落库):
#   独立 type="user_rejected" 后, 该事件不在仅SSE集合 {error,usage,paused,resumed,retrying,cancelled} 内 →
#   通道路由落 else _persist 写库, total_steps 虚增 + 违反"拒绝仅SSE不落库"设计(全拒步 DB 出现无观察配对残步)。
#   [修复] 该集合补 "user_rejected"(按 拒绝/拦截类均非业务步, 不落库不计数 的设计精神)
#   blocked/timeout 走 error 已仅SSE; 前端 deniedStepSet 靠 SSE 独立事件聚合(不受落库影响) — 小欧-2026-09-06
# 2026-09-06 小欧 B2方案C核心(北京老陈裁定, 与 handle_action 预览/规范/拒绝独立事件同commit):
#   通道路由 action 分支识别 _live_only 预览标记(handle_action 早发, tools=all_calls 仅SSE齿轮先行)——
#   带标记跳过 _persist 落库(prev 不落), 无标记 canonical(tools=_exec_calls 真实执行集)照常 _persist;
#   恢复 09-04"拦截/拒绝的action不落库"不变式 + 全拒步无"有action无observation"DB残步; total_steps 口径不变 — 小欧-2026-09-06
# 2026-09-06 小欧 单写入口退役(_append→_publish 统一, 85214690a):
#   startinfo/异常final/守卫补发/终态补发四处自产事件原 _append 直接追加 event_log, 与 publish
#   (经 merge_meta_seq 分配 seq)并存为双写路径 → seq 分配竞态且同序事件来源分裂;
#   [修复] 四处改走 _publish(buffer.publish 同源同序, stream_reader 按 seq 流读无破绽), _append 退役 — 小欧-2026-09-06
# 2026-09-06 小欧 preview 不入 Prompt 日志(6009edc1b, DB-Prompt 对账 2x 二次根因):
#   B2方案C每轮双 action(preview 齿轮先行 + canonical), 订阅体对 preview(_live_only) 也调 log_step_yield →
#   Prompt 日志比 DB 多 preview 行(2x 误报, 对账表);
#   [修复] 订阅体补 `if not event_dict.get("_live_only")` 才 log_step_yield(Prompt 仅记业务 canonical 步) — 小欧-2026-09-06
# 2026-09-07 小欧 消息分类方案(前端消息分类处理分析及设计-小欧-2026-09-06.md, 北京老陈批准):
#   start/startinfo 双信号拆分——startinfo 合并入 start:
#   ① run_agent_in_background 入口将 eager ai_message_id 透传挂到 agent._ai_message_id(供 react_loop start 发布前装配);
#   ② 删 start 分支 startinfo 派生构造 13 行, 仅保留 _persist 落库(start 已自带 ai_message_id);
#   ③ 通道路由注释同步(start/startinfo 不再双发, startinfo 事件从链路移除, 前端不再消费) — 小欧-2026-09-07
# 2026-09-08 小欧 方案五(G路径, 北京老陈 2026-09-08, 见doc-9月优化):
#   ②CancelledError 取消分支(CancelledError 系 orchestrator 异常→bg_task.cancel() 触发, G路径):
#   未标记来源时置 agent._cancel_source="orchestrator_error"; finally 守卫 CANCELLED 分支文案改
#   cancel_terminal_text(source) 按来源出; 守卫 FinalStep 携带 cancel_source 落库/下发(A-G全覆盖)
# 2026-09-08 小欧 补缺日志(北京老陈"新改代码需合理log"核查): G路径来源定级处补 logger.info
#   ("未标记取消来源, 定为 orchestrator_error"), 取消终态文案出处排查不再无痕 — 小欧-2026-09-08
# 2026-09-08 小欧 北京老陈指令(console可见性): G路径来源定级 logger.info→log_and_print 双写,
#   后端命令行可见"未标记取消来源,定为orchestrator_error"; 另 B2 守卫兜底补发取消终态补 logger.info(仅文件)
#   — 小欧-2026-09-08
# 2026-09-11 小欧 - 方案: ①新增 _publish_final_stats 延后单发(门禁+兜底帧+先落库t3后发布t3'+落库失败照发);
#   ②死码清理3处(_final_stats_publish_index/扫描循环收集/finally覆写); ③短信号补 duration — 小欧-2026-09-11
# 2026-09-11 小欧 - 修复: _publish_final_stats 包裹 try/except ValueError, build 异常降级走兜底帧,
#   防 outcome="" + agent.status=None 致 ValueError 崩溃 — 小欧-2026-09-11
# 2026-09-11 小欧 - 修复: 兜底帧 step 从硬编码 0 改为 agent.llm_call_count, 与正常帧对齐 — 小欧-2026-09-11
# 2026-09-12 小欧 - X2 终态长短信号分离(方案): 扫描侧长短判定/终态缓冲机制退役, 收窄为"从发射侧缓存取长条落库":
#   ①删扫描侧状态声明(_has_chunk_steps/_action_steps/_pending_terminal_events/_final_publish_index, L244-251);
#   ②删扫描侧 chunk/action 登记(_has_chunk_steps.add/_action_steps.add, L405-417; action 落库逻辑 B2 方案C 原样保留);
#   ③final 分支落库改取 agent._pending_final_db 长条(短条场景 DB 恒完整 response) + 消费即清(置 None 防重复落库),
#     长条场景(failed/cancelled/return_direct)缓存在兜底 `_pending_final_db or event_dict` 下落现条完整件;
#   ④finally 覆写/补发段整体删除(L642-653, _final_publish_index 覆写与 _pending_terminal_events 补发,
#     event_log 原位即应转发形态, G2 根治); 保留 _persist_final 与 _publish_final_stats(延后单发 DB 就绪信号) — 小欧-2026-09-12
# 2026-09-12 小欧 - X2 竞态根因修复(方案): 删除临时 [Diag] 诊断日志
#   (final_stats before_publish/publish done), _publish_final_stats 还原为纯"先落库后发布";
#   根因在 react_loop 内部两处过早 done.set()(详见 react_loop.py 编辑历史 2026-09-12 条目),
#   本文件 done 权威置位 L708-713 唯一保留(所有事件含 final_stats 发布完成后) — 小欧-2026-09-12
# 2026-09-12 小欧 - 追踪关键日志(北京老陈指令): ①_publish_final_stats 发布后补 logger.info(seq/status),
#   供比对 SSE 是否收全终态; ②done 置位后快照缓冲状态(last_type/has_final_stats), 监控"置位时终态是否已入队"
#   (E2E-X2-01 竞态监控点, 若末类型非 final_stats 即 SSE 提前关闭根源) — 小欧-2026-09-12
# 2026-09-13 小欧 - TDD 修复(行338): _publish_final_stats 日志 status 由引用闭包变量 _fs_outcome
#   改为本函数入参 outcome——_fs_outcome 仅在本函数外 finally 赋值, 闭包耦合潜在 NameError(free variable referenced
#   before assignment), 现靠唯一调用点先赋值侥幸躲过; 改 outcome 消除闭包耦合(违 KISS-DIRECT/SLAP), 行为不变
# 2026-09-13 小欧 - TDD 修复(行258-259): X2 删除标记注释改述——原称"L244-251 删除", 但 L244-248
#   (缓冲缺省 ensure create_task_stream_buffer) 仍是活代码, 注释与实际矛盾误导读者; 改为仅述"长短判定/终态缓冲/
#   finally 覆写机制已删除", 明确缓冲 ensure 保留在役
# 2026-09-17 小欧 - 统一拒绝事件 type="rejected": 行433 SSE集合新增 "rejected"(原 "user_rejected") - 小欧-2026-09-17
# 2026-09-17 小欧 会审V3(#13): 行435 SSE仅转发集合注释更新(user_rejected 表述更正为已统一 rejected, 原注释过时) - 小欧-2026-09-17
# 2026-09-20 - 小欧 - 锚回填修复(B组, 配合 message_builder 锚演进): 终态 update_user_message_final 的
#   user_message_id 由 db_ops.user_msg_id 改为优先取 agent.message_builder.current_user_msg_id(B机制注入消息经
#   _absorb_inbox 落库取真实 uid 演进锚), DB 层 db_ops.user_msg_id 仅兜底 —— B机制注入的 user 消息回填不再落空。
#   compliance: SRP/DRY(锚单点在 message_builder)/禁止backward
# 2026-09-20 - 小欧 - 修复(共享池快照免误关): close 分支由 base_service.close 判据兜底——共享池快照
#   仅"独占才真关", 快照 close 不再误杀同池其他会话(工作区代码 L527-528)。
# 2026-09-20 - 小欧 - D-1修复(B机制注入消息DB幽灵): 终态 update_user_message_final 增传 session_id,
#   由 storage 侧对该注入 user_message_id 补 chat_tasks 配对(注入消息答复归属任务), 消除 fetch 重建"user+AI"对时的
#   NULL 幽灵(前端双栖渲染/linked 误判未回答)。compliance: KISS-DIRECT/禁止backward
# 2026-09-25 小欧 - finally 关客户端判据改无条件: resolver 恒返回任务私有快照(_is_snapshot 死判据消亡),
#   关闭语义由 base_service.close 三分支兜底(共享 lease 归还幂等/独占 aclose/单例 no-op) — 使用说明
# 2026-09-28 - 小欧 - 活跃任务注入：终态回填 _active_uid 加 uid>0 守卫,
#   None/0/合成负id 一律回落 db_ops.user_msg_id 兜底 — 小欧 2026-09-28
# 2026-09-29 小欧 - import 改唯一创建入口 create_task_stream_buffer + reclaim_memory_buffer；
#   直连兜底建 buffer 时同样注入落库能力（漏注入则跳过编排层直跑的任务只写内存）— 小欧 2026-09-29
# 2026-09-29 20:42:06 小欧 - 并发撞锁加固: ①_persist 补 ai_message_id is None 防线(对齐异常分支/守卫兜底分支
#   两处既有 `if ai_message_id is not None` 守卫风格, 落库前 return + ERROR 留痕, 杜绝任务行未建立时
#   NOT NULL 抛穿成 ERROR/Traceback 风暴); ②_persist/异常终态/守卫兜底终态/终态 UPDATE 四处
#   append_step+_finalize_task_db 启用 atxn(retry_locked=3) 有限重试(终态 UPDATE 撞锁失败会致任务永久
#   executing, 严重性最高) — 小欧-2026-09-29
# 2026-10-01 小欧 - 解 [1] A 组(运行期逐步落库, 步骤落库前移到运行期, 见 doc-10月优化/[1]刷新后显示其他任务结果):
#   ①退役"末尾扫描 event_log 批量落库"机制(该机制致步骤只在终态可见, 中途崩溃/被重启打断即全丢), 改由
#      StreamBuffer.persist_sink 回调在 publish 收口实时投递本模块的 _route_step_to_db; 新增 _enqueue_step/
#      _write_step/_drain_steps/_flush_steps/_persist_sink/_step_usage_json/_write_token/_enqueue_user_final/
#      _write_user_message_final 八函数: 队列单消费者 FIFO 顺序落库、_enqueue 只做 O(1) 投递不阻塞事件产生、
#      _flush_steps 在终态写前必调保证 DB 与内存统计同源; _write_step 有限重试且失败只记不抛(A4/A9/A12);
#   ②token_usage 明细实时落库(A10), finally 不再批量插; chat_user_message 正文运行期回填(E13);
#   ③total_steps 改走 agent_telemetry.count_business_steps(解 E1/E2/4-1, 口径单一真源);
#   ④落库消费者收尾: 哨兵移至 done.set 之前(实测原顺序致消费者提前退出后 join 永久挂起 → finally 永不完成
#      → done 不置位 → SSE 挂死); 存量数据不回填(北京老陈裁定只改代码不碰存量) — 小欧-2026-10-01
# 2026-10-02 小欧 - 轮次边界 flush(北京老陈定案): 增 buffer.flush_sink = _flush_steps, 由 react_loop
#   每轮迭代顶调用。_enqueue_step 只入队即返回, 进程被杀则队列内帧全丢(实测 task_interrupted 样本
#   chat_task_steps 0 行而 Journal 事件齐全)。每轮 join 一次, 被打断最多丢本轮(无工具副作用)。
# 2026-10-03 - 小欧 - refactor: SSE 不落库集合去重(删本地 _SSE_ONLY_TYPES 硬编码, 改 import agent_telemetry.SSE_ONLY_TYPES 唯一真源; 转发表改由 ALL_STEP_TYPES 推导。文档[5] 5.2 D4)
# 2026-10-05 小欧 - _flush_steps: 消费者死亡即时止损(原只等 join 120s 超时); file_persist 落库队列入队改工厂化(杜绝 ne
# 2026-10-06 小欧 - 报告核查修 P0-01/P3-08: ①update_ai_message_id 移到 start_request 之后(原序写入上一请求
#   残留 log 且新 log 该字段恒 None, 实测 79.13% 落盘为 null); ②log_step_yield 的 round_number 改取
#   agent.llm_call_count(原取 ed["step"], 致「轮次」恒等于步骤, 实测 100%)ver awaited 泄漏告警)。
"""
agent_runner — agent 后台运行器（与 SSE 传输解耦）

北京老陈 2026-07-12: 将 agent 执行从 HTTP handler 解耦为独立后台任务。
事件写入 agent_streams[task_id].event_log（append-only，含 seq），
SSE 连接只从 event_log 按 seq 偏移读取，支持断线重连。 — 小欧 2026-07-12

设计原则：
- SRP: 本模块是"生产者"单一职责，只负责运行 agent + 写事件缓冲
- DRY: 复用 run_react_cycle / db_ops 持久化回调
- KISS-DIRECT: 无注册表/无抽象层，直接写缓冲
- 禁止 backward: 不保留旧 run_sse_stream 调用方式
- 持久化: 不直接 import chat 模块, 持久化能力通过 db_ops 注入
"""

import asyncio
import itertools
import sqlite3
import time
from typing import Any, Dict, List, Optional

from app.db import db
from app.db.models.chat_models import ModelRef   # 归一: 模型身份唯一结构 — 小欧 2026-08-22
from app.services.agent.steps import ErrorStep, MetaStep, FinalStep  # 小欧 2026-07-18: 加 FinalStep（多态自包含终态）
from app.services.agent.status_table import AgentStatus, set_cancelled, set_failed
from app.services.task.task_registry import task_cleanup
from app.tools import cleanup_shell_pool_by_task  # P5a: 从门面导入 — 小沈 2026-08-13
from app.services.task.task_state import (
    running_tasks, running_tasks_lock,
    agent_streams, create_task_stream_buffer, reclaim_memory_buffer,
)
from app.services.chat.stream_event_journal import append as journal_append   # [63] 3.6.5 直连兜底注入 Journal sink
from app.logger import logger, log_and_print  # 2026-09-08 小欧: log_and_print 双写(console可见G路径定级) — 小欧-2026-09-08
from app.logger.prompt_logger import get_prompt_logger
from app.utils.time_utils import get_local_iso_timestamp  # S2 update_task end_time(10.1.7②-1) — 小欧 2026-08-16
from app.services.chat.storage import update_user_message_final  # v2.0 改动2 — 小欧 2026-08-19
from app.monitoring.agent_telemetry import count_business_steps, SSE_ONLY_TYPES  # total_steps 口径单一真源(解 [1] E1/E2/4-1); SSE_ONLY_TYPES 落库侧过滤集(文档[5] 5.2 D4 去重) — 小欧 2026-10-01 / 2026-10-03
from app.utils.json_utils import safe_json_dumps  # v2.0 改动2: accumulated_usage序列化 — 小欧 2026-08-19
from app.utils.text_utils import normalize_blank_lines  # 13.11 落库收口 — 小欧 2026-08-30


# 后台任务强引用表: asyncio 仅持有 Task 弱引用, 若 SSE 消费者断开后任务再无强引用,
# 会被 GC 回收并取消, 导致 finally 的 DB落库finalize/update_task 被打断、结果丢失。
# 集中持有强引用, done 时 discard 防内存泄漏 — 小欧 2026-07-13
_background_tasks: set = set()


# 仅 SSE 不落库的事件类型 — 直接用 agent_telemetry.SSE_ONLY_TYPES(落库侧唯一真源, 2026-10-03 由本地
# 硬编码改 import; 原别名 _SSE_ONLY_TYPES 已删, 禁 backward 不留同义名) — 小欧 2026-10-03

# 落库队列排空超时上限(秒) — 小欧 2026-10-01
#   单帧落库实测 0.6~1.1s(stream_event_journal 注释), 百步任务约 1~2 分钟, 留足余量;
#   仅为"消费者不可用"时的挂死兜底, 正常路径远达不到。
_STEP_FLUSH_TIMEOUT_SEC = 120.0


async def _persist_final(coro):
    """终态落库防二次 cancel 薄壳(shield) — 小欧 2026-08-24

    为什么需要它:
        run_agent_in_background 的 finally 内改为 await db.atxn 后, 若 finally 期间
        任务再次收到 cancel, await 被打断 → 终态 finalize/update_task 可能未落库。
        (旧同步写在 cancel 下必完成, 此处补齐等价保证。)
    设计要点:
        - shield 首次被 cancel 打断时, 内层事务 task 已脱离外层继续执行;
        - 立即重试 await 内层一次(此时取消已消费, 通常直接等到完成);
        - 极端下再次被 cancel, 内层 task 仍独立跑完(loop 存活即必达);
        - 等待有界: get_conn 锁退避上限 ~3.5s + 单条 SQL, 不会悬挂回收。
    已修复(原知悉级边缘):
        双重 cancel 下内层 task 被遗弃为孤儿, 其完成时异常无人 retrieve →
        "Task exception never retrieved" 日志噪声。现 add_done_callback 确保异常必达 retrieve,
        杜绝日志噪声, 不影响数据正确性。 — 小沈 2026-08-24
    """
    _t = asyncio.ensure_future(coro)
    # 孤儿task异常必达retrieve: 双重cancel下 await _t 被 cancel 时内层 task 仍独立跑完,
    # done_callback 无条件调 t.exception() 标记异常已retrieve, 杜绝 "Task exception never retrieved" 日志噪声 — 小沈 2026-08-24
    _t.add_done_callback(lambda t: t.exception() if not t.cancelled() else None)
    try:
        return await asyncio.shield(_t)
    except asyncio.CancelledError:
        try:
            return await _t
        except asyncio.CancelledError:
            # 双重cancel: _t 已脱离外层继续运行(loop存活即必达), add_done_callback 已确保异常被 retrieve
            # 不 re-raise 避免外层 CancelledError 重入; return None 等价终态降级 — 小沈 2026-08-24
            logger.debug(f"[Shield] 双重cancel, 孤儿task异常已由done_callback retrieve")
            return None


async def run_agent_in_background(
    agent,
    task_id: str,
    last_message: str,
    context: Optional[dict],
    session_id: str,
    stream_state: Any = None,
    start_time: Optional[float] = None,
    db_ops: Any = None,  # 持久化操作命名空间(由调用方注入), 消除agent→chat反向依赖 — 小沈 2026-08-13
    ai_message_id: Optional[int] = None,  # 12.2-C4: orchestrator eager分配注入(原首步惰性) — 小欧 2026-08-21
) -> None:
    """后台运行 agent，事件追加到 event_log，结束置 done。

    解决什么问题：前端 SSE 断线时，FastAPI 会取消 handler 协程；
    若 agent 在 handler 内运行，断线即终止 agent。解耦后 agent 在
    独立后台任务运行，断线不影响，前端可重连读取同一 event_log。 — 小欧 2026-07-12
    """
    # 强引用自身任务, 防止 SSE 消费者断开后任务被 GC 回收→取消→打断 finally 的 DB 保存
    # (功能退化修复: 升级前 LLM 正常/异常结束 DB 均落库, 升级后断流导致任务被回收而丢失结果)
    # 与 openai.py 声明的"断线不影响 agent"解耦设计一致 — 小欧 2026-07-13
    _self_task = asyncio.current_task()
    if _self_task is not None:
        _background_tasks.add(_self_task)
        _self_task.add_done_callback(_background_tasks.discard)

    buffer = agent_streams.get(task_id)
    if buffer is None:
        # 4C(5.8.5): 缓冲缺省 ensure —— react_loop/react_step 在 run_react_cycle 内经 publish 直写 event_log,
        #   无缓冲时 react_loop 抛 RuntimeError; 此处确保既有直连入口(跳过 stream_orchestrator)亦可创建 — 小欧-2026-09-06
        # 直连兜底同样注入落库能力（与编排层两条路统一，禁裸调旧入口）— 小欧 2026-09-29
        buffer = create_task_stream_buffer(task_id, session_id, journal_append)
    current_execution_steps: List[Dict] = []
    end_type = "unknown"
    # 4.4.3(2026-09-07 小欧): ai_message_id 透传 agent 层, 供 react_loop start 发布时携带;
    #   startinfo 合并入 start 的前提(eager 值在 run_react_cycle 启动前已就绪, 无需延迟 publish)
    agent._ai_message_id = ai_message_id
    # X2(2026-09-12 小欧): 长短判定/登记上移 react_step 发射侧(_emit_publish, agent._final_short_ctx),
    #   终态缓冲+finally 覆写机制整体移除(见 4.2.4); 上方 L244-248 缓冲缺省 ensure 保留在役(直连入口) — 小欧 2026-09-12

    # [新] 生产者全权拥有 prompt-log 生命周期(创建) — 小欧 2026-07-18
    get_prompt_logger().start_request(last_message, session_id)
    # 2026-10-06 小欧 修 P0-01 时序倒置: 必须 AFTER start_request(建新 log) 再填 ID;
    #   原在本行之前(12.2-C4 eager 注入), 写入的是上一请求的残留 log, 而 start_request 新建的
    #   log 里 AI消息ID=None 且无后续补写 → 实测 2426/3066 落盘文件(79.13%)该字段为 null
    if ai_message_id is not None:
        get_prompt_logger().update_ai_message_id(str(ai_message_id))

    async def _publish(event_dict: Dict) -> int:
        # 4C 收尾(2026-09-06 小欧): 自产/边缘事件统一改经 StreamBuffer.publish 发射,
        #   seq 分配+append+notify_all 持锁原子权威在 publish(task_state.StreamBuffer),
        #   私有 _append 写 event_log 入口退役(5.8.1 "删事件转发入口"单一写入口收口) — 小欧-2026-09-06
        # Prompt 日志与落库路由均由 buffer.publish 的 persist_sink 承担(小欧 2026-10-01):
        #   事件另有直连 buffer.publish 的路径(handle_action 的 thought/observation),
        #   本函数覆盖不到, 故不在此记账——避免同事件双记且不留漏记缺口。
        return await buffer.publish(event_dict)

    # ── step 实时落库(运行期逐步落库, 解 [1] A 组) ── 小欧 2026-10-01
    # 设计: _publish 单点投递(投递顺序=event_log 顺序) → 单消费者 FIFO 队列顺序落库。
    #   投递 O(1) 不 await 事务, 事件产生零阻塞; 崩溃前 finally flush 即 storage.py:3 承诺的"渐进耐久"。
    #   DB 读取一律 ORDER BY step_index, 故落库先后不影响回放顺序(解 R5)。
    _step_queue: asyncio.Queue = asyncio.Queue()
    _step_seq = itertools.count()   # 独立步序号, 不依赖 current_execution_steps 长度(解 A2/A5/A6)

    # usage 按 step 号索引缓存 — 小欧 2026-10-01
    #   原逐条扫 _usage_events(解 A15 O(n²)): 实时落库后每事件都调, 长任务浪费显著。
    #   只在命中时缓存, 未命中不写 — 允许"该步落库时 usage 尚未到达"的情形后续补取。
    _usage_by_step: Dict[int, Dict] = {}

    def _step_usage_json(ed: Dict) -> Optional[str]:
        """按 step 号取所属 LLM 轮 usage 明细 — 小欧 2026-10-01
        usage 事件本身仅 SSE 不落 chat_task_steps, 本列承载同轮副本, 与 token_usage 同口径。
        时序保障: react_step 在 usage SSE 发布前已 append(_usage_events), 故实时落库必能取到。"""
        no = int(ed.get("step") or 0)
        hit = _usage_by_step.get(no)
        if hit is None:
            for u in (getattr(agent, "_usage_events", None) or []):
                if int(u.get("step") or 0) == no:
                    _usage_by_step[no] = hit = u
                    break
        if hit is None:
            return None
        return safe_json_dumps({
            "prompt_tokens": hit.get("prompt_tokens"),
            "completion_tokens": hit.get("completion_tokens"),
            "total_tokens": hit.get("total_tokens"),
        })

    async def _write_step(idx: int, ed: Dict, usage_json: Optional[str]) -> None:
        """单步落库: 有限重试 + 失败只记不抛(解 A4/A9/A12) — 小欧 2026-10-01
        绝不向上抛: 抛穿会打断 finally 后续终态链(update_task/done.set)致 SSE 挂死,
        亦会杀死消费者致 _flush_steps 永久挂起。"""
        try:
            await db.atxn("chat", lambda conn: db_ops.append_step(
                conn, ai_message_id, session_id, idx, ed, usage=usage_json), retry_locked=3)
        except Exception as _se:
            logger.error(f"[Runner] 步骤落库失败(task={task_id}, idx={idx}): {_se}")

    async def _write_token(step_no: int, ed: Dict) -> None:
        """token_usage 明细实时落库(解 A10) — 小欧 2026-10-01
        原为 finally 批量插, 进程被杀则全丢; 与累计列(react_step 每轮已写)口径对齐到"运行中可见"。"""
        try:
            await db.atxn("chat", lambda conn: db_ops.insert_token(
                conn,
                llm_call_count=step_no,   # 记录时步号, 非任务终值(11.1 修正语义, 保持不变)
                prompt_tokens=int(ed.get("prompt_tokens") or 0),
                completion_tokens=int(ed.get("completion_tokens") or 0),
                total_tokens=int(ed.get("total_tokens") or 0)), retry_locked=3)
        except Exception as _te:
            logger.error(f"[Runner] token_usage 落库失败(task={task_id}, step={step_no}): {_te}")

    async def _write_user_message_final(response: str, reasoning: str) -> None:
        """chat_user_message 正文实时回填(解 E13) — 小欧 2026-10-01
        原为 finally 终态回填, 致任务执行中刷新页面 /sessions/{id}/messages 该行 response 全 NULL,
        前端回落到别的任务结果(本次缺陷第二根因)。
        本项只写 response/reasoning; outcome/chat_model/accumulated_usage 属终态量, 仍由 finally 补,
        二者幂等互补(同 SET、不同字段集)。"""
        _active_uid = getattr(getattr(agent, "message_builder", None), "current_user_msg_id", None)
        # 锚守卫: 仅正整数真 uid 作回填目标; None/0/合成负 id 一律回落任务登记首条(与 finally 同款)
        uid = _active_uid if (_active_uid or 0) > 0 else db_ops.user_msg_id
        if not uid or uid <= 0:
            return
        try:
            await db.atxn("chat", lambda conn: update_user_message_final(
                conn, user_message_id=uid, task_id=task_id,
                response=response or "", reasoning=reasoning or ""), retry_locked=3)
        except Exception as _ue:
            logger.warning(f"[Runner] chat_user_message 实时回填失败(task={task_id}): {_ue}")

    def _enqueue_step(ed: Dict, usage_json: Optional[str]) -> None:
        """分配步序号并投递(O(1), 不阻塞事件产生) — 小欧 2026-10-01"""
        _step_queue.put_nowait(("step", next(_step_seq), ed, usage_json))

    def _enqueue_user_final(response: str, reasoning: str) -> None:
        """投递 chat_user_message 正文回填(解 E13) — 小欧 2026-10-01
        与 step 落库共用同一串行消费者, 故 final 的 step 行先于本项入队, 回放读到的步骤与正文同源。"""
        if not _can_persist:
            return
        _step_queue.put_nowait(("um_final", response, reasoning))

    async def _drain_steps() -> None:
        """单消费者 FIFO 顺序落库 — 小欧 2026-10-01
        step 与 token 两类共用一个消费者: SQLite 单写者, 单消费者串行可回避自锁(解 A13)。
        铁律: 绝不允许因异常退出。消费者一旦死亡, _flush_steps 的 join 永久挂起,
        finally 永不完成 → done 不置位 → SSE 挂死。故异常一律捕获记日志后继续消费。"""
        while True:
            item = await _step_queue.get()
            try:
                if item is None:
                    return
                if item[0] == "token":
                    await _write_token(item[1], item[2])
                elif item[0] == "um_final":
                    await _write_user_message_final(item[1], item[2])
                else:
                    await _write_step(item[1], item[2], item[3])
            except asyncio.CancelledError:
                raise                      # 停机取消必须透传, 不吞
            except Exception as _de:
                logger.error(f"[Runner] 落库消费者异常(继续消费, task={task_id}): {_de!r}")
            finally:
                _step_queue.task_done()

    async def _flush_steps() -> None:
        """等待队列排空 — 终态写前必调, 保证 DB 与内存统计同源 — 小欧 2026-10-01
        超时兜底: 万一消费者不可用(已被 _drain_steps 异常护栏排除), 宁可带未落库帧进入终态,
        也不得让 finally 永久挂起致 done 不置位、SSE 挂死。"""
        try:
            # 2026-10-05 小欧 - 消费者死亡即时止损: 原只 wait_for(join), 消费者被 cancel
            #   退出后 join 永久挂起直至 120s 超时; 改 wait(join_t, drain_task) 任一完成即返回,
            #   消费者先退即立即报残留帧而非干等 120s。
            _join_t = asyncio.ensure_future(_step_queue.join())
            try:
                _done, _pending = await asyncio.wait(
                    {_join_t, _drain_task}, return_when=asyncio.FIRST_COMPLETED,
                    timeout=_STEP_FLUSH_TIMEOUT_SEC)
                if not _done:
                    raise asyncio.TimeoutError()
                if not _join_t.done() and _drain_task.done():
                    logger.error(
                        f"[Runner] 落库消费者已退出(task={task_id}, 残留 {_step_queue.qsize()} 帧), 终态继续"
                    )
            finally:
                if not _join_t.done():
                    _join_t.cancel()
        except asyncio.TimeoutError:
            logger.error(
                f"[Runner] 落库队列排空超时(task={task_id}, 残留 {_step_queue.qsize()} 帧), 继续终态"
            )

    async def _persist_sink(ed: Dict) -> None:
        """StreamBuffer.publish 落库回调(persist_sink) — 小欧 2026-10-01
        挂 buffer 而非本模块调用点: 事件有三条发布路径(_emit_publish / handle_action 直连
        _buf.publish / _events 批量), 挂调用点必漏(解 [1] A1)。仅 O(1) 投递, 不 await 事务。"""
        _t = ed.get("type", "")
        if not ed.get("_live_only"):
            # 2026-10-06 小欧 修 P3-08: round_number 语义是 LLM 调用轮次, 原取 ed["step"](事件序号),
            #   致落盘「轮次」恒等于步骤(实测 3609560/3609560 = 100%); 改取 agent.llm_call_count,
            #   与 llm_response_builder._log_llm_response 同源, 消除两处口径分叉
            get_prompt_logger().log_step_yield(ed, round_number=getattr(agent, "llm_call_count", 0) or 0)
        _route_step_to_db(ed)

    def _route_step_to_db(ed: Dict) -> None:
        """通道路由 → 落库投递 — 小欧 2026-10-01
        逐条等价搬迁自末尾扫描循环, 扫描机制退役后本函数为唯一真源(解 R1/R2/R3/R4 双份漂移)。
        落库的步(含 preview 过滤与 final 长短分流决策)即"业务步"权威集合 —— 统计口径亦取自此,
        保证 chat_tasks.total_steps 与 final_stats.step_count 同源等值(见 _business_step_count)。"""
        _t = ed.get("type", "")
        if _t in SSE_ONLY_TYPES:
            if _t == "usage":
                _step_queue.put_nowait(("token", int(ed.get("step") or 0), ed))   # 明细实时落库(解 A10)
            return                                    # 仅 SSE 不落 chat_task_steps
        if _t == "action" and ed.get("_live_only"):
            return                                    # 预览 action 不落库(齿轮先行, DB/Prompt 对账 2x 误报防线)
        if _t == "final":
            ed = getattr(agent, "_pending_final_db", None) or ed   # 取长条(短条已剥 response)
            agent._pending_final_db = None                          # 消费即清(防重复落库)
            # E13: final 到达即回填 chat_user_message 正文, 不待 finally(收尾链含 update_task 事务、
            #   token 对账、文件 footer, 耗时可观)。缩的是"任务已结束但刷新仍看不到回答"的窗口,
            #   非"执行中可见部分正文"—— 后者由 C 组(前端按 task_id 读实时已落库步骤)解决, 不属本项。
            # 走队列而非直接 await: 保持 publish 路径 O(1) 不阻塞(与 step 落库同一串行消费者)。
            _enqueue_user_final(str(ed.get("response") or ""), str(ed.get("reasoning") or ""))
        if _t == "thought":                           # 落库收口: 仅规约三字段, 其它类型/字段绝不触碰
            for _k in ("content", "thought", "reasoning"):
                _v = ed.get(_k)
                if isinstance(_v, str):
                    ed[_k] = normalize_blank_lines(_v)
        current_execution_steps.append(ed)           # 与落库同源(下游 total_steps/error/末条final 取数)
        # 挂落库权威给遥测统计: final_stats.step_count 据此与 chat_tasks.total_steps 同源等值
        # (解 [1] 4-1)。两者共用本列表, preview action 已在上面 return 处剔除, 故天然一致。
        agent._persisted_steps = current_execution_steps
        if not _can_persist:
            return                                    # 落库能力缺失, 已在上方一次性留痕
        if ai_message_id is None:                     # 任务行未建立时 append_step 必撞 NOT NULL, 记 ERROR 跳过
            logger.error(f"[Runner] 步骤落库跳过(ai_message_id 缺失): task={task_id}, type={_t}")
            return
        _enqueue_step(ed, _step_usage_json(ed))

    # 2026-09-11 小欧 v1.12: final_stats 延后单发(发布铁律(0) + 方案A t3/t3' 落地)——统计在
    #   react_loop 返回后已全齐; 门禁逐段校验 7 键(缺段绝不发), telemetry 缺失构造 7 键默认合法帧照发(兜底,
    #   折叠必达)
    # 2026-10-01 小欧 解 [1] E10: 语义校正 —— 原注释称“先落库(t3)后发布(t3'), DB 就绪信号”。
    #   逐步落库(A1)后该时序已变为“本步随 publish 自动投递, 随后的 flush 保证本步入库”;
    #   且信号强度提升: 运行期全程 DB 可读(不再只保证最后一行), final_stats 不再是
    #   “DB 就绪的唯一门槛”, 前端据此刷新任务列表仍正确。flush 即新语义的落点。
    async def _publish_final_stats(agent_ref, outcome):
        _tel = getattr(agent_ref, "telemetry", None)
        if _tel is not None:
            try:
                _fs_dict = _tel.build_final_stats_step(outcome=outcome).to_dict()
            except (ValueError, TypeError) as _build_err:
                logger.error(f"[Runner] final_stats build 失败(task={task_id})，降级走兜底帧: {_build_err}")
                _tel = None  # 走下方兜底帧逻辑
        if _tel is None:
            # 极端兜底(telemetry 未初始化): 构造 7 键默认合法帧照发——折叠必达 + 每键有值两不误
            _fs_dict = {
                "type": "final_stats", "step": getattr(agent_ref, "llm_call_count", 0), "timestamp": get_local_iso_timestamp(),
                "duration": 0.0, "artifacts": [], "final_status": outcome,
                "tool_stats": {}, "llm_call_count": 0, "retry_count": 0, "step_count": 0,
            }
        _need = ("duration", "artifacts", "final_status", "tool_stats",
                 "llm_call_count", "retry_count", "step_count")
        _missing = [k for k in _need if _fs_dict.get(k) is None]
        if _missing:  # build 层已用 getattr 兜底永不产 None 键; 此处抓到即代码 bug, 绝不残发
            logger.error(f"[Runner] final_stats 缺段 {_missing}，拒绝发布(task={task_id})")
            return
        # 运行期逐步落库下 t3/t3' 语义更新 — 小欧 2026-10-01:
        #   本步随 publish 自动投递落库, 随后的 flush 保证 final_stats 自身已入 DB,
        #   故前端收到折叠帧即可读 DB(运行期逐步落库已使 DB 全程可读)。
        _fs_seq = await _publish(_fs_dict)  # 落库投递 + 发布
        await _flush_steps()                 # 保证本步入库(其余在途帧一并排空)
        logger.info(f"[Runner] final_stats 已发布(task={task_id}, seq={_fs_seq}, status={outcome})")  # 小欧-2026-09-12 追踪点

    # 落库路由注入 buffer.publish 收口 — 小欧 2026-10-01
    #   必须早于首个事件 publish; 本任务首个事件由下方 run_react_cycle 产出, 故此处安全。
    #   buffer 复用(同 task_id 已有 journal_backed 条目)属异常场景, 不补投历史事件。
    # 落库能力前置校验: 缺失时一次性留痕并停投递(否则每帧一条 ERROR 刷屏, 且内存/DB 静默分叉)。
    _can_persist = db_ops is not None and getattr(db_ops, "append_step", None) is not None
    if not _can_persist:
        logger.error(
            f"[Runner] 落库能力缺失(db_ops.append_step 未注入), step 仅在内存/SSE 不入库: task={task_id}"
        )
    else:
        buffer.persist_sink = _persist_sink
    _drain_task = asyncio.create_task(_drain_steps())
    # 2026-10-02 小欧 - 轮次边界 flush(北京老陈定案): _enqueue_step 只入队即返回, 真落库在
    #   _drain_steps 协程; 进程被杀则队列内帧全丢(实测 task_interrupted 样本 steps 0 行而 Journal 齐)。
    #   每轮迭代顶 join 一次, 被打断最多丢本轮(无工具副作用), 不丢已完成轮次。
    buffer.flush_sink = _flush_steps

    # 退出分支与DB保存保证 — 小欧 2026-07-13
    # 本函数有 3 个退出路径，无论哪条路径 finally 都会执行 DB 保存：
    #
    # 1. try 正常完成：run_react_cycle 正常结束，current_execution_steps 有完整数据
    #    → finally: flush 队列(运行期逐步落库) ✅
    #
    # 2. except asyncio.CancelledError：任务被取消（主动/被动）
    #    → finally 守卫补 FinalStep(outcome="cancelled") → flush ✅
    #
    # 3. except Exception：其他异常（LLM 错误/工具异常/网络超时等）
    #    → 异常分支落 FinalStep(outcome="failed") → flush ✅
    #
    # 强引用保障：_background_tasks 集合持有 Task 引用，防止 GC 回收导致 finally 不执行
    # （无强引用时 Task 被 GC → CancelledError → finally 可能被打断 → DB 结果丢失）

    # ① 正常结束分支 — 小欧 2026-07-13
    try:
        # 注册 agent 到任务运行表，供暂停路径设置 AgentStatus.SUSPENDED — 小欧 2026-07-12
        async with running_tasks_lock:
            if task_id in running_tasks:
                running_tasks[task_id]["agent"] = agent
        llm_service = getattr(agent, "llm_client", None)
        if llm_service is not None and hasattr(llm_service, "context_limit") and llm_service.context_limit:
            agent.message_builder.MAX_CONTEXT_TOKENS = llm_service.context_limit

        # 注入停止检查回调，消除 llm→task 反向依赖 — 小沈 2026-06-17
        # 小欧 2026-07-13: 采用"循环粒度取消"(方案 B)。_stop_check 仅查取消(中断在飞 LLM 流);
        # 暂停不再经此中断, 改由 react_cycle 循环顶 task_pause_check 阻塞等待恢复(符合人类认知"原地等")。
        if llm_service is not None and hasattr(llm_service, "set_stop_check"):
            async def _stop_check():
                from app.services.task.task_runtime import check_cancelled
                # 仅查取消: 暂停不再经此中断 LLM 流, 改由 react_cycle 循环顶 task_pause_check 阻塞处理
                # (符合人类认知"原地等"); 否则暂停会令在飞 LLM 流被打断→忙等空转/误判。 — 小欧 2026-07-13
                return await check_cancelled(task_id)
            llm_service.set_stop_check(_stop_check)

        # 加载会话历史，支持多轮对话 — 北京老陈 2026-06-13
        ctx = {}
        if session_id and db_ops and db_ops.load_previous:
            prev = db_ops.load_previous(session_id)
            if prev:
                ctx["previous_messages"] = prev
        run_context = context or ctx or None

        # 4C(5.8.5): run_react_cycle 收敛普通 async(5.8.3)——事件已在内部经 publish 直写 event_log,
        #   落库亦在 _publish 单点完成(运行期逐步落库, 2026-10-01), 本层不再扫描补落;
        #   SSE 实时由 stream_reader(独立协程按 seq 实时读 publish 事件)负责, 实时性不受影响;
        #   自产事件(startinfo/异常final/守卫补发)统一经 _publish 发射, 单一写入口(5.8.1) — 小欧-2026-09-06
        await agent.run_react_cycle(
            task=last_message, context=run_context, task_id=task_id, start_time=start_time  # 11.2-B start_time 同源透传 — 小欧 2026-08-20
        )
        # stream_state 终态正文/推理取数 — 小欧 2026-10-01
        #   落库已前移 _publish 单点, 末尾扫描机制退役; 数据源改末条 final(落库取长条, 恒含完整 response),
        #   比原"event_log 短条 + chunk 逐段累加"更准(短条场景原需靠 chunk 累加还原正文)。
        if stream_state is not None:
            for _s in reversed(current_execution_steps):
                if _s.get("type") == "final":
                    stream_state.current_content = _s.get("response") or ""
                    stream_state.current_thought = _s.get("reasoning") or ""
                    break

        # 正常结束：终态由 react_cycle 内部设置(agent.status), 无需在此补发

    # ② 取消分支 — 小欧 2026-07-13
    except asyncio.CancelledError:
        # 后端主动取消（task 被清理等）— 小沈 2026-06-09 修复
        # 取消终态由 finally 守卫补 FinalStep(outcome="cancelled") — 小欧 2026-07-18
        # 守卫覆盖步: step构建→to_dict→current_execution_steps→DB→prompt log→SSE _append
        # 此处仅设状态: set_cancelled 让守卫读到 CANCELLED 即可补发
        logger.info(f"[Runner] 任务 {task_id} 被取消(CancelledError)")
        if agent is not None:
            try:
                set_cancelled(agent)
            except ValueError:
                pass
            if getattr(agent, "_cancel_source", None) is None:
                # 方案五 G路径: CancelledError 系 orchestrator 异常→bg_task.cancel() 触发(链路),
                #   非用户取消, 未标记来源则定为后端自保取消; A/B 若已标记则尊重原来源不覆盖 — 小欧 2026-09-08
                agent._cancel_source = "orchestrator_error"
                log_and_print(f"{time.strftime('%H:%M:%S')} [Runner] 任务 {task_id} 未标记取消来源, 定为 orchestrator_error(后端自保取消)")  # 2026-09-08 小欧: 双写(console可见) — 小欧-2026-09-08

    # ③ 异常分支 — 小欧 2026-07-13
    except Exception as e:
        # 失败终态改为自包含 FinalStep(outcome="failed") — 小欧 2026-07-18
        logger.error(f"[Runner] 任务 {task_id} 异常: {e}", exc_info=True)
        s = (agent.llm_call_count if agent else None) or 1  # 弃 next_step, 统一 agent 轮数; 三堂会审复核(小欧): agent 空防御统一
        error_content = str(e)[:200]
        final_step = FinalStep(
            step=s, response="任务执行失败", reasoning=error_content,
            outcome="failed", error_type="agent_operation_error", error_message=error_content,
        )
        final_dict = final_step.to_dict()
        # 终态 step 立即落库 + 发布 — 小欧 2026-07-14; 2026-10-01 落库随 publish 自动投递,
        #   step_index 由独立计数器分配(不再依赖内存列表长度, 解 A2/A6)
        await _publish(final_dict)
        await _flush_steps()               # 终态必达: 后续终态链读 DB/内存统计须与 DB 同源
        if stream_state is not None:
            stream_state.current_content = "任务执行失败"  # 兜底: ③路径 response_text 非空, 根治空 bug
        if agent is not None:
            try:
                set_failed(agent, error_content)
            except ValueError:
                pass

    # finally: 统一DB保存（①②③都会执行）— 小欧 2026-07-13
    finally:
        # 关闭本任务持有的客户端(快照恒私有, 无条件 close) — 小欧 2026-09-25
        #   三分支由 base_service.close/LLMClient.close 兜底: 共享池快照→归还 lease(ref-1, 归零自动关),
        #   独占池快照→aclose, 单例(relinquish 后 owns=False)→no-op; _is_snapshot 死判据消亡。
        #   连接顺序: resolve(388) < bg_task 创建(489) < 本 finally——resolve 抛错时 runner 不执行, 无裸单例入口
        _snap_client = getattr(agent, "llm_client", None) if agent is not None else None
        if _snap_client is not None:
            try:
                await _snap_client.close()
                logger.info(f"[Runner] 任务客户端已关闭(task={task_id})")
            except Exception as _ce:
                logger.warning(f"[Runner] 关闭任务客户端失败(task={task_id}): {_ce}")
        # === 守卫：兜底补发 FinalStep（覆盖 ②CancelledError + react_cycle 内部 set_failed 等无 final 路径）— 小欧 2026-07-18 ===
        if not any(
            isinstance(s, dict) and s.get("type") == "final"
            for s in current_execution_steps
        ):
            _oc, _resp, _et, _em = "failed", "任务执行失败", "agent_operation_error", ""
            if agent and agent.status == AgentStatus.CANCELLED:
                # 方案五 G路径(2026-09-08 小欧): 文案按来源出(orchestrator_error="服务内部异常，任务已终止"), 不再统一"任务已取消"
                from app.services.task.task_runtime import cancel_terminal_text
                _oc, _resp, _et, _em = "cancelled", cancel_terminal_text(getattr(agent, "_cancel_source", None)), "", ""
                logger.info(f"[Runner] 守卫兜底补发取消终态(task={task_id}, source={getattr(agent, '_cancel_source', None)}, text={_resp})")  # 2026-09-08 小欧 北京老陈指令: 兜底补发留痕(仅文件, 不双写) — 小欧-2026-09-08
            elif agent and agent.status == AgentStatus.COMPLETED:
                # 防御性: 正常流程成功必有 FinalStep, 此处仅兜底, 不误标 failed — 小欧 2026-07-18
                _oc, _resp, _et, _em = "completed", "任务执行完成", "", ""
            else:  # FAILED / RETRYING / SUSPENDED → 读 agent._last_error（error仅SSE不落current_execution_steps）
                _last_err = getattr(agent, "_last_error", None) if agent else None
                if _last_err:
                    _et, _em = _last_err[0] or "agent_operation_error", _last_err[1] or ""
            _fs = FinalStep(step=(agent.llm_call_count if agent else None) or 1, response=_resp, reasoning=_em or _resp,  # 弃 next_step, 统一 agent 轮数; 三堂会审复核(小欧): agent 空防御统一
                            outcome=_oc, error_type=_et, error_message=_em,
                            cancel_source=(getattr(agent, "_cancel_source", None) if _oc == "cancelled" else ""))  # 方案五: 取消终态带来源落库/下发 — 小欧 2026-09-08
            _fd = _fs.to_dict()
            if stream_state is not None and _oc != "completed":
                stream_state.current_content = _resp or stream_state.current_content
            await _publish(_fd)

        # 队列排空后再做终态写 — 小欧 2026-10-01
        #   保证 chat_tasks.total_steps / token 对账与 DB 行数同源(解 A7 口径分叉)
        #   _persist_final 薄壳防 finally 期间再收 cancel 致排空半途而废
        #   此处只排空, 不投哨兵: 下方 _publish_final_stats 仍会经 _publish→persist_sink 投递 final_stats,
        #   消费者提前退出会致其 join 永久挂起(2026-10-01 实测卡死, 哨兵已移至 done.set 前)
        await _persist_final(_flush_steps())

        # 从 agent.status 推导 end_type — 小欧 2026-07-12 从 stream.py 迁移
        if end_type == "unknown" and agent is not None:
            _m = {
                AgentStatus.COMPLETED: "final",
                AgentStatus.FAILED: "failed",
                AgentStatus.CANCELLED: "cancelled",
                AgentStatus.RETRYING: "failed",
                AgentStatus.SUSPENDED: "paused",
            }
            end_type = _m.get(agent.status, "unknown")

        # 统一保存入口：正常、异常、取消都走这里 — 小欧 2026-06-26
        # 小欧 2026-07-13: 落 chat_messages.status 列（终态），正常路径依赖该列
        _STATUS_MAP = {"final": "completed", "failed": "failed",
                       "cancelled": "cancelled", "paused": "paused"}
        # 小沈 2026-07-13: 默认必须用 "failed"(fail-safe), 不能用 "completed"。
        # end_type 仅在 agent 为 None 或 agent.status 不在映射表中时才落到 default;
        # 此时该任务并非真正完成, 若误标 completed 会让崩溃/异常任务在 DB 被当成成功,
        # 前端会话列表与历史回放都会显示错误终态。失败默认失败, 完成必须显式完成。
        _terminal_status = _STATUS_MAP.get(end_type, "failed")
        saved_content = stream_state.current_content if stream_state else ""
        saved_thought = stream_state.current_thought if stream_state else ""
        # finalize_message 已随 chat_messages 表退役整体移除(阶段2 2026-08-27 小欧); 终态 content/status/thought
        # 由 append_execution_step(step_json) 与 _finalize_task_db(update_task+回填chat_user_message) 承载, 无需此处镜像写

        if agent is not None and stream_state is not None:
            stream_state.llm_call_count = getattr(agent, "llm_call_count", 0)

        # Task 生命周期日志（结束）— 小欧 2026-06-26
        if db_ops and db_ops.log_task_end:
            db_ops.log_task_end(task_id, end_type, start_time, current_execution_steps, agent)

        # S2 chat_tasks 终态 UPDATE(10.1.7②-1, 设计1914-1932) — 小欧 2026-08-16
        if db_ops and db_ops.update_task:
            try:
                _terminal = stream_state.current_content if stream_state else ""
                # total_steps 口径单一真源 count_business_steps(解 [1] E1/E2/4-1)——
                # 与 final_stats.step_count 同函数同数据源, 故两值恒等。
                # 存量数据不回填(北京老陈裁定 2026-10-01: 只改代码不碰存量)。
                _total = count_business_steps(current_execution_steps)
                _err_type, _err_msg = "", ""
                # 三堂会审修复(小欧 2026-08-16): 原条件 `not stream_state` 恒 False(orchestrator 正常路径
                #   stream_state 恒为 StreamState 实例 truthy), error_type/error_message 永远提取不到→任务失败
                #   时 chat_tasks 错误信息丢失。改为按终态判定: failed 时从末条 final 实取(异常分支必先 append final_dict)
                if _terminal_status == "failed" and current_execution_steps:
                    _last = current_execution_steps[-1]  # 末条 final 取错误, 避免伪 _final_err_type/_final_err_msg
                    _err_type, _err_msg = str(_last.get("error_type") or ""), str(_last.get("error_message") or "")
                # 落库 offload 出事件循环(后端卡死修复 小欧 2026-08-24): DB 部分(update_task+回填chat_user_message)进 atxn 子线程
                def _finalize_task_db(conn):
                    db_ops.update_task(
                        conn, status=_terminal_status, response=_terminal,
                        end_time=get_local_iso_timestamp(),
                        duration=round(time.time() - start_time, 1) if start_time else None,
                        accumulated_usage=db_ops.query_task_acc(conn, task_id=task_id),  # 12.2-Q3/C3: 从chat_tasks.task_accumulated_tokens读出写入,不再取agent内存 — 小欧 2026-08-21; 小欧 2026-08-30 去双重编码: update_task内已调safe_json_dumps, 此处传dict
                        llm_call_count=getattr(agent, "llm_call_count", 0),
                        total_steps=_total, retry_count=getattr(agent, "_retry_count", 0),
                        error_type=_err_type, error_message=_err_msg,
                        artifacts=getattr(getattr(agent, "telemetry", None), "_artifacts", None))

                    # v2.0 改动2: 任务完成后回填 chat_user_message final 字段 — 小欧 2026-08-19
                    # B组修复(2026-09-20 小欧): user_message_id 取锚演进后的 builder.current_user_msg_id
                    #   (B机制注入消息经 _absorb_inbox 落库取真实 uid 演进锚), DB 层 db_ops.user_msg_id 仅兜底
                    try:
                        _last_final = None
                        for _s in (current_execution_steps or [])[::-1]:
                            if isinstance(_s, dict) and _s.get("type") == "final":
                                _last_final = _s
                                break
                        # 归一(小欧 2026-08-22 报告v1.25 6.3): model/provider 两键 → task_model: ModelRef 结构
                        # 三堂会审修复: 现网 FinalStep 均未传 final_model → 键值为 None,
                        #   ModelRef(provider=None) 必抛 ValidationError 致回填整体失败(response/reasoning 连带丢失),
                        #  仅 provider/model 均非空才构造, 否则落 NULL(与旧行为等价)
                        _tf_p = _last_final.get("provider") if _last_final else None
                        _tf_m = _last_final.get("model") if _last_final else None
                        _active_uid = getattr(
                            getattr(agent, "message_builder", None), "current_user_msg_id", None)
                        # 锚守卫：仅正整数真 uid 作回填目标;
                        #   None/0/合成负id(占位锚, WHERE id<0 必落空)一律回落 db_ops.user_msg_id 兜底。
                        #   property 补齐后 _active_uid 通常为真 uid, 本守卫防传值失误。
                        _final_uid = _active_uid if (_active_uid or 0) > 0 else db_ops.user_msg_id
                        update_user_message_final(
                            conn,
                            user_message_id=_final_uid,
                            task_id=task_id,
                            response=saved_content or "",
                            reasoning=saved_thought or "",
                            outcome=_terminal_status,
                            task_model=ModelRef(provider=_tf_p, model=_tf_m)
                                        if (_tf_p and _tf_m) else None,
                            accumulated_usage=safe_json_dumps(getattr(agent, "accumulated_usage", None)),
                        )
                    except Exception as _um_e:
                        logger.warning(f"[Runner] 回填chat_user_message final失败(task={task_id}): {_um_e}")
                # 终态必达防二次cancel(_persist_final 小欧 2026-08-24)
                # 2026-09-04 小欧 方案一: try/finally 保证无论 status 落库成败, 终态 SSE 必达——
                #   DB chat_tasks.status 落库(成功则已 terminal)后统一补发 final/final_stats,
                #   根治"SSE final 先到、DB status 后到"致前端 StaticStatsBlock 读 detail.status 卡 executing 的竞态
                try:
                    # retry_locked=3(小欧 2026-09-29): 终态 UPDATE 撞锁失败仅被下方外层
                    #   `except Exception as _task_e` 记 warning,
                    #   chat_tasks.status 永不落库 → 任务永久 executing(前至下次启动 reconcile 才收尾);
                    #   此处为与 _persist 同级的实证高危写路径, 补齐有限重试。
                    await _persist_final(db.atxn("chat", _finalize_task_db, retry_locked=3))
                finally:
                    # X2(2026-09-12 小欧): L642-653 覆写/补发段整体删除——终态形态发射侧已定(event_log 原位
                    #   =应转发形态, 实时 stream_reader 与重连回放读同一形态), 覆写失去作用对象且会逆转终态(G2 复发);
                    #   _persist_final(status 落库) 与 final_stats 延后单发(DB 就绪信号)保留 — 小欧 2026-09-12
                    _fs_outcome = getattr(agent, "status", None)
                    _fs_outcome = _fs_outcome.value if _fs_outcome is not None else "failed"
                    await _publish_final_stats(agent, _fs_outcome)
                # 文件A/B footer(终态回填 end_time/status/record_count) — 小欧 2026-08-23
                #   非DB文件写, 移出DB事务块(后端卡死修复 offload 小欧 2026-08-24):
                #   成功路径等价; 失败路径更稳——旧代码 footer 写失败会连坐回滚整个 update_task 事务,
                #   现 DB 先提交、footer 失败仅告警, 终态不再被文件写失败吞掉
                _fp = getattr(agent, "file_persist", None)
                if _fp is not None:
                    try:
                        _fp.finalize(status=_terminal_status)
                    except Exception as _fp_e:
                        logger.warning(f"[Runner] 文件A/B footer 失败(task={task_id}): {_fp_e}")
            except Exception as _task_e:
                logger.warning(f"[Runner] 回填task_id失败: {_task_e}", exc_info=True)

        # #15 修正(2026-08-23): H5 兜底——db_ops 缺失/update_task 抛异常时 footer 永不写且
        #   worker 协程悬挂(哨兵永不投递); 补 finally 级兜底: finalize 幂等(_closed 守卫),
        #   主落点已写则此处空转, 零副作用 — 小欧 2026-08-23
        _fp_fb = getattr(agent, "file_persist", None)
        if _fp_fb is not None and not getattr(_fp_fb, "_closed", False):
            try:
                _fp_fb.finalize(status="failed")   # 走到兜底即主终态链路未正常完成
            except Exception as _fp_e2:
                logger.warning(f"[Runner] 文件A/B footer 兜底失败(task={task_id}): {_fp_e2}")

        # token_usage 明细已前移 _publish 路由实时落库(2026-10-01, 解 A10), finally 不再批量插;
        # 累计列更早前移 react_step 每轮即时写(11.1b), 此处零 token 写。

        # 12.2-Q3 对账告警: token_usage明细SUM vs 权威累计列不一致即告警(不阻断) — 小欧 2026-08-21
        if db_ops and hasattr(db_ops, 'query_task_acc'):  # 防御: db_ops=None/注入不完整时跳过(与 insert_token/update_task 同守卫风格) — 小欧 2026-08-21 三堂会审修复
            try:
                # 落库 offload 出事件循环(后端卡死修复 小欧 2026-08-24)
                _sum_row, _auth_acc = await db.atxn("chat", lambda conn: (
                    conn.execute(
                        "SELECT COALESCE(SUM(total_tokens),0) FROM token_usage WHERE task_id=?",
                        (task_id,)).fetchone(),
                    db_ops.query_task_acc(conn, task_id=task_id)))
                if int(_sum_row[0]) != int(_auth_acc.get("total_tokens") or 0):
                    logger.warning(
                        f"[Runner] token对账不一致(task={task_id}): 明细SUM={_sum_row[0]} "
                        f"权威累计={_auth_acc.get('total_tokens')}")
            except Exception as _rec_e:
                logger.warning(f"[Runner] token对账查询失败(task={task_id}): {_rec_e!r}")

        # 生命周期清理：原 openai.py finally 的 task_cleanup 迁入此处 — 小欧 2026-07-12
        # 修复旧 bug：断线时不再误删在跑的 agent（cleanup 由生产者自身在结束时调用）
        await task_cleanup(task_id, getattr(agent, "llm_call_count", 0) if agent else 0)

        # Shell 池清理：关闭该任务的所有 PersistentShell 实例 — 小沈 2026-07-30
        # 治理第1步-H2(2026-10-04 小欧): cleanup_by_task持池锁+taskkill属同步重活, 移出事件循环。
        await asyncio.to_thread(cleanup_shell_pool_by_task, task_id)

        # 落库消费者收尾 — 小欧 2026-10-01
        #   位置铁律: 必须在本 finally 最末(done.set 前)。此前置于守卫块之后, 而下方
        #   _publish_final_stats 仍经 _publish→persist_sink 投递 final_stats, 消费者已退出致
        #   join 永久挂起 → finally 永不完成 → done 不置位 → SSE 挂死(2026-10-01 实测)。
        #   先排空(final_stats 入库)再投哨兵, 顺序不可颠倒。
        await _persist_final(_flush_steps())
        _step_queue.put_nowait(None)      # 哨兵: 消费者收尾退出
        await _persist_final(_drain_task)

        if buffer is not None:
            buffer.done.set()
            # 2026-09-12 小欧 - 追踪关键点: done 置位为本 SSE 流的"权威结束信号"(所有事件含 final_stats 已 publish);
            #   done 置位后立即快照缓冲状态, 供后续核对——若置位时末类型非 final_stats 即 SSE 会被提前关闭,
            #   对照 [Runner] final_stats 已发布 seq 定位根源(E2E-X2-01 竞态监控点) — 小欧-2026-09-12
            _tail_type = (buffer.event_log[-1] or {}).get("type") if buffer.event_log else "empty"
            _has_fs = any((e or {}).get("type") == "final_stats" for e in (buffer.event_log or []))
            logger.info(f"[Runner] done置位(task={task_id}, event_log_len={len(buffer.event_log or [])}, "
                        f"last_type={_tail_type}, has_final_stats={_has_fs})")  # 小欧-2026-09-12 追踪点
            # 必须持锁调 notify_all(同 _append), 否则 RuntimeError — 小欧 2026-07-13
            async with buffer.cond:
                buffer.cond.notify_all()

            # [新] 生产者权威存盘: 终态 FinalStep 已由上方守卫补记(_fd),
            #      此刻 current_execution_steps 必含终态。 — 小欧 2026-07-18
            _pl = get_prompt_logger()
            _label_map = {"completed": "已完成", "failed": "异常终止",
                          "cancelled": "已取消", "paused": "已暂停"}
            _pl.set_terminal_status(_label_map.get(_terminal_status, "异常终止"))
            _pl.save()

            try:
                loop = asyncio.get_event_loop()
                # 只回收内存缓冲（event_log/cond/done），绝不删除 Journal 里已落库的事件
                loop.call_later(300, lambda: reclaim_memory_buffer(task_id))
            except Exception as e:
                logger.debug(f"reclaim_memory_buffer调度失败: {e}")


