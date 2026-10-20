# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 修复: 删known_risk.requires_confirmation死分支
# 2026-07-18 小欧 修复: 删SafetyResult.is_safe死字段
# 2026-07-30 - 小欧 - auto_confirm+绕过时仍查needs_confirmation
# 2026-07-31 - 小欧 - 撤销auto_confirm: 恢复开关关闭时的原绕过路径, 删auto_confirm字段
# 2026-08-04 - 小欧 - 开关关闭仍拒绝已知风险: bypass只跳过确认询问不跳过危险防护, _check_known_risks(路径越权/写入保护/代码注入)检测到即blocked拒绝执行; 普通needs_confirmation仍auto_confirm放行
# 2026-08-04 - 小欧 - 重构DRY: _check_known_risks提到两分支共同入口(无条件防线), 未注册check前置统一; 开关只分流确认策略, 危险防护与开关解耦
# 2026-08-04 - 小欧 - delete专属安全(双轨接入): check_before_execute 一次性计算 delete_risk; R1/R2 仍由 known_risks(_is_forbidden_path)覆盖, R6 入 _check_known_risks 无条件拦截, R3-R5 入 _get_needs_confirmation 确认分流; 惰性导入 delete_safety 避免循环依赖
# 2026-08-04 - 小欧 - fix: _check_known_risks 中 write 的 content 可能为 dict/list(LLM结构化传参), content.encode() 崩溃致误拦; 对齐工具层 check_content_safety 的 dict/list→json 转换
# 2026-08-04 - 小欧 - 撤销dict转json转换方案(YAGNI): 写保护只需量字节数, content为dict/list(非str)走 isinstance(str) 判typeskip(new_size=0), 不崩不误拦且无需转json; 与工具层json转换职责解耦
# 2026-08-10 - 小欧 - 步骤1实施: SafetyResult新增auth_path字段; _check_known_risks白名单外路径(非禁区/系统目录)转为临时授权请求(needs_confirm+auth_path), 由action_handler HITL确认后grant_temp_auth放行
# 2026-08-10 - 小欧 - 修复: delete R6(项目根/授权目录外递归)外层先于 _check_known_risks 判定(if delete_risk.blocked: return), 杜绝R6被白名单临时授权绕过
# 2026-08-10 - 小欧 - 修复: _check_known_risks 白名单外授权请求的 auth_path 改用 validate_tool_path 返回的 failed_path(真正越权参数的真实路径), 不再固定 params.get("path") or params.get("dest")(多路径参数工具 copy/move/compress/extract 越权在dest时原逻辑授权对象错误)
# 2026-08-10 - 小欧 - 实施(第二次代码更新): _check_known_risks 接收 validate_tool_path 4元组(is_valid, msg, failed_path, category); T2 按 category+mode 显式分流(替代 msg 字符串特征判断): category=="system"写删硬拦永不授权 / category=="non_system"写→任务级授权请求 / category==None→白名单外临时授权 / category=="system"/"non_system"且读→放行
# 2026-08-10 - 小欧 - T2 缺陷修复: category=="non_system" 分支未区分写/删, 违反「非系统禁区删硬拦永不授权」; 修复: 按 normalize_tool_name 判断 delete 操作→硬拦 blocked, 写操作保持任务级授权请求
# 2026-08-10 - 小欧 - 写保护判定修复: 原 `tool_name == _WRITE_RISK_TOOL("write")` 用 LLM 原始名, 别名(write_text/writefile等) normalize 前不等于 write → 写入大小保护被绕过; 统一走 normalize_tool_name 再判(与 delete 判定同模式)
# 2026-08-11 - 小欧 - 回归修复: 开关关闭(bypass)时 _check_known_risks 白名单外临时授权请求(needs_confirm+auth_path) 未设 auto_confirm, 仍挂起HITL等确认; E2E自动化无人在线确认→超时→任务failed。修复: 白名单外授权请求在 _is_hitl_bypass()=true 时设 auto_confirm=True 直放
# 2026-08-11 - 小欧 - 全分支补日志: bypass自动放行+各硬拦截统一用log_and_print, 覆盖 工具未注册/delete R6/授权请求bypass直放/已知风险拦截/普通确认bypass/系统禁区删拦/写入大小保护
# 2026-08-11 - 小欧 - bypass自动放行(无需确认) 改为仅 logger.info 不上控制台(高频路径刷屏, 只log不print)
# 2026-08-12 - 小欧 - 越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件 import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - 迁移: validate_tool_path 迁 app/tools/security/path_safe_check(import 同步), SafetyResult dataclass 迁 app/tools/security/safety_result(本文件删除本地定义改 import, __all__ 保留导出)
# 2026-08-16 - 小欧 - 会话信任豁免读取接入: check_before_execute 增 session_id 可选参; needs_confirm 前查 check_session_trust(chat_session_trust), 会话已信任该工具则豁免二次确认(跳 HITL); 危险防护(known_risk blocked)不受豁免仍拦截
# 2026-08-17 - 小健 - 架构修复: 本层不再 import app.services.chat.storage(消除 test_layer_boundaries 守护的 safety→services 反向依赖违规)。会话信任预查上移到调用方(action_handler, services层)查 check_session_trust + normalize_tool_name 后, 本层 check_before_execute 用新增 skip_confirmation 参数(原 session_id 参数移除)接收信任结果豁免确认; 危险防护不受 skip_confirmation 豁免仍拦截。T1 normalize 语义随查询移至 action_handler, 与写保护修复同模式。
# 2026-08-25 - 小欧 - 沙箱预检置位: 四条置位路径在 destructive 级条件成立时置 SafetyResult.sandbox_required=True(白名单外 destructive 写授权请求/路径越权/注册表写 registrywrite/registrydelete 仅静态分析不动态执行/危险型失败 rc!=0 且产生工作区影响或环境性 stderr); 同时 cleanup 分支补 backend.cleanup() 资源泄漏修复; 开关不读此字段(总闸在 executor.pre_execute 单点), 存量 safe 级零感知
# 2026-09-02 - 小欧 - 提示文案准确性优化: _check_known_risks 用户可见 message 与日志串改为"术语保留+人话解释"并存——非系统禁区删/写、系统禁区、白名单外四套文案(措辞见代码); 仅改文案不改逻辑(安全分级/blocked/needs_confirm/auth_path/auto_confirm 一律不变)
# 2026-09-02 - 小欧 - 会话信任功能修复: _check_known_risks 增 skip_confirmation, 信任豁免传参下沉函数内部(替代调用方在函数外预判); 豁免只跳确认不跳危险防护, 系统禁区/路径越权/细粒度危险防护仍无条件 blocked; 豁免保留信任判定所需 auth_path
# 2026-09-18 小欧 - safety_level→severity全量重命名: SafetyResult字段+内部变量+构造调用+比较, 与SSE协议severity对齐
# 2026-09-18 - 小欧 - 10处用户可见文案改写(文案仅可读性, 逻辑/分级/blocked/needs_confirm/auth_path一律不变): "安全开关已绕过，自动确认执行"/"安全检查异常，已阻止执行"/"该路径在受保护区域，禁止删除"/"该路径在受保护区域，会话已信任，允许写入"/"该路径在受保护区域，写入需申请授权"/"该路径在系统禁区，禁止访问"/"该路径超出允许范围，会话已信任，允许操作"/"该路径超出允许范围，需临时授权"/"数据保护: 写入内容远小于原内容，已阻止"(去字节数, 半角逗号统一改全角)
# 2026-09-18 小欧 - 文案精化: message 尾拼 {msg} 会带出 path_safe_check 整句(双主语+双冒号+括号技术元数据), 改拼 failed_path(真实越权路径, 前缀关键词不变故safety_gate分类不受影响), failed_path为空时回退 display msg 保原因; 用户可见 message 干净, 日志仍留 {msg} 完整审计
# 2026-09-18 小欧 - execute_sql 纯读短路: execute_sql 注册 needs_confirmation=True 一刀切, 纯读 SELECT 也弹; _get_needs_confirmation 加纯读短路 _is_readonly_sql(首词 SELECT/SHOW/DESCRIBE/DESC/EXPLAIN/VALUES/TABLE + 单语句才免, 注释头/WITH/PRAGMA/多语句保守回弹窗); 免确认后 severity 走 safe
# 2026-09-18 小欧 - 去bypass写死文案: bypass需确认分支 message 由"安全开关已绕过，自动确认执行"改空串, content由safety_gate承载真实_message组装; auto_confirm=True仍为bypass唯一识别, 语义零变化
# 2026-09-19 小欧 - 无风险shell不弹HITL修复: _get_needs_confirmation 中 check_shell_command_risk 返回 None 时加 return False, 不再穿透到 return tool_meta.needs_confirmation; 恢复"只有MEDIUM弹窗, HIGH拦截, 无风险直接放行"设计(空content弹窗=逻辑错误)
# 2026-09-19 小欧 - HIGH级shell blocked修复: check_before_execute 返回时读 tool_meta._shell_risk_blocked 设置 blocked, HIGH级改为 blocked=True 走拦截(reject消息用 message); MEDIUM/无风险 blocked=False 不变
# 2026-09-19 小欧 - 修复: 经tool_meta动态属性传递shell风险是隐藏副作用, 且 _shell_risk_blocked=True 置位后永不重置, registry单例共享致首个HIGH拦截后同进程后续无风险shell被误拦; 改 _get_needs_confirmation 返回三元组(needs_confirm, shell_msg, shell_blocked)直线传递, 三处调用点解包直接构造SafetyResult, 彻底删除 tool_meta._shell_risk_* setattr/getattr; 同步修复skip_confirmation分支丢弃blocked(会话信任下HIGH shell被放行)
# 2026-10-02 - 小欧 - 注册名收敛: _WRITE_RISK_TOOL 改为 write(写保护判定按新注册名)
# 2026-10-02 - 小欧 - 注册名归位: shell 类风险判定元组 "shell"→"bash"
# 2026-10-08 - 小欧 - 补接从未生效的保护盾: 新增 _protected_pids(): 自身+父进程+shell池; _get_needs_confirmation shell 分支前置 is_process_kill_protected 判定, 命中即 blocked=True 直返。原实现全项目无第二处传 protected_pids, 故 `if protected_pids:` 恒不生效。
# 2026-10-10 - 小欧 - 预检规则死代码缺口修复(三壳并集): check_shell_command_risk(_cmd) 只传 command, shell_type 取默认 "ps7" → cmd(14条)/bash(7条)标签规则全被跳过(实测仅 22/43 条生效), 两层判定口径不一致; 改调 check_shell_command_risk_all_shells(ps7/cmd/bash 各查一遍取最高严重度), 实测召回15条、白名单误伤0/30、日常命令误伤0/24、降级回归0; 同日 is_process_kill_protected 导入点更正为 app.tools.fundamental.shell_static_guard(safety→tools 合法)
# 2026-10-14 - 小欧 - 标注: 本文件=安全总闸 check_before_execute(上游合法性初查/信任预查, 内调 delete_path_check+path_legality_router, 下游 HITL)
# 2026-10-17 - 小欧 - 标注跟改(模块更名): 内调原名 delete_safety→delete_path_check(删线专属判定 check_delete_permission), path_safe_check(已拆)→path_legality_router(路径路由)+path_classify_category(判定单源)。
# 2026-10-14 - 小欧 - SafetyResult import 改 app.tools.tool_types
# 2026-10-15 - 小欧 - 豁免早返: known_risk 之后加豁免早返(不拦且不需确认即原样返回); 原代码会把「无动作」结果强标 severity=dangerous, 与事实相反
# 2026-10-15 - 小欧 - mode 注释订正: 订正为「mode 由 validate_tool_path 内部按 tool_name 自动推断(调用方不传)」。原注释与实际行为相反(实调只传 (tool_name, params) 两个参数, mode 形参默认 None 由被调方内部推断), 误导性注释按实际改写。
# 2026-10-15 - 小欧 - 置位口径订正: 上文所称「四条置位路径」已全部不成立(命中即return不构造结果; 注册表类不动态执行; 其余由executor内部处理)。真实口径=destructive 即置位, safe/dangerous 不触发。
# 2026-10-16 - 小欧 - 工具未注册单列 tool_unavailable: 告知"工具不可用", 不再报成路径越权。须显式命中, 漏掉会掉进"白名单外路径"分支变成可授权 = 安全放宽。
# 2026-10-16 - 小欧 - 主链重排三级串联: 自杀→danger拒→risk确认→路径权限; 删两处重复判定
# 2026-10-16 - 小欧 - severity destructive→risk(纯改名): 旧值被删除类与中风险类共用; 沙箱判定同步, 行为不变
# 2026-10-16 - 小欧 - tool去检查化: 工具层注释"validate先于本函数执行"订正(门前初查是唯一合法性检查点, 工具只执行+业务警告)。
# 2026-10-17 - 小欧 - delete 专属判定调用点 check_delete_risk → check_delete_permission(封装口, 内部含 guard+validate_delete+check_delete_risk); 本层仍只消费结果(blocked 硬拦 / needs_confirm 进确认), 调用关系不变。
# 2026-10-17 - 小欧 - 未注册判定收口上游: 未注册判定收口到解析层(删本层未注册分支); 删 category="tool_unavailable" 死分支(路径层已不产出)。
# 2026-10-17 - 小欧 - 总闸固化: 总闸固化顺序 + 去双跑 + 去 skip — 删 delete 顶部预计算(唯一一处=路径层删线); 权限段统一走 _check_known_risks 单点(delete 亦走此单点); 确认段删 skip_confirmation 分支(信任预查移入调用方确认层); _get_needs_confirmation 去 delete_risk; _check_known_risks 直返 SafetyResult(调 check_tool_path_permission); import 别名正名; 精简 _medium 冗余条件。SafetyResult 保持原 import。
# 2026-10-17 - 小欧 - _medium 冗余条件: `and _medium.requires_confirmation` 删(契约: check_shell_risk_command_all_shells 只返 needs_confirm=True 或 None)。
# 2026-10-18 - 小欧 - 总闸随契约调整同步: 沙箱标记改读 needs_confirm, 删 severity 中间变量 —— 原式由 needs_confirm 推导 severity 再反推 sandbox_required 是纯冗余回环, 且 severity 字段已废; 到达此处者已排除 blocked(恒为需确认的授权请求), 两式恒等行为不变; 五处构造点补 safety_level 问题来源分类(未注册/工具级确认/自杀拦截), 使分类由决策点直给而非上层反查文本; 两处属性读取随字段改名同步。
# 2026-10-18 - 小欧 - SafetyResult 契约回迁系统层: import 改 app.safety.safety_result(生产者全在本层, 契约随生产者), 判定/构造零改动。
# 2026-10-18 - 小欧 - 确认标签改为按工具名/命令实际动作直给(SafetyLevel), 不再由上层按文案反查:
#   新增 _TOOL_CONFIRM_LEVEL(execute_sql→SQL_EXECUTE_CONFIRM; create_task/delete_task→TASK_DEAL_CONFIRM;
#   registry_write/delete→REGISTRY_DEAL_CONFIRM; 未列出→TOOL_CONFIRM)。
#   未列出的工具归 SHELL_COMMAND_CONFIRM 会让一个写类工具弹窗显示"命令确认", 标签与实际动作不符。
#   新增 shell_confirm_level(按 parse_shell_action 解析出的实际读/写/删动作取档, 多动作并存取最严一档,
#   无路径动作归 SHELL_COMMAND_CONFIRM; 解析异常亦归整条命令级并 warning 记录, 不退化成猜值);
#   新增 confirm_level_for(工具级标签唯一出口, bypass 分支与主 return 共用, 防同表达式写两遍漂移)。
#   硬拦标签同步入枚举: 未注册→BLOCK_UNREGISTERED; 自杀拦截→BLOCK_COMMAND。
#   沙箱预检触发口径、判定顺序与放行条件零变更。
# 2026-10-18 - 小欧 - 本层不再消费 auth_path 定分类: 标签留空交调用方按文案关键词回填会使"标签"取决于"文案怎么写",
#   改一个字换一个分类; 产地已归位到本层与各判定分支。
# 2026-10-18 小欧 - bash 确认策略不再硬拒: _get_needs_confirmation 的 shell 分支原在 check_shell_command_risk
#   返回 None 时 return False, 白名单外的一律只读命令被误判"无风险"而绕过确认; 改为 return tool_meta.needs_confirmation,
#   由注册表的 needs_confirmation 表达"要不要问", 风险判定只管拦不拦(另走 blocked), 二者不再互相吞掉。
#   同批: _is_hitl_bypass 的开关键名跟定为 security.hitl.enabled; 注释精简冗余标注, 技术说明原样保留。
# 2026-10-18 - 小欧 - hitl.enabled 使用点收敛为单点: 原三处确认产地各调一次 _is_hitl_bypass()
#   (中风险命令/路径授权请求/工具级确认), 同一策略三处各判一遍(DRY 违规, 将来新增确认产地必漏)。
#   改函数入口读一次 _bypass, 三处确认产地直线赋值 auto_confirm=_bypass(中风险/路径为原地赋值,
#   工具级并入统一 return), 删除 bypass 独立分支与其重复日志。硬拦(未注册/自杀/危险命令/blocked)
#   一律在前段 return 不受影响。语义零变化: auto_confirm 仅在 needs_confirm 时置位, 只免"要不要问",
#   不改 blocked/safety_level。
# 2026-10-18 小欧 - 确认产地收尾单源化: 新增 _settle_confirm(), 三处确认产地(中风险命令/路径越权
#   授权请求/工具级确认)统一调它定 auto_confirm 与 sandbox_required。此前三处各写一遍, 语义等价
#   但形态三种(硬编码 True / 读 needs_confirm / 短路表达式), 后人新增加确认产地无参照可抄,
#   易抄错"该走沙箱却没走"这一格。现一处定口径, 新增加产地只需调它。
# 2026-10-18 小欧 - 确认路径日志不再上控制台: 两处"转确认"日志的 bypass 值由 log_and_print 改
#   logger.info(硬拦仍留 log_and_print —— 那是用户该看见的终端事件; 确认路径属高频, 控制台刷屏)。
# 2026-10-18 小欧 - 注释订正: check_before_execute 头注的开关表述改为覆盖三处确认产地
#   (原文只说"普通 needs_confirmation", 会让人以为中风险命令不归开关管, 与实际不符)。
# 2026-10-19 小欧 - bash 分支回退硬 return False: 10-18 改为 return tool_meta.needs_confirmation
#   (恒True)致全量 bash 命令 needs_confirm=True; 确认标签产地在 confirm_level_for, 不依赖本分支,
#   该改动依据不成立, 回退。confirm_fn 返 None 不再短路 needs_confirmation, 留文案后交后续分档分支。
# 2026-10-19 小欧 - 入口路径格式化+绝对化(唯一路径处理点): 在 directory_lists_scope 内(名单已建)、
#   _check_before_execute 前, 对非 shell 工具的 path/dest 就地绝对化+format_path; 相对值按工具基准
#   (rename→源父目录, download→下载目录, 其余→project_root);
#   键名不变, 下游各线与执行层零改动。删 resolve_path_param(路径解析双源), 收口到本入口单点。
# 2026-10-19 小欧 - 修复入口格式化误伤非路径工具: _format_tool_paths 原对**所有**到达本入口的工具
#   改写 path/dest; 经 tool_facade.execute_tool(/tool/execute)直调时, registry_read/write/delete
#   (WIN_REGISTRY 工具)的 path 是注册表键, 被改写成 project_root 下的文件路径(实测 'HKLM\\SOFTWARE\\Microsoft'
#   → 'E:\\test_dir\\HKLM\\SOFTWARE\\Microsoft')。现仅在 tool_name ∈ PATH_TOOLS 时格式化。
"""
工具安全检查器 — 执行前安全检查（Safety层入口）

Safety层（本文件 + path_classify_category/path_env/path_legality_router）：
  - 路径黑名单/白名单校验（classify_forbidden_path → 三线 validate）
  - 路径穿越(..)拒绝
  - 写入大小保护
  - 二元安全确认(needs_confirmation)
  - 已知风险检测(路径越权/写入污染)

工具层（validate/content_safety.py + validate/tool_module_checker.py + validate/file_path_checker.py + validate/file_type_checker.py）独立运行、互不调用：
  - check_content_safety: 内容安全检查（None/空/null字节/类型/append冲突）
  - for_write/delete/overwrite: 纯业务警告（大文件/追加超大/递归/强制/覆盖提示；合法性与权限 100% 归 Safety，见 2026-10-16 tool去检查化）
  - check_file_type: 文件类型检查（文本/媒体/文档/压缩）
  - check_tool_module: 依赖库安装检查
  - check_office_file: 类型+模块安全二位一体（路径合法性归门前初查）

Layer 2: 二元安全确认(needs_confirmation)
Layer 3: 已知风险检测(路径越权/写入污染/代码注入)

2026-06-16 小沈 删除5级枚举，改用二元安全
2026-06-17 小沈 删除record_operation/execute_with_safety委托(打破tools→safety循环依赖)，
             路径校验改用同包 safety 模块(打破safety→tools循环依赖)
2026-07-04 小欧 补充两层架构说明注释
2026-07-09  补充validate层完整函数清单
"""


