
# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-13 小欧 add_tool_result异常日志带类型与repr
# 2026-07-16 小欧 op_id双表贯通修复
# 2026-07-17 小欧 handle_action执行工具后重置_consecutive_reasoning_only(空转检测: 本步LLM发起工具调用=非reasoning-only空转, 归零)
# 2026-07-17 小欧 计数器修正: handle_action-tool_name空early-return处补归零(空转检测非reasoning-only出口完备, 不变量严格成立)
# 2026-07-18 小欧 #4 fix: _file_tool_names从模块函数名改为注册名(delete/copy/move/edittext/writetext/compress),op_id双表贯通恢复
# 2026-07-18 小欧 #11 fix: wait_for_confirmation_result超时返回expired=True;超时/拒绝分流
# 2026-07-18 小欧 #12 fix: check_safety_and_confirm拒绝不再return终止整批,收集_denied后继续,最终只执行通过的call
# 2026-07-18 小欧 FinalStep多态自包含终态重构:
#   【病根】原FinalStep无outcome字段, 终态语义隐含在type中,
#          action_handler中return_direct提前返回的FinalStep缺少显式终态声明,
#          与answer_handler/agent_runner的终态产出不一致。
#   【改法】在return_direct分支的FinalStep中显式添加outcome="completed",
#          使所有终态产出点均有显式outcome声明, 与FinalStep多态设计契约一致。
#   [原来] for循环内对每个call查file_operations「最新」op_id写task_operations
#   [问题] ①非文件工具(searchtool等)误关联文件op_id ②同轮多文件工具抢同一op_id撞UNIQUE(constraint failed)
#   [根因] action_handler在"所有工具返回后统一处理"循环中, 查"最新"在多工具同轮时顺序错乱/抢占
#   [改法] 循环外预取file_operations「未写入task_operations」的op_id候选队列, 循环内仅文件类工具(白名单6个)按call顺序pop(0)取用, 非文件工具op_id=None自生成
#   [原理] ①文件工具call顺序==file_operations写入顺序(同轮顺序执行), 升序候选队列+顺序pop精确一一对应
#          ②用"FO未写入TO的op_id"做差集, 天然排除已消耗项, 杜绝UNIQUE冲突
#          ③白名单隔离非文件工具使其不参与贯通(op_id=None自生成), 消除误关联
#          ④纯内部取id(不读result/LLM字段), 符合"operation_id是agent内部字段严禁进LLM返回结构"铁律
# 2026-07-18 小欧 #4 fix: _file_tool_names 白名单值从模块函数名(delete_file等)改为注册名(delete等); 因 call["tool_name"] 是注册名, 原白名单恒 False 致 op_id 双表贯通完全失效
# 2026-07-18 小欧 #11+#12 fix: check_safety_and_confirm 重构 — 超时与拒绝分流(expired标记); 拒绝不return终止整批, 收
#   集_denied后continue, 最终只执行通过的call(通过_out参数回传过滤后列表); 调用方对应改_exec_calls
# 2026-07-19 小欧 build_observation/_add_denial_feedback新增reasoning参数传递
# 2026-07-21 小欧 - #4 自动纠正: 新增 _auto_correct_file_tool + _EXT_TO_READ/WRITE_TOOL 映射, execute_tools 入口扩展名预检自动切换 tool_name, 结果中 llm_data.summary 追加"(工具自动纠正自:{原始名})"
# 2026-07-23 小欧 - log_and_print统一: 删局部_log_and_print函数, 改为import from app.logger.log_and_print; execute_tools中3处logger.info()+print()替换为log_and_print()
# 2026-07-23 小欧 - 局部常量迁移: 删 _MAX_LOG_RESULT_CHARS=5000,
#            改为 from app.constants import ACTION_LOG_RESULT_MAX_CHARS
# 2026-07-25 - 小欧 - 修复readmedia被自动纠错为readtext: _auto_correct_file_tool fallback硬编码"readtext"→tool_name, 无专用映射时不篡改原工具
# 2026-07-25 小欧 - 三分类映射表重构: _EXT_TO_READ/WRITE_TOOL换用file_type_checker常量(TEXT_EXTENSIONS/MEDIA_EXTENSIONS)构建, 删fallback; _auto_correct_file_tool简化: None短路+!=判断; 文本→readtext/文档→专用工具/多媒体→readmedia 三分类全覆盖
# 2026-07-25 小欧 - task006-issue1: operation_id候选查询加task_id类型守卫(isinstance str/int); 非str/int提前短路并降WARNING为DEBUG, 消除测试环境MagicMock刷52次WARNING噪声
# 2026-07-25 小欧 - 回退上述类型守卫: 根因在测试fixture缺task_id而非生产代码(生产代码generate_task_id()永远返回str), 改为测试fixture源头修复; 生产代码恢复原始try-except
# 2026-07-25 小欧 - 欧阳报告缺陷修复:
# 2026-07-28 - 小欧 - BUG#3: _exec_calls原写法_safe_calls or call_result.all_calls, 当_safe_calls为空列表(所有调用均被安全拒绝)时回退到all_calls(含被拒绝调用), 完全绕过安全检查。改为_safe_calls if _safe_calls else [], 拒绝后执行空列表。
#   缺陷1: 删_build_call_list中tool_name空检查的重复日志(DRY, handle_action已兜底ErrorStep+return)
#   缺陷2: build_observation统一call字典访问为.get()防KeyError(与同函数内.get()混用修一致)
#   缺陷3: _correction_map改用enumerate索引替代id(call)(更直观,符合KISS-DIRECT)
#   缺陷4: check_safety_and_confirm拒绝反馈改为循环所有_denied(原只给第一个)
#   缺陷5: _has_conflict跳过无别名工具时补path兜底冲突检测(漏报文件路径竞态)
# 2026-07-30 - 小沈 - ContextVar注入: 导入set_current_task_id; handle_action入口加set_current_task_id(agent.task_id)
# 2026-07-30 - 小沈 - except:pass补日志: add_tool_result双层catch失败改为logger.debug记录
# 2026-07-30 - 小欧 - auto_confirm校验: SafetyResult.auto_confirm=True时不等确认直接通过, 提示照出但SUSPENDED不挂起 — 北京老陈驱动三堂会审
# 2026-07-31 - 小欧 - 撤销auto_confirm: action_handler删auto_confirm判断块, 恢复wait_for_confirmation_result等待逻辑
# 2026-08-03 - 小沈 - P0-01 E2E修复: 重加auto_confirm消费块(07-30加→07-31撤→重加缺失一半, 仅残留checker返回+字段)
#           与tool_safety_checker.py:84返回的auto_confirm=True配对, 实现DB场景表#1(安全绕过时MetaStep照出但立即resolve不过SUSPENDED)
# 2026-08-07 - 小欧 - import同步: param_alias_mapper.py→tools_alias_mapper.py 重命名(名实相符), PARAM_ALIASES引用处同步更新
# 2026-08-07 - 小欧 - P07修复(北京老陈驱动 task001): _EXT_TO_READ_TOOL 从TEXT_EXTENSIONS排除.csv(双域: 文本+表格), 使 read_xlsx(csv)/readtext(csv) 均不被_auto_correct_file_tool自动改写 — 小欧 2026-08-07
# 2026-08-09 - 小欧 - edittext并发竞态修复(北京老陈驱动, 方案二分组调度版):
#   [BUG] 旧_has_conflict用set存工具名不计数, 3×edittext同文件被去重漏检→误走并行→read-modify-write竞态致内容丢失(after模式插入位置异常, log step=11)
#   [改法] ①新增_parse_paths(从旧_has_conflict路径解析循环提取, DRY) ②_has_conflict改为计数版(count>=2且含写操作即冲突)
#         ③新增_partition_calls(并查集连通分量分组) ④分支B改分组调度B': 冲突组内串行+无冲突组并行+组间失败隔离(results保序)
#         ⑤C分支_reason死代码清理(进入B'后C分支仅is_parallel=False触发, "文件路径冲突"永假)
#   [验证] verify_refactor_consistency 14/14一致 + verify_partition_v13 分组/执行/隔离10项全PASS + pytest全量回归
# 2026-08-09 - 小欧 - B'分支DRY优化(规范6, 见doc-8月优化修复代码三堂会审报告): 每组冲突判定 _has_conflict 只算一次
#   存入 _gconf 列表, 监控(_gmode拼接)与执行(_run_group冲突分支判定)共用该结果, 消除二次冗余调用;
#   _has_conflict为确定性纯函数(同参数必同果), 判定一次监控与实际执行必然一致(无失真); _run_group加conflicted参数。
#   验证: ast语法✓ + 三分支(单/并行/串行)语义逐字保留无退化
# 2026-08-09 - 小欧 - B'分组调度监控日志(北京老陈驱动: 需监控时间运行情况):
#   [目的] 原B'仅"分组并行执行"开头日志+总耗时, 无法观察每组是并行/串行及各组实际耗时
#   [改法] ①进入B'后打印分组明细(每组工具+模式: 单工具/并行/串行) ②_run_group内计时,
#          每组执行完打印"分组执行完成: tools=..., 模式=..., 耗时=x.xxs" ③执行逻辑零改动(仅return改为赋值_res后return)
#   [验证] py_compile + verify_prod_smoke(生产代码直接import) + handlers/edittext测试
# 2026-08-10 - 小欧 - BUG-E修复(补A"操作结束即清除"落地): handle_action 工具批执行结束后 finally 调 clear_temp_auth(),
#   清空本请求作用域 ContextVar 临时授权, 杜绝"一次一申请"授权跨工具跨步骤残留复用;
#   try/finally 保证执行异常时也清除(不残留授权) — 小欧 2026-08-10
# 2026-08-10 - 小欧 - H1-H2 实施(第二次代码更新): H1 finally 清零移除(清零点迁移到 task 级 R1 react_cycle.run_react_cycle finally);
#   H2 复用现有 HITL 模式: create_confirmation + wait_for_confirmation_result(前端零改动) — 小欧 2026-08-10
# 2026-08-11 - 小欧 - task002 三堂会审修复A(北京老陈驱动, 问题A窗口并行竞态):
#   [BUG] window_focus/window_resize/set_window_state 作用于同一窗口时状态变更非幂等, 同批并行调度产生竞态;
#         实测 P2: set_window_state(restore)+window_resize 同批并行, resize 0.00s 返回 ERR_WINDOW_RESIZE
#   [改法] ①新增 WINDOW_TARGET_TOOLS 常量 ②_parse_paths 新增窗口分支(返回 "window:{window_title}" 冲突键,
#         缺 title 返回空集——工具参数校验必失败, 不会操作任何窗口, 无竞态风险)
#         ③_has_conflict 遍历与判定条件纳入窗口工具(同标题≥2次调用即冲突→降级串行)
#   [效果] 同批同标题窗口工具自动并入同组串行(_partition_calls 并查集本体零改动), 不同标题窗口仍可跨组并行
#   [验证] py_compile + verify_partition_v13 + verify_refactor_consistency + pytest 回归 — 小欧 2026-08-11
# 2026-08-11 - 小欧 - fix D2: check_safety_and_confirm 同批同名工具误杀修复;
#   _denied从2元组(tool_name,reason)扩展为3元组(tool_name,reason,call), 过滤从按tool_name改按id(call)对象标识;
#   原按tool_name过滤→同批2×edittext(1被拒1通过)全被移除(误杀); 新逻辑仅移除被拒call对象, 保留同名合法调用 — 小欧 2026-08-11
# 2026-08-11 - 小欧 - fix D2反馈层同步(北京老陈三堂会审驱动): 原_add_denial_feedback按tool_name粗粒度遍历all_calls写反馈,
#   ①会执行的同名工具被误标"被安全策略拦截"(与真实执行矛盾) ②自行add_assistant_tool_call与build_observation重复写assistant;
#   现改: check_safety_and_confirm经_denied_out回传被拒call(tool_name,reason,call), handle_action在build_observation之后
#   由_add_denial_feedback精确到call对象补写tool result(assistant统一由build_observation写), 消除矛盾与重复 — 小欧 2026-08-11
# 2026-08-12 - 小欧 - A1越层前置: safety 提升为顶层 app.safety, get_tool_safety_checker/grant_temp_auth 的 import 由 app.services.safety 改 app.safety(配合 tools 禁 app.services 守护规则)
# 2026-08-13 小欧 A4收尾解耦: execute_tools 内 5 处 execute_tool 调用显式传入 agent._retry_engine(对齐 tool_executor.execute_tool 新增 retry_engine 显式依赖, 去除对 agent 私有字段强耦合, 行为不变, 无退化)
# 2026-08-13 - 小沈 - BUG-40修复(三堂会审): bypass 模式(auto_confirm)下白名单外路径(auth_path 存在)仍需 grant_temp_auth,
#   否则工具内 validate_path 会拦截(write 模式白名单外未授权返回 False), 工具返回错误, 违背 bypass"直放"语义;
#   在 auto_confirm 分支内补 grant_temp_auth(若有 auth_path), 与下方确认后授权逻辑对齐, 不退化
# 2026-08-13 - 小欧 - unit-06 三堂会审(北京老陈驱动): FILE_OPERATION_TOOLS 扩展纳入8个office读写工具(见tool_constants.py)
#   [BUG] write_xlsx+read_xlsx 同路径同批误走并行 → read 先于 write 执行, validate_path 的 p.exists()=False 报"路径不存在"
#         (实测 prompt_003749 LLM[5] parallel_calls=7: write 67ms后 read 2ms失败, 重试成功)
#   [根因] _parse_paths/_has_conflict 仅认 FILE_OPERATION_TOOLS(文本工具), 8个office工具不在其中→空冲突键→并行
#   [改法] ①tool_constants.FILE_OPERATION_TOOLS 并入8个office工具 ②_WRITE_OPS 排除集 {"readtext"}→_READ_TOOLS
#         (含4个office读工具, 防 read_xlsx 等被误判写操作致读-读并行退化串行)
#   [效果] 同路径写+读/写×2 并组串行, 同路径读×2/不同路径 仍并行, 无性能退化
# 2026-08-16 - 小欧 - S2(10.1.7②-5/10.1.8 S2, 北京老陈驱动): HITL 确认链 tool_name 透传 + 豁免读取 session_id 接入——
#   ①create_confirmation(agent.task_id) 增传 _cn(tool_name), 供 resolve_confirmation trust 落库;
#   ②check_safety_and_confirm 入口经 agent.task_id 反查 session_id(禁伪 agent.session_id, chat_tasks 已建行),
#     传 check_before_execute(session_id=) 做会话信任豁免(信任过的工具跳二次 HITL)
# 2026-08-17 - 小健 - 三堂会审架构修复(北京老陈驱动): 会话信任预查由 safety 层上移到本 services 层——
#   check_safety_and_confirm 循环内查 check_session_trust(_conn, _session_id, normalize_tool_name(_cn)),
#   查得信任后传 check_before_execute(skip_confirmation=True) 豁免二次确认; 消除 safety→services 反向
#   依赖违规(test_layer_boundaries 护栏); T1 normalize 语义随查询落在本层, 与写保护 BUG-2 同模式(防别名漏检)。
# 2026-08-18 小欧 - §10.3.3(1/2/3): 新增ThoughtStartStep; handle_action发射新ActionStep(exec_type/tools); build_observation重写为tool_result数组+orchestration收集; 删_merge_llm_data/_merge_other_data
# 2026-08-18 - 小健 - 三堂会审修复: ①删除无调用点的死代码 _merge_llm_data/_merge_other_data(编排收集改由 build_observation 按 tool_result[i].other_data 1:1 取代); ②删除 build_observation 死变量 _data(原始 data 已由 data_text/dl 承载); ③Bug#7 status/action 可能为 str 防御(isinstance 前判), 防 AttributeError
# 2026-08-18 - 小健 - 恢复 op_id 双表贯通设计说明注释块(此前某次编辑被误删, 仅留行660短注释); 置于 _file_tool_names 逻辑正上方, 逐条核对当前代码(6文件工具白名单/预取队列/pop(0)分配)一致, 描述准确予以保留
# 2026-08-18 - 小健 - 三堂会审修复(target推导): 删除硬编码_TARGE_FIELD(文件类工具+键read/web_search失配致_extract_target回退工具名真bug), 改为_resolve_target_field从tool_registry真实input_schema.properties按_TARGET_PARAM_PRIORITY推导字段名(target值取call入参LLM确定值); ActionStep.target极少截断; 预留ToolMetadata.target_param显式扩展点(OCP)
# 2026-08-18 - 小欧 - §10.4.4 P3(错误全仅SSE): blocked/timeout/user_rejected/invalid_action 四处 ErrorStep→MetaStep(type="error", content=错误信息, error_type=); 删 ErrorStep import
# 2026-08-18 - 小欧 - §10.4.4 P4(severity): error 四处加 severity="warn"; paused 加 severity="attention"; resumed 加 severity="info"
# 2026-08-18 小健 三堂会审: 删除硬编码_TARGE_FIELD——该映射对文件类工具及部分键失配, 使_extract_target回退为工具名(真实bug):
#   ①键失配: 映射键"read"/"web_search"与注册名"readtext"/未注册不符, _TARGET_FIELD.get()返回None→回退tool_name;
#   ②字段失配: 文件类映射值file_path/dir_path/search_dir 与真实schema属性名path/pattern不符, _params.get(...)取到空串→回退tool_name;
#   (注: grep/shell/httpget/fetchpage/download/ping_port/query_sql/execute_sql 映射值恰与schema一致, 旧代码本可工作; 推导化后统一正确且新增工具自动获得)
#   字段名由_resolve_target_field从tool_registry真实input_schema.properties推导; target值取自call["tool_params"]的LLM已回传确定入参值(非结果)。
# 2026-08-18 小欧 - §10.3.3(2) target 提取: 来源=工具调用入参(与observation展示的llm_data.action.target同源, 后者经工具内部转发)
# 规范化主参数优先级: 用于在工具真实input_schema.properties中选定"操作对象"字段;
# pattern置于path之前以区分搜索类(grep/find取pattern)与路径类(其余取path); 新增工具若含这些标准字段即自动获得target(DRY)
# 2026-08-20 - 小欧 - 11.2-C 工具遥测回调(P0-2 修复): handle_action 执行结果处调用 agent.telemetry.on_tool_call(tool_name, success, duration), 供 tool_execution_seconds/task_tool_metrics 聚合(原未调用 → tool_execution_seconds 恒 0)
# 2026-08-21 - 小欧 - 11.6.2: 回调循环扩展收集artifacts(工具自声明+target兜底派生); import os/extract_ext
# 2026-08-21 - 小欧 - 12.2-Q1-D2(已撤销): 原设计将_operation_id经build_extra传action_handler双表贯通,
#   但_operation_id是内部ID不应出现在给LLM的工具返回中(违反SRP:工具返回只服务LLM观察)。
#   撤销: 删除result.get/pop _operation_id逻辑+白名单_file_tool_names+operation_id参数传递;
#   record_operation不再传operation_id(由内部UUID生成, 双表贯通暂断, 后续如需恢复应改用side channel而非LLM可见返回)
#   连带: 删除db导入依赖(operations/task_tracker仅预取块使用, 删除后无其他消费点)
# 2026-08-22 - 小欧 - artifacts结构补充tool_name字段(4字段: tool_name/name/path/type): 收集时注入_tname到每个artifact
# 2026-08-22 - 小欧 - 三堂会审F1定案(北京老陈): 删兜底派生, artifacts仅认写工具with_artifacts自声明;
#   读工具(read_*/query_sql/analyze_data等)也构造action.target, 兜底派生会把读取对象误落为伪产出物(违反"art只能是写的tool"铁律);
#   14个写工具均已自声明零丢失; 连带删除仅服务派生的import os/extract_ext
# 2026-08-23 - 小欧 - 落盘文件A/B 实施(文档[1]11.8.5 D3/D3b/11.9 P3-P4): ①handle_action 先定义 _fp_factory 闭包
#   (按全局序号注入 tool_no; params_raw 权威源=闭包携带的 params_raw_str, #16/#20)再传 on_attempt_recorded 调 execute_tools;
#   ②execute_tools 三分支(A单/B'分组并行/C顺序)全部以全局序号取号透传(#18); ③_build_call_list 透传 params_raw_str(D3b);
#   build_observation 零改动(H3 已移入引擎回调, 防重复记)
# 2026-08-24 - 小欧 - 后端卡死修复收尾(offload): check_safety_and_confirm 的 session 反查与每工具信任预查
#   两处同步 db.get_conn_with_retry 改经 db.atxn 进子线程 offload 出事件循环(复用既有薄壳, 行为等价),
#   ReAct 执行期 loop 不再被锁重试 time.sleep 短暂独占
# 2026-08-25 - 小欧 - 合规重构(北京老陈驱动): M3 沙箱闸门逻辑从 check_safety_and_confirm 内嵌闭包(_sandbox_precheck/_sandbox_resolve)拆出至新建 app/services/agent/handlers/sandbox_gate.py(模块级函数+显式参数, 去隐式捕获约10个外层变量的"七绕八绕", 修正违反1.3公用函数规范-分层/先查后建/登记FUNCTIONS.md 与 KISS-DIRECT); 三处汇合点(①auto_confirm ②用户确认 ③循环体兜底)改显式调用; 业务语义/分支/状态机零改动(复制不重写)
# 2026-08-25 - 小欧 - 合规重构: build_observation 内嵌闭包 _format_llm_data_text(纯展示格式化函数被囚为闭包, 违反1.3/复用优先)拆出至全局层 app/utils/display_utils.format_llm_data_text; 同步删除仅服务于该闭包的死 import json; 逻辑零改动(复制不重写)
# 2026-08-26 小欧 - action步落库记录层修复(com-test 09实证): 原_exec_calls=_safe_calls if _safe_calls else [], 当全部调用被安全拦截时_exec_calls=[]→ActionStep.tools=[]→DB步骤完整性FAIL(无工具调用信息); 改法: 记录层新增_record_calls=_exec_calls if _exec_calls else call_result.all_calls(兜底取LLM意图调用含被拒项), 仅用于ActionStep.tools落库补全; 执行层仍用_exec_calls(绝不回退all_calls, 不绕过安全检查)
# 2026-08-28 小欧 - yield日志审计: check_safety_and_confirm 关键决策点(blocked/paused/timeout/rejected/resumed)补 logger(warning/info), 覆盖11个无日志yield(SRP); 三堂会审无逻辑修正
# 2026-08-30 小欧 - 控制台写离线化收口(case09挂起根治): handle_action 内唯一裸 print([Action]step=) → log_and_print, 延续2026-07-23统一治理; 事件循环线程零同步stdout写 + [Action]获得文件留痕增强
# 2026-09-01 - 小欧 - 紧急bug修复(北京老陈驱动, 前端badge卡paused致耗时秒表失实时): 暂停后恢复路径补发resumed使事件成对——
#   ①S1 auto_confirm分支(resolve_confirmation+set_status EXECUTING之后, 沙箱预检前)补发 MetaStep(type="resumed");
#   ②S2 真HITL分支 resumed 从 if auth_path 内移出, 确认后无条件发1条(授权信息并入文案), 消除重复(KISS/DRY),
#      user确认即恢复与是否授权白名单外路径解耦; resumed 非业务step, agent_runner.py 剔除集合已含, 不影响 total_steps。
# 2026-09-02 小欧 三堂会审task005-BUG-001修复: auto_confirm分支resumed移至sandbox之后(原在sandbox前),
#   若sandbox需用户裁决且被拒绝,无paired paused→resumed, badge卡running; 现仅sandbox通过(放行/无需预检)才发resumed, 语义=真正恢复执行
# 2026-09-02 - 小欧 - P9双重resumed去重(北京老陈驱动「问题报告P9验证」): auto_confirm/真HITL两处插入点
#   sandbox_resolve 已含resumed(用户裁决确认, sandbox_gate:82)时跳过外层二次resumed, 以
#   any(s.type=="resumed" for s in _steps) 去重, 规避报告A方案"无条件continue致bypass场景0次"缺陷;
#   仅改去重不改语义(单次resumed成对, 双次幂等去重), 三堂会审通过(合规/合理/关联逻辑零退化)
# 2026-09-02 - 小欧 - 会话信任功能修复(v1.5, 北京老陈定案, 详见doc-9月优化/会话信任功能修复方案):
#   5.1③: auto_confirm分支(实际在S1 bypass分支)调用改为 await resolve_confirmation(confirm_id, confirmed, trust_session=False) 异步落库零竞态;
#   5.4: trust_session 固定 False, bypass 直放不产生信任, 防自动落库污染信任清单;
#   5.3⑤: 豁免收口点(L428插入点③前)补 grant_temp_auth(auth_path, recursive=True), 信任豁免跳窗但执行放行闭环;
#   5.5④: 新增 _extract_trust_path 辅助 + 信任预查/check_session_trust/create_confirmation 带 path(tool+path 前缀递归精确化);
#   5.7.1/5.7.4①②: auto_confirm 分支从立即resolve改为 wait_for_confirmation_result(S1窗口) 等前端 confirm_timeout 到0自动代发, S1超时bypass兜底放行;
#   5.7.4①: paused emit 增 trust_path/auto_confirm/confirm_timeout/backend_timeout 四字段(后端唯一计时权威=后端窗口−提前量, constants.py HITL_CONFIRM_LEAD/BYPASS_AUTO_LEAD)
# 2026-09-03 - 小欧 - bypass/真HITL确认超时可配置化(北京老陈驱动): auto_confirm_delay默认5→10(前端倒计时10−2=8s), 
#   真HITL确认超时 HITL_TIMEOUT 改读 security.hitl_timeout(config.yaml优先, 默认120兜底); else分支补 get_config import 防NameError
# 2026-09-03 小欧 Bug-1: build_observation 用 zip_longest 防 all_calls/results 长度不齐截断; 全拦截/空 results 无条件发 ObservationStep(改前空 tool_result return 不发事件→前端齿轮永驻); 合成"无结果"占位保数组长度
# 2026-09-03 小欧 Bug-25: grant_temp_auth 三处(bypass自动确认/用户确认授权/白名单豁免直通)包 try/finally 或 try/except, 授权异常不跳过 resolve_confirmation、不阻断执行流程, confirm_id 必收口
# 2026-09-03 小欧 D2-01: synthetic占位补llm_data.summary使折叠区显“已安全拦截：tool”，可观测性增强
# 2026-09-03 小欧 D2-02: _confirm_timeout钳制max(5,bt-LEAD)避免0秒窗口（HITL/bypass/sandbox同钳）
# 2026-09-03 小欧 P0-1: bypass S1已expired不二次resolve（已pop死码），防404僵死
# 2026-09-03 小欧 D2-03: trust_path复用_extract_trust_path消除别名盲区（path/file_path/source_path等），防通配污染
# 2026-09-03 小欧 17.1: sandbox_gate硬编码7key含window_title误授权，改函数内延迟import复用_extract_trust_path
# 2026-09-03 小欧/北京老陈: bypass流程补日志 — S1窗口开始/S1结果两处关键节点, 改前无log无法排查bypass时序
# 2026-09-04 小健 DRY重构: check_safety_and_confirm三处sandbox重复调用→统一入口 run_sandbox_gate
#   [问题] ①auto_confirm ②用户确认 ③循环体兜底 三处sandbox_precheck+sandbox_resolve调用逻辑几乎完全相同(DRY违规)
#   [改法] import新增run_sandbox_gate; 三处重复代码→改为一行调用 run_sandbox_gate(agent,step,call,cn,cp,safety_result,denied)
#   [效果] 三处20行重复代码→三处5行调用, 逻辑集中在sandbox_gate.py一个入口, DRY+KISS+SRP
# 2026-09-04 小健 第1阶段拆分: 信任域+冲突检测+文件工具下沉
#   [改法] 新建trust.py/conflict_detector.py/file_tool_utils.py; action_handler删内联→import新模块
#   [效果] action_handler 1144→976行(-168行); 环依赖消除(sandbox_gate→trust单向); SRP违规6→0处
# 2026-09-04 小健 第2阶段拆分: target提取+文件落盘回调+遥测收集下沉
#   [改法] ①_TARGET_PARAM_PRIORITY/_resolve_target_field/_extract_target → import app.tools.target_utils
#          ②_fp_factory闭包 → import app.file_persist.make_fp_callback(回调工厂下沉file_persist)
#          ③execute_tools批量遥测收集 → 调用 agent.telemetry.collect_and_report(all_calls, results)
#   [效果] action_handler不再持有工具schema查询/文件落盘细节/遥测收集逻辑, 职责更单一
# 2026-09-04 小健 回归修复(bypass乱序严重bug): run_sandbox_gate DRY重构遗漏bypass路径无条件
#   yield resumed + continue → 绕过确认的工具沙箱放行后误落入真HITL等待(confirm_id已resolve/弹出
#   →entry=None→误判"用户拒绝"), 复现: E2E中shell被误拒致失败; 现恢复预DRY的resumed+continue
"""
action_handler — action类型处理（SRP拆分，模块级函数）

3个职责单一的函数:
- check_safety_and_confirm: 安全检查+HITL确认(async generator,IncidentStep先yield再等确认)
- execute_tools: 工具执行 → 返回results
- build_observation: 构建observation → 返回events

小沈 2026-06-09
小沈 2026-06-10 合并check_safety+wait_confirmation,消除重复check_before_execute调用
小沈 2026-06-10 修复HITL bug: check_safety_and_confirm改为async generator,IncidentStep先yield再等确认
小沈 2026-06-13 移除ActionHandler类,改为模块级函数
"""
import asyncio

