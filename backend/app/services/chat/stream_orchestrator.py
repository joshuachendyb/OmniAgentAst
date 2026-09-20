# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-08-13 - 小欧 - 新建: A7 聊天流编排器(方案4.7.3步骤1)。从 api/v1/chat/openai.py 一次性全迁编排逻辑
#   (chat_stream generate 主体 / _stream_with_control / StreamState / generate_task_id / validate_chat_config /
#   _agent_tasks / step_start), 仅改导入归属, 业务逻辑一字不改(禁止 backward, 无兼容 shim)。依赖路径以真实代码为准:
#   create_stream_buffer/get_stream_buffer 取 app.services.task.task_state, task_cancel_check* 取 app.services.task.task_runtime。
#   orchestrator 不依赖 api/v1 的 DTO(API 层解包 ChatRequest 后传原始参数)。
# 2026-08-13 - 小沈 - BUG-32修复(三堂会审): except Exception 块内 cancel bg_task, 避免后台 agent 继续运行但前端收到错误的
#   状态不一致; bg_task 预初始化 None 防 NameError; cancel 后 run_agent_in_background 的 finally 仍执行 DB 保存(已产出结果不丢失)
# 2026-08-13 - 小沈 - P4 agent→chat反向引用回调解耦: agent_runner 删除对 chat 模块的直接 import,
#   持久化回调(allocate_and_insert_message/append_execution_step/finalize_message/save_execution_steps_to_db/
#   _load_previous_messages/_log_task_end)由本编排器构造 db_ops SimpleNamespace 注入 run_agent_in_background,
#   依赖方向变为 chat→agent 单向。6个属性与原 agent_runner 直接 import 的6个chat函数一一对应,KISS-DIRECT。
# 2026-08-14 - 小欧 - 改名名实相符引用同步: handlers.py→sse_events.py, stream.py→stream_reader.py(4处import更新, 行为不变)
# 2026-08-16 - 小欧 - S1/S2(10.1.4⑤⑥/10.1.7②): db_ops 扩展9属性(insert_task/update_task/insert_token 任务级读写),
#   白名单 context_link_mode + 链根计算注入 load_previous 闭包; load_previous 补传上界 upper_message_id=_user_msg_id;
#   agent 创建后 INSERT chat_tasks 任务行(provider/model 取 agent.llm_client); S2 model_override 编排层覆盖
# 2026-08-16 - 小欧 - S4(10.1.1③/10.1.7④): 取消 orchestrator 旁路(step_start 调用+函数删除), start 构造/emit 移入
#   react_cycle(initialize_run_state 后、while 前, 占 step 0); P4 注入模式: agent._start_step_factory 闭包捕获
#   chat 层装配数据(send_start_step/next_step/链字段/warning), react_cycle 内注入 system_prompt/context_summary 调用,
#   agent 层不 import chat 层; start 落库走 agent_runner 事件流(不再 execution_steps 双写)
# 2026-08-16 - 小欧 - S4 修正(三堂会审/老陈驱动): 删 _model_warning 提前 return 终态分支——S4 后 start 由 react_cycle
#   emit(带 warning 字段), 该分支会不发 start 直接 failed(config_error), 与 start 进 steps 设计冲突(退化);
#   warning 仅作 start 提示字段下传(不终止任务), 同步删 FinalStep/format_agent_sse 死 import
# 2026-08-17 - 小健 - 三堂会审修复(北京老陈驱动, 11 bug 复核3遍):
#   A1: line55 模块级统一 `from app.db import db`, 消除原 line245 裸引用 db 的 NameError(chat_tasks 永不建行)。
#   E2: line168-178 track(_user_message_ids) 内存 dict 重启即丢时, 从 DB 兜底取本会话最后一条 user 消息 id 作
#       linked 续聊 upper 上界(防链外/全部消息进上下文)。
#   AE: 覆盖共享单例 ai_service.model 前保存原值 _orig_model, finally 统一还原(消除单例持久污染/并发会话串 model);
#       _orig_model 预初始化 None 防无覆盖/取消时 NameError(边修 AE 时补该缺陷)。
# 测试: tests/test_s2_s4_review_bugs.py 16 passed, 相关4文件 52 passed。
# 2026-08-17 - 小健 - 必备日志补齐(老陈驱动): AE finally 还原单例 model 打 logger.info(并发审计点);
#   E2 DB 兜底恢复 upper 打 logger.info(诊断 track 缺失)。均仅落文件不刷 console。
# 2026-08-17 - 小健 - start 业务过程收敛(老陈驱动): 闭包 _start_step_factory 只做 P4 捕获传参,
#   context_summary 计算与 StartStep 构造收拢到 sse_events.build_start_step(单一归属); 删本文件 MessageBuilder 死 import
# 2026-08-17 - 小健 - start 业务彻底单归属(老陈驱动, 三思三省): 契约构造逻辑自 sse_events 迁入 start_step 模块,
#   本文件不再承载任何 start 业务——删除 _start_step_factory 闭包与 build_start_step/send_start_step import,
#   改将运行元数据 dict 注入 agent._start_meta(ai_service/task_id/next_step/user_input/session_id/链字段/warning),
#   react_cycle 经 assemble_start_step 从 _start_meta 读齐装配(chat 层退化为纯数据捕获, P4 方向不变)
# 2026-08-17 - 小健 - 最合理核查(老陈追问): _start_meta 删除 ai_service 键(DRY, 与 agent.llm_client 同对象),
#   仅保留 agent 拿不到的 chat 数据; start_step 直接读 agent.llm_client.provider/model — 小健 2026-08-17
# 2026-08-17 - 小健 - 全系统DRY扫描收敛(老陈指示按10大规范): _start_meta 再删 task_id 键(task_id 由 agent.task_id
#   权威持有, base_agent:59, 构造时注入); 仅保留 react_cycle 拿不到的必需运行数据(next_step/session_id/user_input/
#   链字段/warning); 与 ai_service 删除同属真冗余收敛(单一归属, 不退化) — 小健 2026-08-17
# 2026-08-17 - 小健 - 编排分区分号注释(老陈要求按编排步骤注清逻辑): chat_stream_orchestrator 增 ①~⑪ 分区分号
#   注释头(输入校验/取全局服务/算链根/建基元/取续聊边界/建agent/db_ops组装/_start_meta注入/后台任务/流式转发/
#   异常收尾); 仅加注释不改逻辑, 标明编排对象与依赖顺序 — 小健 2026-08-17
# 2026-08-17 - 小健 - 三堂会审深挖(北京老陈): task_cancel_check_and_yield 已删死参数, 调用点同步收敛,
#   不再白算 state.current_content 传入 — 小健 2026-08-17
# 2026-08-18 - 小欧 - §10.4.4 P2(弃用 next_step): 删 next_step = create_step_counter() 赋值; _start_meta 删 next_step 键;
#   run_agent_in_background 去 next_step 传参; _stream_with_control 签名/调用去 next_step; 删 create_step_counter import
# 2026-08-19 - 小欧 - v2.0核心数据模型重构(9.2+9.4+9.6+9.9): db_ops.append_step加usage参数、
#   allocate_and_insert加user_message_id、insert_task加ai_message_id=None(agent_runner分配后回填)、
#   insert_task后回填chat_messages.task_id(改动7)、_db_ops注入user_msg_id(供agent_runner回填chat_user_message)
# 2026-08-20 - 小欧 - 11.1 token 四层同构: 两 db_ops lambda(insert_task/update_task)改用 storage.query_task/session_accumulation 读真实累计(去重 parse_json), 与 react_cycle 同源基线; 会话级首调用回退 task 累计
# 2026-08-20 - 小欧 - 11.1 修复: db_ops.update_task_accumulation/update_session_accumulation 闭包已绑 task_id/session_id, 原 agent_runner 又经 kwargs 重传致 Python "got multiple values" TypeError 被 except 吞掉→累计永不入DB; 去掉闭包绑定, 改由调用方经 **kw 传入(单一归属, KISS)
# 2026-08-21 - 小欧 - 12.2-Q3/C4(按文档[1]12.2 diff设计落地): ①Q3-D1 :83 导入追加 query_task_accumulation +
#   db_ops 命名空间新增 query_task_acc 条目(终态快照从权威累计列派生); ②C4-D1 编排⑨ eager 分配 assistant 行
#   (allocate_and_insert_message)+创建时即 UPDATE chat_tasks.ai_message_id, _ai_message_id 经 run_agent_in_background
#   新参注入; ③C4 连带清理——db_ops 删 allocate_and_insert 条目(唯一消费点 agent_runner 惰性分支已随 C4-D3 删除)、
#   删 save_steps 条目及 :87 save_execution_steps_to_db 导入(grep 证实仅服务该条目;    sse_events 函数本体保留)
# 2026-08-22 - 小欧 - 北京老陈 2026-08-22 两处定: ①chat_messages 只写铁律: 编排⑥ _load_previous_messages 调用点改读
#     fetch_session_user_message_pairs(经 chat_user_message+chat_tasks 重建历史, 不读 chat_messages); ②L2 sessionModel 结构化: 读 get_session_model
#     覆盖 ai_service.provider+model(替原单 model_override), finally 双还原 provider+model(防单例污染)
# 2026-08-22 - 小欧 - 三堂会审复核整改(北京老陈 2026-08-22): 编排⑥消费点调用名由残留的 get_session_model_override 修正为 get_session_model(2026-08-22 改名后 import 已改、唯独调用点漏改, 此前任一会话请求必 NameError 崩溃, P0 修复); 因 get_session_model 现返回 SessionModelOverride(非 dict), 消费点改属性访问(.model/.provider, 去 .get/下标); 同步修正 line92 import 注释标明改名
# 2026-08-22 - 小欧 - model结构化归一报告v1.25 6.3/6.5/6.8: 全链 ModelRef 归一——validate_chat_config 响应
#   provider/model 键归一 model_ref 结构; _orig_model/_orig_provider 双变量 → _orig_llm_model 单 ModelRef
#   原子覆盖/还原(KISS: 消除半覆盖中间态); [TASK_START] 日志 F8 属性迁移; insert_task/token_usage_insert
#   闭包改传 task_model=agent.llm_client.llm_model(ModelRef), display_name 不再拼装落库(设计要求2)
# 2026-08-23 - 小欧 - 三轮三堂会审修复(P1): L2 覆盖与 finally 还原后各调 ai_service.reset_sdk()——SDK 缓存重建,
#   保 api_base/model 实连一致(配 base_service.reset_sdk 新方法)
# 2026-08-23 - 小欧 - 修复P3-2: L265 display_name 补 fallback 逻辑，session 未设置时继承原配置 display_name
# 2026-08-23 - 小欧 - 锚迁移(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): W6 镜像写点
#   (user 消息回填 task_id 的 UPDATE chat_messages)加 TODO 删除注释; :278 _user_msg_id 注释修正为
#   "chat_user_message.id 原生自增权威锚"(原"与chat_messages.id一对一"口径随锚迁移过时)
# 2026-08-23 - 小欧 - 落盘文件A/B 实施(文档[1]11.8.3 D1/11.8.7.1 D7/11.9 P5): 编排⑨事务内
#   allocate_and_insert_message 之后调 create_task_writer 建 A/B 双文件+header 并挂载 agent.file_persist
#   (局部导入 file_persist/time_utils, #11 必需); model 取 agent.llm_client.llm_model(ModelRef dump);
#   同事务 UPDATE chat_tasks SET files_dir='files/{session_id}/{task_id}/'($dir 排查定位锚, 不重复落文件名)
# 2026-08-24 - 小欧 - 后端卡死修复: 编排⑨事务内落库(insert_task/user消息回填/eager分配assistant+写chat_tasks.ai_message_id/files_dir)整体经 db.atxn 进子线程 offload 出事件循环,
#   loop 不再被同步写大blob+time.sleep锁重试独占, 根治 /health 超时/console 冻结; storage.* 与连接管理零改动复用;
#   create_task_writer(非DB文件写)移出事务块: 成功路径等价, 失败路径更稳(writer 创建失败不再连坐回滚任务落库事务, 任务行保留、file_persist 缺失由 getattr 守卫兜底)
# 2026-08-24 - 小欧 - 后端卡死修复收尾(offload): 编排③链根查询/编排⑤DB兜底user_msg_id/编排⑥sessionModel读取 三处同步 db.get_conn
#   改经 db.atxn 进子线程 offload 出事件循环(复用既有薄壳, 行为等价), 请求编排期 loop 零同步 DB I/O
# 2026-08-24 - 小欧 - 目录前导(北京老陈裁定): chat_tasks.files_dir 落库锚同步改为 files/Sion_{session_id}/Task_{task_id}/,
#   与 TaskFileWriter 物理目录经 file_persist 前缀常量同源拼装(DRY), 排查定位链不断; 旧目录不迁移(禁止backward)
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 整体移除W6镜像写点(_setup_task_db内UPDATE chat_messages SET task_id), 系统对该表零写依赖
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 删除finalize_message的import与db_ops.finalize=传参(随finalize_message整删, 终态由append_execution_step/chat_tasks承载)
# 2026-08-28 小欧 - yield日志审计: 编排①输入校验失败/编排②启动前已取消 两处 yield 前补 logger(warning/info), 覆盖7个无日志yield(KISS); 三堂会审无逻辑修正
# 2026-08-29 - 小沈 - 修复#5(彻底快照): 病根为 sessionModel 覆盖直接改进程单例 llm_model(全局副作用, 还原时序竞态致断连误模/跨会话串模)。改为构造本会话独立 LLM 客户端快照(ai_service.snapshot), 后台任务/流均用快照, 单例恒为全局默认不再被污染, 根除两类退化; run_agent_in_background finally 关闭快照释放连接池
# 2026-09-01 - 小欧 - [TASK_START]日志修复(北京老陈驱动): 原在会话覆盖快照生效(编排⑥)之前用 ai_service.llm_model(全局默认)打印, 且 model 字段显示全局而非实际生效模型, 误导排查(如本次会话覆盖 deepseek-v4-flash 生效, 日志却显 agnes)。移至覆盖快照生效后用 agent.llm_client.llm_model(实际生效客户端)打印
# 2026-09-01 - 小欧 - L2 会话级切跨 provider 模型修复(北京老陈驱动, 503/AgnesAI_error): 编排⑥覆盖生效块
#   按目标 provider+model 从 config.yaml 查 api_base/api_key(经 get_ai_config_resolver().get_service_config)+
#   model_params(复用 service.parse_model_params, DRY 唯一权威): 此前仅传 provider/model, 快照沿用全局
#   agnes 的 api_base/api_key/model_params→切 sensenova 仍 503。api_base 必须用目标 provider 的而非 _ov.api_base;
#   并入 snapshot(api_key/extra_body_params/context_limit 三参); 同步 agent._task_llm_model 为生效快照模型,
#   使 react_cycle/telemetry 日志显示真实生效模型(消除显 agnes 盲点); api_key 后端查配置, 不落库不出前端
# 2026-09-02 小欧 三堂会审task005-BUG-004修复: 配置查找失败显式置空(_pv_cfg/_pv_key/_pv_ebp/_pv_ctx),
#   原仅warning无置空, 虽初始化为None但显式表达降级意图, 日志补"放弃会话模型覆盖"便于排查
# 2026-09-02 - 小欧 - P10跨provider降级修复(北京老陈驱动「问题报告P10验证」): 配置查找失败(_pv_cfg is None
#   且目标provider≠全局)时跳过覆盖, 全链用全局默认模型(不以目标provider名+全局api_base错配快照致401/503);
#   规避报告_flag方案冗余, 以_pv_cfg判空直判, 仅改降级分支不改成功路径, 三堂会审通过(合规/合理/关联逻辑零退化)
# 2026-09-05 - 小健 - [7]8.6 一拆三: 消费转发 stream_reader(原 stream_reader.py 行257-284)整份并入本模块
#   (逐字复制零改动, 作为模块级函数, import format_agent_sse); _load_previous_messages 改指 history_loader,
#   _log_task_end 改指 agent_telemetry; 删 stream_reader.py 空壳不留垫片(禁backward)
# 2026-09-08 - 小欧 - 方案一心跳修订(北京老陈 2026-09-08 裁定, 三堂会审3轮):
#   [P1吞事件] 心跳原 yield ": ping" 无换行尾 → 与下一条 data: 事件粘连成一行, 前端 split('\n') 后整行
#    前缀非 'data: '(sseParser.ts:113 return) → 心跳后的第一个业务事件被整行丢弃(可能 final → 前端卡终态);
#    改 yield ": ping\n" 心跳独立成行(SSE 注释行标准带换行)。
#   [边界] 心跳周期原 60s 与前端 IDLE_TIMEOUT=60000 同时到期零余量, 网络/调度抖动下前端先判死致多余重连;
#    timeout 60.0→25.0(老陈裁定 25s 与前端 60s 错开), 保证 60s 窗口内必收字节, 日志/注释文案同步。
#   log: 心跳仍走 logger.debug("[SSE] cond.wait 25s超时" task_id) — 高频心跳不升 info 防日志噪杂。 — 小欧-2026-09-08
# 2026-09-08 - 小欧 - 心跳周期 25.0 抽常量化(北京老陈 2026-09-08 指令): timeout/日志/注释硬编码 25s 改引
#   constants.py §6 HEARTBEAT_INTERVAL(常量注释含与前端 IDLE_TIMEOUT=60000ms 的错开关系即"心跳先于前端判死"设计依据,
#   变更须前端联动); 功能零变化, 消除裸魔法数。 — 小欧-2026-09-08
# 2026-09-08 - 小欧 - 北京老陈指令(console可见性): 客户端断开"agent后台继续"(触发方案四断连取消链路)
#   logger.info→log_and_print 双写, 后端命令行可见断开动作(task_id); 心跳 yield 仍保持 logger.debug
#   (老陈"其他处不需双写,加log即可", 此处本就有debug日志) — 小欧-2026-09-08
# 2026-09-08 - 小欧 - 北京老陈 2026-09-08 后续指令勘正: 心跳 yield ": ping\n" 必须双写+计数——
#   原上一条(:118)按"心跳只需加log"保留 logger.debug 即属理解偏差, 本条目正式更改为
#   logger.debug→log_and_print 双写(console 可见每次心跳+序号 heartbeat_seq), 高频克制: 25s 一次, 不刷屏。
#   不得回改 debug, 不得删此条目(铁规: 编辑型禁删历史) — 小欧-2026-09-08
# 2026-09-11 - 小欧 - 通用规则落地(method2, 北京老陈 2026-09-11 定案): SSE 转发层唯一咽喉点
#   (stream_reader L450 format_agent_sse, 实时/重连共用)按类型过滤"仅落库不入SSE"事件——
#   thought 照常 publish 进 event_log(落库扫描/簿记/序号零改动), reader 转发时跳过;
#   新增 _SSE_EXCLUDE_TYPES 集合(OCP: 未来同类仅落库事件只扩集合, reader 零改动);
#   根因修复: 前端因 thought 双通道(实时SSE+历史回放DB)重复显示/裹挟(文档[26]问题一/二)
# 2026-09-12 小欧 - X2 E2E-X2-01 竞态根因修复(方案[31] §5.4): 删除临时 [Diag] reader exit 诊断日志,
#   恢复 done 分支纯 return; 根因在 react_loop 内部过早 done.set()(详见 react_loop.py 编辑历史 2026-09-12),
#   修复后 done 由 agent_runner finally 权威置位(所有事件含 final_stats 已发布), reader 排空即全量 — 小欧-2026-09-12
# 2026-09-12 小欧 - 追踪关键日志(北京老陈指令): stream_reader done 退出点补 logger.info(已转发offset/缓冲总长/
#   末类型/含final_stats), 与 [Runner] final_stats 已发布 seq 比对即可判定"SSE 漏发终态"(offset 停在 fs seq 前)
#   或"正常全量"(offset 越过 fs seq); 重连同语义 — 小欧-2026-09-12
# 2026-09-12 小欧 - 白名单落地([29]§7.3, 北京老陈 2026-09-12 批准 TDD 实施): 黑名单 _SSE_EXCLUDE_TYPES 反转为
#   白名单 _SSE_FORWARD_TYPES(默认拦截结构性杜绝 thought 事故), 配套登记源 steps/__init__.py ALL_STEP_TYPES;
#   过滤点 L481 反向判定 not in; 行为不变(白名单全集==当前转发全集=16实时+cancelled防御) — 小欧-2026-09-12
# 2026-09-13 小欧 - [30]§8.2 TDD P2(行488-490): 删除持锁死分支(原 L479 async with buffer.cond 持锁期间生产者
#   无法追加, 排空后复查 len 的 offset<len 分支恒 False 永不触发) 与 "# #30 fix:" 双井号噪声注释——
#   消费不丢由 notify_all 唤醒保证, 删除零行为差异(死代码清理)
# 2026-09-13 小欧 - 重连链路追踪补齐(北京老陈指令, 补点A/B): ①重连端点 chat_stream_reconnect_orchestrator
#   补 logger.info/logger.warning(收到重连请求: task/after_seq/session/缓冲总长/含final_stats;
#   任务不存在留 warning), 消除重连 zero-log——谁何时以 after_seq 发起重连、续传多少帧均可查;
#   ②stream_reader done 退出日志追加 is_reconnect/起点seq/续传帧数, 首连(after_seq=0)与重连可区分,
#   多 client 连同一 task 可分辨, 对账闭环(after_seq→续传帧数→已转发→含final_stats) — 小欧-2026-09-13
# 2026-09-17 小欧 - 统一拒绝事件 type="rejected": _SSE_FORWARD_TYPES 新增 "rejected", 删除 "user_rejected" - 小欧-2026-09-17
# 2026-09-20 - 小欧 - P3 B机制编排接入(13.4, 北京老陈定案"机会②"): 同会话已有活跃任务时, 新消息经
#   inject_message_to_task 注入该任务 inbox(可多条), 待下一轮 LLM 调用前合并吸收; 无活跃任务正常新建。
#   工具执行不被打断(安全底线); 注入失败(目标任务已终态)降级新建, 不丢消息。
#   compliance: SRP(编排仅负责路由/注入, 数据层在 task_registry)/KISS-DIRECT
# 2026-09-20 - 小欧 - 三堂会审BUG-11修复: 注入成功改用retrying类型(非error语义, 注入成功是正常业务路径)
"""
stream_orchestrator — 聊天流编排器(services 层)

职责(方案4.7.3, 小欧 2026-08-13): 负责任务生命周期、Agent 后台启动、SSE 消费编排。
API 层只保留路由薄壳, 编排逻辑单一归属本模块(SRP/SLAP)。
"""
import asyncio
import time
import uuid
from dataclasses import dataclass
from typing import Optional, AsyncGenerator, Dict, List