import os
from typing import Dict, Optional

from app.logger import logger, log_and_print
from app.config import get_config
from app.tools.registry import tool_registry
from app.safety.path_legality_router import (
    check_tool_path_permission as _check_tool_path_permission,  # 2026-10-17 小欧 - C5 正名(原 validate_tool_path as _validate_tool_path)
    LINE_DELETE, LINE_DUAL, LINE_WRITE, line_of,  # 2026-10-20 小欧 - 归线/确认开关: 归线口径唯一来源
)
from app.safety.shell_process_guard import check_shell_self_kill  # 2026-10-16 小欧: 自杀检查唯一入口(判定全在 guard 层); 快照组装下沉同层, 本文件不再碰 shell_engine
from app.safety.shell_parse import parse_shell_action  # 命令动作解析单一真源: 确认标签按命令内实际读/写/删动作取档
from app.safety.safety_result import SafetyLevel, SafetyResult  # 契约: 安全层单源
# 2026-10-19 小欧 - 目录名单收口: 每 loop 构建一次目录名单, 作用域内自动还原; 入口对 tool 路径做格式化
from app.safety.path_dir_lists import directory_lists_scope, format_path
from app.tools.tool_constants import PATH_TOOLS  # 2026-10-19 小欧 - 入口格式化范围门: 仅路径工具改写 path/dest
from app.safety.safety_switch import safety_enabled, safety_switch  # 2026-10-20 小欧 - 总闸 + 各独立开关唯一读取口
from app.utils.path_utils import absolutize_path, get_download_dir  # 2026-10-19 小欧 - 入口相对值绝对化(基准=project_root)+下载目录基准; 均为工具层公用, 不反向依赖工具