import time
from dataclasses import dataclass, field
from itertools import zip_longest  # 2026-09-03 小欧 Bug-1: build_observation 用 zip_longest 防 all_calls/results 长度不齐截断丢失 tool_result
from typing import Dict, List, Any, Optional, Set
from app.logger import logger, log_and_print

from app.constants import ACTION_LOG_RESULT_MAX_CHARS
from app.utils.display_utils import format_llm_data_text  # 小欧 2026-08-25 合规重构: 纯展示格式化函数拆至全局层 display_utils(去内嵌闭包)
from app.logger.prompt_logger import get_prompt_logger
from app.services.agent.steps import ThoughtStep, ThoughtStartStep, ActionStep, ObservationStep, MetaStep, FinalStep  # 小欧 2026-07-13: 移除 ChunkStep; 2026-08-18 ThoughtStartStep新增; 2026-08-18 ErrorStep→MetaStep(type="error") P3
from app.services.agent.status_table import AgentStatus, set_status
from app.services.agent.observation_formatter import build_observation_text
from app.constants import HITL_TIMEOUT, HITL_CONFIRM_LEAD, BYPASS_AUTO_LEAD, HITL_MIN_CONFIRM_TIMEOUT  # v1.5.13(2026-09-02 小欧): 后端唯一计时权威前后端计时关联 — 小欧 2026-09-02
# 2026-09-03 小欧/北京老陈: 前端倒计时最小值改常量3(改前硬编码5)
from app.services.agent.tool_executor import execute_tool
from app.services.task.task_context import set_current_task_id
from app.db.models.operation_models import OperationStatus
from app.db import db

