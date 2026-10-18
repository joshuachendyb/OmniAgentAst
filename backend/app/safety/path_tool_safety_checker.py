# -*- coding: utf-8 -*-
# 编辑历史:
# 2026-07-18 小欧 修复: 删known_risk.requires_confirmation死分支
# 2026-07-18 小欧 修复: 删SafetyResult.is_safe死字段
# 2026-07-30 - 小欧 - auto_confirm+绕过时仍查needs_confirmation
# 2026-07-31 - 小欧 - 撤销auto_confirm: 恢复security.enabled=false原绕过路径, 删auto_confirm字段
# 2026-08-04 - 小欧 - 开关false仍拒绝已知风险: bypass只跳过确认询问不跳过危险防护, _check_known_risks(路径越权/写入保护/代码注入)检测到即blocked拒绝执行; 普通needs_confirmation仍auto_confirm放行 — 北京老陈驱动
# 2026-08-04 - 小欧 - 重构DRY: _check_known_risks提到两分支共同入口(无条件防线), 未注册check前置统一; 开关只分流"确认策略", 危险防护与开关解耦 — 三堂会审驱动(合规SRP/DRY/KISS最优)
# 2026-08-04 - 小欧 - delete专属安全(双轨接入): check_before_execute 一次性计算 delete_risk; R1/R2 仍由 known_risks(_is_forbidden_path)覆盖, R6 入 _check_known_risks 无条件拦截, R3-R5 入 _get_needs_confirmation 确认分流; 惰性导入 delete_safety 避免循环依赖 — 北京老陈驱动(设计文档 v1.15)
# 2026-08-04 - 小欧 - fix: _check_known_risks 中 write 的 content 可能为 dict/list(LLM结构化传参), content.encode() 崩溃致误拦; 对齐工具层 check_content_safety 的 dict/list→json 转换 — E2E 回归发现
# 2026-08-04 - 小欧 - 三堂会审(YAGNI)撤销转换方案: 写保护只需量字节数, content为dict/list(非str)走 isinstance(str) 判typeskip(new_size=0), 不崩不误拦且无需把dict转json; 与工具层json转换职责解耦 — 北京老陈审出多余转换
# 2026-08-10 - 小欧 - 步骤1实施(⑮, 北京老陈驱动「项目根=tool工作区, 代码库根=tool禁区」): SafetyResult新增auth_path字段; _check_known_risks白名单外路径(非禁区/系统目录)转为临时授权请求(requires_confirmation+auth_path), 由action_handler HITL确认后grant_temp_auth放行
# 2026-08-10 - 小欧 - 修复: delete R6(项目根/授权目录外递归)外层先于 _check_known_risks 判定(if delete_risk.blocked: return), 杜绝R6被白名单临时授权绕过
# 2026-08-10 - 小欧 - 修复: _check_known_risks 白名单外授权请求的 auth_path 改用 validate_tool_path 返回的 failed_path(真正越权参数的真实路径), 不再固定 params.get("path") or params.get("dest")(多路径参数工具 copy/move/compress/extract 越权在dest时原逻辑授权对象错误) — 小欧 2026-08-10
# 2026-08-10 - 小欧 - 实施(第二次代码更新, 基于设计框架): _check_known_risks 接收 validate_tool_path 4元组(is_valid, msg, failed_path, category); T2 按 category+mode 显式分流(替代 msg 字符串特征判断): category=="system"写删硬拦永不授权 / category=="non_system"写→任务级授权请求 / category==None→白名单外临时授权 / category=="system"/"non_system"且读→放行
# 2026-08-10 - 小欧 - T2 缺陷修复(三堂会审关联逻辑复核发现): category=="non_system" 分支未区分写/删, 违反「非系统禁区删❌硬拦永不授权」; 修复: 按 normalize_tool_name 判断 delete 操作→硬拦 blocked, 写操作保持任务级授权请求(3.2.13)
# 2026-08-10 - 小欧 - 三堂会审修复(v1.45): _check_known_risks 写保护判定原 `tool_name == _WRITE_RISK_TOOL("write")` 用 LLM 原始名, 别名(write_text/writefile等) normalize 前不等于 write → 写入大小保护被绕过; 统一走 normalize_tool_name 再判(与 delete 判定同模式) — 小欧 2026-08-10
# 2026-08-11 - 小欧 - 回归修复: security.enabled=false(bypass)时 _check_known_risks 白名单外临时授权请求(requires_confirmation+auth_path) 未设 auto_confirm, 仍挂起HITL等确认; E2E自动化无人在线确认→超时→任务failed。修复: 白名单外授权请求在 _is_skip_safety()=true 时设 auto_confirm=True 直放 — 北京老陈驱动E2E
# 2026-08-11 - 小欧 - 全分支补日志留痕(北京老陈驱动): bypass自动放行+各硬拦截统一用log_and_print, 覆盖 工具未注册/delete R6/授权请求bypass直放/已知风险拦截/普通确认bypass/check_fn拦截/系统禁区删拦/写入大小保护
# 2026-08-11 - 小欧 - bypass自动放行(无需确认) 改为仅 logger.info 留痕不上控制台(高频路径刷屏, 只log不print)
# 2026-08-12 - 小欧 - A1越层前置: safety 整目录由 app.services.safety 提升为顶层 app.safety, 本文件 import 路径同步更新(配合 tools 禁 app.services 守护规则)
# 2026-08-12 - 小欧 - A1盲点二/四迁移: validate_tool_path 迁 app/tools/security/path_safe_check(import 同步), SafetyResult dataclass 迁 app/tools/security/safety_result(本文件删除本地定义改 import, __all__ 保留导出) — 小欧 2026-08-12
# 2026-08-16 - 小欧 - 会话信任豁免读取接入(北京老陈驱动): check_before_execute 增 session_id 可选参; check_fn 后、needs_confirm 前查 check_session_trust(chat_session_trust), 会话已信任该工具则豁免二次确认(跳 HITL); 危险防护(known_risk/check_fn blocked)不受豁免仍拦截(功能只增强不退化)
# 2026-08-17 - 小健 - 三堂会审架构修复(北京老陈驱动): 本层不再 import app.services.chat.storage(消除 test_layer_boundaries 守护的 safety→services 反向依赖违规)。会话信任预查上移到调用方(action_handler, services层)查 check_session_trust + normalize_tool_name 后, 本层 check_before_execute 用新增 skip_confirmation 参数(原 session_id 参数移除)接收信任结果豁免确认; 危险防护不受 skip_confirmation 豁免仍拦截。T1 normalize 语义随查询移至 action_handler, 与写保护修复同模式。
# 2026-08-25 - 小欧 - 沙箱预检置位(设计文档): 四条置位路径在 destructive 级条件成立时置 SafetyResult.sandbox_required=True(①白名单外 destructive 写授权请求 ②路径越权 ③注册表写 registrywrite/registrydelete 仅静态分析不动态执行 ④危险型失败兜底 rc!=0 且产生工作区影响/环境性 stderr); 同时 cleanup 分支补 backend.cleanup() 资源泄漏修复; 安全开关不读此字段(总闸在 executor.pre_execute 单点), 存量 safe 级零感知
# 2026-09-02 - 小欧 - 提示文案"准确+可读"优化(北京老陈驱动「提示文字看不懂」): _check_known_risks 用户可见 message 与日志串改为"术语保留+人话解释"并存——非系统禁区删/写、系统禁区、白名单外四套文案(措辞见代码); 仅改文案不改逻辑(安全分级/blocked/requires_confirmation/auth_path/auto_confirm 一律不变) — 小欧-2026-09-02
# 2026-09-02 - 小欧 - 会话信任功能修复 v1.5(北京老陈定案, 详见doc-9月优化/会话信任功能修复方案): _check_known_risks 增 skip_confirmation, 信任豁免传参下沉函数内部(替代调用方在函数外预判); 豁免只跳确认不跳危险防护, 系统禁区/路径越权/细粒度危险防护仍无条件 blocked; 豁免保留信任判定所需 auth_path — 小欧-2026-09-02
# 2026-09-18 小欧 - safety_level→severity全量重命名: SafetyResult字段+内部变量+构造调用+比较, 与SSE协议severity对齐 — 小欧-2026-09-18
# 2026-09-18 - 小欧 - 10处用户可见文案改写(文案仅可读性, 逻辑/分级/blocked/requires_confirmation/auth_path一律不变): "安全开关已绕过，自动确认执行"/"安全检查异常，已阻止执行"/"该路径在受保护区域，禁止删除"/"该路径在受保护区域，会话已信任，允许写入"/"该路径在受保护区域，写入需申请授权"/"该路径在系统禁区，禁止访问"/"该路径超出允许范围，会话已信任，允许操作"/"该路径超出允许范围，需临时授权"/"数据保护: 写入内容远小于原内容，已阻止"(去字节数, 半角逗号统一改全角) — 小欧-2026-09-18
# 2026-09-18 小欧 - 文案精化(重查挖掘, 人类可读性): message 尾拼 {msg} 会带出 path_safe_check 整句(双主语+双冒号+括号技术元数据), 改拼 failed_path(真实越权路径, 前缀关键词不变故safety_gate分类不受影响), failed_path为空兜底 display msg 保原因; 用户可见 message 干净, 日志仍留 {msg} 完整审计 — 小欧-2026-09-18
# 2026-09-18 小欧 - 毛病1精化(弹窗过宽核查): execute_sql 注册 needs_confirmation=True 一刀切, 纯读 SELECT 也弹; _get_needs_confirmation 加纯读短路 _is_readonly_sql(首词 SELECT/SHOW/DESCRIBE/DESC/EXPLAIN/VALUES/TABLE + 单语句才免, 注释头/WITH/PRAGMA/多语句保守回弹窗); 免确认后 severity 走 safe — 小欧-2026-09-18
# 2026-09-18 小欧 - 去bypass写死文案(北京老陈令): bypass需确认分支 message 由"安全开关已绕过，自动确认执行"改空串, content由safety_gate承载真实_message组装; auto_confirm=True仍为bypass唯一识别, 语义零变化 — 小欧-2026-09-18
# 2026-09-19 小欧 - 无风险shell不弹HITL修复: _get_needs_confirmation 中 check_shell_command_risk 返回 None 时加 return False, 不再穿透到 return tool_meta.needs_confirmation; 恢复"只有MEDIUM弹窗, HIGH拦截, 无风险直接放行"设计 — 北京老陈驱动(空content弹窗=逻辑错误)
# 2026-09-19 小欧 - HIGH级shell blocked修复: check_before_execute 返回时读 tool_meta._shell_risk_blocked 设置 blocked, HIGH级改为 blocked=True 走拦截(reject消息用 message); MEDIUM/无风险 blocked=False 不变 — 北京老陈驱动
# 2026-09-19 小欧 - 修复(北京老陈核查): 经tool_meta动态属性传递shell风险是隐藏副作用, 且 _shell_risk_blocked=True 置位后永不重置, registry单例共享致首个HIGH拦截后同进程后续无风险shell被误拦; 改 _get_needs_confirmation 返回三元组(needs_confirm, shell_msg, shell_blocked)直线传递, 三处调用点解包直接构造SafetyResult, 彻底删除 tool_meta._shell_risk_* setattr/getattr; 同步修复skip_confirmation分支丢弃blocked(会话信任下HIGH shell被放行) — 小欧-2026-09-19
# 2026-10-02 - 小欧 - 注册名收敛: _WRITE_RISK_TOOL 改为 write(写保护判定按新注册名)
# 2026-10-02 - 小欧 - 注册名归位: shell 类风险判定元组 "shell"→"bash"
# 2026-10-08 - 小欧 - 补接从未生效的保护盾(事故驱动, E2E P9-03 后端被 agent 扫射杀进程杀掉): ①新增 _protected_pids(): 自身+父进程+shell池 ②_get_needs_confirmation shell 分支前置 is_process_kill_protected 判定, 命中即 blocked=True 直返。根因: 原实现全项目无第二处传 protected_pids, 故 `if protected_pids:` 恒不生效。 — 小欧-2026-10-08
# 2026-10-10 - 小欧 - 预检21/43条规则死代码缺口修复(三壳并集): check_shell_command_risk(_cmd) 只传 command, shell_type 吃默认 "ps7" → cmd(14条)/bash(7条)标签规则全被跳过(实测仅 22/43 条生效), 两层判定口径不一致; 改调 check_shell_command_risk_all_shells(ps7/cmd/bash 各查一遍取最高严重度), 实测召回15条、白名单误伤0/30、日常命令误伤0/24、降级回归0; 同日 is_process_kill_protected 导入点更正为 app.tools.fundamental.shell_static_guard(safety→tools 合法) — 小欧-2026-10-10
# 2026-10-14 - 小欧 - 标注: 本文件=安全总闸 check_before_execute(执行第3步, 上游合法性初查/信任预查, 内调 delete_path_check+path_legality_router, 下游 HITL) — 小欧-2026-10-14
# 2026-10-17 - 小欧 - 标注订正(模块更名跟改): 内调原名 delete_safety→delete_path_check(删线专属判定 check_delete_permission), path_safe_check(已拆)→path_legality_router(路径路由)+path_classify_category(判定单源)。
# 2026-10-14 - 小欧 - SafetyResult import 改 app.tools.tool_types(契约归工具层单源)
# 2026-10-15 - 小欧 - 豁免早返(P4步18): known_risk 之后加豁免早返(不拦且不需确认即原样返回); 原代码会把「无动作」结果强标 severity=dangerous, 与事实相反
# 2026-10-15 - 小欧 - T1 注释订正: T1 注释订正为「mode 由 validate_tool_path 内部按 tool_name 自动推断(调用方不传)」。病根: 原注释与实际行为相反(实调 L375 只传 (tool_name, params) 两个参数, mode 形参默认 None 由被调方内部推断), 误导性注释按设计订正。— 小欧-2026-10-15
# 2026-10-15 - 小欧 - 错12 订正: L41-42 所称「四条置位路径」已全部不成立(②命中即return不构造结果; ③注册表类不动态执行; ④由executor内部兜底)。真实口径=destructive 即置位, safe/dangerous 不触发。— 小欧-2026-10-15
# 2026-10-16 - 小欧 - 工具未注册单列 tool_unavailable: 告知"工具不可用", 不再报成路径越权。★须显式命中, 漏掉会掉进"白名单外路径"兜底变成可授权 = 安全放宽。— 小欧-2026-10-16
# 2026-10-16 - 小欧 - 老陈裁定 主链重排三级串联: 自杀→danger拒→risk确认→路径权限; 删两处重复判定
# 2026-10-16 - 小欧 - 老陈裁定 severity destructive→risk(纯改名): 名不副实且被删除类与中风险类共用; 沙箱判定同步, 行为不变
# 2026-10-16 - 小欧 - tool去检查化: 工具层注释"validate先于本函数执行"订正(门前初查是唯一合法性检查点, 工具只执行+业务警告)。
# 2026-10-17 - 小欧 - 第十章: delete 专属判定调用点 check_delete_risk → check_delete_permission(封装口, 内部含 guard+validate_delete+check_delete_risk); 本层仍只消费结果(blocked 硬拦 / requires_confirmation 进确认), 调用关系不变。
# 2026-10-17 - 小欧 - 未注册判定收口上游: 未注册判定收口到解析层(删本层未注册分支); 删 category="tool_unavailable" 死分支(路径层已不产出)。
# 2026-10-17 - 小欧 - 总闸固化(核心): 总闸固化顺序 + 去双跑 + 去 skip — ①删 delete 顶部预计算(C4: 唯一一处=路径层删线) ②权限段统一走 _check_known_risks 单点(delete 亦走此单点) ③确认段删 skip_confirmation 分支(信任预查移入调用方确认层) ④_get_needs_confirmation 去 delete_risk ⑤_check_known_risks 直返 SafetyResult(调 check_tool_path_permission); 块0 import 别名正名; 块 G 内部注释去自造子号(全文统一 六阶段编号); 精简 _medium 冗余条件。SafetyResult 保持原 import。
# 2026-10-17 - 小欧 - _medium 冗余条件: `and _medium.requires_confirmation` 删(契约: check_shell_risk_command_all_shells 只返 requires_confirmation=True 或 None)。
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