_READONLY_SQL_FIRST = {"select", "show", "describe", "desc", "explain", "values", "table"}


#: 工具名 → 确认标签(工具元数据确认策略的分类单源) — 小欧 2026-10-18
#: 语义: 这些工具的"需确认"是**整条调用级**的(无具体路径动作), 故不进路径三线标签,
#: 按工具域各给一个标签; 域内同义工具共用一个标签。
#:   execute_sql    → SQL 执行确认
#:   task 类        → 任务处理确认
#:   registry 类    → 注册表处置确认
#: 未列出的工具 → TOOL_CONFIRM(工具级确认的缺省值)。
#:   不可归 SHELL_COMMAND_CONFIRM: 那样一个写类工具会弹窗显示"命令确认", 标签与实际动作不符。
_TOOL_CONFIRM_LEVEL: Dict[str, str] = {
    "execute_sql": SafetyLevel.SQL_EXECUTE_CONFIRM,
    "create_task": SafetyLevel.TASK_DEAL_CONFIRM,
    "delete_task": SafetyLevel.TASK_DEAL_CONFIRM,
    "registry_write": SafetyLevel.REGISTRY_DEAL_CONFIRM,
    "registry_delete": SafetyLevel.REGISTRY_DEAL_CONFIRM,
}
TOOL_CONFIRM_DEFAULT = SafetyLevel.TOOL_CONFIRM