from app.services import get_service
from app.services.model.resolver import get_ai_config_resolver, resolve_session_client  # 8.7 外迁: 会话模型覆盖决议 — 小健 2026-09-05
from app.logger import logger, log_and_print
from app.services.chat.sse_events import create_error_response
from app.services.task.task_registry import (
    register_task,
    has_active_task_in_session,   # 2026-09-20 小欧 13.4.3: B机制注入入口 — 小欧-2026-09-20
    inject_message_to_task,
)
from app.services.task.task_runtime import (
    task_cancel_check, task_pause_check_and_yield, task_cancel_check_and_yield,
)
from app.utils.sse_formatter import format_agent_sse  # 8.6 消费转发并回本模块(SSE格式化) — 小健 2026-09-05
from app.services.agent.agent_runner import run_agent_in_background
from app.services.agent.universal_agent import UniversalAgent
from app.services.task.task_state import create_stream_buffer, get_stream_buffer
from app.constants import HEARTBEAT_INTERVAL  # 心跳周期常量(与前端 IDLE_TIMEOUT 的错开关系见 constants.py §6) — 小欧 2026-09-08
from app.services.task.task_context import _current_task_id
from app.logger.shared_handler import set_session_id
from app.services.chat.storage import get_user_message_id, allocate_and_insert_message, append_execution_step, query_task_accumulation  # 12.2-Q3: 追加权威累计查询 — 小欧 2026-08-21
from app.services.chat.storage import insert_task, update_task, token_usage_insert, get_previous_task_chain  # S1/S2 任务级读写(10.1.4/10.1.7②); get_session_model 已随 8.7 外迁 resolver 侧 — 小健 2026-09-05
from app.services.chat.storage import update_task_accumulation, update_session_accumulation  # 11.1 token 四层同构累计 — 小欧 2026-08-20
from app.db import db  # 小健 2026-08-17 三堂会审-A1修复: 模块级统一导入 db, 消除 line245 裸引用 db 的 NameError(chat_tasks 永不建行)
from app.services.chat.history_loader import _load_previous_messages  # 8.6 历史加载下沉 storage旁(与 fetch_session_user_message_pairs 邻居) — 小健 2026-09-05
from app.monitoring.agent_telemetry import _log_task_end  # 8.6 收尾日志归遥测(统计同类) — 小健 2026-09-05