2026-06-16 小沈 删除5级枚举，改用二元安全+check_fn
2026-06-17 小沈 删除record_operation/execute_with_safety委托(打破tools→safety循环依赖)，
             路径校验改用同包 safety 模块(打破safety→tools循环依赖)
2026-07-04 小欧 补充两层架构说明注释
2026-07-09 北京老陈 补充validate层完整函数清单
"""


from typing import Dict, Optional

from app.logger import logger, log_and_print
from app.config import get_config
from app.tools.registry import tool_registry
from app.safety.path_legality_router import check_tool_path_permission as _check_tool_path_permission  # 2026-10-17 小欧 - C5 正名(原 validate_tool_path as _validate_tool_path)
from app.safety.shell_process_guard import check_shell_self_kill  # 2026-10-16 老陈裁定: 自杀检查唯一入口(判定全在 guard 层); 快照组装下沉同层, 本文件不再碰 shell_engine
from app.tools.tool_types import SafetyResult  # 2026-10-14 小欧 - 契约迁 tool_types

_READONLY_SQL_FIRST = {"select", "show", "describe", "desc", "explain", "values", "table"}


def _is_readonly_sql(sql: str) -> bool:
    """execute_sql 纯读短路(毛病1, 2026-09-18 小欧): 首词纯读关键字 + 单语句(无分号)才免确认。
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