#: 线 -> 确认开关(读线不产生确认; shell 线不进此表: shell_path_confirm 只管路径判定) — 小欧 2026-10-20
_CONFIRM_SWITCH = {
    LINE_WRITE:  "security.hitl.write_confirm",
    LINE_DELETE: "security.hitl.delete_confirm",
    LINE_DUAL:   "security.hitl.dual_path_confirm",
}


def _confirm_ok(tool_name: str) -> bool:
    """该线确认开关是否开启; 无线名(读线/shell 线)按开处理"""
    key = _CONFIRM_SWITCH.get(line_of(tool_name) or "")
    return True if key is None else safety_switch(key)


_SHELL_TOOLS = frozenset({"bash", "execute_shell_command", "execute_command"})

#: 命令动作 → 确认标签。取值为 shell_parse.action.ACTION_KINDS 的**全部 3 种**(read/write/delete,
#:   闭合枚举, PathAction.__post_init__ 对枚举外值 raise, 故不存在第 4 种动作)。
#:   多动作并存时取最严一档(删 > 写 > 读), 与 shell_path_check._judge_actions 的判定优先级同序。
_SHELL_KIND_LEVEL: Dict[str, str] = {
    "delete": SafetyLevel.SHELL_DELETE_CONFIRM,
    "write": SafetyLevel.SHELL_WRITE_CONFIRM,
    "read": SafetyLevel.SHELL_READ_CONFIRM,
}