# 后台 agent 任务强引用表: asyncio 仅持有 Task 弱引用, 若 SSE 消费者(generate)断开后任务再无强引用,
# 会被 GC 回收并取消, 导致 run_agent_in_background 的 finally(DB 保存)被打断、结果丢失(问题2)。
# 与 agent_runner._background_tasks 双重保险(后者 caller-agnostic): 本表在调用点持有引用,
# done 时 discard 防内存泄漏 — 小欧 2026-07-13(自 openai.py 迁入)
_agent_tasks: set = set()


def generate_task_id() -> str:
    """生成统一格式 task-{hex}，全链路唯一贯通 — 小欧 2026-07-16(自 openai.py 迁入)"""
    return f"task-{uuid.uuid4().hex}"


async def validate_chat_config():
    """聊天配置校验 — 自 api/v1/chat/openai.py 迁入 orchestrator — 小欧 2026-08-13
    2026-08-22 小欧 归一报告v1.25 6.6: resolver.validate_config 返回 (is_valid, ModelRef, errors);
    响应键 provider/model 归一为 model_ref 结构(方案B 前端随后端)"""
    from app.logger import logger
    try:
        resolver = get_ai_config_resolver()
        is_valid, config_model, error_messages = resolver.validate_config()
        if not is_valid:
            return {
                "valid": False,
                "message": f"配置验证失败: {', '.join(error_messages)}",
                "model_ref": {"provider": config_model.provider or "unknown",
                              "model": config_model.model or ""},
            }
        return {
            "valid": True,
            "message": f"配置验证通过: {config_model.provider} ({config_model.model})",   # 文本派生, 允许
            "model_ref": {"provider": config_model.provider, "model": config_model.model},
        }
    except Exception as e:
        logger.error(f"验证AI服务配置失败: {e}")
        return {
            "valid": False,
            "message": f"验证失败: {str(e)}",
            "model_ref": None,
        }