from app.tools.tool_constants import SENSITIVE_FIELDS as _SENSITIVE_FIELDS, FILE_OPERATION_TOOLS
from app.tools.tools_alias_mapper import PARAM_ALIASES
from app.tools.validate.file_type_checker import TEXT_EXTENSIONS, MEDIA_EXTENSIONS
from app.tools.registry import tool_registry  # 2026-08-18 小健 三堂会审: target字段从工具schema主参数自动推导(取代硬编码_TARGE_FIELD)
from app.tools.target_utils import _resolve_target_field, _extract_target  # 2026-09-04 小健 第2阶段拆分: target提取下沉工具层
from app.file_persist import make_fp_callback  # 2026-09-04 小健 第2阶段拆分: 文件A落盘回调工厂下沉file_persist
from app.services.agent.handlers.sandbox_gate import sandbox_precheck, sandbox_resolve, run_sandbox_gate  # 小欧 2026-08-25 沙箱闸门逻辑拆分; 小健 2026-09-04 新增run_sandbox_gate统一入口


# 【修复P2-5】封装observation构建上下文 — 北京老陈 2026-06-13
@dataclass
class ObservationContext:
    """构建observation所需的上下文 — 遵守ISP原则"""
    agent: Any
    all_calls: List[Dict]
    results: List[Any]
    step: int
    tool_name: str
    tool_params: Dict
    is_parallel: bool
    pending_calls: List
    fc_context: Dict = None