def _is_skip_safety() -> bool:
    """运行时检查安全开关 — 只读 config.yaml security.enabled"""
    try:
        return not get_config().get("security.enabled", True)
    except Exception:
        return False


class PathToolSafetyChecker:
    """工具执行前安全检查 — 确认判定 + 已知风险检测"""

    def check_before_execute(self, tool_name: str, params: Optional[Dict] = None,
                             pool_pids: Optional[set] = None) -> SafetyResult:
        """
        [4] 执行前安全检查总闸入口（Safety层）—— 危险+权限段, 固定顺序不分叉
        上游: [2] 处理范围门(仅 PATH_TOOLS 到此) → [3] 合法性初查(格式+存在性, 工具层不再复查)
        本层: [4-0] 自杀检查 → [4-1] 危险命令组 → [4-2] 权限三线(读/写/删唯一入口)
        下游: blocked→拒; requires_confirmation→交 [5] 确认层(信任豁免/HITL) → [6] 沙箱预检执行
        路径黑名单/白名单/路径穿越/写入大小保护/二元确认均在本段内

        安全开关: config.yaml security.enabled=false 时跳过所有检查
        2026-08-04 小欧: 已知风险(路径越权/写入保护/代码注入)无条件检测不管开关, 危险即拒绝执行(blocked);
            开关false仅bypass各"确认询问"(普通needs_confirmation), 开关true则正常询问 — 北京老陈驱动重构
        2026-08-17 小健 三堂会审-架构修复: 会话信任预查从本层移至调用方(action_handler, services层),
            本层不再依赖 app.services.chat.storage(消除 safety→services 违规);
            调用方查 trust 后传 skip_confirmation=True 豁免确认询问(危险防护仍生效) — 小健 2026-08-17
        安全总闸: 上游合法性初查/信任预查, 内调删线/路径层, 下游 HITL 确认 — 小欧-2026-10-14
        """
        # 2026-10-17 小欧 - 未注册判定已收口解析层, 本层不再复判(只放 PATH_TOOLS 工具到此)。
        # 2026-10-18 小欧 - 复判补回(fail-closed, 真回归修复): 上条"不再复判"判断有误 —— 解析层只管
        #   Agent 管线进来的 call, tool_facade/测试等直调方仍会带未注册工具名进来, tool_meta=None 一路
        #   传到 _get_needs_confirmation / tool_meta.check_fn 解引用即崩(2026-10-18 全量 pytest 实锤:
        #   test_deep_flow_bugs f5_01/f5_02 AttributeError: 'NoneType' object has no attribute 'name')。
        #   未注册 = 无元数据 = 无法定确认策略与权限线, 只能拒(fail-closed), 不做"猜一条线"放行。
        tool_meta = tool_registry.get_tool(tool_name)
        if tool_meta is None:
            log_and_print(f"[PathToolSafetyChecker] 工具未注册(硬拦): tool={tool_name}")
            return SafetyResult(blocked=True, message=f"工具未注册: {tool_name}", severity="dangerous")

        # [4-0] 自杀检查(2026-10-16 第七章 · 北京老陈裁定): 提到 _check_known_risks **之前**
        #   理由: 自杀与路径/危险等级无关, 且一旦执行后续所有检查皆无意义(E2E P9-03 后端自杀实录);
        #   放在门首 = 排在危险命令与路径权限之前, 不给任何绕过空间。
        #   判定全在 shell_process_guard.check_shell_self_kill(只答通过/不通过), 本层只出结果与文案。
        if (params or {}).get("command"):
            self_kill = PathToolSafetyChecker._check_shell_kill(
                (params or {}).get("command", ""), pool_pids)
            if self_kill is not None:
                log_and_print(f"[PathToolSafetyChecker] 自杀检查拦截(硬拦): {self_kill.message}")
                return self_kill

        # [4-1] 危险命令组(2026-10-16 老陈裁定的顺序, 任一命中即返回, 互不穿透):
        #   自杀检查 → danger(危险, 拒绝) → risk(中风险, 进 HITL 确认) → 路径权限
        #   ★为何 risk 必须排在路径权限之前: 命令既是中风险又路径越权时, 先问"危不危险"再问"能不能动" ——
        #     如 `Start-Process C:\Windows\x`: 按本顺序 → risk 命中, 进 HITL 用户确认即可;
        #     若路径权限在前 → 直接拒绝, 用户连确认机会都没有(语义过重)。
        #   两个风险层都只答"危不危险/要不要确认", 不含任何路径判定(见各自模块头边界铁律)。
        if (params or {}).get("command"):
            _cmd = (params or {}).get("command", "")
            # 危险命令: 命中即拒绝执行
            #   2026-10-16 三堂会审: 删冗余的 `and _danger.blocked` —— 降级机制移除后
            #   check_shell_danger_command 只会返回 blocked=True 或 None, 该条件恒等价于判非空。
            from app.safety.shell_danger_command import check_shell_danger_command_all_shells
            _danger = check_shell_danger_command_all_shells(_cmd)
            if _danger is not None:
                log_and_print(f"[PathToolSafetyChecker] 危险命令拦截: tool={tool_name}, {_danger.message}")
                return _danger
            # 中风险命令: 命中进 HITL 确认
            from app.safety.shell_command_risk import check_shell_risk_command_all_shells
            _medium = check_shell_risk_command_all_shells(_cmd)
            if _medium is not None:
                log_and_print(f"[PathToolSafetyChecker] 中风险命令转确认: tool={tool_name}, {_medium.message}")
                _medium.sandbox_required = True   # 确认前仍走沙箱预检
                return _medium

        # [4-2] 权限三线(按动作分派读/写/删; 唯一入口, delete 亦走此单点) — 小欧 2026-10-17
        #   无条件防线(开关无关): 越权/禁区/delete 判定即便开关 false 也拒绝。
        known_risk = self._check_known_risks(tool_name, params or {})
        if known_risk is not None:
            if known_risk.blocked:
                log_and_print(f"[PathToolSafetyChecker] 权限硬拦截(危险拒绝执行): tool={tool_name}, {known_risk.message}")
                return known_risk
            # requires_confirmation=True: 授权请求, 交确认层⑤(信任/HITL); bypass 直放
            if _is_skip_safety():
                known_risk.auto_confirm = True
                log_and_print(f"[PathToolSafetyChecker] bypass自动放行(授权请求): tool={tool_name}, auth_path={known_risk.auth_path}, {known_risk.message}")
            else:
                log_and_print(f"[PathToolSafetyChecker] 授权请求转HITL确认: tool={tool_name}, auth_path={known_risk.auth_path}, {known_risk.message}")
            known_risk.sandbox_required = (known_risk.severity == "risk")   # risk 级授权请求→沙箱预检
            return known_risk

        # 确认策略分流: 开关只影响"是否询问确认", 不影响危险防护
        if _is_skip_safety():
                _needs, _shell_msg = self._get_needs_confirmation(tool_meta, params or {})
                if _needs:
                    logger.info(f"[PathToolSafetyChecker] bypass自动放行(需确认工具,提示照出): tool={tool_name}")
                    # 2026-09-18 小欧 - 去bypass写死文案(北京老陈令): message保持空串不动,
                    #   bypass仅由auto_confirm=True区分(与hitl_gateway去mode同批), 内容/分级由safety_gate按真实来源组装 — 小欧-2026-09-18
                    return SafetyResult(requires_confirmation=True, auto_confirm=True,
                            blocked=False, message="",
                            severity="risk", sandbox_required=True)   # v1.25 M2-A: bypass risk 确认→沙箱预检
                logger.info(f"[PathToolSafetyChecker] bypass自动放行(无需确认): tool={tool_name}")
                return SafetyResult(requires_confirmation=False,
                        blocked=False, message="安全开关已绕过",
                        severity="safe")   # v1.25 M2-A: safe 级 bypass 不触发沙箱(与 G1 一致)

        if tool_meta.check_fn:
            try:
                custom_result = tool_meta.check_fn(params or {})
                if not custom_result.get("is_safe", True):
                    log_and_print(f"[PathToolSafetyChecker] check_fn拦截: tool={tool_name}, {custom_result.get('message')}")
                    return SafetyResult(
                        blocked=True,
                        message=custom_result.get("message", "安全检查未通过"),
                        severity=custom_result.get("severity", "dangerous"),
                    )
            except Exception as e:
                logger.error(f"[PathToolSafetyChecker] check_fn异常,阻止执行: {e}")
                return SafetyResult(blocked=True,
                        message=f"安全检查异常，已阻止执行: {e}",
                        severity="dangerous")

        # 2026-10-17 小欧 - 会话信任豁免分支已删(信任预查移入调用方确认层⑤), 本层不再收 skip_confirmation。
        needs_confirm, _shell_msg = self._get_needs_confirmation(tool_meta, params or {})
        severity = "risk" if needs_confirm else "safe"
        # v1.25 M2-C: 仅 risk 级触发沙箱(与 G1 唯一触发依据一致); safe 级不进预检
        return SafetyResult(requires_confirmation=needs_confirm,
                blocked=False, message=_shell_msg or "", severity=severity,
                sandbox_required=(severity == "risk"))

    @staticmethod
    def _check_shell_kill(cmd: str, pool_pids: Optional[set] = None) -> Optional["SafetyResult"]:
        """shell 自杀检查单步 — 小欧 2026-10-16

        2026-10-16 老陈裁定: 自杀检查全部归并到 app/safety/shell_process_guard.py,
          本方法只调其唯一入口 check_shell_self_kill(只答通过/不通过), 不通过时由本层出
          SafetyResult 与文案 —— 判定在 guard 层, 返回与话术在本层(SRP 分离)。
        命中受保护 PID/进程名/无目标兜底即 blocked，直返不经确认分流。
        """
        if check_shell_self_kill(cmd, pool_pids):
            return SafetyResult(blocked=True, message="系统保护进程，禁止终止", severity="dangerous")
        return None

    @staticmethod
    def _get_needs_confirmation(tool_meta, params: Dict) -> tuple:
        """获取生效的确认策略：action级 > 工具级 — 小欧 2026-08-04
        2026-10-16 小欧 - 老陈裁定: 本函数只答“要不要确认”，不再答“拦不拦”——回二元组。
        shell 危险拦截（杀/HIGH）已归位 _check_known_risks（无条件防线）；此处 MEDIUM 只产弹窗文案。
        2026-10-17 小欧 - 删 delete_risk（delete 确认由权限三线删线封装口 check_delete_permission 产出）。"""
        from app.tools.tools_alias_mapper import normalize_tool_name  # 延迟导入(同240行模式, 防别名漏判) — 小欧-2026-09-18
        if normalize_tool_name(tool_meta.name or "") == "execute_sql" \
                and _is_readonly_sql((params or {}).get("sql", "")):
            return False, ""  # 毛病1(2026-09-18 小欧): 纯读 SELECT 免确认; 写/DDL/多语句/注释头照旧弹
        if normalize_tool_name(tool_meta.name or "") in ("bash", "execute_command"):
            # 2026-10-16 老陈裁定: danger/risk 已提到 check_before_execute 主链(自杀 → danger → risk → 路径权限),
            #   此处不再重复判定。落到这里说明 danger/risk 都没命中 → 无风险 shell 不弹 HITL
            #   (2026-09-19 小欧 修复: 否则无风险 shell 会弹空 content 窗)
            return False, ""
        if tool_meta.action_confirmation and params.get("action"):
            return tool_meta.action_confirmation.get(
                params["action"], tool_meta.needs_confirmation), ""
        return tool_meta.needs_confirmation, ""

    @staticmethod
    def _check_known_risks(tool_name: str, params: Dict) -> Optional["SafetyResult"]:
        """路径权限检测: 按路径层路由分派到读/写/删三线封装口 — 小欧 2026-10-17(归一化)

        2026-10-17 小欧 - category 分流(system/non_system/None)已下沉三线封装口;
          本层只调路径层拿最终 SafetyResult, 命中 blocked/requires_confirmation 即返回, 否则 None。
        写入大小保护归工具层(file_path_checker.validate_path_for_overwrite), 本层不判。
        """
        risk = _check_tool_path_permission(tool_name, params)   # 路径层 → SafetyResult(三线封装口)
        if risk.blocked or risk.requires_confirmation:
            return risk
        return None


_checker: Optional[PathToolSafetyChecker] = None


def get_path_tool_safety_checker() -> PathToolSafetyChecker:
    global _checker
    if _checker is None:
        _checker = PathToolSafetyChecker()
    return _checker


__all__ = ["SafetyResult", "PathToolSafetyChecker", "get_path_tool_safety_checker"]