def shell_confirm_level(command: Optional[str], shell_type: Optional[str], cwd: Optional[str]) -> str:
    """命令类工具的确认标签 — 按命令内**实际的路径动作**(读/写/删)取档 — 小欧 2026-10-18

    命令内无任何路径动作(如 `npm install`)时, 无动作可依, 归 shell_command_confirm(整条命令级)。
    动作解析复用 shell_parse 单一真源, 本函数只做"动作集合 → 标签"映射, 不判权限。
    """
    if not isinstance(command, str) or not command.strip():
        return SafetyLevel.SHELL_COMMAND_CONFIRM
    try:
        actions = parse_shell_action(command.replace("\r\n", "\n"),
                                     shell_type or "ps7", cwd)
    except Exception:                      # 解析异常不得让标签退化成猜值: 归整条命令级, 判定仍在别处
        logger.warning("[PathToolSafetyChecker] 命令动作解析失败, 确认标签归整条命令级")
        return SafetyLevel.SHELL_COMMAND_CONFIRM
    for kind in ("delete", "write", "read"):     # 顺序即严格度, 不复用 ACTION_KINDS 以固定优先级
        if any(a.kind == kind for a in actions):
            return _SHELL_KIND_LEVEL[kind]
    return SafetyLevel.SHELL_COMMAND_CONFIRM


def confirm_level_for(tool_name: str, params: Optional[dict]) -> str:
    """工具级确认标签的唯一出口 — 命令类按动作取档, 其余按工具名映射 — 小欧 2026-10-18

    bypass 分支与主 return 两处共用本函数, 避免同一表达式写两遍(DRY)导致两处漂移。
    """
    _p = params or {}
    if tool_name in _SHELL_TOOLS:
        return shell_confirm_level(_p.get("command"), _p.get("shell_type"), _p.get("cwd"))
    return _TOOL_CONFIRM_LEVEL.get(tool_name, TOOL_CONFIRM_DEFAULT)


def _is_readonly_sql(sql: str) -> bool:
    """execute_sql 纯读短路(2026-09-18 小欧): 首词纯读关键字 + 单语句(无分号)才免确认。
    保守策略(宁弹不错): 注释头(--//*/#)/WITH(可藏写)/PRAGMA(部分可写)/多语句/空串一律不免, 回注册 True 弹窗"""
    s = (sql or "").strip().lower()
    if not s or s.startswith(("--", "/*", "#")):
        return False
    if ";" in s:
        return False
    parts = s.split(None, 1)
    if not parts:
        return False
    return parts[0].lstrip("(") in _READONLY_SQL_FIRST


def _is_hitl_bypass() -> bool:
    """人工确认旁路开关 — 只读 config.yaml security.hitl.enabled

    返回 True 只免人工确认询问(HITL 弹窗); 硬拦不受影响: 工具未注册/自杀检查/
    危险命令/路径禁区/删根硬底线 一律照旧。开关只决定"要不要问用户",
    不决定"要不要拦"。
    """
    try:
        return not get_config().get("security.hitl.enabled", True)
    except Exception:
        return False