# 以下常量/函数已拆分至 app/tools/file_tool_utils.py — 小健 2026-09-04
from app.tools.file_tool_utils import _auto_correct_file_tool, _EXT_TO_READ_TOOL, _EXT_TO_WRITE_TOOL

# 以下常量/函数已拆分至 app/tools/conflict_detector.py — 小健 2026-09-04
from app.tools.conflict_detector import _has_conflict, _partition_calls, _WRITE_OPS, _READ_TOOLS

# 以下常量/函数已拆分至 app/tools/trust.py — 小健 2026-09-04
from app.tools.trust import _parse_paths, extract_trust_path as _extract_trust_path, WINDOW_TARGET_TOOLS



async def check_safety_and_confirm(agent, all_calls: List[Dict], step: int, fc_context: Dict = None, _out: list = None, _denied_out: list = None):
        """安全检查+HITL确认 — async generator: MetaStep先yield给前端,再等确认 — 小沈 2026-06-10

        拒绝/拦截是可恢复的(符合人类认知: 拒绝≠失败), 不置终态FAILED:
        - 把"工具被拒绝/拦截"作为 observation 写进LLM历史(_add_denial_feedback), 让LLM换方案;
        - 循环回 THINKING 由主循环 EXECUTING→THINKING 处理;
        - 仅当同类拒绝累计>=3次才由 _dispatch_handler 置 FAILED。 — 小欧 2026-07-13
        # 2026-07-18 小欧 #11+#12 fix: 超时/拒绝分流; 拒绝不终止整批, 收集_denied后继续检查剩余工具,
        #   最终只执行通过的call(通过_out返回过滤后的call列表)
        # 2026-08-11 小欧 fix D2: _denied从2元组(tool_name,reason)扩展为3元组(tool_name,reason,call),
        #   _out过滤从按tool_name改按id(call)对象精确标识(同批同名工具1个被拒不再误杀);
        #   反馈推迟到调用方build_observation之后(_denied_out回传), 由_add_denial_feedback精确到call写,
        #   消除"会执行的同名工具被误标被拦截"与"assistant双重写入"的矛盾
        """
        from app.safety.tool_safety_checker import get_tool_safety_checker
        from app.services.task.hitl_confirmation import create_confirmation, wait_for_confirmation_result, resolve_confirmation
        from app.tools.trust import resolve_skip
        safety_checker = get_tool_safety_checker()

        _denied = []
        for call in all_calls:
            _cn = call.get("tool_name", "?")
            _cp = call.get("tool_params", {})

            # 会话信任预查 — 调用 trust.resolve_skip 独立函数 — 小健 2026-09-04
            _skip = await resolve_skip(agent.task_id, _cn, _cp)

            safety_result = safety_checker.check_before_execute(_cn, _cp, skip_confirmation=_skip)

            # v1.25 M3(设计文档 3.2.3): 沙箱预检闸门 — 逻辑已拆分至 sandbox_gate.sandbox_precheck/sandbox_resolve
            # (2026-08-25 合规重构: 去嵌套闭包隐式耦合, Agent编排层落点, 三处汇合点共用, 每 call 恰好预检一次不重复)

            if safety_result.blocked:
                # 2026-08-28 小欧 yield日志审计: 拦截决策日志(SRP)
                logger.warning(f"[action] step={step} blocked: tool={_cn} reason={safety_result.message}")
                yield agent._step_emitter.emit(MetaStep(
                    step=step, type="error", content=safety_result.message, error_type="blocked", severity="warn"
                ))
                _denied.append((_cn, f"被安全策略拦截: {safety_result.message}", call))
                continue  # was: return  — 小欧 2026-07-18 #12 fix

            if safety_result.requires_confirmation:
                desensitized_params = {k: v for k, v in _cp.items()
                                       if k not in _SENSITIVE_FIELDS}

                confirm_id = await create_confirmation(agent.task_id, _cn, _extract_trust_path(_cn, _cp))  # v1.5: path 透传供 tool+path 落库 — 小欧 2026-09-02

                # 2026-08-28 小欧 yield日志审计: 等待确认决策日志(SRP)
                logger.info(f"[action] step={step} paused: tool={_cn} confirm_id={confirm_id}")
                # v1.5.13(老陈三审定案: 后端唯一计时权威 + 前端倒计时=后端窗口−提前量)
                #   真HITL: backend_timeout=HITL_TIMEOUT(120) / confirm_timeout=120-HITL_CONFIRM_LEAD(10)=110;
                #   bypass: backend_timeout=security.auto_confirm_delay(默认10) / confirm_timeout=10-BYPASS_AUTO_LEAD(2)=8
                _bypass = bool(getattr(safety_result, "auto_confirm", False))
                if _bypass:
                    from app.config import get_config as _get_cfg
                    # 对应 config.yaml security.auto_confirm_delay(默认10, 前端倒计时=此值−BYPASS_AUTO_LEAD即8s); 未配置兜底用 10.0 — 小欧-2026-09-03
                    # 2026-09-03 小沈 缺陷2修复: 钳制≥HITL_MIN_CONFIRM_TIMEOUT+BYPASS_AUTO_LEAD, 确保confirm_timeout+S1差≥BYPASS_AUTO_LEAD — 小沈-2026-09-03
                    _backend_timeout = max(HITL_MIN_CONFIRM_TIMEOUT + BYPASS_AUTO_LEAD, int(float(_get_cfg().get("security.auto_confirm_delay", 10.0))))
                    # 2026-09-03 小欧/北京老陈: 0窗钳制≥3s(改前5→常量3)，避免max(0,bt-LEAD)=0致0秒窗口瞬间消失
                    _confirm_timeout = max(HITL_MIN_CONFIRM_TIMEOUT, _backend_timeout - BYPASS_AUTO_LEAD)
                else:
                    from app.config import get_config as _get_cfg
                    # 对应 config.yaml security.hitl_timeout(真HITL后端确认窗口,默认120); 未配置兜底用常量 HITL_TIMEOUT=120 — 小欧 2026-09-03
                    _backend_timeout = int(float(_get_cfg().get("security.hitl_timeout", HITL_TIMEOUT)))
                    # 2026-09-03 小欧/北京老陈: 0窗钳制≥3s(改前5→常量3)
                    _confirm_timeout = max(HITL_MIN_CONFIRM_TIMEOUT, _backend_timeout - HITL_CONFIRM_LEAD)
                _tp = _extract_trust_path(_cn, _cp)  # v1.5.3: trust_path 透传
                yield agent._step_emitter.emit(MetaStep(
                    step=step,
                    type="paused",
                    content=f"需要用户确认工具执行: {_cn}",
                    confirm_id=confirm_id,
                    tool_name=_cn,
                    params=desensitized_params,
                    safety_level=safety_result.safety_level,
                    severity="attention",
                    trust_path=_tp,
                    auto_confirm=_bypass,
                    confirm_timeout=_confirm_timeout,
                    backend_timeout=_backend_timeout,
                ))

                if safety_result.auto_confirm:
                    # v1.5.13(2026-09-02 小欧, 5.7.1 bypass 自动代发): bypass 从"立即resolve"改为"等前端确认消息(S1窗口)"
                    #   前端confirm_timeout到0自动代发confirm → resolve_confirmation → wait收到即走确认流程;
                    #   前端未发(无浏览器/崩溃) → S1超时 → expired → bypass 兜底放行
                    from app.services.task.hitl_confirmation import wait_for_confirmation_result as _wait_confirm
                    from app.config import get_config as _get_cfg
                    # 对应 config.yaml security.auto_confirm_delay(S1后端等待窗口=backend_timeout值,默认10); 未配置兜底 10.0 — 小欧-2026-09-03
                    # 2026-09-03 小沈 缺陷2修复: 与上方同源钳制, 确保S1=backend_timeout — 小沈-2026-09-03
                    _s1 = float(max(HITL_MIN_CONFIRM_TIMEOUT + BYPASS_AUTO_LEAD, int(float(_get_cfg().get("security.auto_confirm_delay", 10.0)))))
                    # 2026-09-03 小欧/北京老陈: bypass S1窗口开始补日志
                    logger.info(f"[action] bypass S1窗口开始: confirm_id={confirm_id}, S1={_s1}s, tool={_cn}")
                    _auth_result = await _wait_confirm(confirm_id, timeout=int(_s1 if _s1 > 0 else 0)) if _s1 > 0 else {"confirmed": True}
                    # 2026-09-03 小欧/北京老陈: bypass S1结果补日志
                    logger.info(f"[action] bypass S1结果: confirm_id={confirm_id}, expired={_auth_result.get('expired')}, confirmed={_auth_result.get('confirmed')}")
                    # 2026-09-03 小欧 P0-1: S1已expired则不再二次resolve(已pop死码)，仅confirmed分支需resolve
                    if _auth_result.get("expired"):
                        _bypass_confirmed = True
                    else:
                        _bypass_confirmed = bool(_auth_result.get("confirmed", False))
                        try:
                            # 2026-09-03 小欧 Bug-25: grant_temp_auth 包 try/finally, 授权异常不跳过 resolve_confirmation,
                            #   confirm_id 必被 resolve 收口, 前端 Modal 不泄漏挂到后端超时; 授权失败仅告警不改安全意图
                            if getattr(safety_result, "auth_path", None):
                                from app.tools.security.temp_auth import grant_temp_auth
                                grant_temp_auth(safety_result.auth_path, recursive=True)
                        except Exception as e:
                            logger.warning(f"[action] grant_temp_auth失败仍放行: {e!r}")
                        finally:
                            await resolve_confirmation(confirm_id, confirmed=_bypass_confirmed, trust_session=False)
                    set_status(agent, AgentStatus.EXECUTING, "安全策略自动确认工具执行")
                    # v1.25 M3 插入点①: auto_confirm 汇合路径(continue 之前) — 沙箱预检最后闸门
                    # 2026-09-02 小欧 三堂会审BUG-001修复: resumed移至sandbox之后(原在sandbox前),
                    #   若sandbox需用户裁决且被拒绝,无paired paused→resumed, badge卡running;
                    #   现仅sandbox通过(放行/无需预检)才发resumed, 语义=真正恢复执行
                    _pre = await sandbox_precheck(safety_result, _cn, _cp)
                    if _pre is not None:
                        _ok, _steps = await sandbox_resolve(agent, step, call, _cn, _cp, _pre, safety_result, _denied)
                        for _st in _steps:
                            yield _st
                        if not _ok:
                            continue
                        if any(getattr(_s, "type", None) == "resumed" for _s in _steps):
                            continue
                    # 2026-09-02 小欧 BUG-001: sandbox通过后才发resumed(对齐下方真HITL确认后恢复语义,
                    #   前端badge据此回running恢复耗时秒表); 若sandbox拒绝已continue不发resumed
                    # 2026-09-04 小健 DRY: 三处重复sandbox调用→统一入口 run_sandbox_gate
                    # 2026-09-04 小健 回归修复: bypass路径沙箱放行(无冲突,run_sandbox_gate返回True,[])后必须无条件
                    #   yield resumed + continue(预DRY原有无条件continue被DRY重构遗漏), 否则落入下方真HITL等待
                    _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied)
                    for _st in _steps:
                        yield _st
                    if not _ok:
                        continue
                    if any(getattr(_s, "type", None) == "resumed" for _s in _steps):
                        continue
                    yield agent._step_emitter.emit(MetaStep(
                        step=step, type="resumed",
                        content=f"已自动确认工具执行: {_cn}",
                        severity="info",
                        confirm_id=confirm_id,
                    ))
                    continue

                set_status(agent, AgentStatus.SUSPENDED, f"等待用户确认工具执行: {_cn}")
                from app.config import get_config as _get_cfg_wait
                # 对应 config.yaml security.hitl_timeout(与 emit 的 backend_timeout 同源,默认120); 未配置兜底用常量 HITL_TIMEOUT — 小欧 2026-09-03
                auth = await wait_for_confirmation_result(confirm_id, timeout=int(float(_get_cfg_wait().get("security.hitl_timeout", HITL_TIMEOUT))))

                if not auth.get("confirmed"):
                    if auth.get("expired"):
                        # #11 fix: 超时与拒绝分流 — 小欧 2026-07-18
                        # 2026-08-28 小欧 yield日志审计: 超时决策日志(SRP)
                        logger.warning(f"[action] step={step} timeout: tool={_cn}")
                        yield agent._step_emitter.emit(MetaStep(
                            step=step, type="error", content=f"工具确认超时未响应: {_cn}", error_type="timeout", severity="warn"
                        ))
                        _denied.append((_cn, "确认超时未响应", call))
                    else:
                        # 2026-08-28 小欧 yield日志审计: 拒绝决策日志(SRP)
                        logger.warning(f"[action] step={step} rejected: tool={_cn}")
                        yield agent._step_emitter.emit(MetaStep(
                            step=step, type="error", content=f"用户拒绝执行工具: {_cn}", error_type="user_rejected", severity="warn"
                        ))
                        _denied.append((_cn, "被用户拒绝执行", call))
                    set_status(agent, AgentStatus.EXECUTING, "用户拒绝/超时，恢复执行态")
                    continue  # was: return  — 小欧 2026-07-18 #12 fix

                # 用户已确认：恢复执行态继续工具执行（SUSPENDED→EXECUTING 合法）— 小欧 2026-07-12
                # ⑮ 白名单外临时授权: 确认后授予本次操作权限(一次一申请, 支持递归, per-request) — 小欧 2026-08-10
                # 2026-09-01 小欧 - 紧急bug修复S2(前端badge卡paused): resumed从if auth_path内移出,
                #   用户确认即恢复(与是否授权白名单外路径解耦), 无条件发1条, 授权信息并入文案, 消除重复(KISS/DRY)
                try:
                    # 2026-09-03 小欧 Bug-25: 用户确认授权白名单外路径, grant_temp_auth 异常不阻断恢复执行态
                    if getattr(safety_result, "auth_path", None):
                        from app.tools.security.temp_auth import grant_temp_auth
                        grant_temp_auth(safety_result.auth_path, recursive=True)
                        # 2026-08-28 小欧 yield日志审计: 临时授权日志(SRP) — 保留(2026-09-01 S2移出resumed时同步保留授权留痕)
                        logger.info(f"[action] step={step} resumed+auth: tool={_cn} path={safety_result.auth_path}")
                except Exception as e:
                    logger.warning(f"[action] 确认后grant_temp_auth失败不阻断: {e!r}")
                # 2026-08-28 小欧 yield日志审计: 临时授权日志(SRP)
                set_status(agent, AgentStatus.EXECUTING, "用户已确认工具执行")
                # 2026-09-03 小沈 缺陷1修复: resumed增confirm_id, 前端收到后可据此关弹窗(防御性兜底) — 小沈-2026-09-03
                yield agent._step_emitter.emit(MetaStep(
                    step=step, type="resumed",
                    content=(f"已临时授权白名单外路径: {safety_result.auth_path}"
                             if getattr(safety_result, "auth_path", None)
                             else f"用户已确认工具执行: {_cn}"),
                    severity="info",
                    confirm_id=confirm_id,
                ))
                # v1.25 M3 插入点②: 用户确认汇合路径 — 2026-09-04 小健 DRY: 统一入口
                _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied)
                for _st in _steps:
                    yield _st
                if not _ok:
                    continue
                if any(getattr(_s, "type", None) == "resumed" for _s in _steps):
                    continue
                continue

            # 5.3(2026-09-02 小欧, 病根3.5): 信任豁免/safe 直通汇合点统一授权收口——
            #   tool_safety_checker 豁免返回 requires_confirmation=False 但保留 auth_path,
            #   此处补 grant_temp_auth 闭环, 防"豁免跳窗不放行"(工具内部 validate_path 拦截执行失败)
            try:
                # 2026-09-03 小欧 Bug-25: 白名单外豁免直通亦包 try/except, grant_temp_auth 异常不阻断 sandbox 汇合
                if getattr(safety_result, "auth_path", None):
                    from app.tools.security.temp_auth import grant_temp_auth
                    grant_temp_auth(safety_result.auth_path, recursive=True)
            except Exception as e:
                logger.warning(f"[action] 豁免直通grant_temp_auth失败不阻断: {e!r}")

            # v1.25 M3 插入点③: 循环体末尾兜底(仅 safe 直通/会话信任豁免触达) — 2026-09-04 小健 DRY: 统一入口
            _ok, _steps = await run_sandbox_gate(agent, step, call, _cn, _cp, safety_result, _denied)
            for _st in _steps:
                yield _st
            if not _ok:
                continue

        # 回传未被拒的call索引给调用方 — 小欧 2026-07-18 #12 fix
        # 2026-08-11 小欧 fix D2: 用call对象id标识被拒调用,而非tool_name;
        #   原按tool_name过滤→同批同名工具(如2×edittext)1个被拒全部误杀
        if _out is not None:
            _denied_call_ids = {id(d[2]) for d in _denied}
            _out[:] = [c for c in all_calls if id(c) not in _denied_call_ids]
        # 2026-08-11 小欧 fix D2: _denied(含call对象)回传给调用方, 反馈在build_observation之后
        #   由_add_denial_feedback精确到call写(避免在execute前写tool result导致assistant重复/同名误标)
        if _denied_out is not None:
            _denied_out[:] = list(_denied)


