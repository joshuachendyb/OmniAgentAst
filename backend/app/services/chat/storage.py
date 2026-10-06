# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-14 - 小欧 - 新增allocate_and_insert_message/append_execution_step/load_execution_steps/finalize_message四函数,支撑运行期逐步落库+渐进耐久
# 2026-07-14 - 小欧 - 修复load_execution_steps: 无步骤且无legacy blob时返回[]而非None,避免API返回execution_steps=None
# 2026-07-18 - 小欧 - FinalStep多态自包含终态重构: derive_status_from_steps改为读最后一条final.outcome
#   【病根】原derive_status_from_steps基于type推断终态(cancelled→cancelled, error→failed),
#          与FinalStep多态设计不一致; 且type=final始终返回completed, 无法区分failed终态。
#   【改法】改为遍历找最后一条type=final, 读其outcome字段返回; 无final时兜底返回completed。
# 2026-07-18 - 小欧 - create_timestamp→get_utc_timestamp() (3处); append_execution_step 补 created_at 入库
# 2026-07-18 - 小欧 - 修复#1空步骤谎报完成: derive_status_from_steps 空/无final步默认"failed"(fail-safe, 对齐agent_runner兜底); 修复#6拼写错 ccancelled→cancelled
# 2026-07-18 - 小欧 - 修复: allocate_and_insert_message 首行补 ensure_session_exists, 消除孤儿消息风险
# 2026-07-18 - 小欧 - 修复: allocator锁范围扩大覆盖SELECT+dict写入,消除竞态
# 2026-07-21 - 小欧 - SQLite存储适配: MAX_TOOL_RESULT_STR_LEN=100(0a054a05e)→10000(4ee3ff070), _truncate_tool_result_strings方法, 写入前截断tool_result超长字符串防SQLite行溢出; _truncate_step_dict调用链; 不碰observation字段
# 2026-07-21 - 小欧 - 修复 _truncate_step_dict 漏掉 execution_result+parallel_results 截断;
# 2026-07-21 - 小欧 - 加 _truncate_tool_result_strings (带 tag 日志, 不碰 observation);
# 2026-07-21 - 小欧 - 移动 MAX_TOOL_RESULT_STR_LEN 等常量;
# 2026-07-23 - 小欧 - 北京老陈驱动: 安全兜底 MAX_TOOL_RESULT_STR_LEN
#         10000→100000 (各tool自行截断输出后, storage仅兜底,
#         不再做激进取舍)
# 2026-08-08 - 小欧 - 全程统一本地时区: get_utc_timestamp→get_local_iso_timestamp (L147/189/232/329 4处写入), 本地ISO无Z入库
# 2026-08-11 - 小欧 - task006方案5落地: 截断字符串附加"原长N字符"标记, 让LLM感知base64/长文本被截断, 影像分析类任务不被截断误导
# 2026-08-13 - 小欧 - 三堂会审修复#1/#9: #1 allocate_and_insert_message 的 local_time 提前到 if is_new 外赋值,
#   消除 is_new=False(同session二次任务 agent_runner路径)时 UPDATE 引用未绑定变量 NameError;
#   #9 _truncate_tool_result 递归返回值统一回写父节点, 修复 list 内嵌超长 list 截断失效(如 {"rows":[[…1001…]]})
# 2026-08-16 - 小欧 - S2(10.1.7②, 北京老陈 2026-08-16 定案): 任务级读写落库扩展——
#   ②-1 insert_task/update_task(chat_tasks 建行+终态, update 幂等缺省不覆盖); ②-2 allocate_and_insert_message/
#   append_execution_step 增 task_id 列(任务级贯通), load_execution_steps 增 task_id 双条件(未传退化按 message_id);
#   ②-3 token_usage_insert; ②-4 get_session_model_override; ②-5 insert_session_trust/check_session_trust +
#   get_session_id_by_task(task_id→session_id 反查, HITL trust 落库/豁免用, 禁伪 agent.session_id);
#   ②-6 query_token_usage 四维聚合 + get_previous_task_chain(S1 链根计算)
# 2026-08-17 - 小健 - 三堂会审修复(北京老陈驱动, 11 bug 复核3遍):
#   E2: line69-77 新增 get_last_user_message_id(DB兜底), 供 orchestrator 在 track 缺失时为 linked 续聊恢复 upper 上界。
#   AM2/STORAGE_1: AssistantMessageIdAllocator.allocate 增 always_new 参数(默认False保留legacy复用语义);
#       allocate_and_insert_message 设 always_new=True 每任务独立新行——绝 user 未track时 expected 命中已存在
#       assistant 行导致内容覆盖(同session多任务共用一行)。[2026-09-30 小欧: 原"is_new=False 仍 +1 虚高"半句随计数器退役删]
#   STORAGE_2: 每任务独立行后, load_execution_steps 按 task_id 双条件不再混任务步骤。
# 2026-08-17 - 小健 - 必备日志补齐(老陈驱动「昨天今天提交代码都必须加」): allocate 的 always_new 递增寻空位
#   打 logger.warning 留痕(异常回落/越界审计点, 仅落文件不刷 console)。
# 2026-08-18 - 小健 - 三堂会审 修复: _truncate_step_dict 补新 ActionStep 字段 tools[i].params 超长字符串截断(旧实现仅截断 execution_result/parallel_results, 漏 tools 致长SQL/content撑爆SQLite); 已核实 ActionStep.to_dict() 输出键为 tools, 非死代码
# 2026-08-19 - 小欧 - v2.0核心数据模型重构(9.1→9.4→9.6→9.9): append_execution_step参数message_id→ai_message_id
#   +新增usage/user_message_id列、load_execution_steps去掉chat_messages.execution_steps回退、allocate_and_insert_message
#   加user_message_id参数、insert_task加ai_message_id参数、新增6函数(insert_user_message/update_user_message_final/
#   load_user_message_by_task/get_task_detail/get_task_tool_stats/load_steps_by_task)
# 2026-08-19 - 小欧 - 三堂会审修复: insert_assistant_message INSERT列 reply_to_message_id→user_message_id
#   (v2.2列改名后旧列名新库不存在, 执行即OperationalError; 模型字段名保留API层, DB列名对齐v2改名)
# 2026-08-20 - 小欧 - 11.1 token 四层同构累计三堂会审修复: ①import types; ②_EMPTY_TOKEN 改 types.MappingProxyType 冻结(防外部 mutate 污染全局); ③新增 _normalize_acc() 显式判键归一(parse_json('{}') 返 truthy 空对象, 原 `or dict` 不兜底致下游 _old['prompt_tokens'] KeyError 致命bug, 现统一归一含3键零值); ④query_task/session_accumulation 加 row 缺失守卫+改调 _normalize_acc; ⑤update_task/session_accumulation 加 rowcount==0 告警(检测累计静默丢失)
# 2026-08-20 - 小欧 - 11.1 测试驱动修复(_normalize_acc, 小欧单测 tests/test_token_accumulation_11_1.py 锁定): 原仅对非法/空对象归一, 对"含部分键"的 JSON(如 {'prompt_tokens':5})原样返回 → query 返回缺键 dict(违反设计11.1.2含3键零值)、update 下游 _old[k] KeyError 崩溃、react_cycle 基线 [k] KeyError 被 except 吞致历史累计静默清零; 现改为缺键统一补零并 int 强转, 保留已存键。3 用例(部分键归一/update不崩/基线)已加。
# 2026-08-20 - 小欧 - 10.5 问题4/6 三堂会审落地: 新增 list_session_tasks(会话任务列表+总数, B1/问题6 任务数=用户消息数, chat_tasks 行数新口径) + list_session_trust(D1 信任清单) + delete_session_trust(D3 撤销信任)。
# 2026-08-21 - 小欧 - 11.6.4: update_task 新增 artifacts 参数+safe_json_dumps 写库; get_task_detail parse_json 反序列化 artifacts 为 list
# 2026-08-22 - 小欧 - 新增 load_user_messages_by_session (按 session_id 读 chat_user_message 列表，替代 chat_messages)
# 2026-08-22 - 小欧 - 北京老陈 2026-08-22 定: L2 会话级模型覆盖 sessionModel 结构化: ① get_session_model_override 改名 get_session_model,
#     读 sessionModel 列(JSON)→dict(provider+model, 用 parse_json 容错); ②关联调用点 stream_orchestrator 同步改名引用
# 2026-08-22 - 小欧 - 三堂会审复核整改(北京老陈 2026-08-22): ①新增全系统唯一 parse_session_model(消除 message_service/session_service 重复实现, DRY), 返回 SessionModelOverride; ②get_session_model 返回值由 dict 改为 SessionModelOverride(类型统一, 杜绝调用方误用 .get 致 AttributeError); 关联 stream_orchestrator 消费点改属性访问(.model/.provider)
# 2026-08-22 - 小欧 - BUG修复(北京老陈 2026-08-22 铁律"系统代码不得退化"): 铁律后占用检查改读 chat_user_message+chat_tasks(禁读 chat_messages), 若 chat_messages 已存在该 id(如 legacy 直写助手消息未镜像至 chat_tasks)落库时 UNIQUE 撞键→500; save_execution_steps 改为撞键时退化为复用该消息(UPDATE, is_new 置 False 不重复计数), 与铁律前 chat_messages 占用检查"复用而非新建"语义一致, 不读 chat_messages、不污染 chat_tasks
# 2026-08-22 - 小欧 - model结构化归一报告v1.25/v1.26 6.3: 写侧三函数归一——insert_task(provider/model/display_name 三参→task_model: ModelRef 必填, 落 sessionModel JSON 单列)、token_usage_insert(model/provider→task_model: ModelRef 必填, NOT NULL)、update_user_message_final(model/provider→task_model: Optional[ModelRef], SET chat_model); 六读者派生——query_token_usage(model=→model_ref: json_extract 双键)、load_user_message_by_task/load_user_messages_by_session/fetch_session_user_message_pairs/get_task_detail/list_session_tasks (chat_model/sessionModel JSON→parse_session_model 派生 model/provider 键, 键名不变); import 补 ModelRef
# 2026-08-23 - 小欧 - 三轮三堂会审修复: insert_task 删 `if task_model else None` 死防御——参数已必填, Pydantic 实例恒真值, else 分支永不可达(SLAP); 直取 model_dump_json()
# 2026-08-23 - 小欧 - 锚A解除(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): insert_user_message id 分配锚迁移——user_message_id 显式入参退役(原=chat_messages.lastrowid 一对一贯通), 改 chat_user_message AUTOINCREMENT 原生自增并返回 lastrowid; INSERT OR REPLACE 随显式 id 退役(自增无撞键)改普通 INSERT; W2/W3/W4/W5 四个镜像写点加 TODO 删除注释(写保留, 系统零依赖 chat_messages)
# 2026-08-23 - 小欧 - 截断退役(文档落码, 定案"现役表不截断"): 删 _truncate_tool_result/_truncate_step_dict/_truncate_tool_result_strings 三函数+两 MAX_TOOL_RESULT_* 常量, 新增 _warn_oversize_step_dict 超限 error 告警扫描(安全网不砍数据); append_execution_step 改完整 step_json 落库保历史回放权威源(5.1 铁律), 签名/返回值 -> None 原样零感知; 原"实验性的功能:TODO"占位随删除块一并清理
# 2026-08-26 - 小欧 - D-1(8.D): list_session_tasks SELECT 补 context_link_mode 列, 前端左列"续聊/新任务"类型徽标数据源(4.8.3-B 契约已含该字段, 后端 SELECT 遗漏)
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 整体移除镜像写点W2(insert_assistant_message)/W3(allocate_and_insert_message内INSERT空白行)/W4(update_message_fields)/W5(finalize_message内UPDATE)及save_execution_steps中对W2/W4的调用; 删除后终态/步骤真实存储由chat_task_steps.step_json与chat_tasks承载; 同步清理孤儿import(IntegrityError/extract_metadata_from_steps)
# 2026-08-27 - 小欧 - B1 SELECT 补 response 列: list_session_tasks 查询增加 response 字段返回，支撑左列任务列表显示任务结果全文（设计文档4.8.2要求user_input+response双列显示）
# 2026-08-27 - 小欧 - 阶段2(chat_messages表退役): 整删finalize_message函数(原W5写chat_messages终态), 同步移除stream_orchestrator.db_ops.finalize=传参与agent_runner调用块(行446-461), 终态由append_execution_step(step_json)与_finalize_task_db(update_task+回填chat_user_message)承载
# 2026-08-29 - 小沈 - 修复: update_task 的 response 默认从 "" 改为 None; 循环内 `if _val is not None` 已存在, 故未显式传 response 时不再用空串覆盖已有列(幂等缺省不覆盖语义落地)。
# 2026-08-30 - 小欧 - 排序调整(设计文档v1.103): list_session_tasks 排序 DESC→ASC(左列时间线=会话全部任务时间线清单, 新任务在底部; 原 DESC 是顶栏锚点"首行=最新"的专用依赖, 一手排序喂两个反方向职责违反 SRP); 新增返回 latest_task_id(最新任务显式锚点, 顶栏/默认选中/结束沿 token 锚点统一消费, 排序一义+显式锚点解耦)。调用方 sessions.py 同步解包三元组(见 diff)。
# 2026-08-30 - 小欧 - 出参收口(设计文档, 北京老陈 2026-08-30 批准): load_steps_by_task 对 thought 步骤剥离 content 键出参(回放只取 thought/reasoning 两字段契约), 仅剥 content、其余键原样保全
# 2026-08-30 - 小欧 - get_task_tool_stats SQL修复: json_extract $.tools[0].name→$.tools[0].tool(根因: ActionStep写入key为"tool"非"name", 致工具汇总全归null×4)
# 2026-09-02 - 小欧 - 会话信任功能修复 v1.5⑤②(北京老陈定案"只有tool+path才是准确对象", 详见doc-9月优化/会话信任功能修复方案):
#   chat_session_trust 四函数整体替换增 path 参数 + 前缀递归匹配——
#   insert_session_trust(conn, session_id, tool_name, path=None): path=None=工具级通配, 非空=resolve绝对化落库;
#   check_session_trust(conn, session_id, tool_name, path=None): path=None仅命中工具级通配行(path IS NULL), path给定命中通配行或信任根等于目标/为目标祖先目录(前缀递归, 与temp_auth语义对齐);
#   list_session_trust: 返回增 path 字段(D1 信任清单带 path 展示);
#   delete_session_trust(conn, session_id, tool_name, path=None): (tool,path)精确撤销, path=None仅删工具级通配行(D3);
#   新增 _norm_trust_path 路径规范化(resolve绝对化, 落库/查询双侧一致); 文件首增 from pathlib import Path
# 2026-09-05 - 小欧 - 架构边界修正(三堂会审): insert_session_trust/check_session_trust/get_session_id_by_task
#   三函数迁往 app/tools/trust_db.py(逐字复制不改逻辑)——修复 trust.py(app/tools) 越层 import app.services.chat.storage
#   违反"app/tools 禁 app.services"依赖方向守护(test_architecture_boundaries.py)。唯一调用方 trust.py 已改引 trust_db;
#   _norm_trust_path 本层保留(delete/list 仍用)。该项与本仓库既有 2-5 层存储分离无关, 是 09-04 resolve_skip 重构残址。
# 2026-09-16 - 小欧 - 问题修复: _norm_trust_path 增 tool_name 参数, 与 trust_db.py:17 同位同步
#   非文件信任域(registry/sql)跳过 Path.resolve() —— 撤销侧一致性, 防 registry 原样键路径再被臆造 resolve 致撤消失配; — 小欧-2026-09-16
# 2026-09-16 - 小欧 - 函数化(DRY/KISS核查): 删除本层 _norm_trust_path 双份副本, 撤销侧改消费
#   trust_db.norm_trust_path 单一来源(services→tools 合法单向); 同步删仅被其使用的 from pathlib import Path — 小欧-2026-09-16
# 2026-09-20 - 小欧 - D-2修复(删会话内存ID泄漏): allocator 增 forget_session(session_id) 双侧清空
#   (_user_ids/_assistant_ids), 模块级 forget_session_message_ids 清 track 字典; delete_session 经 session_service 接入。
# 2026-09-20 - 小欧 - E-4修复(一条消息拉到多 task 配对的重复气泡): fetch_session_user_message_pairs 按
#   user_message_id 取 chat_tasks MAX(id) 行聚合, 陈旧 _user_msg_id 复用的一对多只剩最新终态一对。
# 2026-09-20 - 小欧 - D-1修复(注入消息DB幽灵): update_user_message_final 对"注入吸收的新 uid(非任务登记首条)"补
#   chat_tasks 配对行(同任务行同源复制 ai_message_id); fetch 侧 D-1兜底: 无配对(ct=NULL)时回退本会话最近任务行的
#   ai_message_id, 消除前端渲染双栖/linked 误判未回答。
# 2026-09-28 - 小欧 - 活跃任务注入缺陷修复: ①新增 bind_message_to_task(注入即绑执行期归属,
#   修 task_id 仅终态写入的空窗); ②删"复制源任务行补配对"整段与 session_id 参数(复制源任务行致列表重复/
#   React key 冲突/总数虚高, 且 fetch 精确 JOIN 已能配对, 禁 backward); ③fetch 删会话级 fb 兜底改单条精确
#   JOIN(注入凭 cum.task_id / 首条凭 cum.id 归任务, 消除跨任务错配); ④list_session_tasks 按 task_id 折叠 +
#   补 merged_inputs(cum.task_id 单一路由, 存量 NULL 副本已按 5.3 一次性 DELETE 清理)。
#   compliance: SRP/KISS-DIRECT/DRY/禁止backward/YAGNI(零 DDL 零新表)
# 2026-09-28 19:32:44 小欧 - 三堂会审修复: ①fetch 补 pair_task_id(行配对任务)作渲染合并同任务判据;
#   ②list_session_tasks merged_inputs 改会话级 1 次查询(原每任务 1 次子查询 N+1)。
#   compliance: 复用优先/KISS-DIRECT — 小欧-2026-09-28
# 2026-09-28 20:18:31 小欧 三堂会审 F16: fetch JOIN 改 COALESCE 优先 task_id 匹配(防跨任务错配) — 小欧-2026-09-28
# 2026-09-29 小欧 - L0 僵尸任务收尾(北京老陈驱动): 新增 reconcile_orphaned_tasks, 启动期把崩溃残留的 executing 残行改 failed+task_interrupted(病根: status 只由 agent_runner finally 改, 进程被 kill 时 finally 不执行致残行永久"执行中"); 零 DDL 零新状态值 — 小欧-2026-09-29
# 2026-09-29 20:42:06 小欧 - update_task 补 UPDATE 影响 0 行告警(19:49 PAR-05 故障中任务行压根没建成, 终态
#   UPDATE 静默影响0行且日志无痕, 只能事后比对 DB 定位); 三处同款 0 行判据(本函数/update_task_accumulation/
#   update_session_accumulation)统一收敛到 _warn_zero_row 单一出口(DRY/复用优先, 既有两条日志文案逐字不变) — 小欧-2026-09-29
# 2026-09-30 20:05:00 小欧 - 计数器退役: message_count 只增不减致列表虚高(实测清理前 1879/3195 会话"有计数无回答"),
#   读取侧改走新增的 count_session_messages() 真值(列表/详情共用); update_session_message_count 去计数改名
#   touch_session_updated_at(只留刷时间戳), allocate_and_insert_message 的 +1 同步删除; is_valid 语义不动 — 小欧-2026-09-30
# 2026-10-01 小欧 - 解 [1] E5~E9/E11: ①append_execution_step 补 task_id 缺失即抛 fail-loud(实测 SQLite 唯一索引中 NULL 互不相等, 缺 task_id 落库恒幂等失败) + ON CONFLICT DO NOTHING 幂等化配 idx_steps_unique; ②load_steps_by_task 工具名提取 json_extract 路径 $.tools[0].name 改 $.tools[0].tool(ActionStep 写入键为 tool 非 name, 原致工具汇总全归 null); ③thought 收口抽为公用 _strip_thought_content 供 load_execution_steps 复用, 两入口形状一致(原仅 load_steps_by_task 做); ④_warn_zero_row 增 level 参数, "字段永久丢失且不可事后补算"场景(如 ai_message_id)提级 error; ⑤删 save_execution_steps 与 ExecutionStepsUpdate(随 E8 空壳退役, save_execution_steps 自 2026-08-27 起已不写任何步骤) 及 derive_status_from_steps(唯一调用方随删)
#   compliance: DRY(单一真源)/fail-loud/YAGNI(零调用方即删)/复用优先 — 小欧-2026-10-01
# 2026-10-02 - 小欧 - 文档[4] 5.7 项2：get_previous_task_chain 口径改「最近一条任务任意状态」
#   (原仅认 completed, 致上一任务 failed 时链根错误回溯), 返回值由 dict 收窄为链根字符串(删死键 task_id)。
#   项10: list_session_tasks 的 SELECT 补 context_root_task_id —— 前端徽标按它归链的唯一分组键。
# 2026-10-03 - 小欧 - 文档[4] 5.10.1：新增 conn 级读函数 get_session_link(会话级 link 真源),
#   与 get_previous_task_chain 同族同出口, 供编排器经 db.atxn offload 调用。
#   不复用 session_service.get_session_info: 它含 2 条 COUNT(*) GROUP BY 且同步取连接, 放进
#   async 生成器等于每条消息在 loop 上同步跑 3 条 SQL, 违反编排器「loop 零同步 DB I/O」纪律。
# 2026-10-03 - 小欧 - 文档[4] 5.7.14 单元3: 新增 conn 级写函数 set_session_link_conn(与 get_session_link 对称),
#   返回 rowcount 供调用方直接判定(不用 conn.total_changes 差值反推), 供编排器经 db.atxn offload 落
#   随消息携带的 link 值; session_service.set_session_link 改为委托之, UPDATE SQL 单一来源(DRY)。
# 2026-10-03 - 小欧 - 文档[4] 5.12.3 副作用修复: set_session_link_conn 删 updated_at 写入(改开关非内容变更, 顺带刷新会把会话顶到列表首位; set_session_info/PATCH 路径是真内容修改, 其 updated_at 保留)。
"""
storage — 会话存储业务逻辑
从 conversation_storage.py 移入
小欧 2026-07-10
"""