@dataclass
class StreamState:
    """流式状态 — 【修复P3-5】明确语义 — 北京老陈 2026-06-13(自 openai.py 迁入)"""
    llm_call_count: int = 0
    current_content: str = ""
    current_thought: str = ""  # 小欧 2026-07-16
    step_events: list = None

    def __post_init__(self):
        if self.step_events is None:
            self.step_events = []


async def chat_stream_orchestrator(
    messages: list,
    session_id: Optional[str] = None,
    context_link_mode: Optional[str] = None,
) -> AsyncGenerator[str, None]:
    """聊天流编排入口：负责任务生命周期、Agent 启动、SSE 消费。

    由 API 层解包 ChatRequest 后以 (messages, session_id) 调用；services 层不反向依赖 api/v1 DTO。
    2026-08-16 - 小欧 - S1: 增 context_link_mode(任务上下文链, 10.1.4);
      白名单校验(10.1.4⑧): 非法值/缺失一律按 independent, 防误灌历史(防退化)
    """
    # ── 编排①输入校验(链模式白名单 + 消息非空) ———————————————————————————— 小健 2026-08-17
    # 白名单校验(10.1.4⑧): {"linked","independent"} 之外的非法值按 independent 处理并记 warning
    if context_link_mode not in ("linked", "independent"):
        if context_link_mode is not None:
            logger.warning(f"[chat] context_link_mode 非法值 '{context_link_mode}', 按 independent 处理")
        context_link_mode = "independent"
    if not messages:
        # 2026-08-28 小欧 yield日志审计: 输入校验失败日志(KISS)
        logger.warning("[chat] 输入校验失败: 消息列表为空")
        yield create_error_response(error_type="invalid_request", error_message="消息列表不能为空")
        return
    user_input = messages[-1].content or ""
    if not user_input.strip():
        # 2026-08-28 小欧 yield日志审计: 输入校验失败日志(KISS)
        logger.warning("[chat] 输入校验失败: 消息内容为空")
        yield create_error_response(error_type="invalid_request", error_message="消息内容不能为空")
        return

    # ── 编排②取全局服务(LLM单例/model警告/task_id) ————————————————————————— 小健 2026-08-17
    ai_service = get_service()
    session_id = session_id or str(uuid.uuid4())
    _model_warning = get_ai_config_resolver().pop_model_warning()

    task_id = generate_task_id()
    # ── 编排③算任务上下文链根(linked继承 / independent自为链根) ————————————————— 小健 2026-08-17
    # S1 上下文链计算(10.1.4④⑧)：context_root_task_id
    #   linked=续聊(需显式): 继承本会话最近一条成功任务的链根(曾续则沿链根); 无成功任务则=自身
    #   independent=新任务(默认): =自身(从零自为链根)；cancelled/failed 不继承(防链到失败任务)
    _context_root_task_id = task_id
    if context_link_mode == "linked" and session_id:
        _prev_chain = None
        try:
            # 落库 offload 出事件循环(后端卡死修复收尾 小欧 2026-08-24)
            _prev_chain = await db.atxn("chat", lambda conn: get_previous_task_chain(conn, session_id))
        except Exception as _e:
            logger.warning(f"[chat] 取上一任务链根失败(session={session_id}): {_e}")
        if _prev_chain:
            _context_root_task_id = _prev_chain["context_root_task_id"]
    _task_token = _current_task_id.set(task_id)  # try/finally reset, 防 ContextVar 泄漏(方案4.7.3与A4对齐)
    set_session_id(session_id)
    # ── 编排④建运行基元(步号计数器 + SSE流状态容器) ———————————————————————————— 小健 2026-08-17
    # 2026-08-18 小欧 P2(§10.4.4): 删 next_step = create_step_counter()(step 统一 agent.llm_call_count 口径)
    execution_steps = []
    state = StreamState()

    # ── 编排⑤取续聊历史边界(user_msg_id 上界, 服务重启DB兜底) ——————————————————— 小健 2026-08-17
    _task_start_time = time.time()
    _user_msg_id = None
    try:
        _user_msg_id = get_user_message_id(session_id)
    except Exception:
        logger.warning(f"[chat] 获取user_message_id失败: session_id={session_id}")
    # 小健 2026-08-17 三堂会审-E2修复: track 为内存 dict(重启即丢), 缺失时从 DB 兜底取本会话最后一条
    #   user 消息 id 作为 linked 上界, 修复"服务重启后用第二任务续聊"时 upper=None 上界失效令链外/全部消息进上下文
    if not _user_msg_id and session_id:
        try:
            from app.services.chat.storage import get_last_user_message_id
            # 落库 offload 出事件循环(后端卡死修复收尾 小欧 2026-08-24)
            _row_u_id = await db.atxn("chat", lambda conn: get_last_user_message_id(conn, session_id))
            if _row_u_id:
                _user_msg_id = _row_u_id
                logger.info(f"[chat] E2 track缺失, DB兜底恢复upper: session={session_id}, user_msg_id={_user_msg_id}")
        except Exception as _eu:
            logger.warning(f"[chat] DB兜底取user消息id失败(session={session_id}): {_eu}")
    log_and_print(f"INFO: {time.strftime('%Y-%m-%d %H:%M:%S')}")

    bg_task = None  # BUG-32修复: 预初始化, 防 except 块 NameError — 小沈 2026-08-13
    try:

        # 2026-09-20 小欧 B机制(北京老陈定案): 同会话已有活跃任务时, 新消息注入该任务 inbox(可多条),
        #   待其下一轮 LLM 调用前合并吸收; 无活跃任务时走正常新建任务。工具执行不被打断(安全底线)。 — 小欧-2026-09-20
        _active_tid = await has_active_task_in_session(session_id)
        if _active_tid:
            _injected_ok = await inject_message_to_task(_active_tid, user_input)
            if _injected_ok:
                logger.info(f"[chat] 同会话运行中注入(session={session_id}, 目标task={_active_tid}, 新task={task_id}作废)")
                # BUG-11修复(小欧 2026-09-20): 注入成功是正常业务路径, 非error语义, 改用retrying类型(已在白名单)
                from app.llm.core import create_payload_chunk
                yield create_payload_chunk(ai_service.llm_model, {
                    "type": "retrying",
                    "content": "消息已注入当前执行中的任务，将在下一轮吸收",
                    "wait_time": None,
                })
                return
            # 注入失败(目标任务恰好终态): 降级新建任务(下述正常路径), 不丢消息
            logger.warning(f"[chat] 注入失败(目标任务finish), 降级新建任务: session={session_id}, target={_active_tid}")

        buffer = create_stream_buffer(task_id)
        await register_task(task_id, ai_service, session_id=session_id)

        is_cancelled, cancel_msg = await task_cancel_check(task_id)
        if is_cancelled:
            # 2026-08-28 小欧 yield日志审计: 任务已取消日志(KISS)
            logger.info(f"[chat] 任务启动前已取消: task={task_id}")
            yield cancel_msg
            return

        # ── 编排⑥建 UniversalAgent + 会话sessionModel(先建才有 llm_client) ——— 小健 2026-08-17
        agent = UniversalAgent(llm_client=ai_service, task_id=task_id)
        # 8.7 会话模型覆盖决议外迁 resolver.resolve_session_client(纯搬迁, 逻辑零改动) — 小健 2026-09-05
        #   无覆盖/无 session_id 返回 None, agent 维持全局默认; 有覆盖则换装独立客户端快照(单例不受污染)
        _session_client = await resolve_session_client(ai_service, session_id)
        if _session_client is not None:
            agent.llm_client = _session_client
            # S2 同步 _task_llm_model 为生效快照模型, 使 react_cycle 日志/telemetry 显示真实生效模型
            #   (而非全局 agnes), 与 TASK_START 显示实际生效模型同一精神 — 小欧 2026-09-01
            agent._task_llm_model = getattr(_session_client, "llm_model", None)
        # ── [TASK_START] 在会话覆盖快照生效后打印, 用 agent.llm_client(实际生效模型)非全局默认
        #    (修复: 原先打印 ai_service.llm_model 是全局默认且时机在覆盖前, 误导排查) — 小欧 2026-09-01
        log_and_print(
            f"[TASK_START] provider={agent.llm_client.llm_model.provider} model={agent.llm_client.llm_model.model} |\n "
            f"task_id={task_id} session_id={session_id} "
            f"user_message_id={_user_msg_id} |\n "
            f"user_input={user_input}"
        )
        # ── 编排⑦组装 db_ops 持久化回调命名空间(经闭包注入后台, 依赖 ⑥ agent) ——— 小健 2026-08-17
        # P4: 构造 db_ops 命名空间注入 agent_runner, 消除 agent→chat 反向依赖 — 小沈 2026-08-13
        #   10.1.7②-1 9属性(任务级读写扩展) — 小欧 2026-08-16
        import types as _types
        _db_ops = _types.SimpleNamespace(
            append_step=lambda c, mid, sid, idx, d, usage=None: append_execution_step(c, mid, sid, idx, d, task_id, usage=usage, user_message_id=_user_msg_id),  # _user_msg_id即chat_user_message.id（原生自增权威锚, 北京老陈 2026-08-23 锚迁移）— 小健 2026-08-19 P1-4
            load_previous=lambda sid: _load_previous_messages(  # 任务上下文过滤(10.1.4⑤⑥)，经闭包注入链路计算的 context 两字段+上界(_user_msg_id)
                sid, context_link_mode=context_link_mode, context_root_task_id=_context_root_task_id,
                upper_message_id=_user_msg_id),
            log_task_end=_log_task_end,
            insert_task=lambda c: insert_task(  # ②-1 chat_tasks 创建 — 归一: task_model 传 ModelRef, display_name 不再拼装落库(设计要求2) — 小欧 2026-08-22
                c, task_id=task_id, session_id=session_id, user_message_id=_user_msg_id,
                ai_message_id=None,  # agent_runner 分配后回填 — 小欧 2026-08-19
                user_input=user_input, context_link_mode=context_link_mode,
                context_root_task_id=_context_root_task_id,
                task_model=agent.llm_client.llm_model),
            update_task=lambda c, **kw: update_task(c, task_id=task_id, **kw),  # ②-1 chat_tasks 终态
            insert_token=lambda c, **kw: token_usage_insert(  # ②-3 共用 — 归一: task_model 传 ModelRef — 小欧 2026-08-22
                c, task_id=task_id, session_id=session_id,
                task_model=agent.llm_client.llm_model, **kw),
            update_task_accumulation=lambda c, **kw: update_task_accumulation(c, **kw),  # 11.1 任务级token累计(去闭包双重绑定, 由调用方经**kw传task_id)
            update_session_accumulation=lambda c, **kw: update_session_accumulation(c, **kw),  # 11.1 会话级token累计(去闭包双重绑定, 由调用方经**kw传session_id)
            query_task_acc=lambda c, **kw: query_task_accumulation(c, **kw),  # 12.2-Q3/C3: 终态快照从权威累计列派生 — 小欧 2026-08-21
            user_msg_id=_user_msg_id,  # v2.0 改动2: 供agent_runner回填chat_user_message — 小欧 2026-08-19
        )
        # ── 编排⑧注入 start 运行元数据(_start_meta, start_step 装配用) ———————— 小健 2026-08-17
        # S4/S5(10.1.1③/10.1.7④): start 运行元数据注入 agent — 取消 orchestrator 旁路(step_start),
        #   start 业务完整归 start_step 模块(chat 层仅 P4 捕获运行数据注入 agent._start_meta),
        #   react_cycle 经 assemble_start_step 从 _start_meta 读齐装配, 不再有 chat 层 start 构造逻辑 — 小健 2026-08-17
        #   只注入 agent 拿不到的 chat 运行数据: task_id(agent.task_id 已持有)、provider/model(agent.llm_client
        #   已持有)、user_input? 见下——next_step/session_id/链字段/warning 为必需 (react_cycle 无权威源)
        #   2026-08-17 小健 收敛真冗余: task_id 由 agent.task_id 权威持有(base_agent:59), 不重复注入; 余键保留
        agent._start_meta = {
            "user_input": user_input,
            "session_id": session_id,
            "context_link_mode": context_link_mode,
            "context_root_task_id": _context_root_task_id,
            "warning": _model_warning,
        }
        # ── 编排⑨落库任务行 + 建后台 agent 任务(asyncio.create_task 独立运行) ——— 小健 2026-08-17
        # ②-1 落点：建 agent 后、后台运行前 INSERT 任务行(provider/model 取 agent.llm_client) — 小欧 2026-08-16
        _ai_message_id = None
        try:
            # 目录前导常量局部导入(北京老陈 2026-08-24): files_dir 落库锚与物理目录唯一同源(DRY, 前缀定义于 file_persist)
            from app.file_persist import SESSION_DIR_PREFIX, TASK_DIR_PREFIX
            # ②-1 落库热路径 offload 出事件循环(后端卡死修复 小欧 2026-08-24):
            #   原 `with db.get_conn_with_retry` 在 loop 主线程同步写大 blob + time.sleep 锁重试,
            #   致 loop 被独占、/health 超时; 整段 DB 操作经 db.atxn 进子线程, conn 同线程闭环零跨线程。
            def _setup_task_db(conn):
                _db_ops.insert_task(conn)
                # v2.0 改动7: user 消息回填 task_id — 小欧 2026-08-19
                # 镜像写点 W6(UPDATE chat_messages SET task_id) 已随 chat_messages 表退役整体移除 — 小欧 2026-08-27
                # 12.2-C4: eager分配assistant行+创建时即写chat_tasks.ai_message_id —
                #   任务启动即分配(原首步惰性), 消除agent_runner finally legacy save_steps分支
                #   (步骤丢失/覆写旧消息双风险根除) — 小欧 2026-08-21
                _aid = allocate_and_insert_message(conn, session_id, task_id, user_message_id=_user_msg_id)
                conn.execute(
                    "UPDATE chat_tasks SET ai_message_id=? WHERE task_id=?",
                    (_aid, task_id),
                )
                # D7/#5(2026-08-23): 11.7.5-1 落库 $dir 引用(物理目录 = files/Sion_{session_id}/Task_{task_id}/,
                #   前导 2026-08-24 北京老陈裁定, 与 TaskFileWriter._dir 同源常量拼装),
                #   供排查定位(任务→files_dir→文件A 按 step/tool_no/retry_no 定位块→文件B); 不重复落库文件名 — 小欧 2026-08-23
                conn.execute(
                    "UPDATE chat_tasks SET files_dir=? WHERE task_id=?",
                    (f"files/{SESSION_DIR_PREFIX}{session_id}/{TASK_DIR_PREFIX}{task_id}/", task_id),
                )
                return _aid
            _ai_message_id = await db.atxn("chat", _setup_task_db)
            # 11.8-H1/D1: 文件A/B 创建(header)——assistant 分配即建(11.7.4-4); 创建后挂载
            #   agent.file_persist 供 agent 层钩子使用(telemetry 同模式, agent 零 chat 依赖) — 11.9 P5 — 小欧 2026-08-23
            #   非DB文件写, 移出DB事务块(后端卡死修复 offload 小欧 2026-08-24):
            #   成功路径等价; 失败路径更稳——writer 创建失败不再连坐回滚任务落库事务(仅告警),
            #   任务行/ai_message_id 已持久化, agent.file_persist 缺失由下游 getattr 守卫兜底
            from app.file_persist import create_task_writer
            from app.utils.time_utils import get_local_iso_timestamp  # 局部导入必需(#11: 顶层无该符号, 缺则 NameError 被吞降级无文件)
            _mr = getattr(getattr(agent, "llm_client", None), "llm_model", None)
            agent.file_persist = create_task_writer(
                session_id=session_id,
                task_id=task_id,
                ai_message_id=_ai_message_id,
                start_time_iso=get_local_iso_timestamp(),
                model=(_mr.model_dump(exclude_none=True) if hasattr(_mr, "model_dump") else None),
            )
        except Exception as _task_e:
            logger.warning(f"[chat] chat_tasks INSERT/eager分配失败(task={task_id}): {_task_e}")
        # 持有强引用，防 GC 回收导致任务被取消→打断 DB 保存(问题2修复) — 小欧 2026-07-13
        bg_task = asyncio.create_task(run_agent_in_background(
            agent, task_id, user_input, None, session_id, state, _task_start_time,
            db_ops=_db_ops, ai_message_id=_ai_message_id))
        _agent_tasks.add(bg_task)
        bg_task.add_done_callback(_agent_tasks.discard)

        # ── 编排⑩流式转发(消费后台 agent 产出的 SSE → 转前端) ————————————————— 小健 2026-08-17
        async for sse_chunk in _stream_with_control(buffer, task_id, session_id, execution_steps, state):
            yield sse_chunk
    # ── 编排⑪异常/收尾(断连静默/异常取消后台/reset ContextVar) ———— 小健 2026-08-17; 小沈 2026-08-29 bug#5: 去 finally 还原单例副作用
    except asyncio.CancelledError:
        # 客户端断开：静默返回，agent 后台继续 — 北京老陈 2026-07-12 小欧 2026-07-12
        log_and_print(f"{time.strftime('%H:%M:%S')} [chat_stream_orchestrator] 客户端断开(task={task_id})，agent 后台继续")  # 2026-09-08 小欧: 双写(console可见断开动作) — 小欧-2026-09-08
        return
    except Exception as e:
        logger.error(f"[chat_stream_orchestrator] Error: {e}", exc_info=True)
        # BUG-32修复(三堂会审 小沈 2026-08-13): orchestrator 异常时 cancel bg_task, 避免后台继续运行但前端收到错误的状态不一致;
        #   bg_task 已启动(若进入 try 块内), cancel 后 run_agent_in_background 的 finally 仍会执行 DB 保存(已产出结果不丢失)。
        try:
            if bg_task and not bg_task.done():
                bg_task.cancel()
                logger.info(f"[chat_stream_orchestrator] 已取消后台 agent 任务: {task_id}")
        except Exception as _ce:
            logger.warning(f"[chat_stream_orchestrator] 取消 bg_task 失败: {_ce}")
        yield create_error_response(error_type="router_error", error_message=f"路由异常: {str(e)}")
    finally:
        _current_task_id.reset(_task_token)