def _add_denial_feedback(agent, denied_items, fc_context=None):
    """HITL拒绝/拦截→把反馈写入LLM历史, 让LLM换方案(符合人类认知: 拒绝≠失败) — 小欧 2026-07-13

    2026-08-11 小欧 fix D2: 精确到call对象, 只对被拒call写observation:
      原实现遍历all_calls按tool_name匹配→同批同名工具(实际会执行)被误标"被拦截",
      且自行add_assistant_tool_call→与build_observation的assistant双重写, LLM历史矛盾;
      现assistant统一由build_observation写(L649), 本函数在execute_tools后只补被拒call的tool result。
    """
    for _cn, _reason, _call in (denied_items or []):
        _tid = _call.get("_tool_call_id", "")
        _obs = f"[Observation] 工具 {_cn} {_reason}. 请改用其他工具或方式完成用户任务。"
        try:
            agent.message_builder.add_tool_result(_tid, _obs)
        except Exception as e:
            logger.debug(f"add_tool_result(_tid={_tid})失败, 尝试空ID: {e}")
            try:
                agent.message_builder.add_tool_result("", _obs)
            except Exception as e2:
                logger.debug(f"add_tool_result(空ID)也失败: {e2}")




async def execute_tools(agent, all_calls: List[Dict], is_parallel: bool,
                        tool_name: str, tool_params: Dict,
                        on_retry_started=None, on_attempt_recorded=None) -> List[Any]:
        """工具执行调度 — 三分支策略（遵守SLAP：本层只做决策不分派执行细节）
         
        三分支说明：
          A: 单工具（len==1）→ execute_tool(on_retry_started=...)
             单个工具执行，注入重试回调。引擎层自动处理重试+通知。
          B: 多工具无冲突 → execute_tool(parallel=True, 无on_retry_started)
             各工具并行执行，用try_once一次执行不重试。
             设计理由（YAGNI）：并行工具的瞬态失败概率低，不需要引擎自动重试。
             LLM从observation看到失败后可自行决定重试。同时避免asyncio.gather内
             多重试的复杂性。
          C: 多工具有冲突/非并行模式 → 顺序执行，每个调execute_tool(on_retry_started=...)
             文件路径冲突（一写多读）→降级顺序避免并发竞态。
             非并行模式→依次执行不并发。
         
        参数变化历史：
        北京老陈 2026-07-04: 初版，三分支+文件冲突检测
        小欧 2026-07-09: 
          - 并行分支B改用parallel=True（→try_once），删除手动重试循环（解决SRP/DRY违规）
          - 新增on_retry_started参数，透传给单工具/顺序分支（解决重试无前端通知问题）
        """
        start_time = time.time()

        # #4 自动纠正: 文件工具扩展名预检 — 小欧 2026-07-21
        _correction_map = {}
        for i, c in enumerate(all_calls):
            _orig = c.get("tool_name", "")
            _corrected, _raw = _auto_correct_file_tool(_orig, c.get("tool_params", {}))
            if _raw:
                logger.info(f"[action_handler] 自动纠正: {_raw}→{_corrected}")
                c["tool_name"] = _corrected
                _correction_map[i] = _raw
        _corrected_tn, _raw_tn = _auto_correct_file_tool(tool_name, tool_params)
        if _raw_tn:
            tool_name = _corrected_tn
            if all_calls:
                _correction_map[0] = _raw_tn

        def _cn(c):
            return c.get("tool_name", "") if isinstance(c, dict) else ""
        def _cp(c):
            return c.get("tool_params", {}) if isinstance(c, dict) else {}

        if len(all_calls) == 1:
            # A: 单工具
            log_and_print(f"{time.strftime('%H:%M:%S')} [action_handler] 单工具执行: tool={tool_name}")
            # #18(2026-08-23): 文件A 每次尝试回调按【全局序号】取号 — 小欧 2026-08-23
            _cb = on_attempt_recorded(1) if on_attempt_recorded else None
            result = await execute_tool(agent, tool_name, tool_params, agent._retry_engine,
                                        on_retry_started=on_retry_started, on_attempt_recorded=_cb)
            results = [result]

        elif is_parallel:
            # B': 并行分组调度 — 冲突组内串行, 无冲突组并行("该并行就并行") — 小欧 2026-08-09
            _names = [_cn(c) for c in all_calls]
            log_and_print(f"{time.strftime('%H:%M:%S')} [action_handler] 分组并行执行: tools={_names}")
            groups = _partition_calls(all_calls)
            # DRY(规范6): 每组冲突判定只算一次, 监控(_gmode)与执行(_run_group)共用,
            # 消除二次 _has_conflict 冗余调用; 纯函数确定性保证监控与实际执行必然一致(无失真) — 小欧 2026-08-09
            _gd = []
            _gconf = []  # 每组冲突判定结果, 按 groups 顺序对齐
            for _g in groups:
                _gt = [_cn(all_calls[i]) for i in _g]
                _conflicted = len(_g) > 1 and _has_conflict([all_calls[i] for i in _g])
                _gconf.append(_conflicted)
                _gmode = "单工具" if len(_g) == 1 else ("并行" if not _conflicted else "串行")
                _gd.append(f"[{'/'.join(_gt)}:{_gmode}]")
            log_and_print(f"{time.strftime('%H:%M:%S')} [action_handler] 分组明细({len(groups)}组): {' '.join(_gd)}")

            async def _run_group(indices: List[int], conflicted: bool):
                group = [all_calls[i] for i in indices]
                _g_start = time.time()  # 监控: 每组执行耗时起点 — 小欧 2026-08-09
                if len(group) == 1:  # 单工具, 语义同原A
                    # #18(2026-08-23): 工厂实参=全局序号(indices[0]+1), 禁用组内局部下标 — 小欧 2026-08-23
                    _cb = on_attempt_recorded(indices[0] + 1) if on_attempt_recorded else None
                    _res = [await execute_tool(agent, _cn(group[0]), _cp(group[0]), agent._retry_engine,
                                               on_retry_started=on_retry_started, on_attempt_recorded=_cb)]
                    _gmode = "单工具"
                elif not conflicted:  # 组内无冲突→并行(try_once), 语义同原B
                    # #18(2026-08-23): zip(indices, group) 对齐全局下标取号 — 小欧 2026-08-23
                    tasks = [execute_tool(agent, _cn(c), _cp(c), agent._retry_engine, parallel=True,
                                          on_attempt_recorded=(on_attempt_recorded(_gi + 1) if on_attempt_recorded else None))
                             for _gi, c in zip(indices, group)]
                    _res = await asyncio.gather(*tasks, return_exceptions=True)
                    _gmode = "并行"
                else:  # 组内冲突→串行(带重试), 语义同原C
                    _res = []
                    for _gi, call in zip(indices, group):
                        try:
                            _cb = on_attempt_recorded(_gi + 1) if on_attempt_recorded else None
                            _res.append(await execute_tool(agent, _cn(call), _cp(call), agent._retry_engine,
                                                           on_retry_started=on_retry_started, on_attempt_recorded=_cb))
                        except Exception as e:
                            logger.warning(f"[action_handler] 工具{_cn(call)}组内顺序执行失败: {e}")
                            _res.append(e)
                    _gmode = "串行"
                logger.info(f"[action_handler] 分组执行完成: tools={[_cn(c) for c in group]}, 模式={_gmode}, 耗时={time.time()-_g_start:.2f}s")
                return _res

            _grouped = await asyncio.gather(*[_run_group(g, _gconf[i]) for i, g in enumerate(groups)],
                                            return_exceptions=True)  # 组间失败隔离: 单组异常不取消其他组
            results = [None] * len(all_calls)  # 结果按原顺序填回
            for _indices, _res in zip(groups, _grouped):
                if isinstance(_res, Exception):  # 整组失败: 组内全部标记为该异常(与原C分支单工具异常append语义一致)
                    for _i in _indices:
                        results[_i] = _res
                    continue
                for _i, _r in zip(_indices, _res):
                    results[_i] = _r
        else:
            # C: 非并行模式 → 顺序执行（一个不丢）
            _names = [_cn(c) for c in all_calls]
            _reason = "非并行模式"
            log_and_print(f"{time.strftime('%H:%M:%S')} [action_handler] 顺序执行({_reason}): tools={_names}")
            results = []
            for _gi, call in enumerate(all_calls, 1):
                try:
                    # #18(2026-08-23): 顺序分支按全局序号取号 — 小欧 2026-08-23
                    _cb = on_attempt_recorded(_gi) if on_attempt_recorded else None
                    result = await execute_tool(agent, _cn(call), _cp(call), agent._retry_engine,
                                                on_retry_started=on_retry_started, on_attempt_recorded=_cb)
                    results.append(result)
                except Exception as e:
                    logger.warning(f"[action_handler] 工具{_cn(call)}顺序执行失败: {e}")
                    results.append(e)

        elapsed = time.time() - start_time
        tool_names = [_cn(c) for c in all_calls]
        logger.info(f"[action_handler] 工具执行完成: tools={tool_names}, 耗时={elapsed:.2f}s")

        for i, (call, result) in enumerate(zip(all_calls, results)):
            if isinstance(result, Exception):
                logger.info(f"[action_handler] 工具原始结果: tool={_cn(call)}, params={_cp(call)}, result=ERROR({result})")
            else:
                _r_str = str(result)
                if len(_r_str) > ACTION_LOG_RESULT_MAX_CHARS:
                    _r_str = _r_str[:ACTION_LOG_RESULT_MAX_CHARS] + f"...(截断{len(_r_str)}字符)"
                logger.info(f"[action_handler] 工具原始结果: tool={_cn(call)}, params={_cp(call)}, result={_r_str}")
            _orig_tool = _correction_map.get(i)
            if _orig_tool and isinstance(result, dict):
                _llm = result.get("llm_data")
                if isinstance(_llm, dict) and isinstance(_llm.get("summary"), str):
                    _llm["summary"] += f"（工具自动纠正自:{_orig_tool}）"

        # 11.2-C 工具遥测回调（P0-2 修复：on_tool_call 未调用 → tool_execution_seconds 恒 0）— 小欧 2026-08-20; 2026-09-04 小健 第2阶段拆分: 批量聚合下沉 agent_telemetry.collect_and_report
        _tele = getattr(agent, "telemetry", None)
        if _tele is not None:
            _tele.collect_and_report(all_calls, results)

        return results