import json
import threading
import types  # 11.1 冻结 token 零值常量, 防外部 mutate 污染全局 — 小欧 2026-08-20
from typing import Any, Dict, List, Optional, Tuple
from sqlite3 import Connection

from fastapi import HTTPException
from pydantic import BaseModel, Field

from app.logger import logger
from app.db import db
from app.db.models.chat_models import SessionModelOverride, ModelRef   # 归一: ModelRef=SessionModelOverride 别名 — 小欧 2026-08-22
from app.utils.json_utils import safe_json_dumps, parse_json
from app.utils.time_utils import get_local_iso_timestamp  # 小欧 2026-08-08 全程统一本地时区: 本地ISO无Z入库
from app.tools.tool_constants import NON_FILE_TRUST_TOOLS  # 小欧 2026-09-16 撤销侧规范化同位(与 trust_db:15 同步)
from app.tools.trust_db import norm_trust_path              # 小欧 2026-09-16 函数化: 撤销侧消费 trust_db 单一来源(原本层双份副本已删) — 小欧 2026-09-16
from app.tools.trust_db import trust_scope_path             # 小欧 2026-10-06 撤销侧与落库侧同走登记范围归一(同一口径, DRY) — 小欧 2026-10-06

# 存储每个session的消息ID
# key: session_id, value: user_message_id 或 assistant_message_id
_user_message_ids: Dict[str, int] = {}
_message_ids_lock = threading.Lock()