def _format_tool_paths(tool_name: str, params: Optional[Dict]) -> None:
    """入口路径格式化+绝对化(唯一路径处理点): 把工具 path/dest 统一到与目录名单同格式(键名不变) — 小欧 2026-10-19

    唯一接入点: 非 shell 路径工具到此已过合法性初查, 在此把参数值就地绝对化 + format_path;
    下游读/写/删/dual 各线与执行层拿到的已是绝对且统一格式, 不再各自解析(解析双源已删)。
    · 绝对 → 原样; 相对 → 按基准绝对化(公用 absolutize_path(value, base))。
    · 基准缺省 = tool 工作区(project_root); 工具专属语义(下载目录 / rename 源父目录)仅在此一声明:
        download.dest → 下载目录 + 原值; rename.dest → 源父目录 + 新文件名(basename, 与工具 Path(dest).name 一致)。
    · 最终统一 format_path; 不做路径穿越处理(交安全线/工具自持判定)。
    · shell 工具无 path/dest 键, 天然不命中。
    """
    if not params:
        return
    for key in ("path", "dest"):
        value = params.get(key)
        if not isinstance(value, str) or not value.strip():
            continue
        base = get_config().get_project_root()
        if tool_name == "download" and key == "dest":
            base = get_download_dir()
        elif tool_name == "rename" and key == "dest":
            src = params.get("path")
            if isinstance(src, str) and src:
                base, value = os.path.dirname(src), os.path.basename(value)
        params[key] = format_path(absolutize_path(value, base))