async def build_observation(ctx: ObservationContext) -> "tuple[List, Dict]":
    """构建 observation - tool_result 数组方案（§10.3.3(3)）— 2026-08-18 小欧

    职责不变: 1条assistant(tool_calls)+逐工具add_tool_result喂LLM; record_operation双表同号
    变更: 删 ActionStep 发射/删 _merge_other_data/删顶层 llm_data/tool_result/other_data/parallel_results
          ObservationStep 仅 tool_result 数组; 编排层从各 tool_result[i].other_data 收集(return_direct/attachment/warning)
    返回: (events, orchestration)  orchestration={"return_direct","attachments","warning","return_direct_message"}
    """
    events: List = []
    tool_result: List[Dict[str, Any]] = []
    orchestration = {"return_direct": False, "attachments": [], "warning": "", "return_direct_message": ""}

    # assistant+tool 配对 — 建1条assistant带所有tool_calls
    _fc = ctx.fc_context or {}
    _shared_tc = _fc.get("tool_calls", [])
    if _shared_tc:
        ctx.agent.message_builder.add_assistant_tool_call(
            _shared_tc, content=_fc.get("llm_content", "") or None,
            reasoning=_fc.get("llm_reasoning", "") or None,
        )

    for call, result in zip_longest(ctx.all_calls, ctx.results):
        if call is None:
            continue
        # 2026-09-03 小欧 Bug-1: 全工具被安全拦截时 results 可能缺失该 call 的结果(zip_longest 补 None),
        #   用合成"无结果"占位, 使 ObservationStep 必然发出、前端 results 保长度, 齿轮/动画不再永驻
        # 2026-09-03 小欧 D2-01: synthetic补summary使折叠区可见“已安全拦截：tool”
        if result is None:
            _syn_tool = call.get("tool_name", "?") if isinstance(call, dict) else "?"
            result = {"llm_data": {"status": {"exec_code": "error"}, "summary": f"已安全拦截：{_syn_tool}"}, "other_data": {"synthetic": True}}
        if isinstance(result, Exception):
            obs_text = f"Observation: 工具{call.get('tool_name', '?')}执行异常: {result}"
            _is_failed = True
        else:
            obs_text = build_observation_text(result, call.get("tool_name", ""), call.get("tool_params", {}))
            _llm_data = result.get("llm_data") if isinstance(result.get("llm_data"), dict) else {}
            # 2026-08-18 小健 三堂会审 Bug#7: status 可能为 str(工具实现不规范), 防御防 AttributeError
            _status = _llm_data.get("status") if isinstance(_llm_data.get("status"), dict) else {}
            _ec = _status.get("exec_code", "")
            _is_failed = _ec == "error"

        get_prompt_logger().log_observation(
            step_name=f"步骤{ctx.step}: 工具执行结果",
            observation_content=obs_text, tool_name=call.get("tool_name", ""),
            tool_params=call.get("tool_params", {}), round_number=ctx.step, raw_data=result,
        )
        _tool = call.get("tool_name", "?")
        ctx.agent.record_operation(
            _tool,
            status=OperationStatus.FAILED.value if _is_failed else OperationStatus.SUCCESS.value,
            error=str(result) if _is_failed else None,
        )
        repair_warning = call.get("_repair_warning", "")
        if repair_warning:
            obs_text = f"Observation: {repair_warning}\n{obs_text}"
            logger.warning(f"[action_handler] step={ctx.step}, {_tool} 参数截断修复: {repair_warning}")
        try:
            tc_id = call.get("_tool_call_id", "")
            ctx.agent.message_builder.add_tool_result(tc_id, obs_text)
        except Exception as e:
            logger.warning(f"[action_handler] add_tool_result异常: {type(e).__name__}: {e!r}")
            try:
                ctx.agent.message_builder.add_tool_result("", obs_text)
            except Exception as e2:
                logger.warning(f"[action_handler] add_tool_result最终异常: {type(e2).__name__}: {e2!r}")

        # ── 构建 tool_result[i]（每元素自包含, other_data 1:1 不合并）── 2026-08-18 小欧
        # 2026-08-18 小健 三堂会审 Bug#4: 删除死变量 _data(只赋值未使用, 原始 data 已由 data_text/dl 承载)
        if isinstance(result, dict):
            _llm = result.get("llm_data") if isinstance(result.get("llm_data"), dict) else {}
            _other = result.get("other_data") if isinstance(result.get("other_data"), dict) else {}
        else:
            _llm, _other = {}, {}
        tool_result.append({
            "tool_name": _tool,
            "llm_data": _llm,
            "llm_data_text": format_llm_data_text(_llm),
            "data_text": obs_text,
            "other_data": _other,
        })
        # ── 编排层收集（取代旧 _merge_other_data 盲目合并）── 2026-08-18 小欧
        if _other.get("return_direct"):
            orchestration["return_direct"] = True
            # 2026-08-18 小健 Bug#7: status 可能非 dict, .get 前防御 (line 732 同各 status 取值点)
            _rd_status = _llm.get("status") if isinstance(_llm.get("status"), dict) else {}
            orchestration["return_direct_message"] = _rd_status.get("message", "") or obs_text
        if _other.get("attachment") is not None:
            orchestration["attachments"].append(_other["attachment"])
        if _other.get("warning"):
            _w = str(_other["warning"])
            orchestration["warning"] = (orchestration["warning"] + "\n\n" + _w).strip() if orchestration["warning"] else _w

    # 2026-09-03 小欧 Bug-1: 无条件发 ObservationStep(即使 tool_result 为空/全拦截),
    #   前端 results 到达即卸载等待动画, 杜绝齿轮/动画永驻(改前空 tool_result 直接 return 不发事件)
    # 2026-09-03 小欧 D2-01补：all_calls空时不发空观察（无工具调用无需观察）
    if ctx.all_calls:
        events.append(ctx.agent._step_emitter.emit(ObservationStep(step=ctx.step, tool_result=tool_result)))
    return events, orchestration