# ============================================================
# SSE 转发通道路由表(白名单, 北京老陈 2026-09-12 复核定案; [29]§7.3.2 实施定稿) — 小欧-2026-09-12
# event_log = 落库与 SSE 共源(生产端 publish 直写); stream_reader = 唯一转发咽喉点(实时/重连共用)。
# 白名单语义: 仅下列类型被实时转发前端; 未登记类型一律不转发(默认拦截, 结构性杜绝 thought 事故)。
# 纪律([29]§7.3.1): 新增任何 Step/事件类型必须·在此登记 + ·steps/__init__.py ALL_STEP_TYPES 登记源登记, 缺一不放行。
# 全集来源: [29]§7.1.3(当前 HEAD 4bf3ea987 逐字面值实证)。
# ============================================================
_SSE_FORWARD_TYPES = frozenset({
    # SSE + 落库
    "start", "action", "observation", "final", "final_stats",
    # 仅SSE(实时信号, 落库由 agent_runner 扫描分支处理)
    "chunk", "thought-start",
    "error", "usage", "paused", "resumed", "retrying",
    "rejected", "stats", "context_overview", "truncated",
    # 防御性保留: 当前无独立发射源, 若未来新增取消通知类可转发
    "cancelled",
})


async def stream_reader(buffer, task_id: str, after_seq: int = 0):
    """纯消费者：从事件缓冲按 seq 偏移读取并转发 SSE — 小欧 2026-07-12

    解决什么问题：SSE 只做"读缓冲→转发"，断线即返回、不碰 agent；
    重连复用同一函数（传 after_seq 续传），避免重复事件。 — 北京老陈 2026-07-12

    小健 2026-09-05 自 stream_reader.py 整份并入本模块(8.6 一拆三, 逐字复制零改动)
    """
    offset = after_seq
    heartbeat_seq = 0  # 2026-09-08 小欧: 心跳计数器(北京老陈指令心跳双写+计数, 见编辑历史) — 小欧-2026-09-08
    while True:
        async with buffer.cond:
            while offset < len(buffer.event_log):
                # 2026-08-28 小欧 yield日志审计: SSE发送统一入口(覆盖全部SSE yield, KISS)
                _ev = buffer.event_log[offset]
                offset += 1  # 2026-09-11 小欧 先推进再判: 过滤不卡循环, event_log 序号恒单调连续 — 小欧-2026-09-11
                if not _ev or _ev.get("type") not in _SSE_FORWARD_TYPES:
                    continue  # 白名单: 未登记类型不转发(默认拦截); 落库扫描/event_log/重连均不受影响 — 小欧-2026-09-12
                logger.debug(f"[SSE] seq={offset - 1} task={task_id}")
                yield format_agent_sse(_ev)
            if buffer.done.is_set():
                # 2026-09-12 小欧 - 追踪关键点: sole 流结束/断流截断点——offset 为已转发事件数(≤len),
                #   与远端 [Runner] final_stats 已发布 seq 比对即可判定"SSE 是否漏发终态"(offset 停在 fs seq 之前
                #   = 截断) 或"正常全量"(offset 越过 fs seq)。重连场景 offset 为续传起点, 同语义。
                #   — 小欧-2026-09-12
                _tail_type = (buffer.event_log[-1] or {}).get("type") if buffer.event_log else "empty"
                _has_fs = any((e or {}).get("type") == "final_stats" for e in (buffer.event_log or []))
                logger.info(f"[SSE] reader退出(task={task_id}, is_reconnect={after_seq > 0}, 起点seq={after_seq}, "
                            f"续传帧数={offset - after_seq}, 已转发={offset}, 缓冲总长={len(buffer.event_log or [])}, "
                            f"末类型={_tail_type}, 含final_stats={_has_fs})")  # 小欧-2026-09-13 补点B: 首连/重连可区分, 对账闭环
                return
            # cond.wait()无超时: 若producer崩溃永不set.done, 消费者永久挂起泄漏HTTP连接
            # 加超时并循环重检done — 北京老陈 2026-07-30; 2026-09-08 小欧: timeout 60s→25s(兼心跳保活周期, 见编辑历史)
            try:
                await asyncio.wait_for(buffer.cond.wait(), timeout=HEARTBEAT_INTERVAL)  # 心跳周期 HEARTBEAT_INTERVAL(错开关系见 constants.py §6, 与前端 IDLE_TIMEOUT=60s 错开)
            except asyncio.TimeoutError:
                heartbeat_seq += 1  # 2026-09-08 小欧: 心跳计数递增(北京老陈指令双写+计数) — 小欧-2026-09-08
                log_and_print(f"{time.strftime('%H:%M:%S')} [SSE] 心跳#{heartbeat_seq} task={task_id} cond.wait {HEARTBEAT_INTERVAL}s超时, 发 :ping 保活")  # 2026-09-08 小欧: debug→双写(北京老陈指令) — 小欧-2026-09-08
                # 方案一 SSE keep-alive 心跳(北京老陈 2026-09-08, 周期 HEARTBEAT_INTERVAL): 该周期内无业务事件(如 tool 参数流式期间)时
                #   向前端发 SSE 注释行 ": ping\n" —— 注意带换行尾(修订: 原 ": ping" 无换行会与下一条 data: 事件粘连,
                #   前端 split('\n') 后整行前缀非 'data: ' 被 sseParser.ts:113 整行丢弃, 吞掉心跳后的第一个业务事件),
                #   刷新前端 IDLE_TIMEOUT=60000 空闲计时; 心跳 HEARTBEAT_INTERVAL 与前端 60s 错开(constants.py §6), 无同时到期竞态;
                #   前端 processSSEData 对非 'data: ' 前缀行直接 return(sseParser.ts:112-115), 零业务解析零副作用。
                #   真断连时 heartbeat 随连接自然停发, 前端仍按 60s 判死走重连/兜底。 — 小欧 2026-09-08
                yield ": ping\n"
                if buffer.done.is_set():
                    return
                continue