def next_message_id(conn: Connection) -> int:
    """从 id_sequence 取下一个消息 id(③b: user/assistant 单一序列, AUTOINCREMENT 跨进程原子)

    原 app 侧线性探测(上限10次/耗尽退化全局MAX+1)依赖 threading.Lock, 仅单进程有效;
    序列由 SQLite 写锁串行化, 撞号在构造上不可能。播种见 db_initializer 12.2-C4 — 小欧 2026-10-05
    """
    return conn.execute("INSERT INTO id_sequence DEFAULT VALUES").lastrowid


def track_user_message(session_id: str, message_id: int):
    """记录用户消息ID"""
    with _message_ids_lock:
        _user_message_ids[session_id] = message_id


def get_user_message_id(session_id: str) -> Optional[int]:
    """获取用户消息ID"""
    return _user_message_ids.get(session_id)


def get_last_user_message_id(conn: Connection, session_id: str) -> Optional[int]:
    """取本会话最后一条 user 消息 id(DB兜底) — 小健 2026-08-17 三堂会审-E2修复:
    track(_user_message_ids) 为内存 dict, 服务重启即丢; 该函数从 DB 恢复,
    供 orchestrator 在 track 缺失时为 linked 续聊提供 upper 上界(防链外/全部消息进上下文)"""
    row = conn.execute(
        "SELECT id FROM chat_user_message WHERE session_id=? ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    return row["id"] if row else None


def forget_session_message_ids(session_id: str) -> None:
    """删除会话时清理内存消息ID缓存(track 字典) — 小欧 2026-09-20 D-2修复:
    delete_session 原从不清内存, 会话删除后 dict 无限驻留(长驻内存泄漏)且陈旧 id 可能复活。
    ③b 起 allocator 无内存缓存, 故此处只清 track 字典 — 小欧 2026-10-05"""
    with _message_ids_lock:
        _user_message_ids.pop(session_id, None)


# 2026-10-01 小欧 解 [1] E8 连带 YAGNI 清理: ExecutionStepsUpdate(Pydantic 请求体) 与
#   derive_status_from_steps 整删 —— 二者唯一使用方是已下线的 POST /sessions/{id}/execution_steps
#   (其实现 save_execution_steps 自 2026-08-27 起不写任何步骤) 与同链的 sse_events 死函数。
#   全仓零调用方。终态不再由步骤派生(权威是 chat_tasks.status, 由 agent_runner finally 写),
#   故 derive_status_from_steps 的兜底语义亦无残留消费者。


# 【id 枢纽架构(北京老陈 2026-08-23 定调: chat_tasks 是任务中心表)】— 小欧 2026-08-23
#   user id 登记于 chat_tasks.user_message_id, 助手 id 登记于 chat_tasks.ai_message_id,
#   全部回放/统计以 chat_tasks 为枢纽——中心地位不动。两 id 共用 id_sequence 一个序列,
#   因前端同一消息列表渲染 user/assistant 两种气泡, id 不可重号(见 next_message_id)。
# 2026-10-05 小欧 ③b: AssistantMessageIdAllocator 整类退役(连同 _assistant_ids 缓存、
#   threading.Lock、10次线性探测、always_new 分支、模块级 _allocator 单例)。
#   发号改由 next_message_id 走 id_sequence, 撞号在构造上不可能, 故 ③c 补的耗尽告警随之消失。
#   _user_message_ids 保留: 仍服务 get_user_message_id / stream_orchestrator 兜底, 与分配机制无关。
def allocate_assistant_message_id(conn: Connection) -> int:
    """分配助手消息 id(单一序列, 恒为新号, 天然满足"每任务独立成行")"""
    return next_message_id(conn)


def ensure_session_exists(session_id: str, conn: Connection) -> None:
    """拷贝自 conversation.py 第104-112行"""
    cursor = conn.cursor()
    cursor.execute("SELECT id FROM chat_sessions WHERE id=? AND is_deleted=FALSE", (session_id,))
    if cursor.fetchone() is None:
        raise HTTPException(status_code=404, detail=f"会话不存在: {session_id}")


# 镜像写点 W2(insert_assistant_message 写 chat_messages) 已随 chat_messages 表退役整体移除 — 小欧 2026-08-27


# 镜像写点 W4(update_message_fields 写 chat_messages) 已随 chat_messages 表退役整体移除 — 小欧 2026-08-27


def touch_session_updated_at(conn: Connection, session_id: str) -> None:
    """刷会话 updated_at(列表按其排序)。原 update_session_message_count 的计数职责已退役 — 小欧 2026-09-30"""
    conn.execute(
        "UPDATE chat_sessions SET updated_at=? WHERE id=?",
        (get_local_iso_timestamp(), session_id),
    )


# ====================================================================
# 独立步骤表操作 — 小欧 2026-07-14
# ====================================================================

def allocate_and_insert_message(conn: Connection, session_id: str, task_id: Optional[str] = None,
                                user_message_id: Optional[int] = None) -> int:
    """预分配 assistant 消息ID + 插入空白行 — 小欧 2026-07-14
    ③b: 改调 allocate_assistant_message_id(单一序列), is_new 恒真故该返回位随之退役 — 小欧 2026-10-05
    2026-08-13 - 小欧 - 三堂会审修复#1: local_time 提前到 if is_new 之外赋值,
      消除 is_new=False(同session二次任务, agent_runner路径)时 UPDATE 引用未绑定变量 NameError
    2026-08-16 - 小欧 - S2②-2: chat_messages 补 task_id 列（任务级贯通，10.1.7②-2）
    2026-08-17 - 小健 - 三堂会审-AM2/STORAGE_1修复: 任务级分配新行(always_new=True),
      杜绝同 session 多任务复用同一 assistant 行(内容互相覆盖); [2026-09-30 小欧: 原"+1 虚高"半句随计数器退役删]
      is_new 恒 True 后每次+1 正确, 且各任务独立行 -> load_execution_steps 不再混任务步骤(STORAGE_2)
    2026-08-19 - 小欧 - v2.0: 加 user_message_id 参数，INSERT 同步写入 assistant→user 互指"""
    ensure_session_exists(session_id, conn)  # 修复: 写入前确保会话存在, 消除孤儿消息 — 小欧 2026-07-18
    ai_message_id = allocate_assistant_message_id(conn)
    # 镜像写点 W3(INSERT chat_messages 空白 assistant 行) 已随 chat_messages 表退役整体移除 — 小欧 2026-08-27
    touch_session_updated_at(conn, session_id)
    return ai_message_id


# 告警线(原截断阈值转告警线) — 10.6.2 定案(北京老陈 2026-08-23): 现役表不截断 — 小欧 2026-08-23
# (原"实验性的功能:TODO做正式的持久化设计后进行更新"占位随截断退役一并清理, 正式定案=文档落码)
_ALARM_STEP_ITEMS: int = 1000
_ALARM_STEP_STR_LEN: int = 100000

# 10.6.2 定案(北京老陈 2026-08-23): 截断整体退役 → 仅超限 error 告警扫描(安全网不砍数据)
# 2026-08-23 - 小欧 - 截断退役(文档落码): 删 _truncate_tool_result/_truncate_step_dict/
#   _truncate_tool_result_strings 三函数, 换 _warn_oversize_step_dict 告警扫描 —
#   step_json.tool_result 数组是历史回放唯一权威数据源(5.1 铁律), storage 二次截断=砍坏回放源;
#   工具层自截断(5.7)为唯一合法截断层, 文件A 全量落盘不截断
# 2026-10-05 - 小欧 - ③c: allocator 探测10次耗尽退化全局MAX(m)+1 的 for-else 分支补 ERROR 日志(此前无任何日志, 无法确证是否发生)
# 2026-10-05 - 小欧 - ③b: 新增 next_message_id(发号自 id_sequence); user/assistant 两侧 id 收口同一序列;
#   AssistantMessageIdAllocator 整类退役(连同 _assistant_ids 缓存/threading.Lock/10次探测/always_new/_allocator 单例)
def _warn_oversize_step_dict(step_dict, tag: str = "") -> None:
    """递归统计超限(列表>1000项/字符串>10万字符)仅 error 告警 — 安全网不砍数据 — 小欧 2026-08-23"""
    if isinstance(step_dict, dict):
        for k, v in step_dict.items():
            _warn_oversize_step_dict(v, f"{tag}{k}.")
    elif isinstance(step_dict, list):
        if len(step_dict) > _ALARM_STEP_ITEMS:
            logger.error(f"[storage]{tag}列表超大({len(step_dict)}项>告警线{_ALARM_STEP_ITEMS}), 请核查工具层自截断")
        for i, item in enumerate(step_dict):
            _warn_oversize_step_dict(item, f"{tag}[{i}].")
    elif isinstance(step_dict, str):
        if len(step_dict) > _ALARM_STEP_STR_LEN:
            logger.warning(f"[storage]{tag}字符串超长({len(step_dict)}字符>告警线{_ALARM_STEP_STR_LEN}), 请核查工具层自截断")


def append_execution_step(conn: Connection, ai_message_id: int, session_id: str,
                          step_index: int, step_dict: dict, task_id: Optional[str] = None,
                          usage: Optional[str] = None,
                          user_message_id: Optional[int] = None) -> None:
    """运行期逐步落库 — 小欧 2026-07-14
    小欧 2026-07-21: 落库前截断超大 tool_result(列表+字符串)防 SQLite 撑爆; 不碰 observation
    2026-08-16 - 小欧 - S2②-2: chat_task_steps 补 task_id 列（任务级贯通，10.1.7②-2）
    2026-08-19 - 小欧 - v2.0: 表改名 chat_task_steps + 参数 message_id→ai_message_id + 新增 usage/user_message_id 列
    2026-08-23 - 小欧 - 截断退役(文档落码): 截断退役→超限 error 告警(现役表不截断);
      完整 step_json 落库保回放源(5.1); 签名/返回值保持原样(-> None)——文件A 定位键已改
      step/tool_no/retry_no 三键组(实时落盘), 不再需要本函数返回主键
    2026-10-01 - 小欧 - 幂等化: ON CONFLICT DO NOTHING 配 idx_steps_unique,
      实时落库后重试/并发不再撞 IntegrityError(解 [1] A3)
    2026-10-01 - 小欧 - task_id 缺失即抛(解 [1] E5/E6): 实测 SQLite 唯一索引中 NULL 互不相等,
      task_id 为 NULL 时 idx_steps_unique 完全失效(重复行可无限插入, 已构造实证);
      表达式索引 COALESCE(task_id,'') 虽可归一, 但无法作 ON CONFLICT 的冲突目标(实测报
      "does not match any PRIMARY KEY or UNIQUE constraint"), 会连带废掉 A3 的幂等。
      故不改索引结构, 改为在写入口 fail-loud: task_id 缺失直接抛, 杜绝 NULL 行产生。"""
    if not task_id:
        raise ValueError(
            f"append_execution_step 缺 task_id(唯一索引对 NULL 失效, 须 fail-loud): "
            f"ai_message_id={ai_message_id}, step_index={step_index}"
        )
    _warn_oversize_step_dict(step_dict)
    conn.execute(
        "INSERT INTO chat_task_steps(ai_message_id, task_id, session_id, step_index, step_json, created_at, usage, user_message_id) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?) "
        "ON CONFLICT(ai_message_id, task_id, step_index) DO NOTHING",
        (ai_message_id, task_id, session_id, step_index, safe_json_dumps(step_dict),
         get_local_iso_timestamp(), usage, user_message_id),
    )


def _strip_thought_content(steps: list) -> list:
    """thought 步骤两字段契约收口：回显只取 thought/reasoning，剥掉 content,
    仅保留 type/step/timestamp/thought/reasoning — 小欧 2026-08-30
    2026-10-01 小欧: 提为公用函数(解 [1] E11)——原只有 load_steps_by_task 做此收口,
    load_execution_steps 不做, 同一份数据经两条读入口出参形状不同(前端拿到 content 会双渲
    thought 与 response, 见 final步骤历史回放重复显示)。"""
    return [
        s if s.get("type") != "thought" else {k: v for k, v in s.items() if k != "content"}
        for s in steps
    ]


def load_execution_steps(conn: Connection, ai_message_id: int, task_id: Optional[str] = None) -> Optional[list]:
    """从 chat_task_steps 表组装步骤列表（v2.0: 不再回退读 chat_messages.execution_steps）
    返回结构与原签名完全一致：命中返回 list[step_dict]（按 step_index 升序），未命中返回 []，
    调用方（_load_previous_messages / stream_reader 回放）行为不变 — 小欧 2026-08-19
    2026-10-01 小欧: thought 收口与 load_steps_by_task 统一(解 [1] E11, 见 _strip_thought_content)"""
    if task_id is not None:
        rows = conn.execute(
            "SELECT step_json FROM chat_task_steps WHERE ai_message_id=? AND task_id=? ORDER BY step_index ASC",
            (ai_message_id, task_id),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT step_json FROM chat_task_steps WHERE ai_message_id=? ORDER BY step_index ASC",
            (ai_message_id,),
        ).fetchall()
    if rows:
        return _strip_thought_content([parse_json(r["step_json"], label="step_json") for r in rows])
    return []




# ====================================================================
# S2 任务级读写落库（10.1.7②，北京老陈 2026-08-16 定案）— 小欧 2026-08-16
# ====================================================================

# ---- ②-1 chat_tasks 任务行落库 ----

def insert_task(
    conn: Connection, *,
    task_id: str, session_id: str, user_message_id: Optional[int], ai_message_id: Optional[int] = None,
    user_input: str, context_link_mode: str, context_root_task_id: str,
    task_model: ModelRef,
) -> None:
    """chat_tasks 任务行创建 INSERT（随任务启动，stream_orchestrator 建 task_id 后调用）— 小欧 2026-08-16
    2026-08-22 小欧 归一报告v1.25 6.3: provider/model/display_name 三分离入参 → task_model: ModelRef 单结构,
    落 sessionModel JSON 单列(display_name 列废弃不写, 设计要求2)"""
    now = get_local_iso_timestamp()
    conn.execute(
        """INSERT INTO chat_tasks
           (task_id, session_id, user_message_id, ai_message_id, user_input, context_link_mode,
            context_root_task_id, sessionModel, start_time, status, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
        (task_id, session_id, user_message_id, ai_message_id, user_input,
         context_link_mode, context_root_task_id,
         task_model.model_dump_json(),   # 必填参数直取(三堂会审: 删永不可达的 else None 死防御) — 小欧 2026-08-22
         now, "executing", now, now),
    )


def _warn_zero_row(op: str, key_label: str, key_value: str, reason: str,
                    level: str = "warning") -> None:
    """UPDATE 影响 0 行的统一告警出口 — 小欧 2026-09-29

    病根: UPDATE ... WHERE task_id=? 命中 0 行不报错, 终态/累计静默丢失, 事后无从追溯。
    为何做成单一出口(DRY/复用优先): 本模块 update_task/update_task_accumulation/update_session_accumulation
    三处同款判据(log 文案仅 op/主键标签/成因不同), 集中一处后改格式/加字段只动一个点。
    只告警不改控制流: 保持"缺行不阻断主链路"既有设计(禁止backward), 供日志侧对账定位。
    2026-10-01 小欧: 增 level 参数(解 [1] E9)——"字段永久丢失且不可事后补算"的场景提级 error,
      仅"可由后续流程覆盖"的场景留 warning。
    """
    _msg = f"[storage] {op} 影响0行({key_label}={key_value}): {reason}"
    (logger.error if level == "error" else logger.warning)(_msg)


def update_task(
    conn: Connection, *,
    task_id: str, response: Optional[str] = None, status: str = None,
    end_time: Optional[str] = None, duration: Optional[float] = None,
    accumulated_usage: Optional[Dict] = None, llm_call_count: Optional[int] = None,
    total_steps: Optional[int] = None, retry_count: Optional[int] = None,
    error_type: Optional[str] = None, error_message: Optional[str] = None,
    artifacts: Optional[list] = None,
) -> None:
    """chat_tasks 任务终态 UPDATE（随任务结束，agent_runner finally 落库）— 幂等、缺省字段不覆盖 — 小欧 2026-08-16"""
    _f, _v = [], []
    for _k, _val in (("response", response), ("status", status), ("end_time", end_time),
                     ("duration", duration), ("accumulated_usage", accumulated_usage),
                     ("llm_call_count", llm_call_count), ("total_steps", total_steps),
                     ("retry_count", retry_count), ("error_type", error_type),
                     ("error_message", error_message), ("artifacts", artifacts)):
        if _val is not None:
            _f.append(f"{_k} = ?")
            _v.append(safe_json_dumps(_val) if _k in ("accumulated_usage", "artifacts") else _val)
    if not _f:
        return
    _f.append("updated_at = ?"); _v.append(get_local_iso_timestamp())
    _v.append(task_id)
    _rc = conn.execute(f"UPDATE chat_tasks SET {', '.join(_f)} WHERE task_id = ?", _v).rowcount
    if _rc == 0:  # 小欧 2026-09-29: 补 0 行告警 —— 2026-09-29 19:49 PAR-05 故障中任务行压根没建成,
        #   终态 UPDATE 静默影响0行, 当时日志无任何痕迹, 只能靠事后比对 DB 才定位; 现即时留痕。
        # 2026-10-01 小欧 解 [1] E9: 升级为 ERROR 且补齐"本可救回"的判据 ——
        #   update_task 命中 0 行意味着终态/耗时/统计永久丢失(不可事后补算), 且后续
        #   reconcile_orphaned_tasks 只改 status 不会修这些字段, 故属不可恢复丢失。
        #   仍是 warning+不阻断控制流(禁止 backward, 缺行不阻断主链路), 但提级确保对账能发现。
        _warn_zero_row("update_task", "task", task_id,
                       "任务行缺失(未建立或已清理), 终态/耗时/统计永久丢失且无法事后补算",
                       level="error")


def reconcile_orphaned_tasks(conn: Connection, boot_iso: str) -> int:
    """启动期僵尸任务收尾：把【上次进程崩溃遗留】的 status='executing' 残行改终态 — 小欧 2026-09-29
    病根：status 只由 agent_runner finally 改（agent_runner.py:624），进程被 kill 时
    finally 不执行 → 残行永久 'executing'，前端徽标永远显示"执行中"。
    boot_iso 归属判据：只收尾 start_time < boot_iso 的行。本项目固定单进程启动，这是防御性
    护栏而非已观测场景；非严格归属（若将来多实例共享库，需加 owner_pid/boot_id 列）。
    前提：两值同为本地 naive ISO，同机同时区可比；时钟回拨则不成立。
    终态复用 failed + error_type=task_interrupted；不新增状态值
    （'interrupted' 已被前端 ToolCallLine 占用为"工具被拒"语义）。
    duration 不补算：被打断无真实耗时，补算即编造。幂等，返回受影响行数。"""
    now = get_local_iso_timestamp()
    cur = conn.execute(
        """UPDATE chat_tasks
           SET status = 'failed',
               error_type = 'task_interrupted',
               error_message = '服务重启导致任务中断，后端不支持续算，请重新发起',
               end_time = ?, updated_at = ?
         WHERE status = 'executing'
           AND (start_time IS NULL OR start_time < ?)""",
        (now, now, boot_iso),
    )
    return cur.rowcount


# ---- ②-3 token_usage 落库 ----

def token_usage_insert(
    conn: Connection, *,
    session_id: str, task_id: str, llm_call_count: int,
    task_model: ModelRef,
    prompt_tokens: int, completion_tokens: int, total_tokens: int,
) -> None:
    """token_usage 每轮 LLM 调用一行 INSERT — 小欧 2026-08-16
    2026-08-22 小欧 归一报告v1.25 6.3: model/provider 两分离入参 → task_model: ModelRef 单结构落 JSON 单列"""
    conn.execute(
        """INSERT INTO token_usage
           (session_id, task_id, llm_call_count, task_model,
            prompt_tokens, completion_tokens, total_tokens, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (session_id, task_id, llm_call_count,
         task_model.model_dump_json(),
         prompt_tokens or 0, completion_tokens or 0, total_tokens or 0,
         get_local_iso_timestamp()),
    )


# ---- 11.1 token 四层同构：任务级/会话级实时累计 + 链级计算派生 — 小欧 2026-08-20 ----

_EMPTY_TOKEN = types.MappingProxyType({"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0})  # 11.1 冻结常量: 防外部 mutate 污染全局 — 小欧 2026-08-20


def _normalize_acc(raw, label):
    """解析 token 累计 JSON, 空对象/缺键/非法统一归一为含3键零值 — 小欧 2026-08-20
    注: parse_json('{}') 返回 {} 为 truthy, 不能用 `or` 兜底(会漏 KeyError), 故显式判键
    11.1 增强(2026-08-20 小欧): 已存 dict 若只含部分键(如 {'prompt_tokens':5}), 缺键统一补零并强转 int,
        保留已存键, 杜绝下游 update 的 _old[k] KeyError 与 react_cycle 基线 [k] KeyError(历史累计被静默清零)"""
    _p = parse_json(raw, label=label) if raw else None
    if not isinstance(_p, dict) or "prompt_tokens" not in _p:
        return dict(_EMPTY_TOKEN)
    return {
        "prompt_tokens": int(_p.get("prompt_tokens") or 0),
        "completion_tokens": int(_p.get("completion_tokens") or 0),
        "total_tokens": int(_p.get("total_tokens") or 0),
    }


def query_task_accumulation(conn: Connection, *, task_id: str) -> dict:
    """读取任务级 token 当前累计值（JSON）— 11.1"""
    row = conn.execute(
        "SELECT task_accumulated_tokens FROM chat_tasks WHERE task_id = ?",
        (task_id,)).fetchone()
    if not row:  # 11.1 增强: 任务行缺失时返回零值, 避免 None 下标 TypeError 崩溃 — 小欧 2026-08-20
        return dict(_EMPTY_TOKEN)
    return _normalize_acc(row["task_accumulated_tokens"], label="task_acc")


def query_session_accumulation(conn: Connection, *, session_id: str) -> dict:
    """读取会话级 token 当前累计值（JSON）— 11.1"""
    row = conn.execute(
        "SELECT session_accumulated_tokens FROM chat_sessions WHERE id = ?",
        (session_id,)).fetchone()
    if not row:  # 11.1 增强: 会话行缺失时返回零值, 避免 None 下标 TypeError 崩溃 — 小欧 2026-08-20
        return dict(_EMPTY_TOKEN)
    return _normalize_acc(row["session_accumulated_tokens"], label="session_acc")


def update_task_accumulation(conn: Connection, *, task_id: str, llm_call_count_token: dict) -> None:
    """任务级 token 实时累计 — 11.1"""
    _old = query_task_accumulation(conn, task_id=task_id)
    _new = {k: _old[k] + int(llm_call_count_token.get(k) or 0)
            for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    _rc = conn.execute("UPDATE chat_tasks SET task_accumulated_tokens = ? WHERE task_id = ?",
                       (safe_json_dumps(_new), task_id)).rowcount
    if _rc == 0:  # 11.1 增强: 任务行缺失时 UPDATE 影响0行致累计静默丢失, 显式告警 — 小欧 2026-08-20
        _warn_zero_row("update_task_accumulation", "task", task_id, "任务行可能缺失或列未落库")


def update_session_accumulation(conn: Connection, *, session_id: str, llm_call_count_token: dict) -> None:
    """会话级 token 实时累计 — 11.1"""
    _old = query_session_accumulation(conn, session_id=session_id)
    _new = {k: _old[k] + int(llm_call_count_token.get(k) or 0)
            for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    _rc = conn.execute("UPDATE chat_sessions SET session_accumulated_tokens = ? WHERE id = ?",
                       (safe_json_dumps(_new), session_id)).rowcount
    if _rc == 0:  # 11.1 增强: 会话行缺失时 UPDATE 影响0行致累计静默丢失, 显式告警 — 小欧 2026-08-20
        _warn_zero_row("update_session_accumulation", "session", session_id, "会话行可能缺失或列未落库")


def query_chain_accumulation(conn: Connection, *, context_root_task_id: str, current_task_id: str) -> dict:
    """上下文链 token 累计（计算派生，不落库）— 满足链根聚合语义
    对同 context_root_task_id 的所有「已完成」任务聚合 token_usage（排除当前运行中任务），
    independent 任务 context_root_task_id=自身 → 仅自身（清零重算）；linked 任务链根共享 → 全链 SUM。
    """
    _row = conn.execute(
        "SELECT COALESCE(SUM(prompt_tokens),0) AS p, COALESCE(SUM(completion_tokens),0) AS c, COALESCE(SUM(total_tokens),0) AS t "
        "FROM token_usage WHERE task_id IN (SELECT task_id FROM chat_tasks WHERE context_root_task_id = ?) "
        "AND task_id <> ?",
        (context_root_task_id, current_task_id)).fetchone()
    return {"prompt_tokens": int(_row["p"] or 0), "completion_tokens": int(_row["c"] or 0), "total_tokens": int(_row["t"] or 0)}


# ---- ②-4 chat_sessions sessionModel 生效 ---- 北京老陈 2026-08-22 L2 会话级模型覆盖(结构化 provider+model)

def parse_session_model(raw) -> Optional[SessionModelOverride]:
    """chat_sessions.sessionModel 列(JSON 文本)反序列化为结构化模型; 空/非法→None — 北京老陈 2026-08-22
    全系统唯一解析点(消除 message_service/session_service 重复实现, DRY), 返回 SessionModelOverride"""
    if not raw:
        return None
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
        if not data:
            return None
        return SessionModelOverride(**data)
    except Exception:
        logger.warning(f"[session] sessionModel 解析失败, 视为未设置: {raw}")
        return None


def get_session_model(conn: Connection, session_id: str) -> Optional[SessionModelOverride]:
    """读 chat_sessions.sessionModel（L2 会话级模型覆盖, 结构化）— 北京老陈 2026-08-22 改结构化 JSON:
    返回 SessionModelOverride(provider+model) 或 None（未设置）"""
    row = conn.execute(
        "SELECT sessionModel FROM chat_sessions WHERE id=? AND is_deleted=FALSE",
        (session_id,),
    ).fetchone()
    raw = row["sessionModel"] if row and row["sessionModel"] else None
    if not raw:
        return None
    return parse_session_model(raw)


# ---- ②-5 chat_session_trust 落库 ----

def list_session_trust(conn: Connection, session_id: str) -> list:
    """D1(10.5 问题4): 会话已信任对象清单（tool+path, path 可为 NULL=工具级通配）— 小欧 2026-08-20; v1.5 增 path 返回"""
    rows = conn.execute(
        "SELECT id, tool_name, path, created_at FROM chat_session_trust WHERE session_id=? ORDER BY id DESC",
        (session_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def delete_session_trust(conn: Connection, session_id: str, tool_name: str, path: Optional[str] = None) -> bool:
    """D3(10.5 问题4): 撤销会话对指定信任对象的信任——(tool, path) 精确撤销, path=None 仅删工具级通配行 — 小欧 2026-08-20; v1.5 增 path 匹配
    2026-10-05 小欧 提示(B语义下): check_session_trust 已改为按 path 跨工具放行 —— 只删某一工具的那行,
      同路径下其它工具的登记仍使该目录豁免。
    2026-10-06 小欧 撤销侧对齐落库侧与放行侧(北京老陈"信任反复弹窗"修复配套): 落库已改为登记【所在目录】,
      故撤销一律经 trust_scope_path 归一(传文件或传目录都能命中同一行), 且**跨工具一并删** ——
      放行是跨工具的, 撤销若只删本工具行则该目录实际仍被信任, 撤销形同虚设(安全缺口)。
      path=None 仍只删本工具的通配行(无路径工具之间不互相牵连)。"""
    if path is None:
        cur = conn.execute(
            "DELETE FROM chat_session_trust WHERE session_id=? AND tool_name=? AND path IS NULL",
            (session_id, tool_name),
        )
    else:
        # 跨工具删除: WHERE 不带 tool_name, 与 check_session_trust 的跨工具放行口径对称
        cur = conn.execute(
            "DELETE FROM chat_session_trust WHERE session_id=? AND path=?",
            (session_id, trust_scope_path(path, tool_name)),
        )
    return cur.rowcount > 0


# ---- ②-6 token_usage 四维度查询 API ----

def query_token_usage(
    conn: Connection, *, session_id: Optional[str] = None,
    task_id: Optional[str] = None, model_ref: Optional[ModelRef] = None,
) -> Dict:
    """token 四维度聚合查询（按 session/task/model 过滤 + 三个 token 求和）— 口径同 9.7 — 小欧 2026-08-16
    2026-08-22 小欧 归一报告v1.25 6.3: model 裸列过滤 → task_model JSON 列 json_extract 双键过滤"""
    _w, _v = [], []
    for _k in ("session_id", "task_id"):
        _x = {"session_id": session_id, "task_id": task_id}[_k]
        if _x:
            _w.append(f"{_k} = ?"); _v.append(_x)
    if model_ref:
        _w.append("json_extract(task_model,'$.provider')=? AND json_extract(task_model,'$.model')=?")
        _v.extend([model_ref.provider, model_ref.model])
    _where = ("WHERE " + " AND ".join(_w)) if _w else ""
    row = conn.execute(
        f"SELECT COUNT(*) AS calls, "
        f"COALESCE(SUM(prompt_tokens),0) AS prompt_tokens, "
        f"COALESCE(SUM(completion_tokens),0) AS completion_tokens, "
        f"COALESCE(SUM(total_tokens),0) AS total_tokens "
        f"FROM token_usage {_where}", _v,
    ).fetchone()
    return dict(row)


def get_previous_task_chain(conn: Connection, session_id: str) -> Optional[str]:
    """取本会话最近一条任务的链根 — 文档[4] 5.7 项2（2026-10-02 北京老陈定案）
    口径：最近一条任务任意状态均参与（原仅认 completed，致上一任务 failed/interrupted 时链根错误回溯）。
    并发：同会话存在 running/paused 活跃任务时新消息走注入不新建任务（task_registry.has_active_task_in_session），
    故此处取到的任务必为非活跃态，不存在同组并发。
    返回 context_root_task_id（为空回退其自身 task_id）；无任务返回 None（调用方使自身为链根）"""
    row = conn.execute(
        "SELECT task_id, context_root_task_id FROM chat_tasks "
        "WHERE session_id=? ORDER BY id DESC LIMIT 1",
        (session_id,),
    ).fetchone()
    if row:
        return row["context_root_task_id"] or row["task_id"]
    return None


def get_session_link(conn: Connection, session_id: str) -> bool:
    """取会话级 link 粘性开关（chat_sessions.link_enabled 唯一真源）— 文档[4] 5.7 项8 / 5.10.1。
    conn 级读，供编排器经 db.atxn offload 调用（与 get_previous_task_chain 同族同出口, 判定只在 storage 层）。
    COALESCE 兜 ALTER ADD COLUMN 前存量 NULL 行（=关闭）；会话不存在亦返回 False（fail-closed, 不抛
    HTTPException——避免 HTTP 层异常类型漏进 service 层编排代码）— 小欧 2026-10-03"""
    row = conn.execute(
        "SELECT COALESCE(link_enabled, 0) FROM chat_sessions "
        "WHERE id = ? AND is_deleted = FALSE",
        (session_id,),
    ).fetchone()
    return bool(row[0]) if row else False


def set_session_link_conn(conn: Connection, session_id: str, enabled: bool) -> int:
    """写会话 link 开关，返回命中行数(0=会话不存在) — 文档[4] 5.7.14。
    conn 级写，与同族 get_session_link 对称，供编排器经 db.atxn offload 调用。
    返回 rowcount 供调用方直接判定，不需total_changes 差值反推 — 小欧 2026-10-03

    2026-10-03 小欧 - 删掉 updated_at 写入(文档[4] 5.12.3 第1条副作用修复):
      updated_at 语义是"内容变更时间", 而 list_sessions 按它 ORDER BY DESC 排序、顶栏"更新时间"
      悬浮也读它。改开关不是内容变更, 顺带刷新会把会话顶到列表首位, 属不可预期行为。
      与 set_session_info 的 PATCH 路径不同(那是真内容修改, 刷 updated_at 正确)。"""
    cursor = conn.execute(
        "UPDATE chat_sessions SET link_enabled = ? "
        "WHERE id = ? AND is_deleted = FALSE",
        (1 if enabled else 0, session_id),
    )
    return cursor.rowcount


# ====================================================================
# v2.0 chat_user_message 读写（2026-08-19）
# ====================================================================

def insert_user_message(
    conn: Connection, *,
    session_id: str, content: str,
    client_os: str = None, browser: str = None,
    device: str = None, network: str = None,
) -> int:
    """新建 chat_user_message 行（用户发消息时落库），返回本表 id。
    ③b: id 改由 id_sequence 显式指定(与 assistant 侧同一序列, 前端 user/assistant 气泡 id 不可重号);
    原依赖本表 AUTOINCREMENT 独立计数, 与 assistant 侧只能靠探测防撞 — 小欧 2026-10-05
    锚迁移(北京老陈 2026-08-23 裁定"chat_messages 写保留当空气"): id 分配锚由
    chat_messages.lastrowid 显式指定 → 本表 AUTOINCREMENT 原生自增, user_message_id 入参退役;
    原 INSERT OR REPLACE 随显式 id 一并退役——自增 id 无撞键场景, 退化为普通 INSERT — 小欧 2026-08-23"""
    now = get_local_iso_timestamp()
    cursor = conn.execute(
        """INSERT INTO chat_user_message
           (id, session_id, content, client_os, browser, device, network, created_at)
           VALUES (?,?,?,?,?,?,?,?)""",
        (next_message_id(conn), session_id, content, client_os, browser, device, network, now),
    )
    return cursor.lastrowid


def bind_message_to_task(conn: Connection, user_message_id: int, task_id: str) -> bool:
    """把注入消息绑定到目标任务(执行期归属, 零 DDL, 复用已有 task_id 列) — 小欧 2026-09-28 设计文档[76] 6.5①
    原本 task_id 仅由 update_user_message_final 在终态回填, 任务执行期注入消息的 task_id 恒 NULL →
    左侧列表/历史 fetch 执行期均查不到。注入成功即刻回填补该空窗; 终态回填照旧(幂等重写)。
    返回 True=已绑定; False=影响0行(uid 不存在 或 task_id 已有值/任务已结束, 调用方记 warning)。"""
    cur = conn.execute(
        "UPDATE chat_user_message SET task_id=? WHERE id=? AND task_id IS NULL",
        (task_id, user_message_id))
    return cur.rowcount > 0


def update_user_message_final(
    conn: Connection, *,
    user_message_id: int, task_id: str,
    response: str, reasoning: str = None,
    outcome: str = None, task_model: Optional[ModelRef] = None,
    accumulated_usage: str = None,
) -> None:
    """任务完成后回填 final 字段到 chat_user_message
    2026-08-22 小欧 归一报告v1.25 6.3: model/provider 两分离入参 → task_model: ModelRef 落 chat_model JSON 单列
    2026-09-20 小欧 D-1修复: 注入消息补配对 INSERT(见编辑历史)
    2026-09-28 小欧 删 D-1(设计文档[76] 6.5②): 复制源任务行会致列表重复条目/React key 冲突/总数虚高,
      且其 INSERT 多余(fetch 精确 JOIN 已能配对) → 删除整段与 session_id 参数(唯一用途即 D-1, 禁 backward);
      注入消息归属改由 bind_message_to_task 执行期绑定 + fetch 按 cum.task_id 精确关联。"""
    conn.execute(
        """UPDATE chat_user_message
           SET task_id=?, response=?, reasoning=?, outcome=?,
               chat_model=?, accumulated_usage=?
           WHERE id=?""",
        (task_id, response, reasoning, outcome,
         task_model.model_dump_json() if task_model else None,
         accumulated_usage, user_message_id),
    )


def load_user_message_by_task(conn: Connection, task_id: str) -> Optional[dict]:
    """按 task_id 读 chat_user_message（C1 详情用）
    2026-08-22 小欧 归一报告v1.25 6.3: chat_model JSON 派生 model/provider 键(键名不变)"""
    row = conn.execute(
        "SELECT * FROM chat_user_message WHERE task_id=?", (task_id,),
    ).fetchone()
    if not row:
        return None
    d = dict(row)
    _cm = parse_session_model(d.pop("chat_model", None))
    d["model"] = _cm.model if _cm else None        # 键名保留供消费方渐进迁移 — 小欧 2026-08-22
    d["provider"] = _cm.provider if _cm else None
    return d


def load_user_messages_by_session(conn: Connection, session_id: str) -> list:
    """按 session_id 读 chat_user_message 列表（替代 chat_messages 读取）— 小欧 2026-08-21
    2026-08-22 小欧 归一报告v1.25 6.3: model/provider 键改由 chat_model JSON 列派生(旧列不再读取),
    复用 parse_session_model 唯一解析点(DRY)"""
    rows = conn.execute(
        "SELECT * FROM chat_user_message WHERE session_id=? ORDER BY created_at ASC",
        (session_id,),
    ).fetchall()
    out = []
    for r in rows:
        d = dict(r)
        _cm = parse_session_model(d.pop("chat_model", None))
        d["model"] = _cm.model if _cm else None       # 键名保留, 值源自新 JSON 列 — 小欧 2026-08-22
        d["provider"] = _cm.provider if _cm else None
        out.append(d)
    return out


def count_session_messages(conn: Connection, session_ids: List[str]) -> Dict[str, int]:
    """消息数唯一口径: COUNT(chat_user_message)+COUNT(chat_tasks), 列表/详情共用 — 小欧 2026-09-30"""
    if not session_ids:
        return {}
    counts: Dict[str, int] = {sid: 0 for sid in session_ids}
    placeholders = ",".join("?" * len(session_ids))
    for table in ("chat_user_message", "chat_tasks"):   # 表名为硬编码常量
        for row in conn.execute(
                f"SELECT session_id, COUNT(*) FROM {table} "
                f"WHERE session_id IN ({placeholders}) GROUP BY session_id", session_ids
        ).fetchall():
            counts[row["session_id"]] += row["COUNT(*)"]
    return counts


def fetch_session_user_message_pairs(conn: Connection, session_id: str,
                           lower_id: Optional[int] = None,
                           upper_id: Optional[int] = None) -> list:
    """北京老陈 2026-08-22 铁律: chat_messages 只写严禁读; 本函数从 chat_user_message
    LEFT JOIN chat_tasks 重建"用户+AI"有序消息对(彻底去 chat_messages 读)。
    供 get_session_messages / _load_previous_messages / execution_stream 复用(10规范 DRY/复用优先)。
    返回 list[dict]: 每行一条 user 消息及其配对 assistant(ai_message_id 为 None 表示暂无 AI 回答),
    字段: user_id, user_content, ai_reasoning, model, provider, task_id, created_at, ai_message_id,
    pair_task_id(行配对到的 chat_tasks.task_id — 渲染合并同任务判据; 注入行凭 cum.task_id、登记首条凭
      cum.id=ct.user_message_id 归任务, 二者归一故同任务行 pair_task_id 一致; 配合 ORDER BY cum.id ASC,
      同 pair_task_id 分组的首行即登记首条, 供 message_service 合并注入行时排除自身 — 2026-09-28 小欧)
    2026-08-22 小欧 归一报告v1.25 6.3: cum.model/cum.provider 两列 → cum.chat_model JSON 单列,
    返回 dict 的 model/provider 键由 chat_model 派生(键名不变, 旧列不再读取)
    2026-09-20 小欧 E-4修复: 一条 user 消息仅取最新 task 的配对(chat_tasks 按 user_message_id 取 MAX(id) 行),
    杜绝陈旧 _user_msg_id 复用导致的一对多(前端重复气泡 + 旧终态被覆写)
    2026-09-20 小欧 D-1兜底: 会话级模糊兜底(fb)
    2026-09-28 小欧 精确归属(设计文档[76] 6.5③): 删会话级 fb 兜底, 改单条精确 JOIN —
      注入消息凭 cum.task_id(bind_message_to_task 执行期绑)归任务, 起始消息凭 cum.id=ct.user_message_id 归任务,
      二者归一; MAX(id) 兼容同 task 多行(取最新)。删 COALESCE 后无跨任务错配(原兜底可能把消息配到会话最后任务)。
      注: 存量 task_id=NULL 注入副本已按 5.3 一次性 DELETE 清理, 查询走单一路由。"""
    sql = """SELECT cum.id AS user_id, cum.content AS user_content, cum.response AS ai_content,
                    cum.reasoning AS ai_reasoning,
                    cum.chat_model AS chat_model, cum.task_id AS task_id,
                    cum.created_at AS created_at,
                    ct.ai_message_id AS ai_message_id, ct.task_id AS pair_task_id
             FROM chat_user_message cum
             LEFT JOIN chat_tasks ct ON ct.id = COALESCE(
                 (SELECT MAX(id) FROM chat_tasks WHERE task_id = cum.task_id),
                 (SELECT MAX(id) FROM chat_tasks WHERE user_message_id = cum.id)
             )
             WHERE cum.session_id = ?"""
    params: list = [session_id]
    if lower_id is not None:
        sql += " AND cum.id >= ?"
        params.append(lower_id)
    if upper_id is not None:
        sql += " AND cum.id < ?"
        params.append(upper_id)
    sql += " ORDER BY cum.id ASC"
    rows = conn.execute(sql, params).fetchall()
    out = []
    for r in rows:
        _cm = parse_session_model(r["chat_model"])
        out.append({
            "user_id": r["user_id"],
            "user_content": r["user_content"],
            "ai_content": r["ai_content"],
            "ai_reasoning": r["ai_reasoning"],
            "model": _cm.model if _cm else None,      # 由 chat_model 派生 — 小欧 2026-08-22
            "provider": _cm.provider if _cm else None,
            "task_id": r["task_id"],
            "created_at": r["created_at"],
            "ai_message_id": r["ai_message_id"],
            "pair_task_id": r["pair_task_id"],   # 2026-09-28 小欧: 渲染合并同任务判据(三堂会审)
        })
    return out


# ====================================================================
# v2.0 C1/C2 任务级回放与统计存储（2026-08-19）
# ====================================================================

def get_task_detail(conn: Connection, task_id: str) -> Optional[dict]:
    """C1: 按 task_id 读 chat_tasks 单行详情
    2026-08-22 小欧 归一报告v1.25 6.3: 与 list_session_tasks 同模式——sessionModel JSON 派生
    model/provider 键(键名不变), 复用 parse_session_model 唯一解析点(DRY)"""
    row = conn.execute(
        "SELECT * FROM chat_tasks WHERE task_id=?", (task_id,),
    ).fetchone()
    if not row:
        return None
    _r = dict(row)
    _r["artifacts"] = parse_json(_r.get("artifacts")) if _r.get("artifacts") else []
    _sm = parse_session_model(_r.pop("sessionModel", None))
    _r["model"] = _sm.model if _sm else None       # 键名保留供消费方渐进迁移 — 小欧 2026-08-22
    _r["provider"] = _sm.provider if _sm else None
    return _r


def list_session_tasks(conn: Connection, session_id: str) -> Tuple[list, int, Optional[str]]:
    """B1/问题6(10.5): 会话任务列表 + 总数 + 最新任务id（任务数=用户消息数, 一条用户消息=一个任务;
    失败/取消亦计入, 与设计文档 3.5.3 口径一致）。chat_tasks 行数即新统计口径 — 小欧 2026-08-20
    2026-08-22 小欧 归一报告v1.25 6.3: model/provider 两列 → sessionModel JSON 列派生(键名不变)
    2026-08-30 小欧 设计文档v1.103: 排序 DESC→ASC(左列时间线, 新任务在底部) +
    新增 latest_task_id(显式最新锚点, 顶栏/默认选中/结束沿token锚点统一消费, 解耦 8.C-④ DESC 一手双用)
    2026-09-28 小欧 注入可见性(设计文档[76] 6.5④): ①按 task_id 折叠同 task 多行(防 D-1 假行致重复条目/
    React key 冲突, 保留 ASC 首行); ②每行补 merged_inputs(本任务吸收的追加注入消息, 供前端折叠块显示)
    2026-09-28 19:32:44 小欧 三堂会审: merged_inputs 改会话级 1 次查询+Python 分组(原 N+1 且
    task_id 无索引); 首条排除改用行自带 user_message_id(免子查询)。"""
    total = conn.execute(
        "SELECT COUNT(*) FROM chat_tasks WHERE session_id=?",
        (session_id,),
    ).fetchone()[0]
    rows = conn.execute(
        """SELECT task_id, user_input, response, status, duration, sessionModel,
                  total_steps, llm_call_count, context_link_mode, context_root_task_id, user_message_id,
                  created_at, updated_at
           FROM chat_tasks WHERE session_id=? ORDER BY id ASC""",
        (session_id,),
    ).fetchall()
    # 会话内注入行一次取回按任务分组 — 2026-09-28 小欧 三堂会审(原 N+1)
    _inj_by_task: Dict[str, list] = {}
    for _m in conn.execute(
            """SELECT id, task_id, content FROM chat_user_message
               WHERE session_id=? AND task_id IS NOT NULL ORDER BY id ASC""",
            (session_id,)).fetchall():
        _inj_by_task.setdefault(_m["task_id"], []).append(_m)
    out = []
    _seen_task_ids = set()
    for r in rows:
        d = dict(r)
        # 2026-09-28 小欧: 同 task 多行折叠(防御 D-1 假行), 保留首行
        if d["task_id"] in _seen_task_ids:
            continue
        _seen_task_ids.add(d["task_id"])
        _sm = parse_session_model(d.pop("sessionModel", None))
        d["model"] = _sm.model if _sm else None       # 键名保留供消费方渐进迁移 — 小欧 2026-08-22
        d["provider"] = _sm.provider if _sm else None
        _reg_uid = d.pop("user_message_id", None)     # 首条 uid 仅用于排除, 不进返回契约 — 小欧 2026-09-28
        # 追加注入消息(cum.task_id 单一路由: bind_message_to_task 执行期绑定; 排除任务登记首条 uid)
        d["merged_inputs"] = [
            _m["content"] for _m in _inj_by_task.get(d["task_id"], [])
            if _m["id"] != _reg_uid
        ]
        out.append(d)
    latest_task_id = out[-1]["task_id"] if out else None   # ASC 后最末行为最新任务, 显式锚点 — 小欧 2026-08-30
    return out, total, latest_task_id


def get_task_tool_stats(conn: Connection, task_id: str) -> list:
    """C1: 从 chat_task_steps 统计该任务的工具调用次数
    2026-10-01 小欧 解 [1] E7: 原用 json_extract(step_json,'$.tools[0].tool') 只取首个工具,
      一步内并行多工具调用时其余工具既不进分组也不进计数, 统计偏低。
      改用 json_each 逐元素展开, 一步 N 个工具计 N 次(与 getTaskToolStats 语义"工具调用次数"一致)。
      json_each 遇非数组/非对象返回一行 NULL, 故 WHERE 内再判 json_type='array'。"""
    rows = conn.execute(
        """SELECT
             json_extract(value, '$.tool') as tool_name,
             COUNT(*) as call_count
           FROM chat_task_steps, json_each(chat_task_steps.step_json, '$.tools')
           WHERE task_id=? AND json_extract(step_json, '$.type')='action'
             AND json_type(step_json, '$.tools')='array'
             AND json_extract(value, '$.tool') IS NOT NULL
           GROUP BY tool_name""",
        (task_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def load_steps_by_task(conn: Connection, task_id: str) -> list:
    """C2: 按 task_id 读全部步骤（升序）"""
    rows = conn.execute(
        "SELECT step_json FROM chat_task_steps WHERE task_id=? ORDER BY step_index ASC",
        (task_id,),
    ).fetchall()
    # thought 收口复用公用函数, 与 load_execution_steps 同源(解 [1] E11)
    return _strip_thought_content([parse_json(r["step_json"], label="step_json") for r in rows])