@dataclass
class BuildCallListResult:
    """_build_call_list 返回值 — M-03 6元组→dataclass — 小欧 2026-07-10"""
    tool_name: str
    tool_params: Dict
    fc_context: Dict
    pending_calls: List
    all_calls: List[Dict]
    is_parallel: bool


def _build_call_list(parsed: Dict) -> BuildCallListResult:
    """构建工具调用列表 — 小欧 2026-06-18 从handle_action提取
    chendyg 2026-06-26 P1-10/11修复: 防御tool_name为空和pending_calls缺字段"""
    tool_name = parsed.get("tool_name", "")
    tool_params = parsed.get("tool_params") or {}
    fc_context = parsed.get("fc_context") or {}
    pending_calls = parsed.get("_pending_calls", [])

    # 【P1-10修复】tool_name为空时直接FAILED — chendyg 2026-06-26
    # handle_action已兜底空检查(ErrorStep+return), 此处删除重复日志 — 小欧 2026-07-25

    all_calls = [{
        "tool_name": tool_name, "tool_params": tool_params,
        "_tool_call_id": fc_context.get("tool_call_id", "") if fc_context else "",
        "_repair_warning": parsed.get("_repair_warning", ""),
        "params_raw_str": parsed.get("params_raw_str", ""),   # #3 透传 LLM 原始参数串(11.7.9-2③) — 小欧 2026-08-23
    }]
    # 【P1-11修复】pending_calls条目缺tool_name时跳过 — chendyg 2026-06-26
    for pc in pending_calls:
        pc_name = pc.get("tool_name", "")
        if not pc_name:
            logger.warning(f"[_build_call_list] pending_call缺tool_name,跳过: {pc}")
            continue
        all_calls.append({
            "tool_name": pc_name, "tool_params": pc.get("tool_params") or {},
            "_tool_call_id": pc.get("_tool_call_id", ""),
            "_repair_warning": pc.get("_repair_warning", ""),
            "params_raw_str": pc.get("params_raw_str", ""),   # #3 并行调用各自原始串 — 小欧 2026-08-23
        })

    return BuildCallListResult(
        tool_name=tool_name, tool_params=tool_params, fc_context=fc_context,
        pending_calls=pending_calls, all_calls=all_calls,
        is_parallel=len(all_calls) > 1,
    )