class PathToolSafetyChecker:
    """工具执行前安全检查 — 确认判定 + 已知风险检测"""

    def check_before_execute(self, tool_name: str, params: Optional[Dict] = None,
                             pool_pids: Optional[set] = None) -> SafetyResult:
        """
        [4] 执行前安全检查总闸入口（Safety层）—— 危险+权限段, 固定顺序不分叉
        上游: [2] 处理范围门(仅 PATH_TOOLS 到此) → [3] 合法性初查(格式+存在性, 工具层不再复查)
        本层: [4-0] 自杀检查 → [4-1] 危险命令组 → [4-2] 权限三线(读/写/删唯一入口)
        下游: blocked→拒; needs_confirm→交 [5] 确认层(信任豁免/HITL) → [6] 沙箱预检执行
        路径黑名单/白名单/路径穿越/写入大小保护/二元确认均在本段内

        人工确认旁路开关: config.yaml security.hitl.enabled=false 时免全部确认询问
        (三处确认产地: 中风险命令 / 路径越权授权请求 / 工具级确认), 硬拦照旧
        2026-08-04 小欧: 已知风险(路径越权/写入保护/代码注入)无条件检测不管开关, 危险即拒绝执行(blocked);
            开关false仅免确认询问, 开关true则正常询问
        2026-08-17 小健 分层修正: 会话信任预查从本层移至调用方(action_handler, services层),
            本层不再依赖 app.services.chat.storage(消除 safety→services 违规);
            调用方查 trust 后传 skip_confirmation=True 豁免确认询问(危险防护仍生效) — 小健 2026-08-17
        安全总闸: 上游合法性初查/信任预查, 内调删线/路径层, 下游 HITL 确认 — 小欧-2026-10-14
        """
        # 安全模块总闸: 入口短路, 关闭则不做任何权限判定直接放行 — 小欧 2026-10-20
        if not safety_enabled():
            return SafetyResult.pass_result()
        # 2026-10-18 小欧 - security.hitl.enabled 唯一使用点: 入口读一次, 三处确认产地直用 _bypass。
        #   开关只免"要不要问", 硬拦(未注册/自杀/危险命令/blocked)一律在本函数前段 return, 不受影响。
        _bypass = _is_hitl_bypass()
        # 2026-10-19 小欧 - 目录名单收口: 一个安全模块 loop = 一次 check_before_execute,
        #   故本函数进入目录名单作用域(构建点唯一, 作用域内自动还原)。
        #   上下文管理器可嵌套: 外层(safety_gate)已开作用域时直接复用现有名单, 不二次构建 ——
        #   "每 loop 一次"由作用域在结构上保证, 调用方无从违反。
        # 2026-10-20 小欧 - 名单构建/判定异常 fail-closed: 异常上抛, 由本层单点转 blocked,
        #   即使调用方绕过 safety_gate 直调, 也不会以残缺名单放行。
        try:
            with directory_lists_scope():
                # 仅路径工具做入口格式化: 非路径工具(如 registry_read/write/delete)的 "path" 是注册表键
                #   等非文件路径, 改写会把其变成 project_root 下的文件路径(2026-10-19 实测)。
                if tool_name in PATH_TOOLS:
                    _format_tool_paths(tool_name, params)
                return self._check_before_execute(tool_name, params, pool_pids, _bypass)
        except Exception as e:
            logger.error(f"[PathToolSafetyChecker] 目录名单构建/判定异常(硬拦 fail-closed): "
                         f"tool={tool_name}, {e!r}")
            return SafetyResult(blocked=True, message=f"目录名单构建失败, 拒绝执行: {e}",
                                safety_level=SafetyLevel.BLOCK_COMMAND)

    def _check_before_execute(self, tool_name: str, params: Optional[Dict],
                              pool_pids: Optional[set], _bypass: bool) -> SafetyResult:
        """check_before_execute 的判定主体 — 小欧 2026-10-19 拆出(loop 内名单已由外层建好)"""
        # 2026-10-17 小欧 - 未注册判定已收口解析层, 本层不再复判(只放 PATH_TOOLS 工具到此)。
        # 2026-10-18 小欧 - 复判补回(fail-closed, 真回归修复): 上条"不再复判"判断有误 —— 解析层只管
        #   Agent 管线进来的 call, tool_facade/测试等直调方仍会带未注册工具名进来, tool_meta=None 一路
        #   传到 _get_needs_confirmation 解引用即崩(2026-10-18 全量 pytest 实锤:
        #   test_deep_flow_bugs f5_01/f5_02 AttributeError: 'NoneType' object has no attribute 'name')。
        #   未注册 = 无元数据 = 无法定确认策略与权限线, 只能拒(fail-closed), 不按任一条线推定放行。
        tool_meta = tool_registry.get_tool(tool_name)
        if tool_meta is None:
            log_and_print(f"[PathToolSafetyChecker] 工具未注册(硬拦): tool={tool_name}")
            return SafetyResult(blocked=True, message=f"工具未注册: {tool_name}",
                            safety_level=SafetyLevel.BLOCK_UNREGISTERED)

        # [4-0] 自杀检查(2026-10-16): 提到 _check_known_risks 之前
        #   理由: 自杀与路径/危险等级无关, 且一旦执行后续所有检查皆无意义(实测曾致后端自杀);
        #   放在门首 = 排在危险命令与路径权限之前, 不给任何绕过空间。
        #   判定全在 shell_process_guard.check_shell_self_kill(只答通过/不通过), 本层只出结果与文案。
        if (params or {}).get("command"):
            self_kill = PathToolSafetyChecker._check_shell_kill(
                (params or {}).get("command", ""), pool_pids)
            if self_kill is not None:
                log_and_print(f"[PathToolSafetyChecker] 自杀检查拦截(硬拦): {self_kill.message}")
                return self_kill

        # [4-1] 危险命令组(2026-10-16 定序, 任一命中即返回, 互不穿透):
        #   自杀检查 → danger(危险, 拒绝) → risk(中风险, 进 HITL 确认) → 路径权限
        #   risk 必须排在路径权限之前: 命令既是中风险又路径越权时, 先问"危不危险"再问"能不能动" ——
        #     如 `Start-Process C:\Windows\x`: 按本顺序 → risk 命中, 进 HITL 用户确认即可;
        #     若路径权限在前 → 直接拒绝, 用户连确认机会都没有(语义过重)。
        #   两个风险层都只答"危不危险/要不要确认", 不含任何路径判定(见各自模块头的边界约定)。
        if (params or {}).get("command"):
            _cmd = (params or {}).get("command", "")
            # 两个开关各自独立: 关则跳过本项检查, 不影响另一项与路径判定 — 小欧 2026-10-20
            # 危险命令: 命中即拒绝执行
            #   2026-10-16: 删冗余的 `and _danger.blocked` —— 降级机制移除后
            #   check_shell_danger_command 只会返回 blocked=True 或 None, 该条件恒等价于判非空。
            if safety_switch("security.system.shell_danger_block"):
                from app.safety.shell_danger_command import check_shell_danger_command_all_shells
                _danger = check_shell_danger_command_all_shells(_cmd)
                if _danger is not None:
                    log_and_print(f"[PathToolSafetyChecker] 危险命令拦截: tool={tool_name}, {_danger.message}")
                    return _danger
            # 中风险命令: 命中进 HITL 确认
            if safety_switch("security.system.shell_risk_block"):
                from app.safety.shell_command_risk import check_shell_risk_command_all_shells
                _medium = check_shell_risk_command_all_shells(_cmd)
                if _medium is not None:
                    logger.info(f"[PathToolSafetyChecker] 中风险命令转确认: tool={tool_name}, bypass={_bypass}, {_medium.message}")
                    return self._settle_confirm(_medium, _bypass)   # 与 shell_path_confirm 无关

        # [4-2] 权限三线(按动作分派读/写/删; 唯一入口, delete 亦走此单点) — 小欧 2026-10-17
        #   无条件防线(开关无关): 越权/禁区/delete 判定即便开关 false 也拒绝。
        known_risk = self._check_known_risks(tool_name, params or {})
        if known_risk is not None:
            if known_risk.blocked:
                log_and_print(f"[PathToolSafetyChecker] 权限硬拦截(危险拒绝执行): tool={tool_name}, {known_risk.message}")
                return known_risk
            # needs_confirm=True: 授权请求, 交确认层(信任/HITL)
            logger.info(f"[PathToolSafetyChecker] 授权请求转确认: tool={tool_name}, auth_path={known_risk.auth_path}, bypass={_bypass}, {known_risk.message}")
            return self._settle_confirm(known_risk, _bypass or not _confirm_ok(tool_name))

        # 确认策略分流: hitl.enabled 只影响"是否询问确认", 不影响危险防护
        # 2026-10-18 小欧: 去 bypass 独立分支 —— 原 bypass 分支(需确认→auto_confirm=True /
        #   无需确认→message="安全开关已绕过")与常规分支各写一遍, 现统一为一遍, auto_confirm
        #   由入口读到的 _bypass 直线给出(仅 needs_confirm 时置位)。
        needs_confirm, _shell_msg = self._get_needs_confirmation(tool_meta, params or {})
        # 仅需确认级触发沙箱; 免确认不进预检
        # 2026-10-18 小欧: 删 severity 中间变量(纯冗余回环), 沙箱标记直读 needs_confirm
        # 2026-10-18 小欧: 确认标签按工具名在本层直给(_TOOL_CONFIRM_LEVEL), 不再留空等调用方
        #   按文案关键词反查 —— 那条链会让"标签"取决于"文案怎么写", 改一个字就换一个分类。
        #   本出口是"整条调用级"确认(无路径动作); 命令内路径的读/写/删已由 shell_path_check
        #   派三线标签(WRITE_PROTECTED / DELETE_* 等), 二者不重复编码。
        return self._settle_confirm(
                SafetyResult(needs_confirm=needs_confirm,
                        blocked=False, message=_shell_msg or "",
                        safety_level=confirm_level_for(tool_name, params) if needs_confirm else ""),
                _bypass or not _confirm_ok(tool_name))

    @staticmethod
    def _settle_confirm(result: SafetyResult, bypass: bool) -> SafetyResult:
        """确认产地统一收尾 —— 中风险命令 / 路径授权请求 / 工具级确认 三处共用同一口径

        auto_confirm 只免"要不要问", 一律不改 blocked/safety_level/message;
        沙箱预检口径单源: 需确认即需预检。
        口径分三处各写一遍时后人新增加确认产地无参照可抄, 必然抄错 auto_confirm/sandbox_required
        的组合(该走沙箱却没走 / 不该走却走了), 故收口于此。
        """
        result.auto_confirm = result.needs_confirm and bypass
        result.sandbox_required = result.needs_confirm
        return result

    @staticmethod
    def _check_shell_kill(cmd: str, pool_pids: Optional[set] = None) -> Optional["SafetyResult"]:
        """shell 自杀检查单步 — 小欧 2026-10-16

        2026-10-16 小欧 自杀检查全部归并到 app/safety/shell_process_guard.py,
          本方法只调其唯一入口 check_shell_self_kill(只答通过/不通过), 不通过时由本层出
          SafetyResult 与文案 —— 判定在 guard 层, 返回与话术在本层(SRP 分离)。
        命中受保护 PID/进程名/无目标兜底即 blocked，直返不经确认分流。
        """
        if check_shell_self_kill(cmd, pool_pids):
            return SafetyResult(blocked=True, message="系统保护进程，禁止终止", safety_level=SafetyLevel.BLOCK_COMMAND)
        return None

    @staticmethod
    def _get_needs_confirmation(tool_meta, params: Dict) -> tuple:
        """获取生效的确认策略：action级 > 工具级 — 小欧 2026-08-04
        2026-10-16 小欧 - 本函数只答“要不要确认”，不再答“拦不拦”——回二元组。
        shell 危险拦截（杀/HIGH）已归位 _check_known_risks（无条件防线）；此处 MEDIUM 只产弹窗文案。
        2026-10-17 小欧 - 删 delete_risk（delete 确认由权限三线删线封装口 check_delete_permission 产出）。"""
        from app.tools.tools_alias_mapper import normalize_tool_name  # 延迟导入(同240行模式, 防别名漏判) — 小欧-2026-09-18
        if normalize_tool_name(tool_meta.name or "") == "execute_sql" \
                and _is_readonly_sql((params or {}).get("sql", "")):
            return False, ""  # 2026-10-18 小欧: 纯读免确认; 非只读交工具层 confirm_fn 逐条判定
        _why_text = ""
        if getattr(tool_meta, "confirm_fn", None):
            # 2026-10-18 小欧 - 工具级确认回调: 只调不判, 异常按需确认收(fail-closed)
            # 契约: 返回 (bool|None, str) = 要否确认 + 弹窗文案
            #   bool = 回调自行判定(execute_sql 按 SQL 逐条判)
            #   None = 回调不表态, 只供文案, 判定交后续分档分支(bash 即此档) — 2026-10-19 小欧改判据
            try:
                _ok, _why = tool_meta.confirm_fn(params or {})
            except Exception as exc:
                logger.warning(f"[PathToolSafetyChecker] confirm_fn 异常, 按需确认收: "
                               f"tool={tool_meta.name}, {exc!r}")
                return True, ""
            if _ok is not None:
                return bool(_ok), (str(_why or ""))
            _why_text = str(_why or "")
        if normalize_tool_name(tool_meta.name or "") in ("bash", "execute_command"):
            # 2026-10-19 小欧 - 恢复硬 return False: 危险/中风险/路径动作由主链三线判定, 标签由 confirm_level_for 产出
            # 2026-10-20 小欧 - 维持硬 return False(回归矩阵裁决权威): 危险/中风险/路径三线
            #   已在主链先行判定, 走到这里=全链放行; 若 return tool_meta.needs_confirmation 会使
            #   bash 恒弹确认(包括白名单内写/建目录), E2E 实锤: 无人应答 120s×2 超时, 任务挂死失败
            #   (agent 被迫往 HITL 无底洞重复试探)。矩阵白名单下级写=PASS 是设计值, 兜底不得加弹。
            #   危险链产出的确认窗不受影响(那层自带 needs_confirm=True 返回, 到不了这里)。
            return False, _why_text
        if tool_meta.action_confirmation and params.get("action"):
            return tool_meta.action_confirmation.get(
                params["action"], tool_meta.needs_confirmation), ""
        return tool_meta.needs_confirmation, ""

    @staticmethod
    def _check_known_risks(tool_name: str, params: Dict) -> Optional["SafetyResult"]:
        """路径权限检测: 按路径层路由分派到读/写/删三线封装口 — 小欧 2026-10-17(格式化)

        2026-10-17 小欧 - category 分流(system/non_system/None)已下沉三线封装口;
        2026-10-18 小欧 - 字段随契约改名同步: 命中 blocked/needs_confirm 即返回, 否则 None。
        写入大小保护归工具层(file_path_checker.validate_path_for_overwrite), 本层不判。
        """
        risk = _check_tool_path_permission(tool_name, params)   # 路径层 → SafetyResult(三线封装口)
        if risk.blocked or risk.needs_confirm:
            return risk
        return None


_checker: Optional[PathToolSafetyChecker] = None


def get_path_tool_safety_checker() -> PathToolSafetyChecker:
    global _checker
    if _checker is None:
        _checker = PathToolSafetyChecker()
    return _checker


__all__ = ["SafetyResult", "PathToolSafetyChecker", "get_path_tool_safety_checker"]