async def _stream_with_control(buffer, task_id: str, session_id: str,
                               execution_steps: list, state=None, after_seq: int = 0):
    """SSE 消费者包装：读缓冲 + 注入 pause/cancel 检查 — 自 openai.py 迁入 — 小欧 2026-08-13

    首次请求(after_seq=0)与重连请求(after_seq=N)共用本函数，DRY。
    客户端断开时 CancelledError 向上传播，由 orchestrator 捕获。
    2026-08-18 小欧 P2(§10.4.4): 删 next_step, task_pause/cancel_check 步号统一 _current_step(task_id)
    """
    async for sse_chunk in stream_reader(buffer, task_id, after_seq):
        async for pause_event in task_pause_check_and_yield(task_id):
            yield pause_event
        cancelled_sse = await task_cancel_check_and_yield(
            task_id, execution_steps)
        if cancelled_sse:
            yield cancelled_sse
            return
        yield sse_chunk


async def chat_stream_reconnect_orchestrator(
    task_id: str, session_id: Optional[str] = None, after_seq: int = 0
) -> AsyncGenerator[str, None]:
    """SSE 重连编排：读同一任务的流态缓冲，不启动新 agent — 自 openai.py 迁入 — 小欧 2026-08-13"""
    buffer = get_stream_buffer(task_id)
    if not buffer:
        logger.warning(f"[SSE] 重连任务不存在(task={task_id}, after_seq={after_seq}, session={session_id or '-'})")  # 小欧-2026-09-13 重连追踪补点A
        yield create_error_response(error_type="not_found", error_message="任务不存在或已结束")
        return
    logger.info(f"[SSE] 重连请求接收(task={task_id}, after_seq={after_seq}, session={session_id or '-'}, 缓冲总长={len(buffer.event_log or [])}, 含final_stats={any((e or {}).get('type') == 'final_stats' for e in (buffer.event_log or []))})")  # 小欧-2026-09-13 重连追踪补点A
    async for sse_chunk in _stream_with_control(
        buffer, task_id, session_id or "", [], None, after_seq
    ):
        yield sse_chunk