async def handle_action(agent, parsed: Dict):
    """完整action处理流程 — FC-only: 提取fc_context传递
     
    处理管线（遵守SLAP，逐层递进）：
    1. _build_call_list → 解析parsed为all_calls
    2. emit ThoughtStep → LLM推理内容
    3. check_safety_and_confirm → 安全检查+HITL（async generator）
    4. build retry notification callback → 收集重试通知
    5. execute_tools → 三分支执行（单/并行/顺序）
    6. 工具重试由 tool_retry_engine 内部执行（隐蔽，前端不可见）— 小欧 2026-07-13
    7. build ObservationContext → 收集执行结果
    8. build_observation → yield ActionStep + ObservationStep
    9. return_direct检查 → 需要时yield FinalStep提前结束
     
    小沈 2026-06-11
    小欧 2026-07-09: 新增重试通知注入（步骤4-6）
    """
    set_current_task_id(agent.task_id)
    call_result = _build_call_list(parsed)
    step = agent.llm_call_count

    if not call_result.tool_name:
        logger.warning(f"[handle_action] tool_name为空, parsed={parsed}")
        agent._consecutive_reasoning_only = 0  # 2026-07-17 - 小欧 - action空名异常非reasoning-only, 归零防残留
        # chendyg 2026-07-01: 删set_failed，_dispatch_handler从MetaStep(type="error")推断状态
        yield agent._step_emitter.emit(MetaStep(
            step=step, type="error", content="LLM返回的action中tool_name为空", error_type="invalid_action", severity="warn"
        ))
        return

    params_str = str(call_result.tool_params); params_short = (params_str[:180] + '..') if len(params_str) > 180 else params_str  # 小欧 2026-07-01 控制台截断 — 小沈 2026-07-05 50→100
    # 2026-08-30 小欧 收口: 裸print→log_and_print(延续2026-07-23统一治理), 控制台镜像离线化 + [Action]文件留痕增强
    log_and_print(f"{time.strftime('%H:%M:%S')} [Action]step={step} ={call_result.tool_name}, pars:{params_short}")

    # thought 步骤 — content=LLM推理内容, reasoning=内部思维过程 — 小欧 2026-07-01
    yield agent._step_emitter.emit(ThoughtStartStep(step=step))   # 2026-08-18 小欧 thought-start
    yield agent._step_emitter.emit(ThoughtStep(
        step=step,
        content=parsed.get("thought", ""),
        reasoning=parsed.get("reasoning", ""),
    ))

    # #11+#12 fix: 传_out收集通过安全检查的call, 拒绝不终止整批 — 小欧 2026-07-18
    # 2026-08-11 小欧 fix D2: 传_denied_out收集被拒call(tool_name,reason,call), 反馈在build_observation后写
    _safe_calls = []
    _denied_list = []
    async for event in check_safety_and_confirm(agent, call_result.all_calls, step,
                                                call_result.fc_context,
                                                _out=_safe_calls, _denied_out=_denied_list):
        yield event
    _exec_calls = _safe_calls if _safe_calls else []

    # ── 新 action step: execute_tools 执行前 yield 一次（§10.3.3(2)）── 2026-08-18 小欧
    # 记录层兜底: 全部调用被安全拦截致_exec_calls空时, 取意图调用all_calls补全落库(执行层仍仅用_exec_calls, 不绕过安全) - 小欧 2026-08-26
    _record_calls = _exec_calls if _exec_calls else call_result.all_calls
    _action_tools = [{
        "tool": c.get("tool_name", ""),
        "target": _extract_target(c),
        "params": c.get("tool_params", {}) or {},
    } for c in _record_calls]
    yield agent._step_emitter.emit(ActionStep(
        step=step,
        exec_type="single" if len(_action_tools) == 1 else "multi",
        tools=_action_tools,
    ))

    # ── 工具重试（隐蔽，前端不可见）── 小欧 2026-07-13
    # 工具重试由 tool_retry_engine 内部执行, 不向前端 emit 任何 step(北京老陈要求: tool 重试隐蔽)。
    # 重试回调不再收集/上报, 仅后端内部重试。
    # H1 (v1.43): 移除工具批 finally 的 clear_temp_auth() — 清零点迁移到 task 级(R1, react_cycle.run_react_cycle finally)

    # 2026-08-23 #B 闭环(北京老陈 裁定②): 文件A 工厂回调, 每次重试尝试各写一块, 闭合 11.7.9-2 — 小欧 2026-08-23
    # v3.29: 回调内直接落盘(write_tool_block), step=本步 llm_call_count(系统既有字段名); 工厂按全局工具序号闭包注入 tool_no
    # 2026-09-04 小健 第2阶段拆分: 回调工厂下沉 file_persist.make_fp_callback(逻辑完整复制)

    try:
        # #20 修正(2026-08-23 终审): 先定义工厂、调用时传参, 回调内部 file_persist=None 守卫保证无文件任务空转安全 — 小欧 2026-08-23
        results = await execute_tools(agent, _exec_calls, call_result.is_parallel,
                                      call_result.tool_name, call_result.tool_params,
                                      on_attempt_recorded=make_fp_callback(agent, step, _exec_calls))
    except Exception as e:
        logger.error(f"[action_handler] execute_tools 异常: {e}")
        raise

    agent._consecutive_reasoning_only = 0  # 2026-07-17 - 小欧 - 本步LLM发起工具调用(非reasoning-only空转), 归零空转计数

    ctx = ObservationContext(
        agent=agent, all_calls=_exec_calls, results=results, step=step,
        tool_name=call_result.tool_name, tool_params=call_result.tool_params,
        is_parallel=call_result.is_parallel, pending_calls=call_result.pending_calls,
        fc_context=call_result.fc_context,
    )
    # 2026-08-18 小欧 - build_observation 返回 (events, orchestration); 不再传 merged_other
    events, orchestration = await build_observation(ctx)
    for event in events:
        yield event
    # 2026-08-11 小欧 fix D2: 被拒call反馈在build_observation后补写(assistant已由build_observation统一写),
    #   精确到call对象, 不误标会执行的同名工具, 也不重复写assistant
    if _denied_list:
        _add_denial_feedback(agent, _denied_list, call_result.fc_context)
    if orchestration.get("return_direct"):
        for _s in agent._step_emitter.emit_final_with_stats(FinalStep(
            step=step, response=orchestration.get("return_direct_message", ""),
            outcome="completed", reasoning="",
        )):
            yield _s

